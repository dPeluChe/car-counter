from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from carcounter.detection import detect_and_track


def make_model():
    box = SimpleNamespace(xyxy=np.array([[10, 20, 30, 40]]), cls=np.array([2]), conf=np.array([0.9]))
    model = Mock()
    model.names = {2: "car"}
    model.return_value = [SimpleNamespace(boxes=[box])]
    return model


def echo_tracker():
    return SimpleNamespace(update_detections=Mock(side_effect=lambda frame, dets, classes: [
        (*map(int, row[:4]), 7, name) for row, name in zip(dets, classes)]))


def detect(frame, model, roi, exclusion=None, tracker="echo"):
    return detect_and_track(
        frame, model=model, sahi_model=None, sahi_predict_fn=None,
        sort_tracker=echo_tracker() if tracker == "echo" else tracker,
        use_sahi=False, effective_conf=0.1, imgsz=640, conf_for=lambda name: 0.1,
        geo_constraints={}, exclusion_np=exclusion or {},
        sahi_slice_w=256, sahi_slice_h=256, sahi_overlap=0.2, sahi_nms_threshold=0.3,
        inference_roi=roi,
    )


def test_crop_restores_global_coordinates_and_preserves_id():
    model = make_model()
    result = detect(np.zeros((200, 300, 3), np.uint8), model, [100, 50, 250, 150])
    assert model.call_args.args[0].shape == (100, 150, 3)
    assert result == [(110, 70, 130, 90, 7, "car")]


def test_crop_applies_exclusions_in_global_coordinates():
    model = make_model()
    polygon = np.array([[110, 70], [130, 70], [130, 90], [110, 90]], dtype=np.int32)
    original = polygon.copy()
    result = detect(np.zeros((200, 300, 3), np.uint8), model, [100, 50, 250, 150],
                    {"excluded": polygon})
    assert result == []
    np.testing.assert_array_equal(polygon, original)


@pytest.mark.parametrize("roi", [[0, 0, 400, 200], [100, 50, 50, 100],
                                 [-1, 0, 100, 100], [0, 0, 100], [0, 0, 100.5, 100]])
def test_invalid_crop_fails_before_inference(roi):
    model = make_model()
    with pytest.raises(ValueError, match="inference_roi"):
        detect(np.zeros((200, 300, 3), np.uint8), model, roi)
    model.assert_not_called()


def test_no_crop_preserves_full_frame_behavior():
    model = make_model()
    result = detect(np.zeros((200, 300, 3), np.uint8), model, None)
    assert model.call_args.args[0].shape == (200, 300, 3)
    assert result == [(10, 20, 30, 40, 7, "car")]


def test_missing_tracker_fails_before_inference():
    model = make_model()
    with pytest.raises(RuntimeError, match="IDs persistentes"):
        detect(np.zeros((200, 300, 3), np.uint8), model, None, tracker=None)
    model.assert_not_called()


def test_config_roundtrip_preserves_crop_and_counting_thresholds():
    from carcounter.app_config import AppConfig
    settings = {"inference_roi": [100, 50, 250, 150], "min_origin_frames": 1,
                "min_dest_frames": 2, "min_crossing_frames": 4}
    saved = AppConfig.from_dict({"settings": settings}).to_dict()["settings"]
    assert {key: saved[key] for key in settings} == settings


@pytest.mark.parametrize("settings,fragment", [
    ({"inference_roi": [10, 10, 5, 50]}, "inference_roi"),
    ({"inference_roi": [0, 0, 100]}, "inference_roi"),
    ({"camera_max_drift_px": 0}, "camera_max_drift_px"),
    ({"camera_max_drift_px": "5"}, "camera_max_drift_px"),
])
def test_profile_validation_rejects_bad_roi_and_drift(settings, fragment):
    from carcounter.app_config import AppConfig
    errors = AppConfig.from_dict({"counting_mode": "lines", "lines": [{"name": "L", "points": [[0, 0], [9, 9]]}],
                                  "settings": settings}).validate()
    assert any(fragment in error for error in errors)
