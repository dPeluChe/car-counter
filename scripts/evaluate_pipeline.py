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
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from carcounter.paths import paths
from carcounter.constants import COCO_NAMES, VEHICLE_CLASSES, VEHICLE_CLASS_IDS
from carcounter.validation import (
    load_labelme_annotations,
    match_detections,
    compute_metrics,
    counting_accuracy,
)


def evaluate(frames_dir, annotations_dir, model_path, iou_threshold=0.5,
             conf_threshold=0.1, imgsz=1280):
    """Corre el pipeline sobre frames con ground truth y calcula metricas."""
    frames_dir = Path(frames_dir)
    annotations_dir = Path(annotations_dir)

    gt_by_frame = load_labelme_annotations(annotations_dir)
    if not gt_by_frame:
        print(f"ERROR: No hay anotaciones en {annotations_dir}")
        sys.exit(1)

    print(f"Cargadas anotaciones de {len(gt_by_frame)} frames")

    from ultralytics import YOLO
    model = YOLO(str(model_path))

    # Acumuladores globales y por clase
    total_tp = total_fp = total_fn = 0
    per_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0,
                                      "pred_count": 0, "gt_count": 0})

    total_pred = total_gt = 0

    for frame_stem, gt_dets in gt_by_frame.items():
        frame_path = None
        for ext in (".jpg", ".png", ".JPG", ".PNG"):
            candidate = frames_dir / f"{frame_stem}{ext}"
            if candidate.exists():
                frame_path = candidate
                break
        if frame_path is None:
            print(f"  skip {frame_stem} (no se encontro frame)")
            continue

        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue

        results = model(frame, conf=conf_threshold, imgsz=imgsz,
                        classes=VEHICLE_CLASS_IDS, verbose=False)
        preds = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else ""
                if cls_name in VEHICLE_CLASSES:
                    preds.append((x1, y1, x2, y2, cls_name))

        match = match_detections(preds, gt_dets, iou_threshold=iou_threshold)
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
    count_acc = counting_accuracy(total_pred, total_gt)

    print("\n" + "=" * 60)
    print(f"Resultados globales (IoU threshold={iou_threshold})")
    print("=" * 60)
    print(f"  Precision:          {overall['precision']:.4f}")
    print(f"  Recall:             {overall['recall']:.4f}")
    print(f"  F1:                 {overall['f1']:.4f}")
    print(f"  Counting accuracy:  {count_acc:.4f}")
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
        "counting_accuracy": count_acc,
        "per_class": dict(per_class),
    }


def main():
    parser = argparse.ArgumentParser(description="Evalua pipeline vs ground truth")
    parser.add_argument("--frames-dir", default=str(paths.data_dir / "validation" / "frames"))
    parser.add_argument("--annotations-dir", default=str(paths.data_dir / "validation" / "annotations"))
    parser.add_argument("--model", default=str(paths.default_model))
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--conf", type=float, default=0.1)
    parser.add_argument("--imgsz", type=int, default=1280)
    args = parser.parse_args()

    evaluate(args.frames_dir, args.annotations_dir, args.model,
             args.iou_threshold, args.conf, args.imgsz)


if __name__ == "__main__":
    main()
