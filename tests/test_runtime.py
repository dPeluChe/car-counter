from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from carcounter import runtime
from carcounter.counting import VehicleCounter
from carcounter.detection import _track_with_sort
from carcounter.profiler import Profiler


@pytest.mark.parametrize("headless,no_save,serve,rendered", [
    (True, True, False, False),
    (True, False, False, True),
    (True, True, True, True),
    (False, True, False, True),
])
def test_render_only_when_consumed(monkeypatch, headless, no_save, serve, rendered):
    monkeypatch.setattr(runtime, "detect_and_track", Mock(return_value=[
        (0, 0, 20, 20, 1, "car")]))
    drawing = Mock()
    monkeypatch.setattr(runtime, "draw_tracked_boxes", drawing)
    counter = VehicleCounter({}, [])
    profiler = Profiler()
    runtime.process_frame(
        np.zeros((100, 100, 3), dtype=np.uint8), frame_count=7,
        counter=counter, cfg={"counting_mode": "zones"},
        args=SimpleNamespace(headless=headless, no_save=no_save, serve=serve,
                             demo_mode=False, show_fps=False),
        detect_state={"profiler": profiler, "fn_kwargs": {}, "consecutive_errors": 0},
        fps_samples=deque(maxlen=30), zones_np={}, exclusion_np={},
        counting_lines=[], use_sahi=False, heatmap=None, vid_w=100, total_frames=10,
    )
    assert drawing.called == rendered
    assert counter.tracks_info[1]["last_seen_frame"] == 7
    assert bool(profiler.stats["visualization"]) == rendered


def test_missing_tracker_does_not_invent_ids():
    with pytest.raises(RuntimeError, match="IDs persistentes"):
        _track_with_sort(None, np.array([[0, 0, 20, 20, 0.9]]), ["car"])


def test_empty_detections_still_advance_tracker():
    tracker = Mock()
    tracker.update.return_value = np.empty((0, 5))
    detections = np.empty((0, 5))
    assert _track_with_sort(tracker, detections, []) == []
    tracker.update.assert_called_once_with(detections)


def test_sahi_preserves_selected_tracker():
    pytest.importorskip("lap")
    backend, tracker = runtime.setup_tracker(
        SimpleNamespace(tracker="bytetrack"),
        {"tracker_cfg": {"track_buffer": 12}},
        use_sahi=True, vid_fps=25,
    )
    assert backend == "bytetrack"
    assert tracker.options["track_buffer"] == 12


def test_missing_sort_fails_during_setup(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "carcounter.sort", None)
    with pytest.raises(RuntimeError, match="SORT no disponible"):
        runtime.setup_tracker(SimpleNamespace(tracker="sort"),
                              {"tracker_cfg": {}}, use_sahi=False, vid_fps=30)
