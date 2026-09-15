import cv2
import numpy as np
import pytest

from carcounter.detection_cache import cache_signature
from carcounter.video_segments import segment_by_stability
from tests.test_camera_motion import textured_frame  # noqa: F401  (fixture)


def shifted(frame, dx, dy=0):
    return cv2.warpAffine(frame, np.float32([[1, 0, dx], [0, 1, dy]]), (frame.shape[1], frame.shape[0]))


def spans(segments):
    return [(s["label"], s["start_frame"], s["end_frame"], s["reference_frame"]) for s in segments]


def test_stable_video_is_one_segment(textured_frame):
    samples = [(number, textured_frame) for number in (1, 31, 61, 91)]
    segments = segment_by_stability(samples, 120)
    assert spans(segments) == [("stable", 1, 120, 1)]
    assert segments[0]["split"] is None


def test_camera_shift_opens_segment_with_its_own_reference(textured_frame):
    moved = shifted(textured_frame, 12, -8)
    samples = [(1, textured_frame), (31, textured_frame), (61, moved), (91, moved)]
    segments = segment_by_stability(samples, 120, max_drift_px=5)
    assert spans(segments) == [("stable", 1, 60, 1), ("stable", 61, 120, 61)]
    assert segments[0]["split"]["status"] == "moved"
    assert segments[1]["max_drift_px"] < 1


def test_short_segments_merge_into_transition_without_reference(textured_frame):
    frames = [textured_frame, shifted(textured_frame, 12), shifted(textured_frame, 24),
              shifted(textured_frame, 36), shifted(textured_frame, 36)]
    samples = list(zip((1, 31, 61, 91, 121), frames))
    segments = segment_by_stability(samples, 180, max_drift_px=5, min_stable_frames=60)
    assert spans(segments) == [("transition", 1, 90, None), ("stable", 91, 180, 91)]
    assert [s["index"] for s in segments] == [1, 2]


def test_no_samples_is_an_error():
    with pytest.raises(ValueError, match="muestras"):
        segment_by_stability([], 10)


def test_cache_signature_changes_only_when_starting_later(tmp_path):
    video, model = tmp_path / "video.bin", tmp_path / "model.pt"
    video.write_bytes(b"video")
    model.write_bytes(b"model")
    cfg = dict(video_path=str(video), model_path=str(model), imgsz=640, settings={}, effective_conf=0.1)
    base = cache_signature(cfg, "yolo", False)
    assert "start_frame" not in base
    assert cache_signature(cfg, "yolo", False, start_frame=1) == base
    assert cache_signature(cfg, "yolo", False, start_frame=5395)["start_frame"] == 5395
