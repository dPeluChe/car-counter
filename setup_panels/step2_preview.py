"""Mixin de preview de zonas/video para el Paso 2.

Metodos extraidos de step2_zones.py para dejar ese archivo mas focalizado
en la logica de zonas + construccion del panel compartido.

Metodos:
  - _toggle_zone_preview / _start_zone_preview / _stop_zone_preview
  - _zone_preview_tick (loop de reproduccion con overlay)
  - _toggle_yolo_preview (toggle de deteccion en preview)
"""

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
        if self.zone_drawing:
            self.status_var.set("⚠ Termina de dibujar la zona actual antes de reproducir.")
            return
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
        if hasattr(self, "btn_preview") and self.btn_preview:
            self.btn_preview.config(text="▶  Reproducir zonas", bg="#F9E2AF", fg="#11111B")
        self._redraw_zones()

    def _zone_preview_tick(self):
        if not self._preview_playing or self._preview_cap is None:
            return
        SKIP = 1
        for _ in range(SKIP - 1):
            self._preview_cap.grab()
        ret, frame = self._preview_cap.read()
        self._preview_frame_idx += SKIP

        if not ret or self._preview_frame_idx >= self.total_frames:
            self._preview_frame_idx = 0
            self._preview_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._preview_job = self.after(80, self._zone_preview_tick)
            return

        base = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self._preview_show_detections and self.model is not None:
            self._draw_detections_on_preview(base, frame)

        self._overlay_zones_on_preview(base)

        self.display_frame_zones = base
        self._redraw()
        det_tag = "  🔍 YOLO" if self._preview_show_detections else ""
        self.status_var.set(
            f"▶{det_tag}  Frame {self._preview_frame_idx}/{self.total_frames}  |  ⏸ para pausar"
        )
        self._preview_job = self.after(80, self._zone_preview_tick)

    def _draw_detections_on_preview(self, base_rgb, frame_bgr):
        """Corre YOLO sobre el frame y dibuja detecciones en el preview RGB."""
        for det in self._predict_current_profile(frame_bgr):
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
