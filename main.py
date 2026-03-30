"""
main.py — Car Counter
=====================
Contador de vehiculos con tracking y deteccion YOLO.
Soporta zonas A->B (glorietas, intersecciones) y cruce de linea (aforo).
Lee la configuracion generada por setup.py.

Uso:
  python main.py
  python main.py --config config/config.json --video assets/video.mp4
  python main.py --no-sahi --tracker bytetrack --benchmark
"""

import cv2
import json
import time
import os
import argparse
import importlib.util
import numpy as np
from carcounter.paths import paths
from carcounter.counting import VehicleCounter
from carcounter.detection import detect_and_track
from carcounter.drawing import (
    draw_zones, draw_lines, draw_exclusion_zones, draw_tracked_boxes,
    draw_routes_panel, draw_scoreboard, draw_hud, format_time,
    DensityHeatmap,
)
from carcounter.export import (
    print_summary, export_json, export_csv, export_benchmark,
    export_tracks_csv, export_od_matrix_csv,
)
from carcounter.device import detect_device


def build_parser():
    """Construye el parser de argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="Car Counter — conteo de vehiculos con YOLO + tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default=str(paths.default_config))
    parser.add_argument("--video", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--no-sahi", dest="no_sahi", action="store_true")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--show-fps", dest="show_fps", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--output", default=str(paths.default_output_video))
    parser.add_argument("--no-save", dest="no_save", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--detector", default="yolo", choices=["yolo", "rfdetr"])
    parser.add_argument("--rfdetr-variant", default="base",
                        choices=["nano", "small", "medium", "base", "large"])
    parser.add_argument("--tracker", default="bytetrack", choices=["bytetrack", "botsort", "sort", "ocsort"])
    parser.add_argument("--output-json", default=str(paths.default_output_json))
    parser.add_argument("--no-output-json", dest="no_output_json", action="store_true")
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-tracks-csv", default=None)
    parser.add_argument("--output-od-csv", default=None)
    parser.add_argument("--heatmap", action="store_true")
    parser.add_argument("--demo-mode", dest="demo_mode", action="store_true")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.no_save and args.output_json == str(paths.default_output_json):
        args.no_output_json = True
    paths.ensure_dirs()

    # ─────────────────────────────────────────────
    # Cargar configuracion
    # ─────────────────────────────────────────────
    config_path = args.config
    if not os.path.exists(config_path):
        print(f"No se encontro: {config_path}\n   Ejecuta primero: python setup.py")
        exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    COUNTING_MODE = config.get("counting_mode", "zones")
    zones_config  = config.get("zones", {})
    lines_config  = config.get("lines", [])
    excl_config   = config.get("exclusion_zones", {})
    settings      = config.get("settings", {})
    sahi_cfg      = config.get("sahi", {})
    tracker_cfg   = config.get("tracker", {})

    VIDEO_PATH   = args.video or config.get("video_path", str(paths.default_video))
    MODEL_PATH   = args.model or config.get("model_path", str(paths.default_model))
    CONF_THRESH  = settings.get("conf_threshold", 0.10)
    CONF_PER_CLASS = settings.get("conf_per_class", {})
    EFFECTIVE_CONF = min(min(CONF_PER_CLASS.values()), CONF_THRESH) if CONF_PER_CLASS else CONF_THRESH
    INFER_IMGSZ  = args.imgsz or settings.get("imgsz", 1600)
    sc = settings.get("sample_constraints") or {}
    _geo_constraints = {
        "min_area": settings.get("min_area", 0), "max_area": settings.get("max_area", 999999),
        "min_width": sc.get("min_width", 0), "max_width": sc.get("max_width", 999999),
        "min_height": sc.get("min_height", 0), "max_height": sc.get("max_height", 999999),
        "min_aspect": sc.get("min_aspect", 0.0), "max_aspect": sc.get("max_aspect", 999999.0),
    }
    SLICE_W     = sahi_cfg.get("slice_width",  512)
    SLICE_H     = sahi_cfg.get("slice_height", 512)
    OVERLAP     = sahi_cfg.get("overlap_ratio", 0.2)
    NMS_SAHI    = sahi_cfg.get("nms_threshold", 0.3)
    TRACKER_YAML = f"{args.tracker}.yaml"
    USE_SAHI    = not args.no_sahi

    def _conf_for(cls_name):
        return CONF_PER_CLASS.get(cls_name, CONF_THRESH)

    # ─────────────────────────────────────────────
    # Device
    # ─────────────────────────────────────────────
    DEVICE, device_desc = detect_device(args.device)

    DETECTOR_BACKEND = args.detector

    print("=" * 65)
    print(f"Car Counter  |  {COUNTING_MODE}  |  {DETECTOR_BACKEND}  |  {args.tracker}  |  {'SAHI' if USE_SAHI else 'rapido'}")
    print(f"Config: {config_path}  |  Video: {VIDEO_PATH}")
    print(f"Device: {device_desc}")
    print("=" * 65)

    # ─────────────────────────────────────────────
    # Modelos
    # ─────────────────────────────────────────────
    model_yolo = None
    rfdetr_model = None

    if DETECTOR_BACKEND == "rfdetr":
        from carcounter.rfdetr_detector import is_rfdetr_available, load_rfdetr_model
        if not is_rfdetr_available():
            print("'rfdetr' no instalado — fallback a YOLO")
            DETECTOR_BACKEND = "yolo"
        else:
            rfdetr_model = load_rfdetr_model(
                variant=args.rfdetr_variant,
                weights=MODEL_PATH if not MODEL_PATH.endswith(".pt") else None,
                device=DEVICE,
            )
            print(f"Detector: RF-DETR {args.rfdetr_variant}")
            # RF-DETR no tiene .track() — forzar SORT/OC-SORT si se pidio ByteTrack nativo
            if args.tracker in ("bytetrack", "botsort"):
                print(f"  RF-DETR no soporta {args.tracker} nativo — usando SORT para tracking")
                args.tracker = "sort"

    if DETECTOR_BACKEND == "yolo":
        from ultralytics import YOLO
        model_yolo = YOLO(MODEL_PATH)

    sahi_model = None
    sahi_predict_fn = None
    if USE_SAHI:
        if DETECTOR_BACKEND == "rfdetr":
            print("SAHI + RF-DETR no soportado aun — fallback a modo rapido")
            USE_SAHI = False
        else:
            try:
                from sahi import AutoDetectionModel
                from sahi.predict import get_sliced_prediction
                sahi_model = AutoDetectionModel.from_pretrained(
                    model_type="yolov8", model_path=MODEL_PATH,
                    confidence_threshold=EFFECTIVE_CONF, device=DEVICE,
                )
                sahi_predict_fn = get_sliced_prediction
            except ImportError:
                print("SAHI no instalado — fallback a modo rapido")
                USE_SAHI = False

    # ─────────────────────────────────────────────
    # Video
    # ─────────────────────────────────────────────
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"No se pudo abrir: {VIDEO_PATH}")
        exit(1)

    VID_W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    VID_H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    VID_FPS = cap.get(cv2.CAP_PROP_FPS)
    TOTAL_F = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    DURATION = TOTAL_F / VID_FPS if VID_FPS > 0 else 0
    print(f"{VID_W}x{VID_H} @ {VID_FPS:.1f}fps  —  {DURATION:.1f}s ({TOTAL_F} frames)")

    # ─────────────────────────────────────────────
    # Tracker fallback
    # ─────────────────────────────────────────────
    TRACKER_BACKEND = args.tracker
    if TRACKER_BACKEND in {"bytetrack", "botsort"} and not importlib.util.find_spec("lap"):
        print("'lap' no instalado — fallback a SORT")
        TRACKER_BACKEND = "sort"
    if TRACKER_BACKEND == "ocsort":
        from carcounter.ocsort_wrapper import is_ocsort_available
        if not is_ocsort_available():
            print("'trackers' no instalado — fallback a SORT")
            TRACKER_BACKEND = "sort"

    _sort_tracker = None
    if TRACKER_BACKEND == "ocsort":
        from carcounter.ocsort_wrapper import OCSortWrapper
        _sort_tracker = OCSortWrapper(
            max_age=tracker_cfg.get("max_age", 40),
            min_hits=tracker_cfg.get("min_hits", 3),
            iou_threshold=tracker_cfg.get("iou_threshold", 0.2),
            high_conf_threshold=settings.get("conf_threshold", 0.1),
            frame_rate=VID_FPS,
        )
        print(f"Tracker: OC-SORT (direction_consistency=0.2)")
    elif USE_SAHI or TRACKER_BACKEND == "sort":
        try:
            from carcounter.sort import Sort
            _sort_tracker = Sort(
                max_age=tracker_cfg.get("max_age", 40),
                min_hits=tracker_cfg.get("min_hits", 3),
                iou_threshold=tracker_cfg.get("iou_threshold", 0.2),
            )
        except ImportError:
            pass

    # ─────────────────────────────────────────────
    # Zonas, lineas y contador
    # ─────────────────────────────────────────────
    zones_np = {name: np.array(pts, dtype=np.int32) for name, pts in zones_config.items()}
    zone_names = list(zones_np.keys())
    _exclusion_np = {name: np.array(pts, dtype=np.int32) for name, pts in excl_config.items()}

    counting_lines = []
    if COUNTING_MODE == "lines":
        for i, lc in enumerate(lines_config):
            pts = lc.get("points", [])
            if len(pts) >= 2:
                counting_lines.append({
                    "name": lc.get("name", f"Linea {i+1}"),
                    "pt1": tuple(pts[0]), "pt2": tuple(pts[1]),
                    "tolerance": lc.get("tolerance", 15),
                })

    # Directions config (for directions mode)
    directions_config = config.get("directions", {})

    counter = VehicleCounter(
        zones_np=zones_np, counting_lines=counting_lines,
        min_origin_frames=settings.get("min_origin_frames", 3),
        min_dest_frames=settings.get("min_dest_frames", 3),
        frame_size=(VID_W, VID_H),
        directions=directions_config,
        min_crossing_frames=settings.get("min_crossing_frames", 2),
    )

    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"), VID_FPS, (VID_W, VID_H)) \
        if not args.no_save else None

    _heatmap = DensityHeatmap(VID_W, VID_H) if args.heatmap else None

    # ─────────────────────────────────────────────
    # Main loop
    # ─────────────────────────────────────────────
    frame_count = 0
    start_time = time.time()
    fps_samples = []
    benchmark_data = []
    DISPLAY = not args.headless

    print(f"\nIniciando...  ('q' para salir)\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_count += 1
            counter.set_frame(frame_count)
            t0 = time.time()

            # -- Deteccion + tracking --
            tracked_boxes = detect_and_track(
                frame, model=model_yolo, sahi_model=sahi_model,
                sahi_predict_fn=sahi_predict_fn, sort_tracker=_sort_tracker,
                use_sahi=USE_SAHI, tracker_backend=TRACKER_BACKEND,
                tracker_yaml=TRACKER_YAML, effective_conf=EFFECTIVE_CONF,
                imgsz=INFER_IMGSZ, conf_for=_conf_for,
                geo_constraints=_geo_constraints, exclusion_np=_exclusion_np,
                sahi_slice_w=SLICE_W, sahi_slice_h=SLICE_H,
                sahi_overlap=OVERLAP, sahi_nms_threshold=NMS_SAHI,
                device=DEVICE,
                detector_backend=DETECTOR_BACKEND, rfdetr_model=rfdetr_model,
            )

            # -- Conteo --
            for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                counter.update(trk_id, cx, cy, cls_name, COUNTING_MODE,
                               bbox=(x1, y1, x2, y2))

            if frame_count % 120 == 0:
                counter.purge_stale()

            # -- Heatmap --
            if _heatmap:
                centroids = [((x1+x2)//2, (y1+y2)//2) for x1,y1,x2,y2,_,_ in tracked_boxes]
                _heatmap.update(centroids)
                _heatmap.draw(frame)

            # -- Visualizacion --
            draw_exclusion_zones(frame, _exclusion_np)
            if COUNTING_MODE == "lines":
                draw_lines(frame, counting_lines)
            else:
                draw_zones(frame, zones_np)

            draw_tracked_boxes(frame, tracked_boxes, counter.tracks_info, zone_names,
                               trails=counter.trails)

            if args.demo_mode:
                draw_scoreboard(frame, counter.routes_matrix, len(tracked_boxes),
                                counter.total_vehicles_ever, VID_W, zone_names)
            else:
                draw_routes_panel(frame, counter.routes_matrix, len(tracked_boxes))

            elapsed = time.time() - t0
            fps_samples.append(1.0 / elapsed if elapsed > 0 else 0)
            fps_avg = np.mean(fps_samples[-30:])

            if args.show_fps or USE_SAHI:
                draw_hud(frame, frame_count, TOTAL_F, fps_avg, len(tracked_boxes),
                         sum(counter.routes_matrix.values()), VID_W)

            # Progreso consola
            if frame_count % 60 == 0:
                et = time.time() - start_time
                pct = frame_count / TOTAL_F * 100 if TOTAL_F > 0 else 0
                eta = (et / frame_count) * (TOTAL_F - frame_count) if frame_count > 0 else 0
                print(f"  {pct:.1f}%  f={frame_count}/{TOTAL_F}  fps={fps_avg:.1f}  "
                      f"ETA={format_time(eta)}  rutas={sum(counter.routes_matrix.values())}")
                if args.benchmark:
                    benchmark_data.append({"frame": frame_count, "elapsed": et, "fps": fps_avg,
                        "detections": len(tracked_boxes), "tracks": len(tracked_boxes),
                        "routes": sum(counter.routes_matrix.values())})

            if DISPLAY:
                cv2.imshow("Car Counter", frame)
            if writer:
                writer.write(frame)
            if args.max_frames and frame_count >= args.max_frames:
                break
            if DISPLAY and cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        pass

    # ─────────────────────────────────────────────
    # Resultados
    # ─────────────────────────────────────────────
    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0
    rm = counter.routes_matrix

    print_summary(video_path=VIDEO_PATH, config_path=config_path, use_sahi=USE_SAHI,
                  tracker_backend=TRACKER_BACKEND, frame_count=frame_count,
                  total_frames=TOTAL_F, total_time=total_time, avg_fps=avg_fps,
                  zone_names=zone_names, total_vehicles=counter.total_vehicles_ever,
                  routes_matrix=rm)

    if not args.no_output_json:
        export_json(args.output_json, video_path=VIDEO_PATH, config_path=config_path,
                    use_sahi=USE_SAHI, tracker_backend=TRACKER_BACKEND,
                    counting_mode=COUNTING_MODE, frame_count=frame_count,
                    total_frames=TOTAL_F, duration=DURATION, total_time=total_time,
                    avg_fps=avg_fps, total_vehicles=counter.total_vehicles_ever,
                    routes_matrix=rm, zone_names=zone_names)

    if args.output_csv:
        export_csv(args.output_csv, rm)

    if args.output_tracks_csv:
        export_tracks_csv(args.output_tracks_csv, counter.get_track_data())

    if args.output_od_csv:
        export_od_matrix_csv(args.output_od_csv, counter.od_matrix)

    if args.benchmark and benchmark_data:
        export_benchmark(str(paths.benchmarks_dir), video_path=VIDEO_PATH,
                         config_path=config_path, use_sahi=USE_SAHI,
                         total_time=total_time, avg_fps=avg_fps,
                         routes_matrix=rm, benchmark_data=benchmark_data)

    if writer:
        writer.release()
    cap.release()
    cv2.destroyAllWindows()
    print("=" * 65)
    print("Procesamiento completo")
    print("=" * 65)


if __name__ == "__main__":
    main()
