"""Mixin para Paso 3: SAHI + Guardar."""

import os
import tkinter as tk
from tkinter import messagebox

from carcounter.app_config import AppConfig
from carcounter.config_io import build_config, save_config


class SAHIMixin:
    """Métodos de configuración SAHI y guardado (Paso 3)."""

    def _build_panel_sahi(self):
        """Construye el panel lateral del Paso 3."""
        self.panel_step3 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step3, "PARÁMETROS SAHI", bold=True, color="#CDD6F4")
        self._lbl(self.panel_step3,
                  "SAHI divide el frame en tiles para\n"
                  "detectar autos pequeños/lejanos.\n"
                  "Compara errores y tiempo antes\nde elegir el tamaño de tile.",
                  color="#A6ADC8")

        tk.Frame(self.panel_step3, bg="#313244", height=1).pack(fill="x", pady=6)

        tk.Checkbutton(self.panel_step3, text="Usar SAHI en detección y calibración",
                       variable=self.sahi_enabled, bg="#181825", fg="#CDD6F4",
                       selectcolor="#313244").pack(fill="x")

        params = [
            ("Ancho de tile (px):", self.slice_w, 128, 1024, 128),
            ("Alto de tile (px):", self.slice_h, 128, 1024, 128),
        ]
        for lbl, var, mn, mx, res in params:
            self._lbl(self.panel_step3, lbl, color="#CDD6F4")
            tk.Scale(self.panel_step3, from_=mn, to=mx, resolution=res,
                     variable=var, orient="horizontal",
                     bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                     highlightthickness=0, command=lambda _: self._update_tile_preview()
                     ).pack(fill="x")

        self._lbl(self.panel_step3, "Overlap entre tiles:", color="#CDD6F4")
        tk.Scale(self.panel_step3, from_=0.0, to=0.5, resolution=0.05,
                 variable=self.overlap, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0, command=lambda _: self._update_tile_preview()
                 ).pack(fill="x")

        self._lbl(self.panel_step3, "NMS post-SAHI (IoU threshold):", color="#CDD6F4")
        tk.Scale(self.panel_step3, from_=0.0, to=0.9, resolution=0.05,
                 variable=self.nms_threshold, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")

        self.lbl_tiles = tk.Label(self.panel_step3, text="Tiles por frame: —",
                                   bg="#181825", fg="#89B4FA", font=("Arial", 10))
        self.lbl_tiles.pack(pady=4)

        tk.Frame(self.panel_step3, bg="#313244", height=1).pack(fill="x", pady=6)
        self._lbl(self.panel_step3, "BYTETRACK / BOT-SORT", bold=True, color="#CDD6F4")
        self._lbl(self.panel_step3, "Confianza baja: recuperar un ID. Alta: asociar cajas. Nueva: crear un ID.")
        for label, variable in (("Confianza baja", self.track_low_thresh),
                                ("Confianza alta", self.track_high_thresh),
                                ("Nuevo ID", self.new_track_thresh)):
            self._lbl(self.panel_step3, label)
            tk.Scale(self.panel_step3, from_=0.0, to=1.0, resolution=0.05,
                     variable=variable, orient="horizontal", bg="#181825", fg="#CDD6F4",
                     troughcolor="#313244", highlightthickness=0).pack(fill="x")
        self._lbl(self.panel_step3, "Retención de IDs (frames a 30 FPS)")
        tk.Scale(self.panel_step3, from_=1, to=150, variable=self.track_buffer,
                 orient="horizontal", bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")
        tk.Checkbutton(self.panel_step3, text="Combinar confianza e IoU (fuse_score)",
                       variable=self.fuse_score, bg="#181825", fg="#CDD6F4",
                       selectcolor="#313244").pack(fill="x")
        self._lbl(self.panel_step3, "PARÁMETROS SORT FALLBACK", bold=True, color="#CDD6F4")

        tracker_params = [
            ("Max age (frames):", self.max_age, 10, 100, 5),
            ("Min hits:", self.min_hits, 1, 10, 1),
        ]
        for lbl, var, mn, mx, res in tracker_params:
            self._lbl(self.panel_step3, lbl, color="#CDD6F4")
            tk.Scale(self.panel_step3, from_=mn, to=mx, resolution=res,
                     variable=var, orient="horizontal",
                     bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                     highlightthickness=0).pack(fill="x")

        self._lbl(self.panel_step3, "IOU threshold tracker:", color="#CDD6F4")
        tk.Scale(self.panel_step3, from_=0.05, to=0.5, resolution=0.05,
                 variable=self.iou_thresh, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")

        tk.Frame(self.panel_step3, bg="#313244", height=1).pack(fill="x", pady=6)

        self.btn_tile_grid = tk.Button(self.panel_step3, text="🔲  Ocultar cuádrícula",
                                        command=self._toggle_tile_grid,
                                        bg="#313244", fg="#89B4FA", relief="flat", pady=4)
        self.btn_tile_grid.pack(fill="x", pady=2)

        self.btn_save = tk.Button(self.panel_step3, text=f"💾  Guardar {os.path.basename(self._output_config)}",
                                  command=self._save_config,
                                  bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                  relief="flat", pady=8)
        self.btn_save.pack(fill="x", pady=8)

        self.lbl_save_status = tk.Label(self.panel_step3, text="",
                                         bg="#181825", fg="#A6E3A1", font=("Arial", 9))
        self.lbl_save_status.pack()

    # ── Lógica ───────────────────────────────────
    def _update_tile_preview(self, *_):
        if not self.img_w:
            return
        self._redraw()

    def _toggle_tile_grid(self):
        self._tile_grid_visible = not self._tile_grid_visible
        if self._tile_grid_visible:
            self.btn_tile_grid.config(text="🔲  Ocultar cuádrícula", fg="#89B4FA")
        else:
            self.btn_tile_grid.config(text="🔳  Mostrar cuádrícula", fg="#6C7086")
            self.lbl_tiles.config(text="Tiles por frame: —")
        self._redraw()

    def _build_current_config(self):
        config = build_config(
            counting_mode=self.counting_mode.get(),
            exclusion_zones=self.exclusion_zones,
            zones=self.zones,
            counting_lines=self.counting_lines,
            directions=self.directions,
            min_area=self.min_area.get(),
            max_area=self.max_area.get(),
            conf_threshold=self.conf_threshold.get(),
            imgsz=self.infer_imgsz.get(),
            sample_constraints=self._sample_constraints(),
            sample_count=len(self.vehicle_samples),
            conf_per_class={
                "car": self.conf_car.get(),
                "motorbike": self.conf_motorbike.get(),
                "bus": self.conf_bus.get(),
                "truck": self.conf_truck.get(),
                "van": self.conf_van.get(),
                "motor": self.conf_motorbike.get(),
                "motorcycle": self.conf_motorbike.get(),
            },
            conf_per_class_modified=self._conf_per_class_modified,
            slice_w=self.slice_w.get(),
            slice_h=self.slice_h.get(),
            overlap=self.overlap.get(),
            nms_threshold=self.nms_threshold.get(),
            max_age=self.max_age.get(),
            min_hits=self.min_hits.get(),
            iou_threshold=self.iou_thresh.get(),
            video_path=self.video_path,
            model_path=self._model_path,
            loaded_config=self._loaded_config,
        )

        config["sahi"]["enabled"] = self.sahi_enabled.get()
        config["tracker"].update({key: getattr(self, key).get() for key in (
            "track_low_thresh", "track_high_thresh", "new_track_thresh", "track_buffer", "fuse_score")})
        config["settings"]["vehicle_samples"] = list(self.vehicle_samples)
        return config

    def _save_config(self):
        ok, msg = self._validate_zones()
        if not ok:
            messagebox.showwarning("Guardar", msg)
            return
        config = self._build_current_config()
        errors = AppConfig.from_dict(config).validate()
        if errors:
            messagebox.showwarning("Perfil inválido", "No se guardó:\n\n" + "\n".join(errors))
            return
        try:
            save_config(self._output_config, config)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            return
        self._loaded_config = config
        if hasattr(self, "_autosave"):
            self._autosave.mark_clean()
        excl_info = f" · {len(self.exclusion_zones)} excl" if self.exclusion_zones else ""
        self.lbl_save_status.config(
            text=f"✅ Guardado: {self._output_config}\n{len(self.zones)} zonas{excl_info} · SAHI {self.slice_w.get()}×{self.slice_h.get()}",
            fg="#A6E3A1")
        self.status_var.set(f"✅ Perfil guardado en {self._output_config}")
        excl_msg = f"\nExclusiones: {', '.join(self.exclusion_zones)}" if self.exclusion_zones else ""
        roi_msg = f"\n\nAviso: {msg}" if msg else ""
        messagebox.showinfo("Guardado",
                            f"Perfil guardado en:\n{self._output_config}\n\n"
                            f"Zonas: {', '.join(self.zones)}{excl_msg}{roi_msg}\n\n"
                            f"Para contar:\n  env/bin/python main.py --config {self._output_config}")
