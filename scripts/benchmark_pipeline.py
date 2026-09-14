#!/usr/bin/env python3
"""Benchmark del pipeline de Car Counter por etapa.

Mide el tiempo promedio de cada etapa del pipeline sobre un video corto
para identificar cuellos de botella antes de optimizar.

Uso:
  python scripts/benchmark_pipeline.py --video assets/glorieta_fast.MP4 --max-frames 200
  python scripts/benchmark_pipeline.py --video assets/glorieta_fast.MP4 --no-sahi
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from ultralytics import YOLO

from carcounter.paths import paths
from carcounter.profiler import Profiler
from carcounter.detection import detect_and_track
from carcounter.counting import VehicleCounter
from carcounter.device import detect_device


def run_benchmark(video_path, model_path, max_frames=200, use_sahi=False, device="auto"):
    """Corre el pipeline completo y reporta tiempos por etapa."""
    DEVICE, device_desc = detect_device(device)
    print(f"Device: {device_desc}")
    print(f"Video:  {video_path}")
    print(f"Model:  {model_path}")
    print(f"Frames: {max_frames}  |  SAHI: {use_sahi}")
    print("-" * 50)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: No se pudo abrir {video_path}")
        sys.exit(1)

    VID_W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    VID_H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    VID_FPS = cap.get(cv2.CAP_PROP_FPS)
    print(f"Resolucion: {VID_W}x{VID_H} @ {VID_FPS:.1f}fps")

    model = YOLO(model_path)

    sahi_model = None
    sahi_predict_fn = None
    if use_sahi:
        try:
            from sahi import AutoDetectionModel
            from sahi.predict import get_sliced_prediction
            sahi_model = AutoDetectionModel.from_pretrained(
                model_type="yolov8", model_path=model_path,
                confidence_threshold=0.1, device=DEVICE,
            )
            sahi_predict_fn = get_sliced_prediction
            print("SAHI: activado")
        except ImportError:
            print("SAHI: no disponible, usando modo rapido")
            use_sahi = False

    from carcounter.sort import Sort
    sort_tracker = Sort(max_age=40, min_hits=3, iou_threshold=0.2)

    counter = VehicleCounter(zones_np={}, counting_lines=[], frame_size=(VID_W, VID_H))
    profiler = Profiler()
    frame_count = 0
    total_start = time.perf_counter()

    _geo_constraints = {
        "min_area": 0, "max_area": 999999,
        "min_width": 0, "max_width": 999999,
        "min_height": 0, "max_height": 999999,
        "min_aspect": 0.0, "max_aspect": 999999.0,
    }
    _exclusion_np = {}

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        frame_count += 1
        counter.set_frame(frame_count)

        # -- Deteccion + tracking --
        profiler.start("detection")
        tracked_boxes = detect_and_track(
            frame, model=model, sahi_model=sahi_model,
            sahi_predict_fn=sahi_predict_fn, sort_tracker=sort_tracker,
            use_sahi=use_sahi, effective_conf=0.1,
            imgsz=1280, conf_for=lambda _: 0.1,
            geo_constraints=_geo_constraints, exclusion_np=_exclusion_np,
            sahi_slice_w=512, sahi_slice_h=512,
            sahi_overlap=0.2, sahi_nms_threshold=0.3,
            device=DEVICE,
        )
        profiler.end("detection")

        # -- Conteo --
        profiler.start("counting")
        for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            counter.update(trk_id, cx, cy, cls_name, "zones", bbox=(x1, y1, x2, y2))
        profiler.end("counting")

        # -- Visualization (solo frame copy para medir overhead de drawing) --
        profiler.start("visualization")
        _ = frame.copy()
        profiler.end("visualization")

        # -- Escritura (simula encode a JPEG como proxy de VideoWriter) --
        profiler.start("writing")
        cv2.imencode('.jpg', frame)
        profiler.end("writing")

    total_elapsed = time.perf_counter() - total_start
    cap.release()

    avgs = profiler.get_averages()
    total_stage_ms = sum(v * 1000 for v in avgs.values())
    pipeline_fps = frame_count / total_elapsed if total_elapsed > 0 else 0

    print(f"\nResultados ({frame_count} frames en {total_elapsed:.1f}s):")
    print(f"  FPS promedio del pipeline: {pipeline_fps:.1f}")
    print()
    print(f"  {'Etapa':<20} {'ms/frame':>10}  {'% del tiempo':>13}")
    print(f"  {'-'*20}  {'-'*10}  {'-'*13}")
    for stage, avg_s in avgs.items():
        ms = avg_s * 1000
        pct = (ms / total_stage_ms * 100) if total_stage_ms > 0 else 0
        print(f"  {stage:<20} {ms:>10.2f}  {pct:>12.1f}%")

    bottleneck = max(avgs, key=avgs.get)
    print(f"\n  Cuello de botella: {bottleneck} ({avgs[bottleneck]*1000:.2f}ms/frame)")

    return avgs


def main():
    parser = argparse.ArgumentParser(description="Benchmark del pipeline por etapa")
    parser.add_argument("--video", default=str(paths.default_video))
    parser.add_argument("--model", default=str(paths.default_model))
    parser.add_argument("--max-frames", type=int, default=200)
    parser.add_argument("--no-sahi", action="store_true")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    run_benchmark(
        video_path=args.video,
        model_path=args.model,
        max_frames=args.max_frames,
        use_sahi=not args.no_sahi,
        device=args.device,
    )


if __name__ == "__main__":
    main()
