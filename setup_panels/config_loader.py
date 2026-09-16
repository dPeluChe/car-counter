"""Mixin para cargar un config.json existente en el estado Tk del configurador."""

import os
from tkinter import messagebox

from carcounter.config_io import (
    load_config, parse_directions, parse_exclusion_zones, parse_lines, parse_settings, parse_zones,
)
from carcounter.geometry import inference_roi


class ConfigLoaderMixin:
    """Requiere self._default_video (video con el que arrancó el configurador)."""

    def _load_from_config(self, path):
        try:
            cfg = load_config(path)
        except Exception as e:
            messagebox.showerror("Error cargando config", str(e))
            return
        self._loaded_config = cfg

        cfg_model = cfg.get("model_path")
        if cfg_model and cfg_model != self._model_path and not self._model_override:
            try:
                self._on_model_selected(os.path.basename(cfg_model), cfg_model)
            except Exception as error:
                # Se carga el resto del perfil y se conserva su model_path para no pisarlo al guardar
                self._model_path = cfg_model
                self.model = self.sahi_model = None
                messagebox.showwarning(
                    "Modelo del perfil",
                    f"No se pudo cargar {cfg_model}:\n{error}\n\n"
                    "Se cargan igual la geometría y los parámetros. Elige un modelo en [Modelos] para probar detección.")
        # Un perfil que no dice nada de SAHI lo deja apagado: encenderlo solo multiplica el costo por tile
        self.sahi_enabled.set(cfg.get("sahi", {}).get("enabled", False))
        self.vehicle_samples = cfg.get("settings", {}).get("vehicle_samples", [])
        self.inference_roi = inference_roi(cfg)
        self._update_roi_label()

        cfg_video = cfg.get("video_path", "")
        if cfg_video and cfg_video != self.video_path \
                and os.path.isfile(cfg_video) and self.video_path == self._default_video:
            self._release_nav_cap()
            self.video_path = cfg_video
            self._load_frame()

        self.exclusion_zones = parse_exclusion_zones(cfg)
        self._invalidate_excl_cache()
        self._refresh_excl_list()
        n = len(self.exclusion_zones) + 1
        while f"Exclusion {n}" in self.exclusion_zones:
            n += 1
        self.excl_zone_name.set(f"Exclusion {n}")

        self.zones = parse_zones(cfg)
        self.counting_lines = parse_lines(cfg)
        self.directions = parse_directions(cfg)
        loaded_mode = cfg.get("counting_mode", "zones")
        self.counting_mode.set(loaded_mode)
        self._set_counting_mode(loaded_mode)
        self._redraw_zones()

        # Aplicar settings/sahi/tracker al estado Tk
        p = parse_settings(cfg)
        sc = p["sample_constraints"]
        self._loaded_sample_constraints = sc
        if sc:
            self.lbl_samples_info.config(
                text=f"Muestras: cargadas  w[{sc['min_width']}–{sc['max_width']}] h[{sc['min_height']}–{sc['max_height']}]")
        _set = lambda var, val: var.set(val) if val is not None else None
        cp = p["conf_per_class"]
        if cp:
            self._conf_per_class_modified = True
        _set(self.min_area, p["min_area"])
        _set(self.max_area, p["max_area"])
        _set(self.conf_threshold, p["conf_threshold"])
        _set(self.infer_imgsz, p["imgsz"])
        _set(self.slice_w, p["slice_width"])
        _set(self.slice_h, p["slice_height"])
        _set(self.overlap, p["overlap_ratio"])
        _set(self.nms_threshold, p["nms_threshold"])
        _set(self.max_age, p["max_age"])
        _set(self.min_hits, p["min_hits"])
        _set(self.iou_thresh, p["iou_threshold"])
        for key in ("track_low_thresh", "track_high_thresh", "new_track_thresh", "track_buffer", "fuse_score"):
            _set(getattr(self, key), cfg.get("tracker", {}).get(key))
        if p["min_area"] is not None:
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        if p["max_area"] is not None:
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
        if cp:
            _set(self.conf_car, cp.get("car"))
            _set(self.conf_motorbike, cp.get("motorbike", cp.get("motor", cp.get("motorcycle"))))
            _set(self.conf_bus, cp.get("bus"))
            _set(self.conf_truck, cp.get("truck"))
            _set(self.conf_van, cp.get("van"))

        n = len(self.zones)
        self.status_var.set(
            f"✅ Perfil cargado: {n} zona{'s' if n != 1 else ''}, {len(self.exclusion_zones)} exclusiones, "
            f"{len(self.counting_lines)} líneas, {len(self.directions)} direcciones ({os.path.basename(path)})")
