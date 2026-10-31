from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from setup_panels.step2_preview import PreviewMixin


def app():
    instance = SimpleNamespace(
        _preview_playing=True, _preview_pending=None, _preview_result=None,
        _preview_cap=Mock(), _preview_infer_busy=False, _preview_generation=1,
        _preview_show_detections=True, model=object(), _preview_frame_idx=4,
        total_frames=10, lbl_frame_info=Mock(), status_var=Mock(), after=Mock(),
        _redraw=Mock(), _overlay_zones_on_preview=Mock(),
        _draw_detections_on_preview=Mock(), _report_preview_error=Mock(),
        _stop_zone_preview=Mock(), _request_preview_detections=Mock(),
    )
    instance._zone_preview_tick = lambda: PreviewMixin._zone_preview_tick(instance)
    return instance


def test_preview_waits_then_draws_exact_inferred_frame():
    instance = app()
    frame = np.full((24, 32, 3), 30, dtype=np.uint8)
    instance._preview_cap.read.return_value = (True, frame)
    instance._zone_preview_tick()
    instance._zone_preview_tick()
    assert instance._preview_cap.read.call_count == 1
    instance._draw_detections_on_preview.assert_not_called()
    instance._preview_result = ([dict(bbox=(1, 2, 3, 4))], None)
    instance._zone_preview_tick()
    assert instance._preview_cap.read.call_count == 1
    assert instance._preview_last_frame[0] == 4
    assert np.array_equal(instance.display_frame_zones, frame)
    instance._draw_detections_on_preview.assert_called_once()


def test_stopped_generation_cannot_publish_results(monkeypatch):
    workers = []
    monkeypatch.setattr("setup_panels.step2_preview.threading.Thread",
                        lambda target, daemon: SimpleNamespace(start=lambda: workers.append(target)))
    instance = app()
    instance._profile_inference_params = lambda: {}
    instance._infer_with_params = lambda frame, params: ["old-result"]
    PreviewMixin._request_preview_detections(instance, np.zeros((2, 2, 3), dtype=np.uint8))
    instance._preview_generation += 1
    workers[0]()
    assert instance._preview_result is None
    assert not instance._preview_infer_busy


def test_inference_failure_stops_without_overwriting_error_status():
    instance = app()
    instance._preview_pending = (4, np.zeros((2, 2, 3), dtype=np.uint8))
    instance._preview_result = ([], RuntimeError("failure"))
    instance._zone_preview_tick()
    instance._stop_zone_preview.assert_called_once()
    instance._report_preview_error.assert_called_once()
    instance._redraw.assert_not_called()
    instance.status_var.set.assert_not_called()
