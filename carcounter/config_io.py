"""Lectura y escritura de config.json para el configurador."""

import json
import os
from carcounter.paths import paths


def load_config(path):
    """Lee un JSON de configuracion y retorna el dict."""
    with open(path) as f:
        return json.load(f)


def parse_exclusion_zones(cfg):
    """Extrae zonas de exclusion del config."""
    raw = cfg.get("exclusion_zones", {})
    return {name: [list(p) for p in pts] for name, pts in raw.items()}


def parse_zones(cfg):
    """Extrae zonas de transito del config."""
    raw = cfg.get("zones", {})
    return {name: [list(p) for p in pts] for name, pts in raw.items()}


def parse_lines(cfg):
    """Extrae lineas de cruce del config."""
    result = {}
    for lc in cfg.get("lines", []):
        name = lc.get("name", f"Linea {len(result)+1}")
        pts = lc.get("points", [])
        if len(pts) >= 2:
            result[name] = [list(pts[0]), list(pts[1])]
    return result


def build_config(*, counting_mode, exclusion_zones, zones, counting_lines,
                 min_area, max_area, conf_threshold, imgsz,
                 sample_constraints, sample_count,
                 conf_per_class, conf_per_class_modified,
                 slice_w, slice_h, overlap, nms_threshold,
                 max_age, min_hits, iou_threshold,
                 video_path, model_path, loaded_config=None):
    """Construye el dict de configuracion para guardar."""
    config = {
        "counting_mode": counting_mode,
        "exclusion_zones": dict(exclusion_zones),
        "zones": dict(zones),
        "lines": [
            {"name": name, "points": pts, "tolerance": 15}
            for name, pts in counting_lines.items()
        ],
        "settings": {
            "min_area": min_area,
            "max_area": max_area,
            "conf_threshold": round(conf_threshold, 2),
            "imgsz": imgsz,
            "sample_constraints": sample_constraints,
            "sample_count": sample_count,
            **({"conf_per_class": {
                    "car": round(conf_per_class["car"], 2),
                    "motorbike": round(conf_per_class["motorbike"], 2),
                    "bus": round(conf_per_class["bus"], 2),
                    "truck": round(conf_per_class["truck"], 2),
                }} if conf_per_class_modified else {}),
        },
        "sahi": {
            "slice_width": slice_w,
            "slice_height": slice_h,
            "overlap_ratio": round(overlap, 2),
            "nms_threshold": round(nms_threshold, 2),
        },
        "tracker": {
            "max_age": max_age,
            "min_hits": min_hits,
            "iou_threshold": round(iou_threshold, 2),
        },
        "video_path": video_path,
        "model_path": model_path,
    }

    # Preservar campos extra del JSON original
    if loaded_config:
        for section in ("settings", "sahi", "tracker"):
            loaded = loaded_config.get(section, {})
            for key, val in loaded.items():
                if key not in config.get(section, {}):
                    config.setdefault(section, {})[key] = val

    return config


def parse_settings(cfg):
    """Extrae settings, sahi y tracker como dicts planos para aplicar a la UI."""
    s = cfg.get("settings", {})
    sahi = cfg.get("sahi", {})
    t = cfg.get("tracker", {})
    return {
        "sample_constraints": s.get("sample_constraints"),
        "min_area": s.get("min_area"),
        "max_area": s.get("max_area"),
        "conf_threshold": s.get("conf_threshold"),
        "conf_per_class": s.get("conf_per_class"),
        "imgsz": s.get("imgsz"),
        "slice_width": sahi.get("slice_width"),
        "slice_height": sahi.get("slice_height"),
        "overlap_ratio": sahi.get("overlap_ratio"),
        "nms_threshold": sahi.get("nms_threshold"),
        "max_age": t.get("max_age"),
        "min_hits": t.get("min_hits"),
        "iou_threshold": t.get("iou_threshold"),
    }


def save_config(path, config):
    """Guarda el dict de configuracion como JSON."""
    paths.ensure_dirs()
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
