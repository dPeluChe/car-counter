"""Tests para carcounter/validation.py."""

import json
import numpy as np
import pytest

from carcounter.validation import (
    phash, hamming_distance, dedup_by_phash,
    detections_to_labelme, labelme_to_detections, load_labelme_annotations,
    iou, match_detections, compute_metrics, counting_accuracy,
)


# ──────────────────────────────────────────────────────────
# pHash
# ──────────────────────────────────────────────────────────

def _frame(val, size=100):
    return np.full((size, size, 3), val, dtype=np.uint8)


def test_phash_returns_64bit_int():
    h = phash(_frame(128))
    assert isinstance(h, int)
    assert h >= 0
    assert h.bit_length() <= 64


def test_phash_identical_frames_same_hash():
    f = _frame(100)
    assert phash(f) == phash(f.copy())


def test_phash_very_different_frames_differ():
    """Frames con estructura diferente deben tener distancia Hamming > 0."""
    rng = np.random.default_rng(42)
    f1 = rng.integers(0, 256, (100, 100, 3), dtype=np.uint8)
    rng2 = np.random.default_rng(99)
    f2 = rng2.integers(0, 256, (100, 100, 3), dtype=np.uint8)
    h1, h2 = phash(f1), phash(f2)
    assert hamming_distance(h1, h2) > 5


def test_hamming_distance_zero_for_identical():
    assert hamming_distance(0b1010, 0b1010) == 0


def test_hamming_distance_counts_differing_bits():
    assert hamming_distance(0b0000, 0b1111) == 4
    assert hamming_distance(0b1010, 0b0101) == 4


def test_dedup_by_phash_keeps_first_of_duplicates():
    hashes = [0b0000, 0b0001, 0b1111_1111]  # 0 y 1 difieren en 1 bit
    kept = dedup_by_phash(hashes, threshold=2)
    assert kept == [0, 2]


def test_dedup_by_phash_threshold_zero_exact():
    hashes = [5, 5, 7]
    kept = dedup_by_phash(hashes, threshold=0)
    assert kept == [0, 2]


def test_dedup_by_phash_empty():
    assert dedup_by_phash([]) == []


# ──────────────────────────────────────────────────────────
# LabelMe serialization
# ──────────────────────────────────────────────────────────

def test_detections_to_labelme_schema():
    dets = [(10, 20, 100, 200, "car")]
    data = detections_to_labelme(dets, "frame_000.jpg", 480, 640)
    assert data["version"] == "6.1"
    assert data["imagePath"] == "frame_000.jpg"
    assert data["imageHeight"] == 480
    assert data["imageWidth"] == 640
    assert len(data["shapes"]) == 1
    shape = data["shapes"][0]
    assert shape["label"] == "car"
    assert shape["shape_type"] == "rectangle"
    assert shape["points"] == [[10.0, 20.0], [100.0, 200.0]]


def test_detections_to_labelme_empty():
    data = detections_to_labelme([], "x.jpg", 100, 100)
    assert data["shapes"] == []


def test_labelme_to_detections_round_trip():
    dets = [(5, 10, 50, 100, "truck"), (200, 300, 400, 500, "motorcycle")]
    data = detections_to_labelme(dets, "x.jpg", 600, 800)
    back = labelme_to_detections(data)
    assert back == dets


def test_labelme_to_detections_skips_non_rectangle():
    data = {
        "shapes": [
            {"shape_type": "polygon", "points": [[0, 0], [10, 0], [5, 10]], "label": "zone"},
            {"shape_type": "rectangle", "points": [[1, 2], [3, 4]], "label": "car"},
        ]
    }
    assert labelme_to_detections(data) == [(1, 2, 3, 4, "car")]


def test_labelme_to_detections_normalizes_corner_order():
    """Si el humano dibuja de abajo-derecha a arriba-izquierda, debe normalizarse."""
    data = {"shapes": [{"shape_type": "rectangle", "points": [[100, 100], [10, 10]], "label": "car"}]}
    dets = labelme_to_detections(data)
    assert dets == [(10, 10, 100, 100, "car")]


def test_load_labelme_annotations_from_dir(tmp_path):
    data = detections_to_labelme([(1, 2, 3, 4, "car")], "frame_001.jpg", 100, 100)
    (tmp_path / "frame_001.json").write_text(json.dumps(data))
    loaded = load_labelme_annotations(tmp_path)
    assert "frame_001" in loaded
    assert loaded["frame_001"] == [(1, 2, 3, 4, "car")]


# ──────────────────────────────────────────────────────────
# IoU y matching
# ──────────────────────────────────────────────────────────

def test_iou_identical_boxes():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_iou_no_overlap():
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_iou_half_overlap():
    # box A: 100x100, box B: desplazado 50 en x
    val = iou((0, 0, 100, 100), (50, 0, 150, 100))
    # inter=50*100=5000, union=100*100 + 100*100 - 5000 = 15000
    assert abs(val - 5000 / 15000) < 0.001


def test_iou_contained_box():
    val = iou((0, 0, 100, 100), (10, 10, 90, 90))
    # inter = 80*80 = 6400, union = 10000 + 6400 - 6400 = 10000
    assert abs(val - 0.64) < 0.001


def test_match_detections_perfect():
    preds = [(0, 0, 10, 10, "car"), (50, 50, 60, 60, "car")]
    gts = [(0, 0, 10, 10, "car"), (50, 50, 60, 60, "car")]
    result = match_detections(preds, gts)
    assert result["tp"] == 2
    assert result["fp"] == 0
    assert result["fn"] == 0


def test_match_detections_false_positive():
    preds = [(0, 0, 10, 10, "car"), (200, 200, 210, 210, "car")]
    gts = [(0, 0, 10, 10, "car")]
    result = match_detections(preds, gts)
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 0


def test_match_detections_false_negative():
    preds = [(0, 0, 10, 10, "car")]
    gts = [(0, 0, 10, 10, "car"), (200, 200, 210, 210, "car")]
    result = match_detections(preds, gts)
    assert result["tp"] == 1
    assert result["fp"] == 0
    assert result["fn"] == 1


def test_match_detections_below_iou_threshold():
    preds = [(0, 0, 10, 10, "car")]
    gts = [(8, 8, 18, 18, "car")]  # IoU bajo
    result = match_detections(preds, gts, iou_threshold=0.5)
    assert result["tp"] == 0
    assert result["fp"] == 1
    assert result["fn"] == 1


def test_match_detections_greedy_picks_best_iou():
    """Cuando un GT matchea con dos preds, debe ganar el de mayor IoU."""
    preds = [
        (0, 0, 10, 10, "car"),       # IoU perfecto con gt
        (2, 2, 12, 12, "car"),       # IoU menor con gt
    ]
    gts = [(0, 0, 10, 10, "car")]
    result = match_detections(preds, gts)
    assert result["tp"] == 1
    assert result["fp"] == 1
    # La prediccion 0 debio ganar (IoU=1.0)
    assert result["matches"][0][0] == 0


# ──────────────────────────────────────────────────────────
# Metricas
# ──────────────────────────────────────────────────────────

def test_compute_metrics_perfect():
    m = compute_metrics(tp=10, fp=0, fn=0)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0


def test_compute_metrics_half():
    m = compute_metrics(tp=5, fp=5, fn=5)
    assert m["precision"] == 0.5
    assert m["recall"] == 0.5
    assert m["f1"] == 0.5


def test_compute_metrics_all_zero():
    m = compute_metrics(tp=0, fp=0, fn=0)
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0
    assert m["f1"] == 0.0


def test_counting_accuracy_exact():
    assert counting_accuracy(10, 10) == 1.0


def test_counting_accuracy_off_by_one():
    # |11-10|/10 = 0.1 → accuracy 0.9
    assert abs(counting_accuracy(11, 10) - 0.9) < 0.001


def test_counting_accuracy_zero_truth():
    assert counting_accuracy(0, 0) == 1.0
    assert counting_accuracy(5, 0) == 0.0


def test_counting_accuracy_bounded_at_zero():
    # Si predecimos 100x mas, accuracy = 0 (no negativo)
    assert counting_accuracy(1000, 10) == 0.0
