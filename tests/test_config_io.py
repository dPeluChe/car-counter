"""Tests para carcounter/config_io.py"""

import json
import os
import tempfile
import pytest
from carcounter.config_io import (
    load_config,
    save_config,
    build_config,
    parse_exclusion_zones,
    parse_zones,
    parse_lines,
    parse_settings,
)


# ── load_config / save_config round-trip ──────

class TestLoadSave:
    """Tests para lectura y escritura de config."""

    def test_round_trip(self, tmp_path):
        config = {"counting_mode": "zones", "zones": {"A": [[0, 0], [100, 0]]}}
        path = str(tmp_path / "config.json")
        save_config(path, config)
        loaded = load_config(path)
        assert loaded == config

    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "config.json")
        save_config(path, {"test": True})
        assert os.path.isfile(path)

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")

    def test_unicode_round_trip(self, tmp_path):
        config = {"zones": {"Norte": [[0, 0]], "Sur": [[1, 1]]}}
        path = str(tmp_path / "config.json")
        save_config(path, config)
        loaded = load_config(path)
        assert "Norte" in loaded["zones"]


# ── parse_exclusion_zones ─────────────────────

class TestParseExclusionZones:
    def test_empty(self):
        assert parse_exclusion_zones({}) == {}

    def test_parses_zones(self):
        cfg = {"exclusion_zones": {"park": [[0, 0], [10, 0], [10, 10]]}}
        result = parse_exclusion_zones(cfg)
        assert "park" in result
        assert result["park"] == [[0, 0], [10, 0], [10, 10]]

    def test_converts_tuples_to_lists(self):
        cfg = {"exclusion_zones": {"park": [(0, 0), (10, 0)]}}
        result = parse_exclusion_zones(cfg)
        assert result["park"] == [[0, 0], [10, 0]]


# ── parse_zones ───────────────────────────────

class TestParseZones:
    def test_empty(self):
        assert parse_zones({}) == {}

    def test_parses(self):
        cfg = {"zones": {"A": [[0, 0], [50, 0], [50, 50]]}}
        result = parse_zones(cfg)
        assert result["A"] == [[0, 0], [50, 0], [50, 50]]


# ── parse_lines ───────────────────────────────

class TestParseLines:
    def test_empty(self):
        assert parse_lines({}) == {}

    def test_parses(self):
        cfg = {"lines": [{"name": "L1", "points": [[0, 50], [100, 50]]}]}
        result = parse_lines(cfg)
        assert "L1" in result
        assert result["L1"] == [[0, 50], [100, 50]]

    def test_skips_incomplete(self):
        cfg = {"lines": [{"name": "L1", "points": [[0, 50]]}]}  # only 1 point
        result = parse_lines(cfg)
        assert len(result) == 0

    def test_auto_names(self):
        cfg = {"lines": [{"points": [[0, 50], [100, 50]]}]}
        result = parse_lines(cfg)
        assert len(result) == 1


# ── parse_settings ────────────────────────────

class TestParseSettings:
    def test_empty(self):
        result = parse_settings({})
        assert result["conf_threshold"] is None
        assert result["sample_constraints"] is None

    def test_extracts_all_fields(self):
        cfg = {
            "settings": {
                "conf_threshold": 0.15,
                "imgsz": 1280,
                "min_area": 100,
                "max_area": 5000,
                "conf_per_class": {"car": 0.1, "bus": 0.2},
                "sample_constraints": {"min_width": 10, "max_width": 200},
            },
            "sahi": {"slice_width": 256, "slice_height": 256,
                     "overlap_ratio": 0.3, "nms_threshold": 0.25},
            "tracker": {"max_age": 30, "min_hits": 2, "iou_threshold": 0.3},
        }
        r = parse_settings(cfg)
        assert r["conf_threshold"] == 0.15
        assert r["imgsz"] == 1280
        assert r["slice_width"] == 256
        assert r["max_age"] == 30
        assert r["conf_per_class"]["car"] == 0.1


# ── build_config ──────────────────────────────

class TestBuildConfig:
    def test_minimal(self):
        config = build_config(
            counting_mode="zones",
            exclusion_zones={},
            zones={"A": [[0, 0]], "B": [[100, 100]]},
            counting_lines={},
            min_area=0, max_area=999999,
            conf_threshold=0.10, imgsz=1600,
            sample_constraints=None, sample_count=0,
            conf_per_class={"car": 0.1, "motorbike": 0.1, "bus": 0.1, "truck": 0.1},
            conf_per_class_modified=False,
            slice_w=512, slice_h=512, overlap=0.2, nms_threshold=0.3,
            max_age=40, min_hits=3, iou_threshold=0.2,
            video_path="video.mp4", model_path="model.pt",
        )
        assert config["counting_mode"] == "zones"
        assert "conf_per_class" not in config["settings"]  # not modified
        assert config["sahi"]["slice_width"] == 512

    def test_conf_per_class_included_when_modified(self):
        config = build_config(
            counting_mode="zones",
            exclusion_zones={},
            zones={"A": [[0, 0]]},
            counting_lines={},
            min_area=0, max_area=999999,
            conf_threshold=0.10, imgsz=1600,
            sample_constraints=None, sample_count=0,
            conf_per_class={"car": 0.15, "motorbike": 0.2, "bus": 0.1, "truck": 0.1},
            conf_per_class_modified=True,
            slice_w=512, slice_h=512, overlap=0.2, nms_threshold=0.3,
            max_age=40, min_hits=3, iou_threshold=0.2,
            video_path="video.mp4", model_path="model.pt",
        )
        assert "conf_per_class" in config["settings"]
        assert config["settings"]["conf_per_class"]["car"] == 0.15

    def test_preserves_loaded_config_fields(self):
        loaded = {"settings": {"custom_field": "preserved"}}
        config = build_config(
            counting_mode="zones",
            exclusion_zones={},
            zones={"A": [[0, 0]]},
            counting_lines={},
            min_area=0, max_area=999999,
            conf_threshold=0.10, imgsz=1600,
            sample_constraints=None, sample_count=0,
            conf_per_class={"car": 0.1, "motorbike": 0.1, "bus": 0.1, "truck": 0.1},
            conf_per_class_modified=False,
            slice_w=512, slice_h=512, overlap=0.2, nms_threshold=0.3,
            max_age=40, min_hits=3, iou_threshold=0.2,
            video_path="video.mp4", model_path="model.pt",
            loaded_config=loaded,
        )
        assert config["settings"]["custom_field"] == "preserved"

    def test_full_round_trip(self, tmp_path):
        """build -> save -> load -> parse produce los mismos valores."""
        config = build_config(
            counting_mode="zones",
            exclusion_zones={"park": [[0, 0], [10, 0], [10, 10]]},
            zones={"A": [[0, 0], [50, 0], [50, 50]], "B": [[100, 100], [150, 100], [150, 150]]},
            counting_lines={"L1": [[0, 50], [100, 50]]},
            min_area=100, max_area=5000,
            conf_threshold=0.15, imgsz=1280,
            sample_constraints={"min_width": 10, "max_width": 200,
                                "min_height": 10, "max_height": 200,
                                "min_area": 100, "max_area": 5000,
                                "min_aspect": 0.5, "max_aspect": 3.0},
            sample_count=5,
            conf_per_class={"car": 0.1, "motorbike": 0.2, "bus": 0.15, "truck": 0.1},
            conf_per_class_modified=True,
            slice_w=256, slice_h=256, overlap=0.3, nms_threshold=0.25,
            max_age=30, min_hits=2, iou_threshold=0.3,
            video_path="test.mp4", model_path="yolo.pt",
        )
        path = str(tmp_path / "config.json")
        save_config(path, config)
        loaded = load_config(path)

        assert loaded["counting_mode"] == "zones"
        zones = parse_zones(loaded)
        assert "A" in zones and "B" in zones
        excl = parse_exclusion_zones(loaded)
        assert "park" in excl
        settings = parse_settings(loaded)
        assert settings["conf_threshold"] == 0.15
        assert settings["conf_per_class"]["motorbike"] == 0.2
        assert settings["slice_width"] == 256
