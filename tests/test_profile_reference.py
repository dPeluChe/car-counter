import shutil

import cv2
import numpy as np
import pytest

from carcounter.profile_reference import (
    make_geometry_reference, reference_errors, validate_profile_video,
)


def video(path, value=0):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
    assert writer.isOpened()
    for offset in (0, 40, 80):
        writer.write(np.full((24, 32, 3), value + offset, dtype=np.uint8))
    writer.release()
    return path


def test_reference_selects_frame_and_accepts_renamed_copy(tmp_path):
    source = video(tmp_path / "source.avi")
    reference = make_geometry_reference(source, 2)
    copy = tmp_path / "copy.avi"
    shutil.copyfile(source, copy)
    frame = validate_profile_video({"geometry_reference": reference}, copy)
    assert reference["frame_index"] == 2
    assert frame.shape == (24, 32, 3)
    assert abs(float(frame.mean()) - 40) < 3


def test_same_resolution_different_content_rejected(tmp_path):
    source = video(tmp_path / "source.avi")
    other = video(tmp_path / "other.avi", 10)
    reference = make_geometry_reference(source, 1)
    with pytest.raises(ValueError, match="no coincide"):
        validate_profile_video({"geometry_reference": reference}, other)


def test_legacy_profile_does_not_accept_another_video(tmp_path):
    source = video(tmp_path / "source.avi")
    other = video(tmp_path / "other.avi", 10)
    assert validate_profile_video({"video_path": str(source)}, source) is None
    with pytest.raises(ValueError, match="Perfil sin referencia"):
        validate_profile_video({"video_path": str(source)}, other)


@pytest.mark.parametrize("field,value", [
    ("frame_index", 0), ("frame_index", True), ("frame_index", 1.5),
    ("width", -1), ("height", None), ("video_sha256", "invalid"),
])
def test_invalid_reference_fields(field, value):
    reference = dict(frame_index=1, width=32, height=24, video_sha256="a" * 64)
    reference[field] = value
    assert reference_errors(reference)


def test_invalid_frame_and_resolution_rejected(tmp_path):
    source = video(tmp_path / "source.avi")
    with pytest.raises(ValueError, match="fuera"):
        make_geometry_reference(source, 4)
    reference = make_geometry_reference(source, 1)
    reference["width"] = 64
    with pytest.raises(ValueError, match="resolución"):
        validate_profile_video({"geometry_reference": reference}, source)
