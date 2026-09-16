"""Mixin para Paso 1: Calibracion de Deteccion."""

import tkinter as tk
from tkinter import messagebox

import cv2

from carcounter.calibration import (
    compute_sample_constraints, passes_sample_constraints, draw_detection_overlay,
)

class CalibrationMixin:
    """Métodos de calibración YOLO (Paso 1)."""

    def _build_panel_calib(self):
        """Construye el panel lateral del Paso 1."""
        self.panel_step1 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step1, "CALIBRACIÓN DE DETECCIÓN", bold=True, color="#CDD6F4")
        self._lbl(self.panel_step1,
                  "1. Haz clic y arrastra sobre un\nauto para definir su tamaño.\n"
                  "2. Presiona [Probar YOLO].\n"
                  "3. Ajusta confianza si es necesario.\n"
                  "4. Guarda y prueba muestras de\n   varios frames y tamaños.\n\n"
                  "Zoom: rueda del mouse\n"
                  "Mover vista: clic der o ESPACIO + arrastrar", color="#A6ADC8")
        self._lbl(self.panel_step1,
                  "Tip aéreo: selecciona un solo auto con un recuadro ajustado.\n"
                  "La prueba usa la misma resolución y ROI que el conteo.",
                  color="#89B4FA")

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=8)

        self._lbl(self.panel_step1, "Frame actual:", color="#CDD6F4")
        self.lbl_frame_info = tk.Label(self.panel_step1, text="Frame 1/1",
                                       bg="#181825", fg="#A6E3A1", font=("Arial", 10))
        self.lbl_frame_info.pack(anchor="w")

        nav_row = tk.Frame(self.panel_step1, bg="#181825")
        nav_row.pack(fill="x", pady=4)
        tk.Button(nav_row, text="⏮ -25", command=lambda: self._step_frame(-25),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=(0, 4))
        tk.Button(nav_row, text="◀ -1", command=lambda: self._step_frame(-1),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=4)
        tk.Button(nav_row, text="+1 ▶", command=lambda: self._step_frame(1),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=4)
        tk.Button(nav_row, text="+25 ⏭", command=lambda: self._step_frame(25),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=4)

        self._lbl(self.panel_step1, "Umbral de confianza:", color="#CDD6F4")
        row = tk.Frame(self.panel_step1, bg="#181825")
        row.pack(fill="x")
        tk.Scale(row, from_=0.05, to=0.95, resolution=0.05,
                 variable=self.conf_threshold, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(side="left", fill="x", expand=True)
        self.lbl_conf_val = tk.Label(self.panel_step1, bg="#181825", fg="#89B4FA",
                                     font=("Arial", 10))
        self.lbl_conf_val.pack()
        self.conf_threshold.trace_add("write", self._update_conf_label)
        self._update_conf_label()

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=4)
        self._lbl(self.panel_step1, "Confianza por clase (opcional):", color="#A6ADC8")
        for _n, _v in [("car", self.conf_car), ("moto", self.conf_motorbike),
                       ("bus", self.conf_bus), ("truck", self.conf_truck), ("van", self.conf_van)]:
            _r = tk.Frame(self.panel_step1, bg="#181825")
            _r.pack(fill="x")
            tk.Label(_r, text=f"  {_n}:", bg="#181825", fg="#A6ADC8",
                     font=("Arial", 9), width=6, anchor="w").pack(side="left")
            tk.Scale(_r, from_=0.05, to=0.95, resolution=0.05,
                     variable=_v, orient="horizontal",
                     bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                     highlightthickness=0,
                     command=lambda _: self._on_per_class_conf_modified()
                     ).pack(side="left", fill="x", expand=True)

        self._lbl(self.panel_step1, "Resolución de inferencia (imgsz):", color="#CDD6F4")
        tk.Scale(self.panel_step1, from_=640, to=1920, resolution=160,
                 variable=self.infer_imgsz, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")
        self.lbl_imgsz_val = tk.Label(self.panel_step1, bg="#181825", fg="#89B4FA",
                                      font=("Arial", 10))
        self.lbl_imgsz_val.pack()
        self.infer_imgsz.trace_add("write", self._update_imgsz_label)
        self._update_imgsz_label()

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=6)
        self._lbl(self.panel_step1, "ROI de inferencia (opcional):", color="#CDD6F4")
        self._lbl(self.panel_step1,
                  "Recorta el área donde se detecta.\nFuera de la ROI no se cuenta nada.")
        self.btn_roi_define = tk.Button(self.panel_step1, text="⬚  Definir ROI",
                                        command=self._start_roi_draw,
                                        bg="#313244", fg="#F9E2AF", relief="flat", pady=4)
        self.btn_roi_define.pack(fill="x", pady=2)
        self.btn_roi_clear = tk.Button(self.panel_step1, text="✕  Quitar ROI",
                                       command=self._clear_roi,
                                       bg="#313244", fg="#F38BA8", relief="flat", pady=4)
        self.btn_roi_clear.pack(fill="x", pady=2)
        self.lbl_roi = tk.Label(self.panel_step1, text="ROI: todo el frame",
                                bg="#181825", fg="#A6ADC8", font=("Arial", 9))
        self.lbl_roi.pack(anchor="w")

        self._lbl(self.panel_step1, "Área mínima detectada:", color="#A6ADC8")
        self.lbl_min_area = tk.Label(self.panel_step1, text="0 px²",
                                     bg="#181825", fg="#A6E3A1", font=("Arial", 10))
        self.lbl_min_area.pack(anchor="w")
        self._lbl(self.panel_step1, "Área máxima detectada:", color="#A6ADC8")
        self.lbl_max_area = tk.Label(self.panel_step1, text="999999 px²",
                                     bg="#181825", fg="#A6E3A1", font=("Arial", 10))
        self.lbl_max_area.pack(anchor="w")
        self.lbl_samples_info = tk.Label(self.panel_step1, text="Muestras: 0",
                                         bg="#181825", fg="#89B4FA", font=("Arial", 10))
        self.lbl_samples_info.pack(anchor="w", pady=(2, 0))

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=8)

        tk.Checkbutton(self.panel_step1, text="Usar SAHI", variable=self.sahi_enabled,
                       bg="#181825", fg="#CDD6F4", selectcolor="#313244").pack(fill="x")
        self.btn_yolo_test = tk.Button(self.panel_step1, text="👁  Probar YOLO",
                                       command=self._run_calib_test,
                                       bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"),
                                       relief="flat", pady=6)
        self.btn_yolo_test.pack(fill="x", pady=4)

        self.btn_global_test = tk.Button(self.panel_step1, text="🛰  Vista Global",
                                         command=self._run_global_detection_test,
                                         bg="#F9E2AF", fg="#11111B", font=("Arial", 10, "bold"),
                                         relief="flat", pady=6)
        self.btn_global_test.pack(fill="x", pady=2)

        self.btn_add_sample = tk.Button(self.panel_step1, text="📌 Agregar muestra vehículo",
                                        command=self._add_vehicle_sample,
                                        bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                        relief="flat", pady=6)
        self.btn_add_sample.pack(fill="x", pady=2)

        tk.Button(self.panel_step1, text="Probar muestras guardadas",
                  command=self._test_saved_samples, bg="#313244", fg="#CDD6F4",
                  relief="flat", pady=4).pack(fill="x", pady=2)

        tk.Button(self.panel_step1, text="Aplicar filtros de las muestras",
                  command=self._apply_sample_constraints, bg="#313244", fg="#CDD6F4",
                  relief="flat", pady=4).pack(fill="x", pady=2)

        self.btn_clear_samples = tk.Button(self.panel_step1, text="🧹 Limpiar muestras",
                                           command=self._clear_vehicle_samples,
                                           bg="#313244", fg="#CDD6F4", relief="flat", pady=4)
        self.btn_clear_samples.pack(fill="x", pady=2)

        self.btn_calib_reset = tk.Button(self.panel_step1, text="↺  Limpiar recuadro",
                                         command=self._reset_calib,
                                         bg="#313244", fg="#CDD6F4", relief="flat", pady=4)
        self.btn_calib_reset.pack(fill="x", pady=2)

        self.lbl_calib_status = tk.Label(self.panel_step1, text="⚠  Pendiente de confirmar",
                                          bg="#181825", fg="#F38BA8", font=("Arial", 9),
                                          wraplength=280, justify="left")
        self.lbl_calib_status.pack(pady=4)

        self.btn_calib_ok = tk.Button(self.panel_step1, text="✅  Confirmar y continuar →",
                                      command=self._confirm_calib,
                                      bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_calib_ok.pack(fill="x", pady=8)

    # ── UI helpers ───────────────────────────────
    def _on_per_class_conf_modified(self):
        self._conf_per_class_modified = True
        self.calib_test_passed = False

    def _update_conf_label(self, *_):
        self.lbl_conf_val.config(text=f"Valor: {self.conf_threshold.get():.2f}")
        self.calib_test_passed = False
        if not self._conf_per_class_modified:
            val = self.conf_threshold.get()
            for v in (self.conf_car, self.conf_motorbike, self.conf_bus, self.conf_truck, self.conf_van):
                v.set(val)

    def _update_imgsz_label(self, *_):
        self.calib_test_passed = False
        self.lbl_imgsz_val.config(text=f"Valor: {self.infer_imgsz.get()} px")

    def _update_samples_label(self):
        if not self.vehicle_samples:
            self.lbl_samples_info.config(text="Muestras: 0")
            return
        areas = [s["area"] for s in self.vehicle_samples]
        self.lbl_samples_info.config(
            text=f"Muestras: {len(self.vehicle_samples)}  areas {min(areas)}-{max(areas)} px²"
        )

    # ── ROI de inferencia ────────────────────────
    def _start_roi_draw(self):
        self.roi_drawing = True
        self.roi_start = self.roi_end = None
        self.canvas.config(cursor="crosshair")
        self.status_var.set("Arrastra sobre el video para marcar la ROI; Escape cancela")
        self._redraw()

    def _clear_roi(self):
        self.inference_roi = None
        self.roi_drawing = False
        self.roi_start = self.roi_end = None
        self._update_roi_label()
        self.status_var.set("ROI quitada: se detecta en todo el frame")
        self._redraw()

    def _update_roi_label(self):
        roi = self.inference_roi
        self.lbl_roi.config(
            text=f"ROI: {roi[0]},{roi[1]} a {roi[2]},{roi[3]}" if roi else "ROI: todo el frame")

    def _finish_roi(self):
        x1, x2 = sorted((self.roi_start[0], self.roi_end[0]))
        y1, y2 = sorted((self.roi_start[1], self.roi_end[1]))
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(self.img_w, x2), min(self.img_h, y2)
        self.roi_drawing = False
        self.roi_start = self.roi_end = None
        if x2 - x1 < 16 or y2 - y1 < 16:
            self.status_var.set("ROI descartada: el área marcada es muy chica")
        else:
            self.inference_roi = [int(x1), int(y1), int(x2), int(y2)]
            self.status_var.set(f"ROI de inferencia: {x1},{y1} a {x2},{y2}")
        self._update_roi_label()
        self._redraw()

    # ── Calibración lógica ───────────────────────
    def _sample_constraints(self):
        return self._loaded_sample_constraints

    def _passes_sample_constraints(self, bbox):
        return passes_sample_constraints(bbox, self._sample_constraints())

    def _reset_calib(self):
        self.calib_rect_start = None
        self.calib_rect_end = None
        self.calib_drawing = False
        self.calib_test_passed = False
        self.frame_rgb = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB)
        self.lbl_calib_status.config(text="⚠  Pendiente de confirmar", fg="#F38BA8")
        self._redraw()

    def _add_vehicle_sample(self):
        if not (self.calib_rect_start and self.calib_rect_end):
            messagebox.showwarning("Muestras", "Primero dibuja un recuadro sobre un vehículo.")
            return
        x1 = min(self.calib_rect_start[0], self.calib_rect_end[0])
        y1 = min(self.calib_rect_start[1], self.calib_rect_end[1])
        x2 = max(self.calib_rect_start[0], self.calib_rect_end[0])
        y2 = max(self.calib_rect_start[1], self.calib_rect_end[1])
        if x2 <= x1 or y2 <= y1:
            self.status_var.set("La muestra debe tener ancho y alto positivos.")
            return
        if any(tuple(sample["bbox"]) == (x1, y1, x2, y2) and sample.get("frame") == self.current_frame_idx
               for sample in self.vehicle_samples):
            self.status_var.set("Esa muestra ya está guardada en este frame.")
            return
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        aspect = width / float(height)
        self.vehicle_samples.append({
            "bbox": (x1, y1, x2, y2),
            "frame": self.current_frame_idx,
            "width": width, "height": height,
            "area": area, "aspect": aspect,
        })
        self._update_samples_label()
        self.lbl_calib_status.config(
            text=f"✅ Muestra agregada ({len(self.vehicle_samples)})", fg="#A6E3A1")
        self.status_var.set(
            "Muestra guardada. Incluye autos y vehículos grandes en varios frames; aplicar filtros es opcional.")
        self._redraw()

    def _clear_vehicle_samples(self):
        self.vehicle_samples = []
        self._loaded_sample_constraints = None
        self.min_area.set(0)
        self.max_area.set(999999)
        self.lbl_min_area.config(text="0 px²")
        self.lbl_max_area.config(text="999999 px²")
        self._update_samples_label()
        self.lbl_calib_status.config(text="⚠  Muestras limpiadas", fg="#F9E2AF")
        self.status_var.set("Muestras limpiadas")
        self._redraw()

    def _apply_sample_constraints(self):
        if len(self.vehicle_samples) < 5:
            self.status_var.set("Marca al menos 5 vehículos de tamaños distintos antes de aplicar filtros.")
            return
        constraints = compute_sample_constraints(self.vehicle_samples)
        self._loaded_sample_constraints = constraints
        self.calib_test_passed = False
        if constraints is None:
            return
        self.min_area.set(constraints["min_area"])
        self.max_area.set(constraints["max_area"])
        self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
        c = constraints
        text = (f"Filtros aplicados: ancho {c['min_width']}-{c['max_width']} px, "
                f"alto {c['min_height']}-{c['max_height']} px, área {c['min_area']}-{c['max_area']} px²")
        self.lbl_samples_info.config(text=text, wraplength=280, justify="left")
        self.status_var.set(f"✅ {text}")

    @staticmethod
    def _point_in_box(px, py, box):
        x1, y1, x2, y2 = box
        return x1 <= px <= x2 and y1 <= py <= y2

    def _ensure_sahi_model(self, conf):
        if self.sahi_model is not None:
            self.sahi_model.confidence_threshold = conf
            self.sahi_model.image_size = self.infer_imgsz.get()
            return self.sahi_model
        try:
            from sahi import AutoDetectionModel
        except ImportError:
            return None
        self.sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8",
            model_path=self._model_path,
            confidence_threshold=conf,
            device="cpu",
            image_size=self.infer_imgsz.get(),
        )
        return self.sahi_model

    def _draw_detection_overlay(self, detections, frame_origin=(0, 0),
                                frame_base=None, highlight_box=None):
        return draw_detection_overlay(
            self.frame_orig, detections,
            constraints=self._sample_constraints(),
            exclusion_zones=self.exclusion_zones,
            frame_origin=frame_origin,
            frame_base=frame_base,
            highlight_box=highlight_box,
        )

    # _run_global_detection_test, _run_calib_test y _restore_original_frame
    # viven ahora en setup_panels/calib_tests.py (CalibTestsMixin).

    def _confirm_calib(self):
        # Calibrar es opcional (autos aéreos chicos pueden no validar); avanzar nunca quita filtros aplicados
        filters = "con filtros de muestras" if self._loaded_sample_constraints else "sin filtros de tamaño"
        tested = "" if self.calib_test_passed else ", sin prueba validada"
        self.lbl_calib_status.config(text=f"✅  Calibración confirmada ({filters}{tested})", fg="#A6E3A1")
        self.status_var.set(f"Calibración confirmada {filters}{tested}; pasando a Paso 2")
        self.after(500, lambda: self._activate_step(2))

    def _on_calib_press(self, event):
        """Maneja clic izquierdo en Paso 1."""
        ix, iy = self._screen_to_img(event.x, event.y)
        if self.roi_drawing:
            self.roi_start = self.roi_end = (ix, iy)
            return
        self.calib_rect_start = (ix, iy)
        self.calib_rect_end = (ix, iy)
        self.calib_drawing = True

    def _on_calib_drag(self, event):
        """Maneja arrastre en Paso 1."""
        if self.roi_drawing and self.roi_start:
            self.roi_end = self._screen_to_img(event.x, event.y)
            self._redraw()
            return
        if self.calib_drawing:
            ix, iy = self._screen_to_img(event.x, event.y)
            self.calib_rect_end = (ix, iy)
            self._redraw()

    def _on_calib_release(self, event):
        """Maneja soltar botón en Paso 1."""
        if self.roi_drawing and self.roi_start:
            self.roi_end = self._screen_to_img(event.x, event.y)
            self._finish_roi()
            return
        ix, iy = self._screen_to_img(event.x, event.y)
        self.calib_rect_end = (ix, iy)
        self.calib_drawing = False
        self.calib_test_passed = False
        self.lbl_calib_status.config(text="⚠  Pendiente de confirmar", fg="#F38BA8")
        self._redraw()
