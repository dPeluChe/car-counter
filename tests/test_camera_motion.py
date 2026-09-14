import cv2
import numpy as np
import pytest

from carcounter.camera_motion import CameraMotionMonitor


@pytest.fixture
def textured_frame():
    rng = np.random.default_rng(12)
    image = np.zeros((480, 640, 3), np.uint8)
    for _ in range(900):
        x, y = rng.integers([0, 0], [640, 480])
        color = tuple(map(int, rng.integers(30, 255, 3)))
        cv2.circle(image, (int(x), int(y)), int(rng.integers(2, 9)), color, -1)
    return image


def test_static_frame_is_stable(textured_frame):
    result = CameraMotionMonitor(textured_frame).check(textured_frame.copy())
    assert result["status"] == "stable"
    assert result["max_drift_px"] < 0.01


def test_translation_is_measured_in_original_pixels(textured_frame):
    moved = cv2.warpAffine(textured_frame, np.float32([[1, 0, 12], [0, 1, -8]]), (640, 480))
    monitor = CameraMotionMonitor(textured_frame, image_width=320, max_drift_px=5)
    result = monitor.check(moved)
    assert result["status"] == "moved"
    assert result["max_drift_px"] == pytest.approx(np.hypot(12, 8), abs=1.5)
    assert result["transform"][0][2] == pytest.approx(12, abs=1.5)


def test_rotation_checks_counting_anchors(textured_frame):
    matrix = cv2.getRotationMatrix2D((320, 240), 3, 1)
    moved = cv2.warpAffine(textured_frame, matrix, (640, 480))
    anchors = [[50, 50], [590, 430]]
    result = CameraMotionMonitor(textured_frame, anchors=anchors).check(moved)
    expected = np.linalg.norm(cv2.transform(np.float32([anchors]), matrix)[0] - anchors, axis=1).max()
    assert result["status"] == "moved"
    assert result["max_drift_px"] == pytest.approx(expected, abs=1.5)


def test_moving_vehicle_region_does_not_move_static_background(textured_frame):
    roi = [200, 100, 440, 380]
    moved = textured_frame.copy()
    moved[100:380, 200:440] = 255
    result = CameraMotionMonitor(textured_frame, inference_roi=roi).check(moved)
    assert result["status"] == "stable"
    assert result["max_drift_px"] < 0.5


def test_blank_or_changed_scene_is_unreliable(textured_frame):
    blank = np.zeros_like(textured_frame)
    assert CameraMotionMonitor(blank).check(blank)["status"] == "unreliable"
    assert CameraMotionMonitor(textured_frame).check(blank)["status"] == "unreliable"
    assert CameraMotionMonitor(textured_frame).check(blank[:100])["status"] == "unreliable"


@pytest.mark.parametrize("threshold", [0, -1, float("nan"), float("inf")])
def test_invalid_threshold_rejected(textured_frame, threshold):
    with pytest.raises(ValueError):
        CameraMotionMonitor(textured_frame, max_drift_px=threshold)
