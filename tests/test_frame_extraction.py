import json
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from carcounter.detection_cache import file_digest
from carcounter.validation import load_labelme_annotations
from scripts.extract_validation_frames import extract_frames


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "source.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
    assert writer.isOpened()
    for index in range(7):
        writer.write(np.full((64, 64, 3), 20 + index * 25, np.uint8))
    writer.release()
    return path


def test_temporal_sampling_preserves_provenance_and_annotation_directory(video, tmp_path):
    output = tmp_path / "dataset"
    assert extract_frames(video, output, n_candidates=3) == 3
    manifest = json.loads((output / "metadata/manifest.json").read_text())
    assert manifest["video_sha256"] == file_digest(video)
    assert manifest["video_name"] == video.name
    assert manifest["fps"] == 10
    assert manifest["reviewed"] is False
    assert manifest["hash_threshold"] is None
    assert [row["frame_index"] for row in manifest["frames"]] == [1, 4, 7]
    assert [row["timestamp_seconds"] for row in manifest["frames"]] == [0, 0.3, 0.6]
    for row, expected in zip(manifest["frames"], [20, 95, 170]):
        assert abs(cv2.imread(str(output / row["image"])).mean() - expected) < 5
    assert load_labelme_annotations(output, require_reviewed=True) == {}
    assert str(tmp_path) not in (output / "metadata/manifest.json").read_text()


@pytest.mark.parametrize("requested,expected", [(1, 1), (20, 7)])
def test_sample_count_is_bounded_by_video(video, tmp_path, requested, expected):
    assert extract_frames(video, tmp_path / "frames", requested) == expected


def test_phash_deduplication_requires_explicit_opt_in(video, tmp_path):
    assert extract_frames(video, tmp_path / "all", 7) == 7
    assert extract_frames(video, tmp_path / "dedup", 7, hash_threshold=5) == 1


@pytest.mark.parametrize("name", ["frame_00000001.jpg", "frame_00000001.json"])
def test_existing_images_and_annotations_are_never_overwritten(video, tmp_path, name):
    output = tmp_path / "frames"
    output.mkdir()
    existing = output / name
    existing.write_bytes(b"human data")
    with pytest.raises(FileExistsError, match="sobrescriben"):
        extract_frames(video, output, 3)
    assert existing.read_bytes() == b"human data"
    assert list(output.iterdir()) == [existing]


@pytest.mark.parametrize("count,threshold", [(0, None), (-1, None), (2, -1), (2, 65)])
def test_invalid_sampling_parameters_fail_before_output(tmp_path, count, threshold):
    output = tmp_path / "frames"
    with pytest.raises(ValueError):
        extract_frames("unused.mp4", output, count, threshold)
    assert not output.exists()


@pytest.mark.parametrize("failure", ["seek", "read", "write", "fps"])
def test_failure_releases_video_without_success_manifest(video, tmp_path, monkeypatch, failure):
    from scripts import extract_validation_frames as extraction

    cap = Mock()
    cap.isOpened.return_value = True
    cap.get.side_effect = [7, 0 if failure == "fps" else 10]
    cap.set.return_value = failure != "seek"
    cap.read.return_value = (failure != "read", np.zeros((64, 64, 3), np.uint8))
    monkeypatch.setattr(extraction.cv2, "VideoCapture", Mock(return_value=cap))
    monkeypatch.setattr(extraction.cv2, "imwrite", Mock(return_value=False))
    output = tmp_path / "frames"
    with pytest.raises((ValueError, OSError)):
        extract_frames(video, output, 3)
    cap.release.assert_called_once()
    assert not (output / "metadata/manifest.json").exists()


def test_partial_extraction_is_not_reported_complete_or_overwritten(video, tmp_path, monkeypatch):
    original_write = cv2.imwrite
    writes = []

    def fail_second_write(path, frame):
        writes.append(path)
        return original_write(path, frame) if len(writes) == 1 else False

    monkeypatch.setattr(cv2, "imwrite", fail_second_write)
    output = tmp_path / "frames"
    with pytest.raises(OSError):
        extract_frames(video, output, 3)
    first = output / "frame_00000001.jpg"
    saved = first.read_bytes()
    assert not (output / "metadata/manifest.json").exists()
    with pytest.raises(FileExistsError):
        extract_frames(video, output, 3)
    assert first.read_bytes() == saved
