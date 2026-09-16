from tkinter import messagebox

import cv2
import numpy as np

from carcounter.geometry import bbox_iou
from carcounter.detection import detect_objects
from carcounter.detector import filter_detections
from carcounter.runtime import resolve_runtime_config
from types import SimpleNamespace


def profile_inference_params(app):
    """Lee el perfil desde las variables de Tk; solo se puede llamar en el hilo de Tk."""
    config = app._build_current_config()
    cfg = resolve_runtime_config(config, SimpleNamespace(
        detector="yolo", video=None, model=None, imgsz=None))
    use_sahi = config["sahi"]["enabled"]
    sahi_model = app._ensure_sahi_model(cfg["effective_conf"]) if use_sahi else None
    predict_fn = None
    if use_sahi:
        from sahi.predict import get_sliced_prediction
        predict_fn = get_sliced_prediction
    return {
        "cfg": cfg, "use_sahi": use_sahi, "sahi_model": sahi_model,
        "predict_fn": predict_fn, "model": app.model,
        "exclusion_np": {name: np.asarray(pts, dtype=np.int32)
                         for name, pts in app.exclusion_zones.items()},
    }


def infer_with_params(frame, params):
    """Inferencia pura: no toca Tk, asi que puede correr en otro hilo."""
    cfg = params["cfg"]
    raw = detect_objects(
        frame, model=params["model"], effective_conf=cfg["effective_conf"],
        imgsz=cfg["imgsz"], use_sahi=params["use_sahi"], sahi_model=params["sahi_model"],
        sahi_predict_fn=params["predict_fn"], sahi_slice_w=cfg["sahi_slice_w"],
        sahi_slice_h=cfg["sahi_slice_h"], sahi_overlap=cfg["sahi_overlap"],
        sahi_nms_threshold=cfg["sahi_nms"],
        inference_roi=cfg["settings"].get("inference_roi"),
    )
    rows, classes = filter_detections(
        raw, lambda name: cfg["conf_per_class"].get(name, cfg["conf_threshold"]),
        cfg["geo_constraints"], params["exclusion_np"],
    )
    return [dict(bbox=tuple(map(int, row[:4])), conf=float(row[4]), cls_name=name)
            for row, name in zip(rows, classes)]


class CalibTestsMixin:
    def _profile_inference_params(self):
        return profile_inference_params(self)

    @staticmethod
    def _infer_with_params(frame, params):
        return infer_with_params(frame, params)

    def _predict_current_profile(self, frame):
        return infer_with_params(frame, profile_inference_params(self))

    def _run_global_detection_test(self):
        if self.model is None:
            messagebox.showwarning("Modelo", "El modelo no está cargado.")
            return
        self.config(cursor="watch")
        self.btn_global_test.config(state="disabled")
        self.status_var.set("Probando el perfil de ejecución en este frame…")
        self.update_idletasks()
        try:
            detections = self._predict_current_profile(self.frame_orig)
            display = self._draw_detection_overlay(detections)
            self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            self._redraw()
            self.lbl_calib_status.config(text=f"{len(detections)} detecciones del perfil actual", fg="#A6E3A1")
            self.status_var.set("Revisa vehículos omitidos y cajas incorrectas en varios frames.")
        except Exception as error:
            self.status_var.set(f"No se pudo probar el perfil: {error}")
        finally:
            self.config(cursor="")
            self.btn_global_test.config(state="normal")

    def _run_calib_test(self):
        if self.model is None or not (self.calib_rect_start and self.calib_rect_end):
            messagebox.showwarning("Calibración", "Carga un modelo y dibuja un recuadro sobre un vehículo.")
            return
        selected = (min(self.calib_rect_start[0], self.calib_rect_end[0]),
                    min(self.calib_rect_start[1], self.calib_rect_end[1]),
                    max(self.calib_rect_start[0], self.calib_rect_end[0]),
                    max(self.calib_rect_start[1], self.calib_rect_end[1]))
        self.calib_test_passed = False
        self.config(cursor="watch")
        self.btn_yolo_test.config(state="disabled")
        self.update_idletasks()
        try:
            detections = self._predict_current_profile(self.frame_orig)
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
        except Exception as error:
            self.status_var.set(f"No se pudo probar el perfil: {error}")
        finally:
            self.config(cursor="")
            self.btn_yolo_test.config(state="normal")

    def _test_saved_samples(self):
        samples = self.vehicle_samples
        if self.model is None or not samples or any("frame" not in sample for sample in samples):
            self.status_var.set("Agrega muestras en varios frames del video antes de probarlas.")
            return
        self.config(cursor="watch")
        self.update_idletasks()
        cap = cv2.VideoCapture(self.video_path)
        matched = 0
        self.calib_test_passed = False
        try:
            for frame_number in sorted({sample["frame"] for sample in samples}):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError(f"No se pudo leer el frame {frame_number}")
                boxes = [sample["bbox"] for sample in samples if sample["frame"] == frame_number]
                matched += count_sample_matches(self._predict_current_profile(frame), boxes)
            self.calib_test_passed = matched == len(samples)
            message = f"Muestras detectadas: {matched}/{len(samples)}. No mide falsos positivos ni precisión del aforo."
            self.status_var.set(message)
            self.lbl_calib_status.config(text=message, fg="#A6E3A1" if self.calib_test_passed else "#F38BA8")
        except Exception as error:
            self.status_var.set(f"Error al probar muestras: {error}")
        finally:
            cap.release()
            self.config(cursor="")

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
