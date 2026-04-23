"""Helpers de inicializacion y procesamiento extraidos de main.py.

Separar responsabilidades:
  - Carga de config/modelo/tracker/counter (inicializacion)
  - Procesamiento de un frame (detect + count + draw)
  - Export de resultados

main.py queda como orquestador delgado.
"""

from __future__ import annotations

import importlib.util
import json
import os
import threading
import time
from collections import deque
from typing import Any

import cv2
import numpy as np

from carcounter import api as carcounter_api
from carcounter.counting import VehicleCounter
from carcounter.detection import detect_and_track
from carcounter.drawing import (
    DensityHeatmap, draw_direction_vectors, draw_exclusion_zones, draw_hud,
    draw_lines, draw_routes_panel, draw_scoreboard, draw_tracked_boxes,
    draw_zones,
)
from carcounter.export import (
    export_benchmark, export_csv, export_json, export_od_matrix_csv,
    export_tracks_csv, print_summary,
)
from carcounter.logging_config import get_logger
from carcounter.paths import paths

log = get_logger("runtime")

MAX_CONSECUTIVE_ERRORS = 10


# ══════════════════════════════════════════════════════════
# Inicializacion
# ══════════════════════════════════════════════════════════

def load_runtime_config(args) -> dict:
    """Carga config.json y resuelve overrides desde CLI args."""
    if not os.path.exists(args.config):
        log.error("No se encontro: %s — Ejecuta primero: python setup.py", args.config)
        raise SystemExit(1)

    with open(args.config, "r") as f:
        config = json.load(f)

    settings = config.get("settings", {})
    sahi_cfg = config.get("sahi", {})
    sc = settings.get("sample_constraints") or {}
    conf_per_class = settings.get("conf_per_class", {})
    conf_threshold = settings.get("conf_threshold", 0.10)

    default_model = (str(paths.default_rfdetr_model)
                     if args.detector == "rfdetr"
                     else str(paths.default_model))

    return {
        "raw_config": config,
        "counting_mode": config.get("counting_mode", "zones"),
        "zones_config": config.get("zones", {}),
        "lines_config": config.get("lines", []),
        "excl_config": config.get("exclusion_zones", {}),
        "directions_config": config.get("directions", {}),
        "settings": settings,
        "sahi_cfg": sahi_cfg,
        "tracker_cfg": config.get("tracker", {}),
        "video_path": args.video or config.get("video_path", str(paths.default_video)),
        "model_path": args.model or config.get("model_path", default_model),
        "conf_threshold": conf_threshold,
        "conf_per_class": conf_per_class,
        "effective_conf": min(min(conf_per_class.values()), conf_threshold)
                          if conf_per_class else conf_threshold,
        "imgsz": args.imgsz or settings.get("imgsz", 1600),
        "geo_constraints": {
            "min_area": settings.get("min_area", 0),
            "max_area": settings.get("max_area", 999999),
            "min_width": sc.get("min_width", 0),
            "max_width": sc.get("max_width", 999999),
            "min_height": sc.get("min_height", 0),
            "max_height": sc.get("max_height", 999999),
            "min_aspect": sc.get("min_aspect", 0.0),
            "max_aspect": sc.get("max_aspect", 999999.0),
        },
        "sahi_slice_w": sahi_cfg.get("slice_width", 512),
        "sahi_slice_h": sahi_cfg.get("slice_height", 512),
        "sahi_overlap": sahi_cfg.get("overlap_ratio", 0.2),
        "sahi_nms": sahi_cfg.get("nms_threshold", 0.3),
    }


def load_detector(args, cfg, device):
    """Carga YOLO o RF-DETR con fallbacks. Retorna (yolo, rfdetr, backend)."""
    model_yolo = None
    rfdetr_model = None
    backend = args.detector

    if backend == "rfdetr":
        from carcounter.rfdetr_detector import is_rfdetr_available, load_rfdetr_model
        if not is_rfdetr_available():
            log.warning("'rfdetr' no instalado — fallback a YOLO")
            backend = "yolo"
        else:
            rfdetr_model = load_rfdetr_model(
                variant=args.rfdetr_variant,
                weights=cfg["model_path"] if not cfg["model_path"].endswith(".pt") else None,
                device=device,
            )
            log.info("Detector: RF-DETR %s", args.rfdetr_variant)
            if args.tracker in ("bytetrack", "botsort"):
                log.warning("RF-DETR no soporta %s nativo — usando SORT", args.tracker)
                args.tracker = "sort"

    if backend == "yolo":
        from ultralytics import YOLO
        model_yolo = YOLO(cfg["model_path"])

    return model_yolo, rfdetr_model, backend


def load_sahi(args, cfg, detector_backend, device):
    """Retorna (sahi_model, sahi_predict_fn, use_sahi)."""
    if args.no_sahi:
        return None, None, False
    if detector_backend == "rfdetr":
        log.warning("SAHI + RF-DETR no soportado aun — fallback a modo rapido")
        return None, None, False
    try:
        from sahi import AutoDetectionModel
        from sahi.predict import get_sliced_prediction
        sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8", model_path=cfg["model_path"],
            confidence_threshold=cfg["effective_conf"], device=device,
        )
        return sahi_model, get_sliced_prediction, True
    except ImportError:
        log.warning("SAHI no instalado — fallback a modo rapido")
        return None, None, False


def setup_tracker(args, cfg, use_sahi, vid_fps):
    """Resuelve tracker backend. Retorna (backend, sort_tracker_or_None)."""
    backend = args.tracker
    if backend in {"bytetrack", "botsort"} and not importlib.util.find_spec("lap"):
        log.warning("'lap' no instalado — fallback a SORT")
        backend = "sort"
    if backend == "ocsort":
        from carcounter.ocsort_wrapper import is_ocsort_available
        if not is_ocsort_available():
            log.warning("'trackers' no instalado — fallback a SORT")
            backend = "sort"

    sort_tracker = None
    tcfg = cfg["tracker_cfg"]
    if backend == "ocsort":
        from carcounter.ocsort_wrapper import OCSortWrapper
        sort_tracker = OCSortWrapper(
            max_age=tcfg.get("max_age", 40),
            min_hits=tcfg.get("min_hits", 3),
            iou_threshold=tcfg.get("iou_threshold", 0.2),
            high_conf_threshold=cfg["settings"].get("conf_threshold", 0.1),
            frame_rate=vid_fps,
        )
        log.info("Tracker: OC-SORT (direction_consistency=0.2)")
    elif use_sahi or backend == "sort":
        try:
            from carcounter.sort import Sort
            sort_tracker = Sort(
                max_age=tcfg.get("max_age", 40),
                min_hits=tcfg.get("min_hits", 3),
                iou_threshold=tcfg.get("iou_threshold", 0.2),
            )
        except ImportError:
            pass

    return backend, sort_tracker


def build_counter_and_lines(cfg, vid_w, vid_h):
    """Construye VehicleCounter y parsea counting_lines. Retorna tupla 4 items."""
    zones_np = {name: np.array(pts, dtype=np.int32)
                for name, pts in cfg["zones_config"].items()}
    exclusion_np = {name: np.array(pts, dtype=np.int32)
                    for name, pts in cfg["excl_config"].items()}

    counting_lines = []
    if cfg["counting_mode"] == "lines":
        for i, lc in enumerate(cfg["lines_config"]):
            pts = lc.get("points", [])
            if len(pts) >= 2:
                counting_lines.append({
                    "name": lc.get("name", f"Linea {i + 1}"),
                    "pt1": tuple(pts[0]), "pt2": tuple(pts[1]),
                    "tolerance": lc.get("tolerance", 15),
                })

    settings = cfg["settings"]
    counter = VehicleCounter(
        zones_np=zones_np, counting_lines=counting_lines,
        min_origin_frames=settings.get("min_origin_frames", 3),
        min_dest_frames=settings.get("min_dest_frames", 3),
        frame_size=(vid_w, vid_h),
        directions=cfg["directions_config"],
        min_crossing_frames=settings.get("min_crossing_frames", 2),
    )
    return counter, zones_np, exclusion_np, counting_lines


def start_api_server(args, counter, total_frames) -> dict:
    """Arranca FastAPI en thread si --serve. Retorna api_meta dict (siempre)."""
    api_meta = {"frame_count": 0, "total_frames": total_frames,
                "fps_avg": 0.0, "start_time": 0.0}
    if not args.serve:
        return api_meta
    try:
        from carcounter.api import run_server
        carcounter_api.set_current_engine(counter, api_meta)
        thread = threading.Thread(
            target=run_server,
            kwargs={"host": "0.0.0.0", "port": args.serve_port},
            daemon=True,
        )
        thread.start()
        log.info("FastAPI server started on port %d", args.serve_port)
    except ImportError as e:
        log.warning("FastAPI not available: %s", e)
    return api_meta


# ══════════════════════════════════════════════════════════
# Procesamiento de un frame
# ══════════════════════════════════════════════════════════

def process_frame(frame, *, frame_count, counter, cfg, args, detect_state,
                  fps_samples, zones_np, exclusion_np, counting_lines, use_sahi,
                  heatmap, vid_w, total_frames):
    """Procesa un frame: detect + count + draw. Retorna (tracked_boxes, fps_avg).

    Lanza RuntimeError si se exceden MAX_CONSECUTIVE_ERRORS en deteccion.
    """
    profiler = detect_state["profiler"]
    t0 = time.time()

    profiler.start("detection")
    try:
        tracked_boxes = detect_and_track(frame, **detect_state["fn_kwargs"])
        detect_state["consecutive_errors"] = 0
    except Exception as e:
        detect_state["consecutive_errors"] += 1
        log.error("Error en deteccion frame %d: %s", frame_count, e)
        if detect_state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
            log.critical("Demasiados errores consecutivos (%d). Abortando.",
                         detect_state["consecutive_errors"])
            raise RuntimeError("too many detection errors") from e
        tracked_boxes = []
    profiler.end("detection")

    profiler.start("counting")
    for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        counter.update(trk_id, cx, cy, cls_name, cfg["counting_mode"],
                       bbox=(x1, y1, x2, y2))
    if frame_count % 120 == 0:
        counter.purge_stale()
    profiler.end("counting")

    profiler.start("visualization")
    if heatmap:
        centroids = [((x1 + x2) // 2, (y1 + y2) // 2)
                     for x1, y1, x2, y2, _, _ in tracked_boxes]
        heatmap.update(centroids)
        heatmap.draw(frame)

    elapsed = time.time() - t0
    fps_samples.append(1.0 / elapsed if elapsed > 0 else 0)
    fps_avg = float(np.mean(fps_samples))
    zone_names = list(zones_np.keys())

    try:
        draw_exclusion_zones(frame, exclusion_np)
        if cfg["counting_mode"] == "lines":
            draw_lines(frame, counting_lines)
        elif cfg["counting_mode"] == "directions":
            draw_direction_vectors(frame, cfg["directions_config"])
        else:
            draw_zones(frame, zones_np)

        draw_tracked_boxes(frame, tracked_boxes, counter.tracks_info,
                           zone_names, trails=counter.trails)

        if args.demo_mode:
            draw_scoreboard(frame, counter.routes_matrix, len(tracked_boxes),
                            counter.total_vehicles_ever, vid_w, zone_names)
        else:
            draw_routes_panel(frame, counter.routes_matrix, len(tracked_boxes))

        if args.show_fps or use_sahi:
            draw_hud(frame, frame_count, total_frames, fps_avg, len(tracked_boxes),
                     sum(counter.routes_matrix.values()), vid_w)
    except Exception as e:
        log.warning("Error en visualizacion frame %d: %s", frame_count, e)
    profiler.end("visualization")

    return tracked_boxes, fps_avg


# ══════════════════════════════════════════════════════════
# Export de resultados
# ══════════════════════════════════════════════════════════

def export_results(args, cfg, counter, *, frame_count, total_frames, duration,
                   total_time, avg_fps, tracker_backend, use_sahi, benchmark_data):
    """Imprime resumen y exporta segun flags CLI."""
    rm = counter.routes_matrix
    zone_names = list(cfg["zones_config"].keys())

    print_summary(
        video_path=cfg["video_path"], config_path=args.config, use_sahi=use_sahi,
        tracker_backend=tracker_backend, frame_count=frame_count,
        total_frames=total_frames, total_time=total_time, avg_fps=avg_fps,
        zone_names=zone_names, total_vehicles=counter.total_vehicles_ever,
        routes_matrix=rm,
    )

    if not args.no_output_json:
        export_json(
            args.output_json, video_path=cfg["video_path"], config_path=args.config,
            use_sahi=use_sahi, tracker_backend=tracker_backend,
            counting_mode=cfg["counting_mode"], frame_count=frame_count,
            total_frames=total_frames, duration=duration, total_time=total_time,
            avg_fps=avg_fps, total_vehicles=counter.total_vehicles_ever,
            routes_matrix=rm, zone_names=zone_names,
        )

    if args.output_csv:
        export_csv(args.output_csv, rm)
    if args.output_tracks_csv:
        export_tracks_csv(args.output_tracks_csv, counter.get_track_data())
    if args.output_od_csv:
        export_od_matrix_csv(args.output_od_csv, counter.od_matrix)

    if args.benchmark and benchmark_data:
        export_benchmark(
            str(paths.benchmarks_dir), video_path=cfg["video_path"],
            config_path=args.config, use_sahi=use_sahi, total_time=total_time,
            avg_fps=avg_fps, routes_matrix=rm, benchmark_data=benchmark_data,
        )
