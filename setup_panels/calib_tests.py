import json
import threading
from tkinter import messagebox

import cv2
import numpy as np

from carcounter.geometry import bbox_iou
from carcounter.detection import detect_objects
from carcounter.detector import filter_detections, detection_rejection
from carcounter.runtime import resolve_runtime_config
from setup_panels.background_job import BackgroundJob
from types import SimpleNamespace


# Calibración y preview comparten el modelo; SAHI además guarda predicciones mutables.
INFERENCE_LOCK = threading.Lock()


def profile_inference_params(app):
    """Lee el perfil desde las variables de Tk; solo se puede llamar en el hilo de Tk.

    No carga modelos: SAHI se prepara en el hilo de trabajo (prepare_sahi)."""
    config = app._build_current_config()
    cfg = resolve_runtime_config(config, SimpleNamespace(
        detector="yolo", video=None, model=None, imgsz=None))
    use_sahi = config["sahi"]["enabled"]
    conf, imgsz = cfg["effective_conf"], cfg["imgsz"]
    return {
        "cfg": cfg, "use_sahi": use_sahi, "sahi_model": None, "predict_fn": None,
        "load_sahi": (lambda: app._sahi_model_for(conf, imgsz)) if use_sahi else None,
        "model": app.model,
        "exclusion_np": {name: np.asarray(pts, dtype=np.int32)
                         for name, pts in app.exclusion_zones.items()},
    }


def prepare_sahi(params):
    """Importa y carga SAHI (lento la primera vez); solo bajo INFERENCE_LOCK y fuera del hilo de Tk."""
    if not params["use_sahi"] or params.get("load_sahi") is None:
        return
    if params["predict_fn"] is None:
        from sahi.predict import get_sliced_prediction
        params["predict_fn"] = get_sliced_prediction
    params["sahi_model"] = params["load_sahi"]()


def infer_with_params(frame, params, diagnostics=False, cancelled=None):
    """Inferencia pura: no toca Tk, asi que puede correr en otro hilo.

    Una a la vez (INFERENCE_LOCK). Devuelve None si se cancela antes de empezar."""
    cfg = params["cfg"]
    with INFERENCE_LOCK:
        if cancelled is not None and cancelled.is_set():
            return None
        prepare_sahi(params)
        raw = detect_objects(
            frame, model=params["model"], effective_conf=cfg["effective_conf"],
            imgsz=cfg["imgsz"], use_sahi=params["use_sahi"], sahi_model=params["sahi_model"],
            sahi_predict_fn=params["predict_fn"], sahi_slice_w=cfg["sahi_slice_w"],
            sahi_slice_h=cfg["sahi_slice_h"], sahi_overlap=cfg["sahi_overlap"],
            sahi_nms_threshold=cfg["sahi_nms"],
            inference_roi=cfg["settings"].get("inference_roi"),
        )
    if diagnostics:
        return [dict(det, rejection=detection_rejection(
            det, lambda name: cfg["conf_per_class"].get(name, cfg["conf_threshold"]),
            cfg["geo_constraints"], params["exclusion_np"])) for det in raw]
    rows, classes = filter_detections(
        raw, lambda name: cfg["conf_per_class"].get(name, cfg["conf_threshold"]),
        cfg["geo_constraints"], params["exclusion_np"],
    )
    return [dict(bbox=tuple(map(int, row[:4])), conf=float(row[4]), cls_name=name)
            for row, name in zip(rows, classes)]


def match_saved_samples(video_path, samples, params, cancelled):
    """Cuenta muestras detectadas por frame; devuelve None si se cancela entre frames."""
    cap = cv2.VideoCapture(video_path)
    matched = 0
    try:
        for frame_number in sorted({sample["frame"] for sample in samples}):
            if cancelled.is_set():
                return None
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"No se pudo leer el frame {frame_number}")
            boxes = [sample["bbox"] for sample in samples if sample["frame"] == frame_number]
            detections = infer_with_params(frame, params, cancelled=cancelled)
            if detections is None:
                return None
            matched += count_sample_matches(detections, boxes)
    finally:
        cap.release()
    return matched


class CalibTestsMixin:
    """Las pruebas de calibración infieren en un hilo: la ventana responde y el resultado se
    descarta si se cancela o cambia el video, el frame, el modelo o el perfil."""

    def _profile_inference_params(self):
        return profile_inference_params(self)

    @staticmethod
    def _infer_with_params(frame, params):
        return infer_with_params(frame, params)

    def _predict_current_profile(self, frame):
        return infer_with_params(frame, profile_inference_params(self))

    def _calib_context(self):
        try:
            profile = json.dumps(self._build_current_config(), sort_keys=True, default=str)
        except Exception:
            profile = None
        return (self.video_path, self.current_frame_idx, id(self.model), profile,
                self.calib_rect_start, self.calib_rect_end)

    def _cancel_calib_if_active(self):
        """Primer paso de cada botón de prueba: con una en curso, el clic solo cancela."""
        job = getattr(self, "_calib_job", None)
        if job is None or not job.active:
            return False
        job.cancel()
        self.status_var.set("Cancelando: el resultado se descartará.")
        return True

    def _calib_buttons(self):
        return [self.btn_yolo_test, self.btn_global_test, self.btn_samples_test]

    def _start_calib_job(self, button, status, work, on_success):
        """Lanza la prueba; pulsar de nuevo el mismo botón (que dice Cancelar) la cancela."""
        if not hasattr(self, "_calib_job"):
            self._calib_job = BackgroundJob()
        self._calib_job.start(self._calib_context(), work)
        self._calib_label = (button, button.cget("text"))
        for other in self._calib_buttons():
            other.config(state="disabled")
        button.config(state="normal", text="✖ Cancelar prueba")
        self.status_var.set(status + " Puedes seguir usando la ventana; cancelar descarta el resultado.")
        self.after(100, lambda: self._poll_calib_job(on_success))

    def _poll_calib_job(self, on_success):
        outcome = self._calib_job.poll(self._calib_context())
        if outcome is None:
            self.after(100, lambda: self._poll_calib_job(on_success))
            return
        button, text = self._calib_label
        button.config(text=text)
        for other in self._calib_buttons():
            other.config(state="normal")
        state, value = outcome
        if state == "descartado":
            self.status_var.set(f"Prueba descartada: {value}.")
        elif state == "error":
            self.status_var.set(f"No se pudo probar el perfil: {value}")
        else:
            try:
                on_success(value)
            except Exception as error:
                self.status_var.set(f"No se pudo mostrar el resultado: {error}")

    def _snapshot_for_test(self):
        """Lee Tk (perfil y frame) en el hilo de Tk; el hilo de trabajo solo ve copias."""
        return profile_inference_params(self), self.frame_orig.copy()

    def _run_global_detection_test(self):
        if self._cancel_calib_if_active():
            return
        if self.model is None:
            messagebox.showwarning("Modelo", "El modelo no está cargado.")
            return
        try:
            params, frame = self._snapshot_for_test()
        except Exception as error:
            self.status_var.set(f"No se pudo probar el perfil: {error}")
            return
        self._start_calib_job(
            self.btn_global_test, "Probando el perfil de ejecución en este frame…",
            lambda cancelled: infer_with_params(frame, params, diagnostics=True, cancelled=cancelled),
            self._show_global_detection_result)

    def _show_global_detection_result(self, detections):
        display = self._draw_detection_overlay(detections)
        self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._redraw()
        from collections import Counter
        rejected = Counter(det["rejection"] for det in detections if det["rejection"])
        accepted = len(detections) - sum(rejected.values())
        reasons = ", ".join(f"{key}: {value}" for key, value in rejected.items()) or "ninguno"
        self.lbl_calib_status.config(
            text=f"Aceptadas: {accepted}. Descartes rojos: {reasons}.", fg="#A6E3A1")
        self.status_var.set("Fuera de ROI no se infiere. Cajas bajo el umbral del modelo no están disponibles.")

    def _run_calib_test(self):
        if self._cancel_calib_if_active():
            return
        if self.model is None or not (self.calib_rect_start and self.calib_rect_end):
            messagebox.showwarning("Calibración", "Carga un modelo y dibuja un recuadro sobre un vehículo.")
            return
        selected = (min(self.calib_rect_start[0], self.calib_rect_end[0]),
                    min(self.calib_rect_start[1], self.calib_rect_end[1]),
                    max(self.calib_rect_start[0], self.calib_rect_end[0]),
                    max(self.calib_rect_start[1], self.calib_rect_end[1]))
        try:
            params, frame = self._snapshot_for_test()
        except Exception as error:
            self.status_var.set(f"No se pudo probar el perfil: {error}")
            return
        self.calib_test_passed = False
        self._start_calib_job(
            self.btn_yolo_test, "Probando el perfil en el vehículo marcado…",
            lambda cancelled: infer_with_params(frame, params, cancelled=cancelled),
            lambda detections: self._show_calib_result(detections, selected))

    def _show_calib_result(self, detections, selected):
        match = best_calibration_match(detections, selected)
        self.calib_test_passed = match is not None
        display = self._draw_detection_overlay(detections, highlight_box=selected)
        cv2.rectangle(display, selected[:2], selected[2:], (255, 230, 0), 2)
        self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._redraw()
        message = (f"Coincidencia: {match['cls_name']} ({match['conf']:.2f}). Revisa más frames."
                   if match else "El perfil actual no detecta el vehículo marcado con IoU >= 0.50.")
        self.lbl_calib_status.config(text=message, fg="#A6E3A1" if match else "#F38BA8")
        self.status_var.set(message)

    def _test_saved_samples(self):
        if self._cancel_calib_if_active():
            return
        samples = [dict(sample) for sample in self.vehicle_samples]
        if self.model is None or not samples or any("frame" not in sample for sample in samples):
            self.status_var.set("Agrega muestras en varios frames del video antes de probarlas.")
            return
        try:
            params = profile_inference_params(self)
        except Exception as error:
            self.status_var.set(f"Error al probar muestras: {error}")
            return
        video_path = self.video_path
        self.calib_test_passed = False
        self._start_calib_job(
            self.btn_samples_test, "Probando las muestras guardadas…",
            lambda cancelled: match_saved_samples(video_path, samples, params, cancelled),
            lambda matched: self._show_samples_result(matched, len(samples)))

    def _show_samples_result(self, matched, total):
        self.calib_test_passed = matched == total
        message = f"Muestras detectadas: {matched}/{total}. No mide falsos positivos ni precisión del aforo."
        self.status_var.set(message)
        self.lbl_calib_status.config(text=message, fg="#A6E3A1" if self.calib_test_passed else "#F38BA8")

    def _restore_original_frame(self):
        self.frame_rgb = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB)
        if self.current_step == 1:
            self._redraw()


def best_calibration_match(detections, selected):
    candidates = [d for d in detections if bbox_iou(d["bbox"], selected) >= 0.5]
    return max(candidates, key=lambda d: (bbox_iou(d["bbox"], selected), d["conf"]), default=None)


def count_sample_matches(detections, selected_boxes):
    candidates = sorted(((bbox_iou(det["bbox"], box), di, bi)
                         for di, det in enumerate(detections)
                         for bi, box in enumerate(selected_boxes)), reverse=True)
    used_detections, used_boxes = set(), set()
    for overlap, di, bi in candidates:
        if overlap >= 0.5 and di not in used_detections and bi not in used_boxes:
            used_detections.add(di)
            used_boxes.add(bi)
    return len(used_boxes)
