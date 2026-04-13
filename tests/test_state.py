"""Tests para carcounter/state.py — Dataclasses de estado."""

import pytest
from carcounter.state import (
    TrackState, ShapeMetrics, VehicleSample,
    ExclusionState, CalibrationState, ZonesState,
    SAHIState, TrackerState,
)


class TestTrackState:
    def test_defaults(self):
        ts = TrackState()
        assert ts.state == "new"
        assert ts.origin is None
        assert ts.cls_name == "car"
        assert ts.zone_frames == 0

    def test_custom_values(self):
        ts = TrackState(state="done", origin="A", cls_name="truck")
        assert ts.state == "done"
        assert ts.origin == "A"
        assert ts.cls_name == "truck"


class TestShapeMetrics:
    def test_first_update(self):
        m = ShapeMetrics()
        m.update(100, 50)
        assert m.avg_width == 100.0
        assert m.avg_height == 50.0
        assert m.avg_area == 5000.0
        assert m.samples == 1

    def test_ema_update(self):
        m = ShapeMetrics()
        m.update(100, 50)
        m.update(100, 50)
        assert abs(m.avg_width - 100.0) < 0.1
        assert m.samples == 2

    def test_to_dict(self):
        m = ShapeMetrics()
        m.update(80, 40)
        d = m.to_dict()
        assert "avg_width" in d
        assert "avg_height" in d
        assert "avg_area" in d
        assert d["samples"] == 1

    def test_elongation(self):
        m = ShapeMetrics()
        m.update(200, 50)
        assert m.avg_elongation == 4.0


class TestVehicleSample:
    def test_defaults(self):
        s = VehicleSample()
        assert s.bbox == (0, 0, 0, 0)
        assert s.width == 0

    def test_custom(self):
        s = VehicleSample(bbox=(10, 20, 50, 60), width=40, height=40, area=1600, aspect=1.0)
        assert s.area == 1600


class TestExclusionState:
    def test_defaults(self):
        s = ExclusionState()
        assert s.zones == {}
        assert not s.drawing
        assert s.zone_name == "Exclusion 1"


class TestCalibrationState:
    def test_defaults(self):
        s = CalibrationState()
        assert s.rect_start is None
        assert not s.confirmed
        assert s.conf_threshold == 0.10


class TestZonesState:
    def test_defaults(self):
        s = ZonesState()
        assert s.zones == {}
        assert not s.drawing
        assert s.counting_mode == "zones"


class TestSAHIState:
    def test_defaults(self):
        s = SAHIState()
        assert s.slice_w == 512
        assert s.tile_grid_visible is True


class TestTrackerState:
    def test_defaults(self):
        s = TrackerState()
        assert s.max_age == 40
        assert s.min_hits == 3
