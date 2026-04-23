#!/usr/bin/env python3
"""Pre-etiqueta frames con YOLO teacher model y exporta a formato LabelMe JSON.

El humano despues abre los JSONs en LabelMe (https://labelme.io) y solo
corrige los errores del teacher. Mucho mas rapido que anotar desde cero.

Uso:
  python scripts/pre_label_frames.py \
      --frames-dir data/validation/frames \
      --output-dir data/validation/annotations \
      --model models/yolo/yolov11l.pt \
      --conf 0.25
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from carcounter.paths import paths
from carcounter.constants import COCO_NAMES, VEHICLE_CLASSES, VEHICLE_CLASS_IDS
from carcounter.validation import detections_to_labelme


def pre_label(frames_dir, output_dir, model_path, conf_threshold=0.25, imgsz=1280):
    """Corre YOLO sobre cada frame y guarda anotaciones LabelMe."""
    frames_dir = Path(frames_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO
    model = YOLO(str(model_path))

    frame_files = sorted(frames_dir.glob("*.jpg")) + sorted(frames_dir.glob("*.png"))
    if not frame_files:
        print(f"ERROR: No hay frames en {frames_dir}")
        sys.exit(1)

    print(f"Pre-etiquetando {len(frame_files)} frames con {model_path}...")
    total_detections = 0

    for frame_path in frame_files:
        frame = cv2.imread(str(frame_path))
        if frame is None:
            print(f"  skip {frame_path.name} (no se pudo leer)")
            continue
        h, w = frame.shape[:2]

        results = model(frame, conf=conf_threshold, imgsz=imgsz,
                        classes=VEHICLE_CLASS_IDS, verbose=False)

        dets = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else ""
                if cls_name in VEHICLE_CLASSES:
                    dets.append((x1, y1, x2, y2, cls_name))

        labelme_data = detections_to_labelme(dets, frame_path.name, h, w)
        out_path = output_dir / f"{frame_path.stem}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(labelme_data, f, indent=2)

        total_detections += len(dets)

    print(f"Anotaciones guardadas en: {output_dir}")
    print(f"Total detecciones pre-etiquetadas: {total_detections}")
    print(f"\nSiguiente paso: abrir {output_dir} con LabelMe y corregir errores del teacher.")


def main():
    parser = argparse.ArgumentParser(description="Pre-etiqueta frames con YOLO teacher")
    parser.add_argument("--frames-dir", default=str(paths.data_dir / "validation" / "frames"))
    parser.add_argument("--output-dir", default=str(paths.data_dir / "validation" / "annotations"))
    parser.add_argument("--model", default=str(paths.default_model))
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Umbral de confianza (mas bajo = mas pre-anotaciones, default: 0.25)")
    parser.add_argument("--imgsz", type=int, default=1280)
    args = parser.parse_args()

    pre_label(args.frames_dir, args.output_dir, args.model, args.conf, args.imgsz)


if __name__ == "__main__":
    main()
