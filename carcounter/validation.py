"""Utilidades para validacion del pipeline contra anotaciones ground truth.

Tres bloques de logica pura (testables sin GPU/video):
  1. Perceptual hashing (pHash DCT 64-bit) para dedup de frames
  2. Serializacion LabelMe JSON
  3. Matching detecciones vs ground truth + metricas precision/recall/F1
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


# ══════════════════════════════════════════════════════════
# 1. Perceptual hashing (DCT pHash)
# ══════════════════════════════════════════════════════════

def phash(frame_bgr: np.ndarray, hash_size: int = 8) -> int:
    """Genera un hash perceptual DCT de 64 bits para un frame BGR.

    Algoritmo pHash clasico:
      1. Grayscale + resize 32x32
      2. DCT 2D
      3. Tomar las hash_size x hash_size componentes de baja frecuencia (excluyendo DC)
      4. Binarizar contra la mediana
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(resized)
    low_freq = dct[:hash_size, :hash_size]
    # Excluir componente DC (0,0) del calculo de mediana
    values = low_freq.flatten()[1:]
    median = np.median(values)
    bits = (low_freq.flatten() > median).astype(np.uint64)
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return int(h)


def hamming_distance(h1: int, h2: int) -> int:
    """Distancia de Hamming entre dos hashes (cuenta bits diferentes)."""
    return bin(h1 ^ h2).count("1")


def dedup_by_phash(hashes: list[int], threshold: int = 5) -> list[int]:
    """Devuelve indices de hashes unicos (primero gana).

    Args:
        hashes: lista de hashes pHash
        threshold: distancia Hamming maxima para considerar duplicados (default 5)

    Returns:
        Indices (0-based) de los hashes a conservar.
    """
    keep: list[int] = []
    kept_hashes: list[int] = []
    for i, h in enumerate(hashes):
        is_dup = any(hamming_distance(h, kh) <= threshold for kh in kept_hashes)
        if not is_dup:
            keep.append(i)
            kept_hashes.append(h)
    return keep


# ══════════════════════════════════════════════════════════
# 2. LabelMe JSON serialization
# ══════════════════════════════════════════════════════════

def detections_to_labelme(
    detections: Iterable[tuple[int, int, int, int, str]],
    image_path: str,
    image_height: int,
    image_width: int,
) -> dict:
    """Convierte detecciones (x1,y1,x2,y2,label) a formato LabelMe JSON.

    Formato compatible con LabelMe v6.x (https://labelme.io).
    """
    shapes = []
    for x1, y1, x2, y2, label in detections:
        shapes.append({
            "label": label,
            "points": [[float(x1), float(y1)], [float(x2), float(y2)]],
            "group_id": None,
            "shape_type": "rectangle",
            "flags": {},
        })
    return {
        "version": "6.1",
        "flags": {},
        "shapes": shapes,
        "imagePath": image_path,
        "imageData": None,
        "imageHeight": image_height,
        "imageWidth": image_width,
    }


def labelme_to_detections(labelme_json: dict) -> list[tuple[int, int, int, int, str]]:
    """Extrae detecciones (x1,y1,x2,y2,label) de un JSON LabelMe."""
    out = []
    for shape in labelme_json.get("shapes", []):
        if shape.get("shape_type") != "rectangle":
            continue
        pts = shape.get("points", [])
        if len(pts) < 2:
            continue
        (x1, y1), (x2, y2) = pts[0], pts[1]
        # Normalizar: (x1,y1) esquina superior-izquierda
        xmin, xmax = sorted([x1, x2])
        ymin, ymax = sorted([y1, y2])
        out.append((int(xmin), int(ymin), int(xmax), int(ymax), shape.get("label", "")))
    return out


def load_labelme_annotations(annotations_dir: str | Path, require_reviewed=False) -> dict[str, list[tuple]]:
    """Carga anotaciones LabelMe de un directorio.

    Returns:
        dict[frame_basename -> list[(x1,y1,x2,y2,label)]]
    """
    annotations_dir = Path(annotations_dir)
    out: dict[str, list[tuple]] = {}
    for json_file in annotations_dir.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if require_reviewed and data.get("flags", {}).get("reviewed") is not True:
            raise ValueError(f"Anotación sin revisión humana confirmada: {json_file.name}; marca flags.reviewed=true después de revisar")
        image_name = data.get("imagePath", json_file.stem)
        stem = Path(image_name).stem
        if stem in out:
            raise ValueError(f"Anotaciones duplicadas para el frame {stem}")
        out[stem] = labelme_to_detections(data)
    return out


# ══════════════════════════════════════════════════════════
# 3. IoU matching + metricas
# ══════════════════════════════════════════════════════════

def iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    """Intersection over Union entre dos boxes (x1,y1,x2,y2)."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def match_detections(
    predictions: list[tuple[int, int, int, int, str]],
    ground_truth: list[tuple[int, int, int, int, str]],
    iou_threshold: float = 0.5,
    class_aware: bool = False,
) -> dict:
    """Matchea predicciones contra ground truth con greedy IoU.

    Returns:
        dict con tp, fp, fn, matches (lista de pares (pred_idx, gt_idx, iou)).
    """
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold debe estar entre 0 y 1")
    matches = []
    matched_gt = set()
    matched_pred = set()

    # Greedy: mayor IoU primero
    candidates = []
    for pi, pred in enumerate(predictions):
        for gi, gt in enumerate(ground_truth):
            if class_aware and canonical_vehicle_label(pred[4]) != canonical_vehicle_label(gt[4]):
                continue
            iou_val = iou(pred[:4], gt[:4])
            if iou_val >= iou_threshold:
                candidates.append((iou_val, pi, gi))
    candidates.sort(reverse=True)

    for iou_val, pi, gi in candidates:
        if pi in matched_pred or gi in matched_gt:
            continue
        matched_pred.add(pi)
        matched_gt.add(gi)
        matches.append((pi, gi, iou_val))

    tp = len(matches)
    fp = len(predictions) - tp
    fn = len(ground_truth) - tp
    return {"tp": tp, "fp": fp, "fn": fn, "matches": matches}


def compute_metrics(tp: int, fp: int, fn: int) -> dict:
    """Calcula precision, recall, F1."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn,
    }


def counting_accuracy(predicted_count: int, truth_count: int) -> float:
    """Counting accuracy = 1 - |pred - truth| / max(truth, 1)."""
    if truth_count == 0:
        return 1.0 if predicted_count == 0 else 0.0
    return max(0.0, 1.0 - abs(predicted_count - truth_count) / truth_count)


def canonical_vehicle_label(label):
    label = label.strip().lower()
    return "motorcycle" if label in {"motor", "motorbike", "motorcycle"} else label
