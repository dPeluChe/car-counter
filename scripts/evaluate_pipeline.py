#!/usr/bin/env python3
"""Evalua el pipeline comparando detecciones vs ground truth humano (LabelMe).

Asume que ya se corrieron:
  1. extract_validation_frames.py (extrae frames)
  2. pre_label_frames.py (pre-etiquetas)
  3. humano corrige anotaciones en LabelMe

Luego este script corre el pipeline sobre esos frames y reporta metricas.

Uso:
  python scripts/evaluate_pipeline.py \
      --frames-dir data/validation/frames \
      --annotations-dir data/validation/annotations \
      --model models/yolo/yolov11l.pt \
      --iou-threshold 0.5
"""

import argparse
import json
from types import SimpleNamespace
import numpy as np
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from carcounter.paths import paths
from carcounter.constants import VEHICLE_CLASSES
from carcounter.detection import detect_objects
from carcounter.detector import filter_detections
from carcounter.geometry import in_exclusion_zone
from carcounter.runtime import resolve_runtime_config, load_sahi
from carcounter.validation import (
    load_labelme_annotations,
    match_detections,
    compute_metrics,
    canonical_vehicle_label,
)


def evaluate(frames_dir, annotations_dir, model_path=None, iou_threshold=0.5,
             conf_threshold=None, imgsz=None, config_path=None, no_sahi=False, device="cpu"):
    """Corre el pipeline sobre frames con ground truth y calcula metricas."""
    frames_dir = Path(frames_dir)
    annotations_dir = Path(annotations_dir)

    gt_by_frame = load_labelme_annotations(annotations_dir, require_reviewed=True)
    if not gt_by_frame:
        print(f"ERROR: No hay anotaciones en {annotations_dir}")
        raise ValueError(f"No hay anotaciones revisadas en {annotations_dir}")

    print(f"Cargadas anotaciones de {len(gt_by_frame)} frames")

    config = json.loads(Path(config_path).read_text()) if config_path else {"sahi": {"enabled": False}}
    settings = config.setdefault("settings", {})
    if conf_threshold is not None:
        settings["conf_threshold"] = conf_threshold
    if imgsz is None and config_path is None:
        imgsz = 1280
    args = SimpleNamespace(detector="yolo", video=None, model=model_path, imgsz=imgsz, no_sahi=no_sahi)
    cfg = resolve_runtime_config(config, args)
    from ultralytics import YOLO
    model = YOLO(cfg["model_path"])
    sahi_model, predict_fn, use_sahi = load_sahi(args, cfg, "yolo", device)
    exclusion = {name: np.asarray(pts, dtype=np.int32) for name, pts in cfg["excl_config"].items()}
    roi = settings.get("inference_roi")

    # Acumuladores globales y por clase
    total_tp = total_fp = total_fn = 0
    per_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0,
                                      "pred_count": 0, "gt_count": 0})

    total_pred = total_gt = total_count_error = 0
    localization_tp = localization_fp = localization_fn = 0
    frames_evaluated = 0

    for frame_stem, gt_dets in gt_by_frame.items():
        frame_path = None
        for ext in (".jpg", ".png", ".JPG", ".PNG"):
            candidate = frames_dir / f"{frame_stem}{ext}"
            if candidate.exists():
                frame_path = candidate
                break
        if frame_path is None:
            raise ValueError(f"Falta el frame anotado: {frame_stem}")

        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise ValueError(f"No se pudo leer el frame: {frame_path}")

        raw = detect_objects(frame, model=model, effective_conf=cfg["effective_conf"], imgsz=cfg["imgsz"],
                             use_sahi=use_sahi, sahi_model=sahi_model, sahi_predict_fn=predict_fn,
                             sahi_slice_w=cfg["sahi_slice_w"], sahi_slice_h=cfg["sahi_slice_h"],
                             sahi_overlap=cfg["sahi_overlap"], sahi_nms_threshold=cfg["sahi_nms"],
                             inference_roi=roi, device=device)
        rows, classes = filter_detections(raw, lambda name: cfg["conf_per_class"].get(name, cfg["conf_threshold"]),
                                          cfg["geo_constraints"], exclusion)
        preds = [(*map(int, row[:4]), canonical_vehicle_label(name)) for row, name in zip(rows, classes)]
        gt_dets = scoped_ground_truth(gt_dets, roi, exclusion)
        match = match_detections(preds, gt_dets, iou_threshold=iou_threshold, class_aware=True)
        localized = match_detections(preds, gt_dets, iou_threshold=iou_threshold)
        localization_tp += localized["tp"]
        localization_fp += localized["fp"]
        localization_fn += localized["fn"]
        total_count_error += abs(len(preds) - len(gt_dets))
        frames_evaluated += 1
        total_tp += match["tp"]
        total_fp += match["fp"]
        total_fn += match["fn"]
        total_pred += len(preds)
        total_gt += len(gt_dets)

        # Por clase
        for (_, gi, _) in match["matches"]:
            cls = gt_dets[gi][4]
            per_class[cls]["tp"] += 1
        # FP sin matching: preds que no aparecen en match["matches"][*][0]
        matched_preds = {pi for pi, _, _ in match["matches"]}
        for pi, pred in enumerate(preds):
            per_class[pred[4]]["pred_count"] += 1
            if pi not in matched_preds:
                per_class[pred[4]]["fp"] += 1
        # FN: gt sin matching
        matched_gts = {gi for _, gi, _ in match["matches"]}
        for gi, gt in enumerate(gt_dets):
            per_class[gt[4]]["gt_count"] += 1
            if gi not in matched_gts:
                per_class[gt[4]]["fn"] += 1

    overall = compute_metrics(total_tp, total_fp, total_fn)
    count_acc = max(0.0, 1.0 - total_count_error / max(total_gt, 1))

    print("\n" + "=" * 60)
    print(f"Resultados globales (IoU threshold={iou_threshold})")
    print("=" * 60)
    print(f"  Precision:          {overall['precision']:.4f}")
    print(f"  Recall:             {overall['recall']:.4f}")
    print(f"  F1:                 {overall['f1']:.4f}")
    print(f"  Exactitud de cajas por frame: {count_acc:.4f} (no mide aforo)")
    print(f"  TP / FP / FN:       {total_tp} / {total_fp} / {total_fn}")
    print(f"  Predicciones / GT:  {total_pred} / {total_gt}")

    print("\nPor clase:")
    print(f"  {'clase':<15} {'P':>8} {'R':>8} {'F1':>8} {'pred':>6} {'gt':>6}")
    for cls in sorted(per_class.keys()):
        stats = per_class[cls]
        m = compute_metrics(stats["tp"], stats["fp"], stats["fn"])
        print(f"  {cls:<15} {m['precision']:>8.3f} {m['recall']:>8.3f} "
              f"{m['f1']:>8.3f} {stats['pred_count']:>6} {stats['gt_count']:>6}")

    return {
        "overall": overall,
        "localization": compute_metrics(localization_tp, localization_fp, localization_fn),
        "frames_evaluated": frames_evaluated,
        "ground_truth_count": total_gt, "prediction_count": total_pred,
        "config_snapshot": config, "model_path": cfg["model_path"],
        "imgsz": cfg["imgsz"], "use_sahi": use_sahi, "human_review_confirmed": True,
        "counting_accuracy": count_acc,
        "per_class": dict(per_class),
    }



def scoped_ground_truth(detections, roi, exclusion):
    result = []
    for x1, y1, x2, y2, name in detections:
        if name.strip().lower() not in VEHICLE_CLASSES:
            continue
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if roi is not None and not (roi[0] <= cx < roi[2] and roi[1] <= cy < roi[3]):
            continue
        if not in_exclusion_zone(cx, cy, exclusion):
            result.append((x1, y1, x2, y2, canonical_vehicle_label(name)))
    return result


def main():
    parser = argparse.ArgumentParser(description="Evalua pipeline vs ground truth")
    parser.add_argument("--frames-dir", default=str(paths.data_dir / "validation" / "frames"))
    parser.add_argument("--annotations-dir", default=str(paths.data_dir / "validation" / "annotations"))
    parser.add_argument("--config", help="Perfil de ejecución con ROI, filtros y SAHI")
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-sahi", action="store_true")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output-json")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    args = parser.parse_args()

    result = evaluate(args.frames_dir, args.annotations_dir, args.model,
                      args.iou_threshold, args.conf, args.imgsz, args.config, args.no_sahi, args.device)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
