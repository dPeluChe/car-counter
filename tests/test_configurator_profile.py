import time

from carcounter import autosave
from carcounter.config_io import build_config, parse_directions, parse_settings
from setup_panels.geometry_checks import elements_outside_roi, inference_roi


def _config(directions, sample_constraints):
    return build_config(
        counting_mode="directions", exclusion_zones={}, zones={}, counting_lines={},
        directions=directions, min_area=120, max_area=4000, conf_threshold=0.2, imgsz=1600,
        sample_constraints=sample_constraints, sample_count=6, conf_per_class={}, conf_per_class_modified=False,
        slice_w=512, slice_h=512, overlap=0.2, nms_threshold=0.5, max_age=30, min_hits=3, iou_threshold=0.3,
        video_path="video.mp4", model_path="model.pt", loaded_config=None)


def test_round_trip_keeps_directions_and_sample_filters():
    constraints = dict(min_width=10, max_width=40, min_height=8, max_height=30,
                       min_area=120, max_area=4000, min_aspect=0.5, max_aspect=2.5)
    directions = {"Norte": [[10, 20], [30, 5]], "Sur": [[1, 2], [3, 4]]}
    config = _config(directions, constraints)

    assert parse_directions(config) == directions
    parsed = parse_settings(config)
    assert parsed["sample_constraints"] == constraints
    assert (parsed["min_area"], parsed["max_area"]) == (120, 4000)


def test_parse_directions_skips_incomplete_vectors():
    assert parse_directions({"directions": {"A": [[1, 1]], "B": [[1, 1], [2, 2]]}}) == {"B": [[1, 1], [2, 2]]}
    assert parse_directions({}) == {}


def test_checkpoint_is_per_profile_and_checks_video(tmp_path, monkeypatch):
    monkeypatch.setattr(autosave, "AUTOSAVE_DIR", tmp_path)
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    assert autosave.checkpoint_path(first) != autosave.checkpoint_path(second)
    assert autosave.checkpoint_path(first) == autosave.checkpoint_path(str(first))

    autosave.save_checkpoint(first, {"video_path": "v1.mp4", "zones": {}})
    assert autosave.usable_checkpoint(first, "v1.mp4")["video_path"] == "v1.mp4"
    assert autosave.usable_checkpoint(first, "otro.mp4") is None
    assert autosave.usable_checkpoint(second, "v1.mp4") is None

    expired = time.time() + autosave.CHECKPOINT_TTL_S + 60
    monkeypatch.setattr(autosave.time, "time", lambda: expired)
    assert autosave.usable_checkpoint(first, "v1.mp4") is None
    autosave.clear_checkpoint(first)
    assert not autosave.checkpoint_path(first).exists()


def test_elements_outside_roi():
    roi = [100, 100, 500, 400]
    zones = {"Dentro": [[100, 100], [500, 400], [300, 200]], "Fuera": [[90, 150], [200, 200], [300, 300]]}
    lines = {"L1": [[150, 150], [600, 200]]}
    assert elements_outside_roi(roi, zones, lines) == ["zona Fuera", "línea L1"]
    assert elements_outside_roi(None, zones, lines) == []
    assert inference_roi({"settings": {"inference_roi": roi}}) == roi
    assert inference_roi(None) is None
