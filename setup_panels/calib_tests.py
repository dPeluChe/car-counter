"""Mixin con las pruebas YOLO/SAHI del Paso 1 (calibracion).

Extraido de step1_calibration.py:
  - _run_global_detection_test: corre YOLO + SAHI sobre todo el frame
  - _run_calib_test: valida el recuadro dibujado por el usuario
  - _restore_original_frame: repinta frame limpio tras test
"""

from tkinter import messagebox

import cv2

from carcounter.calibration import (
    bbox_iou, get_calibration_roi, get_calibration_scale,
)


class CalibTestsMixin:
    """Pruebas visuales de deteccion (Vista Global + YOLO sobre recuadro)."""

    def _run_global_detection_test(self):
        """Corre YOLO + SAHI sobre todo el frame y sugiere min/max area."""
        if self.model is None:
            messagebox.showwarning("Modelo", "El modelo YOLO no está cargado.")
            return
        preview_conf = 0.05
        self.config(cursor="watch")
        self.btn_global_test.config(state="disabled", text="⏳  Procesando…")
        self.status_var.set("🔄  Vista global — paso 1/2: inferencia YOLO…")
        self.update_idletasks()

        yolo_detections, _ = self._predict_roi_boxes(
            self.frame_orig, preview_conf, scale=1.0, use_sahi=False,
            force_imgsz=self.infer_imgsz.get())

        self.status_var.set(
            f"🔄  Vista global — paso 2/2: inferencia SAHI… (YOLO encontró {len(yolo_detections)})"
        )
        self.update_idletasks()

        sahi_detections, _ = self._predict_roi_boxes(
            self.frame_orig, preview_conf, scale=1.0, use_sahi=True)
        self.config(cursor="")
        self.btn_global_test.config(state="normal", text="🛰  Vista Global")

        def _passes(d):
            cx = (d["bbox"][0] + d["bbox"][2]) / 2
            cy = (d["bbox"][1] + d["bbox"][3]) / 2
            return (self._passes_sample_constraints(d["bbox"])
                    and not self._is_in_exclusion(cx, cy))

        filtered_yolo = [d for d in yolo_detections if _passes(d)]
        filtered_sahi = [d for d in sahi_detections if _passes(d)]

        if len(filtered_yolo) >= len(filtered_sahi):
            detections = filtered_yolo
            detector_used = f"yolo-imgsz{self.infer_imgsz.get()}"
        else:
            detections = filtered_sahi
            detector_used = "sahi"

        display = self._draw_detection_overlay(detections)
        self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._redraw()

        if detections:
            self._apply_suggested_area_bounds(detections)
            self.lbl_calib_status.config(
                text=f"✅ Vista global: {len(detections)} vehículos detectados "
                     f"[{detector_used} @ {preview_conf:.2f}]",
                fg="#A6E3A1")
            self.status_var.set(
                f"Vista global completada: {len(detections)} vehículos detectados. "
                "Ajusta el recuadro sobre un auto y valida uno específico.")
        else:
            self.lbl_calib_status.config(
                text="⚠  Vista global sin detecciones. Baja confianza o cambia de frame.",
                fg="#F38BA8")
            self.status_var.set("Vista global sin detecciones")

        self.after(5000, self._restore_original_frame)

    def _apply_suggested_area_bounds(self, detections):
        """Sugiere min/max area desde percentiles de las detecciones."""
        areas = sorted(
            max(0, (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]))
            for d in detections)
        suggested_min = int(max(0, areas[max(0, int(len(areas) * 0.10) - 1)] * 0.6))
        suggested_max = int(areas[min(len(areas) - 1, int(len(areas) * 0.95))] * 1.5)
        self.min_area.set(suggested_min)
        self.max_area.set(max(suggested_min + 1, suggested_max))
        self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        self.lbl_max_area.config(text=f"{self.max_area.get()} px²")

    def _run_calib_test(self):
        """Valida el recuadro del usuario contra YOLO (con fallback a SAHI)."""
        if self.model is None:
            messagebox.showwarning("Modelo", "El modelo YOLO no está cargado.")
            return
        if not (self.calib_rect_start and self.calib_rect_end):
            messagebox.showwarning("Calibración", "Primero dibuja un recuadro sobre un auto.")
            return
        self.config(cursor="watch")
        self.btn_yolo_test.config(state="disabled", text="⏳  Procesando…")
        self.status_var.set("🔄  Ejecutando inferencia YOLO…")
        self.update_idletasks()

        conf = self.conf_threshold.get()
        selected_box = (
            min(self.calib_rect_start[0], self.calib_rect_end[0]),
            min(self.calib_rect_start[1], self.calib_rect_end[1]),
            max(self.calib_rect_start[0], self.calib_rect_end[0]),
            max(self.calib_rect_start[1], self.calib_rect_end[1]),
        )
        roi_box = get_calibration_roi(selected_box, self.img_w, self.img_h)
        scale = get_calibration_scale(selected_box)
        roi_frame = self.frame_orig[roi_box[1]:roi_box[3], roi_box[0]:roi_box[2]]

        display = self.frame_orig.copy()
        best_match, detector_used = self._find_best_match(
            roi_frame, roi_box, selected_box, conf, scale, display,
        )

        cv2.rectangle(display, (roi_box[0], roi_box[1]),
                      (roi_box[2], roi_box[3]), (0, 180, 255), 2)
        cv2.rectangle(display, (selected_box[0], selected_box[1]),
                      (selected_box[2], selected_box[3]), (255, 230, 0), 2)

        if best_match:
            bx1, by1, bx2, by2 = best_match["bbox"]
            cv2.rectangle(display, (bx1, by1), (bx2, by2), (0, 255, 0), 4)
            self.min_area.set(int(best_match["area"] * 0.5))
            self.max_area.set(int(best_match["area"] * 4.0))
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
            self.calib_test_passed = True
            self.calib_confirmed = False
            status_msg = (
                f"✅ Auto validado: {best_match['cls_name']} "
                f"conf={best_match['conf']:.2f} área={best_match['area']}px² "
                f"[{detector_used} x{scale:.1f}]"
            )
        else:
            self.calib_test_passed = False
            self.calib_confirmed = False
            status_msg = (
                "⚠  El recuadro no coincide con un vehículo detectado. "
                "Prueba con un recuadro más justo o baja el umbral."
            )

        self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._redraw()
        self.config(cursor="")
        self.btn_yolo_test.config(state="normal", text="👁  Probar YOLO")
        self.lbl_calib_status.config(
            text=status_msg, fg="#A6E3A1" if best_match else "#F38BA8")
        self.status_var.set(
            "YOLO test completado: calibración válida" if best_match
            else "YOLO test completado: calibración no válida")
        self.after(5000, self._restore_original_frame)

    def _find_best_match(self, roi_frame, roi_box, selected_box, conf, scale, display):
        """Evalua candidatos YOLO (fallback SAHI) contra selected_box.

        Dibuja los candidatos en `display` y retorna (best_match_dict_or_None, detector_used).
        """
        candidates, detector_used = self._predict_roi_boxes(
            roi_frame, conf, scale, use_sahi=False)

        selected_center = (
            (selected_box[0] + selected_box[2]) / 2.0,
            (selected_box[1] + selected_box[3]) / 2.0,
        )
        best_match = [None]  # list para mutar desde closure

        def evaluate(candidate_list):
            for cand in candidate_list:
                x1, y1, x2, y2 = cand["bbox"]
                x1 += roi_box[0]; x2 += roi_box[0]
                y1 += roi_box[1]; y2 += roi_box[1]
                area = (x2 - x1) * (y2 - y1)
                conf_val = cand["conf"]
                cls_name = cand["cls_name"]
                det_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                overlap_iou = bbox_iou((x1, y1, x2, y2), selected_box)
                overlaps = (
                    overlap_iou >= 0.10
                    or self._point_in_box(det_center[0], det_center[1], selected_box)
                    or self._point_in_box(selected_center[0], selected_center[1],
                                           (x1, y1, x2, y2))
                )
                color = (0, 255, 80) if overlaps else (100, 100, 255)
                thickness = 3 if overlaps else 2
                if overlaps:
                    score = (overlap_iou, conf_val)
                    if self._passes_sample_constraints((x1, y1, x2, y2)) and (
                        best_match[0] is None or score > best_match[0]["score"]
                    ):
                        best_match[0] = {
                            "bbox": (x1, y1, x2, y2), "area": area,
                            "conf": conf_val, "cls_name": cls_name, "score": score,
                        }
                cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
                cv2.putText(display, f"{cls_name} {conf_val:.2f} ({area}px²)",
                            (x1, max(0, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        evaluate(candidates)
        if best_match[0] is None:
            sahi_candidates, sahi_mode = self._predict_roi_boxes(
                roi_frame, max(0.10, conf - 0.05), scale, use_sahi=True)
            evaluate(sahi_candidates)
            if best_match[0] is not None:
                detector_used = sahi_mode

        return best_match[0], detector_used

    def _restore_original_frame(self):
        self.frame_rgb = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB)
        if self.current_step == 1:
            self._redraw()
