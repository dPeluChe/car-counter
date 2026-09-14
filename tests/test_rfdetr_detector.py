"""Tests para carcounter/rfdetr_detector.py: nombres de clase según el checkpoint."""

import types

import numpy as np
import pytest

pytest.importorskip("rfdetr")
sv = pytest.importorskip("supervision")

from carcounter.rfdetr_detector import rfdetr_detect


def _model(class_ids, class_names=None):
    n = len(class_ids)
    dets = sv.Detections(
        xyxy=np.array([[i, i, i + 10, i + 10] for i in range(n)], dtype=np.float32),
        confidence=np.full(n, 0.9, dtype=np.float32),
        class_id=np.array(class_ids),
    )
    return types.SimpleNamespace(
        predict=lambda image, threshold: dets,
        model=types.SimpleNamespace(class_names=class_names),
    )


FRAME = np.zeros((32, 32, 3), dtype=np.uint8)


def test_coco_checkpoint_uses_raw_category_ids():
    # COCO: 1 person, 2 bicycle, 3 car, 4 motorcycle, 6 bus, 8 truck
    detections, classes = rfdetr_detect(_model([3, 6, 8, 4, 2, 1]), FRAME)
    assert classes == ["car", "bus", "truck", "motorcycle"]
    assert len(detections) == 4


def test_custom_checkpoint_uses_zero_based_names():
    detections, classes = rfdetr_detect(_model([0, 2, 1], ["Car", "person", "van"]), FRAME)
    assert classes == ["car", "van"]
    assert detections.shape == (2, 5)


def test_unknown_ids_are_dropped():
    detections, classes = rfdetr_detect(_model([999]), FRAME)
    assert classes == [] and detections.shape == (0, 5)
