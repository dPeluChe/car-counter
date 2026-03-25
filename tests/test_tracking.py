"""Tests para carcounter/tracking.py"""

import numpy as np
import pytest
from carcounter.tracking import attach_classes_to_tracks


class TestAttachClassesToTracks:
    """Tests para attach_classes_to_tracks (IoU matching)."""

    def test_perfect_match(self):
        tracks = np.array([[10, 10, 50, 50, 1]])
        dets = np.array([[10, 10, 50, 50, 0.9]])
        classes = ["car"]
        result = attach_classes_to_tracks(tracks, dets, classes)
        assert len(result) == 1
        assert result[0] == (10, 10, 50, 50, 1, "car")

    def test_best_iou_wins(self):
        tracks = np.array([[10, 10, 50, 50, 1]])
        dets = np.array([
            [0, 0, 20, 20, 0.9],     # partial overlap
            [10, 10, 50, 50, 0.8],   # perfect overlap
        ])
        classes = ["truck", "car"]
        result = attach_classes_to_tracks(tracks, dets, classes)
        assert result[0][5] == "car"  # best IoU match

    def test_no_detections_defaults_car(self):
        tracks = np.array([[10, 10, 50, 50, 1]])
        dets = np.array([]).reshape(0, 5)
        classes = []
        result = attach_classes_to_tracks(tracks, dets, classes)
        assert result[0][5] == "car"  # default fallback

    def test_multiple_tracks(self):
        tracks = np.array([
            [0, 0, 40, 40, 1],
            [100, 100, 140, 140, 2],
        ])
        dets = np.array([
            [0, 0, 40, 40, 0.9],
            [100, 100, 140, 140, 0.8],
        ])
        classes = ["truck", "bus"]
        result = attach_classes_to_tracks(tracks, dets, classes)
        assert result[0][5] == "truck"
        assert result[1][5] == "bus"

    def test_preserves_track_id(self):
        tracks = np.array([[10, 10, 50, 50, 42]])
        dets = np.array([[10, 10, 50, 50, 0.9]])
        classes = ["motorbike"]
        result = attach_classes_to_tracks(tracks, dets, classes)
        assert result[0][4] == 42
        assert result[0][5] == "motorbike"
