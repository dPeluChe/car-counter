"""Mixin de preview de zonas/video para el Paso 2."""

import threading

import cv2
import numpy as np

from carcounter.constants import ZONE_COLORS_RGB


class PreviewMixin:
    """Reproduccion del video con zonas/detecciones superpuestas."""

    def _toggle_zone_preview(self):
        if self._preview_playing:
            self._stop_zone_preview()
        else:
            self._start_zone_preview()

    def _start_zone_preview(self):
        if self.zone_drawing or self.line_drawing or self.direction_drawing:
            self.status_var.set("⚠ Termina o cancela (Escape) el dibujo actual antes de reproducir.")
            return
        self._preview_last_frame = None
        self._preview_detections = []
        self._preview_playing = True
        self._preview_frame_idx = self.current_frame_idx
        self._preview_cap = cv2.VideoCapture(self.video_path)
        self._preview_cap.set(cv2.CAP_PROP_POS_FRAMES, self._preview_frame_idx)
        self.btn_preview.config(text="⏸  Pausar", bg="#F38BA8", fg="#11111B")
        self.status_var.set("▶ Reproduciendo con zonas — ⏸ para pausar")
        self._zone_preview_tick()

    def _stop_zone_preview(self):
        if not self._preview_playing and self._preview_job is None:
            return
        self._preview_playing = False
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        if self._preview_cap is not None:
            self._preview_cap.release()
            self._preview_cap = None
        if self._preview_last_frame is not None:
            # Al pausar se dibuja sobre el frame en pantalla, no sobre el de antes de reproducir
            index, frame = self._preview_last_frame
            self._preview_last_frame = None
            self.frame_orig = frame.copy()
            self.frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.current_frame_idx = index
            self.lbl_frame_info.config(text=f"Frame {index + 1}/{self.total_frames}")
        if hasattr(self, "btn_preview") and self.btn_preview:
            self.btn_preview.config(text="▶  Reproducir", bg="#F9E2AF", fg="#11111B")
        self._redraw_zones()

    def _zone_preview_tick(self):
        if not self._preview_playing or self._preview_cap is None:
            return
        try:
            ret, frame = self._preview_cap.read()
            if not ret:
                self._preview_frame_idx = 0
                self._preview_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._preview_job = self.after(80, self._zone_preview_tick)
                return
            self._preview_last_frame = (self._preview_frame_idx, frame)
            self._preview_frame_idx += 1
            base = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if self._preview_show_detections and self.model is not None:
                self._request_preview_detections(frame)
                self._report_preview_error()
                self._draw_detections_on_preview(base)
            self._overlay_zones_on_preview(base)
        except Exception as error:
            self._stop_zone_preview()
            self.status_var.set(f"⚠ Reproducción detenida por un error: {error}")
            return

        self.display_frame_zones = base
        self._redraw()
        det_tag = "  🔍 YOLO" if self._preview_show_detections else ""
        self.status_var.set(
            f"▶{det_tag}  Frame {self._preview_frame_idx}/{self.total_frames}  |  ⏸ para pausar"
        )
        self._preview_job = self.after(80, self._zone_preview_tick)

    def _request_preview_detections(self, frame_bgr):
        """Inferir tarda cientos de ms: va en un hilo para no congelar la ventana.

        El hilo solo escribe atributos, nunca toca widgets; el dibujo usa las
        ultimas cajas listas, asi que pueden ir uno o dos frames atrasadas.
        """
        if self._preview_infer_busy:
            return
        snapshot = frame_bgr.copy()
        try:
            # Leer el perfil toca variables de Tk: va aqui, no en el hilo
            params = self._profile_inference_params()
        except Exception as error:
            self._preview_error = error
            return
        self._preview_infer_busy = True

        def work():
            detections, failure = [], None
            try:
                detections = self._infer_with_params(snapshot, params)
            except Exception as error:
                failure = error
            finally:
                # Solo atributos: el aviso lo muestra el tick, que si corre en el hilo de Tk
                self._preview_detections = detections
                self._preview_error = failure
                self._preview_infer_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _report_preview_error(self):
        """Si el hilo fallo, apaga las detecciones y avisa; el video sigue reproduciendose."""
        if self._preview_error is None:
            return
        error, self._preview_error = self._preview_error, None
        self._preview_show_detections = False
        self.btn_det_toggle.config(text="🔍  Detecciones YOLO: OFF", fg="#6C7086")
        self.status_var.set(f"⚠ Detecciones apagadas por un error: {error}")

    def _draw_detections_on_preview(self, base_rgb):
        """Dibuja en el preview RGB las ultimas detecciones que alcanzo a calcular el hilo."""
        for det in self._preview_detections:
            x1, y1, x2, y2 = det["bbox"]
            label = f"{det['cls_name']} {det['conf']:.2f}"
            cv2.rectangle(base_rgb, (x1, y1), (x2, y2), (255, 200, 50), 2)
            cv2.putText(base_rgb, label, (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 50), 1, cv2.LINE_AA)

    def _overlay_zones_on_preview(self, base_rgb):
        """Mezcla un overlay semitransparente de zonas sobre el frame RGB."""
        overlay = base_rgb.copy()
        zone_meta = []
        for idx, (name, pts) in enumerate(self.zones.items()):
            color = ZONE_COLORS_RGB[idx % len(ZONE_COLORS_RGB)]
            np_pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(overlay, [np_pts], color)
            zone_meta.append((name, np_pts, color))
        # cv2.addWeighted necesita mismo shape; escribimos en el buffer del caller
        base_rgb[:] = cv2.addWeighted(base_rgb, 0.75, overlay, 0.25, 0)
        for name, np_pts, color in zone_meta:
            cv2.polylines(base_rgb, [np_pts], True, color, 2)
            cx = int(np.mean(np_pts[:, 0]))
            cy = int(np.mean(np_pts[:, 1]))
            cv2.putText(base_rgb, name, (cx, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def _toggle_yolo_preview(self):
        if self.model is None:
            self.status_var.set("⚠ Modelo YOLO no cargado — completa el Paso 1 primero.")
            return
        self._preview_show_detections = not self._preview_show_detections
        if self._preview_show_detections:
            self.btn_det_toggle.config(
                text="🔍  Detecciones YOLO: ON  ⚠ más lento", fg="#CBA6F7")
        else:
            self.btn_det_toggle.config(
                text="🔍  Detecciones YOLO: OFF", fg="#6C7086")
