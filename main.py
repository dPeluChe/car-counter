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

La logica pesada vive en carcounter/runtime.py — este archivo es solo
orquestacion: CLI, loop de frames, y callbacks a los helpers.
"""

from __future__ import annotations

import argparse
import time
from collections import deque

import cv2

from carcounter import api as carcounter_api
from carcounter import db
from carcounter.constants import resolve_vehicle_classes
from carcounter.device import detect_device
from carcounter.drawing import DensityHeatmap, format_time
from carcounter.logging_config import get_logger, setup_logging
from carcounter.paths import paths
from carcounter.profiler import Profiler
from carcounter.runtime import (
    build_counter_and_lines, export_results, load_detector, load_runtime_config,
    load_sahi, process_frame, setup_tracker, start_api_server,
)

log = get_logger("main")


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
    parser.add_argument("--tracker", default="bytetrack",
                        choices=["bytetrack", "botsort", "sort", "ocsort"])
    parser.add_argument("--output-json", default=str(paths.default_output_json))
    parser.add_argument("--no-output-json", dest="no_output_json", action="store_true")
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-tracks-csv", default=None)
    parser.add_argument("--output-od-csv", default=None)
    parser.add_argument("--heatmap", action="store_true")
    parser.add_argument("--demo-mode", dest="demo_mode", action="store_true")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server")
    parser.add_argument("--serve-port", type=int, default=8000, help="FastAPI server port")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Nivel de logging (default: INFO)")
    return parser


def main():
    args = build_parser().parse_args()
    setup_logging(level=args.log_level)

    if args.no_save and args.output_json == str(paths.default_output_json):
        args.no_output_json = True
    paths.ensure_dirs()

    # ── Inicializacion ─────────────────────────────────────
    cfg = load_runtime_config(args)
    device, device_desc = detect_device(args.device)

    model_yolo, rfdetr_model, detector_backend = load_detector(args, cfg, device)
    sahi_model, sahi_predict_fn, use_sahi = load_sahi(args, cfg, detector_backend, device)

    log.info("=" * 65)
    log.info("Car Counter  |  %s  |  %s  |  %s  |  %s",
             cfg["counting_mode"], detector_backend, args.tracker,
             "SAHI" if use_sahi else "rapido")
    log.info("Config: %s  |  Video: %s", args.config, cfg["video_path"])
    log.info("Device: %s", device_desc)
    log.info("=" * 65)

    cap = cv2.VideoCapture(cfg["video_path"])
    if not cap.isOpened():
        log.error("No se pudo abrir: %s", cfg["video_path"])
        raise SystemExit(1)

    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    vid_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / vid_fps if vid_fps > 0 else 0
    log.info("%dx%d @ %.1ffps  —  %.1fs (%d frames)",
             vid_w, vid_h, vid_fps, duration, total_frames)

    tracker_backend, sort_tracker = setup_tracker(args, cfg, use_sahi, vid_fps)
    counter, zones_np, exclusion_np, counting_lines = build_counter_and_lines(cfg, vid_w, vid_h)

    writer = None
    if not args.no_save:
        writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"),
                                 vid_fps, (vid_w, vid_h))
    heatmap = DensityHeatmap(vid_w, vid_h) if args.heatmap else None
    api_meta = start_api_server(args, counter, total_frames)

    # ── Estado del loop ────────────────────────────────────
    profiler = Profiler()
    vehicle_class_ids, class_names = resolve_vehicle_classes(model_yolo)
    log.info("Clases de vehiculo: %s", [class_names[i] for i in vehicle_class_ids])
    detect_state = {
        "profiler": profiler,
        "fn_kwargs": dict(
            model=model_yolo, sahi_model=sahi_model, sahi_predict_fn=sahi_predict_fn,
            sort_tracker=sort_tracker, use_sahi=use_sahi, tracker_backend=tracker_backend,
            tracker_yaml=f"{args.tracker}.yaml", effective_conf=cfg["effective_conf"],
            imgsz=cfg["imgsz"],
            conf_for=lambda c: cfg["conf_per_class"].get(c, cfg["conf_threshold"]),
            geo_constraints=cfg["geo_constraints"], exclusion_np=exclusion_np,
            sahi_slice_w=cfg["sahi_slice_w"], sahi_slice_h=cfg["sahi_slice_h"],
            sahi_overlap=cfg["sahi_overlap"], sahi_nms_threshold=cfg["sahi_nms"],
            device=device, detector_backend=detector_backend, rfdetr_model=rfdetr_model,
            vehicle_class_ids=vehicle_class_ids, class_names=class_names,
        ),
        "consecutive_errors": 0,
    }
    fps_samples = deque(maxlen=30)
    benchmark_data = []
    frame_count = 0
    fps_avg = 0.0

    start_time = time.time()
    api_meta["start_time"] = start_time
    log.info("Iniciando...  ('q' para salir)")

    # ── Loop principal ─────────────────────────────────────
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            frame_count += 1
            counter.set_frame(frame_count)

            tracked_boxes, fps_avg = process_frame(
                frame, frame_count=frame_count, counter=counter, cfg=cfg, args=args,
                detect_state=detect_state, fps_samples=fps_samples,
                zones_np=zones_np, exclusion_np=exclusion_np,
                counting_lines=counting_lines, use_sahi=use_sahi,
                heatmap=heatmap, vid_w=vid_w, total_frames=total_frames,
            )

            if writer:
                profiler.start("writing")
                writer.write(frame)
                profiler.end("writing")

            if args.serve:
                api_meta["frame_count"] = frame_count
                api_meta["fps_avg"] = fps_avg
                carcounter_api.set_current_frame(frame)

            if frame_count % 60 == 0:
                et = time.time() - start_time
                pct = frame_count / total_frames * 100 if total_frames > 0 else 0
                eta = (et / frame_count) * (total_frames - frame_count) if frame_count > 0 else 0
                log.info("  %.1f%%  f=%d/%d  fps=%.1f  ETA=%s  rutas=%d",
                         pct, frame_count, total_frames, fps_avg,
                         format_time(eta), sum(counter.routes_matrix.values()))
                if args.benchmark:
                    benchmark_data.append({
                        "frame": frame_count, "elapsed": et, "fps": fps_avg,
                        "stages": profiler.get_averages(),
                        "detections": len(tracked_boxes), "tracks": len(tracked_boxes),
                        "routes": sum(counter.routes_matrix.values()),
                    })

            if not args.headless:
                cv2.imshow("Car Counter", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if args.max_frames and frame_count >= args.max_frames:
                break

    except KeyboardInterrupt:
        log.info("Interrumpido por el usuario")
    except RuntimeError as e:
        log.error("Abortado: %s", e)
    except Exception as e:
        log.critical("Error fatal en el loop principal: %s", e, exc_info=True)

    # ── Cleanup y export ───────────────────────────────────
    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0

    export_results(
        args, cfg, counter,
        frame_count=frame_count, total_frames=total_frames, duration=duration,
        total_time=total_time, avg_fps=avg_fps, tracker_backend=tracker_backend,
        use_sahi=use_sahi, benchmark_data=benchmark_data,
    )

    if writer:
        writer.release()
    cap.release()
    cv2.destroyAllWindows()

    db.save_run(
        video_path=cfg["video_path"], config_path=args.config,
        frames=frame_count, duration=total_time,
        vehicles=counter.total_vehicles_ever,
        routes_matrix=counter.routes_matrix, od_matrix=counter.od_matrix,
    )

    log.info("=" * 65)
    log.info("Procesamiento completo")
    log.info("=" * 65)


if __name__ == "__main__":
    main()
