import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from setup_panels import calib_tests
from setup_panels.background_job import BackgroundJob
from setup_panels.calib_tests import CalibTestsMixin, match_saved_samples


def blocked(release, value):
    """Trabajo que espera a release y devuelve value."""
    return lambda cancelled: (release.wait(2), value)[1]


def wait_for(job, context, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        outcome = job.poll(context)
        if outcome is not None:
            return outcome
        time.sleep(0.005)
    raise AssertionError("el trabajo no terminó")


def test_job_runs_off_the_calling_thread_and_delivers_the_value():
    job, context, threads = BackgroundJob(), ("v", 1, "p"), []
    job.start(context, lambda cancelled: threads.append(threading.current_thread()) or 42)
    assert wait_for(job, context) == ("ok", 42)
    assert threads[0] is not threading.current_thread() and not job.active


def test_start_returns_while_the_work_is_still_running():
    job, context, release = BackgroundJob(), ("v", 1, "p"), threading.Event()
    job.start(context, blocked(release, "late"))
    assert job.active and job.poll(context) is None
    with pytest.raises(RuntimeError):
        job.start(context, lambda cancelled: None)
    release.set()
    assert wait_for(job, context) == ("ok", "late")


def test_worker_errors_are_reported_not_raised():
    job, context = BackgroundJob(), ("v", 1, "p")
    job.start(context, lambda cancelled: 1 / 0)
    state, error = wait_for(job, context)
    assert state == "error" and isinstance(error, ZeroDivisionError)


@pytest.mark.parametrize("changed", [("otro.mp4", 1, "p"), ("v", 2, "p"), ("v", 1, "otro perfil")])
def test_result_is_discarded_when_video_frame_or_profile_change(changed):
    job, context, release = BackgroundJob(), ("v", 1, "p"), threading.Event()
    seen = []

    def work(cancelled):
        release.wait(2)
        seen.append(cancelled.is_set())
        return "viejo"

    job.start(context, work)
    assert job.poll(changed) is None
    release.set()
    state, reason = wait_for(job, changed)
    assert state == "descartado" and "video, el frame o el perfil" in reason and seen == [True]


def test_cancel_discards_even_a_finished_result_and_frees_the_job():
    job, context = BackgroundJob(), ("v", 1, "p")
    job.start(context, lambda cancelled: "listo")
    time.sleep(0.05)
    job.cancel()
    assert wait_for(job, context) == ("descartado", "cancelada por el usuario")
    job.start(context, lambda cancelled: "nuevo")
    assert wait_for(job, context) == ("ok", "nuevo")


def test_sample_test_stops_between_frames_when_cancelled(monkeypatch, tmp_path):
    reads = []

    class FakeCapture:
        def __init__(self, path): pass
        def set(self, prop, value): reads.append(value)
        def read(self): return True, np.zeros((4, 4, 3), np.uint8)
        def release(self): reads.append("release")

    monkeypatch.setattr(calib_tests.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(calib_tests, "infer_with_params", lambda frame, params: [])
    samples = [{"frame": 3, "bbox": (0, 0, 2, 2)}, {"frame": 9, "bbox": (0, 0, 2, 2)}]
    cancelled = threading.Event()
    assert match_saved_samples("v.mp4", samples, {}, cancelled) == 0
    cancelled.set()
    reads.clear()
    assert match_saved_samples("v.mp4", samples, {}, cancelled) is None
    assert reads == ["release"]


class FakeApp:
    def __init__(self):
        self.video_path, self.current_frame_idx, self.model = "v.mp4", 5, object()
        self.profile = {"conf": 0.1}
        self.frame_orig = np.zeros((8, 8, 3), np.uint8)
        self.status_var = Mock()
        self.lbl_calib_status = Mock()
        self.btn_yolo_test, self.btn_global_test, self.btn_samples_test = Mock(), Mock(), Mock()
        self.btn_yolo_test.cget.return_value = "Probar YOLO"
        self.scheduled = []
        self._redraw = Mock()
        self.vehicle_samples = []

    def after(self, ms, callback):
        self.scheduled.append(callback)

    def _build_current_config(self):
        return dict(self.profile)

    def tick(self):
        self.scheduled.pop(0)()


def bind(app):
    for name in ("_calib_context", "_calib_buttons", "_start_calib_job", "_poll_calib_job"):
        setattr(app, name, getattr(CalibTestsMixin, name).__get__(app))
    return app


def run_until_idle(app, limit=400):
    for _ in range(limit):
        if not app.scheduled:
            return
        app.tick()
        time.sleep(0.005)
    raise AssertionError("la interfaz sigue esperando")


def test_ui_stays_free_and_shows_cancel_while_a_test_runs():
    app, release, shown = bind(FakeApp()), threading.Event(), []
    app._start_calib_job(app.btn_yolo_test, "Probando.", blocked(release, "ok"), shown.append)
    app.btn_yolo_test.config.assert_called_with(state="normal", text="✖ Cancelar prueba")
    app.btn_global_test.config.assert_called_with(state="disabled")
    app.tick()
    assert len(app.scheduled) == 1 and shown == []
    release.set()
    run_until_idle(app)
    assert shown == ["ok"]
    app.btn_yolo_test.config.assert_called_with(state="normal")


def test_pressing_the_button_again_cancels_and_drops_the_result():
    app, release, shown = bind(FakeApp()), threading.Event(), []
    app._start_calib_job(app.btn_yolo_test, "Probando.", blocked(release, "ok"), shown.append)
    app._start_calib_job(app.btn_yolo_test, "Probando.", lambda cancelled: None, shown.append)
    release.set()
    run_until_idle(app)
    assert shown == []
    assert "cancelada por el usuario" in app.status_var.set.call_args[0][0]


@pytest.mark.parametrize("change", [
    lambda app: setattr(app, "current_frame_idx", 6),
    lambda app: setattr(app, "video_path", "otro.mp4"),
    lambda app: app.profile.update(conf=0.9),
    lambda app: setattr(app, "model", object()),
])
def test_ui_drops_the_result_when_context_changes_mid_run(change):
    app, release, shown = bind(FakeApp()), threading.Event(), []
    app._start_calib_job(app.btn_yolo_test, "Probando.", blocked(release, "ok"), shown.append)
    change(app)
    app.tick()
    release.set()
    run_until_idle(app)
    assert shown == []
    assert "Prueba descartada" in app.status_var.set.call_args[0][0]


def test_worker_error_is_shown_without_raising():
    app, shown = bind(FakeApp()), []
    app._start_calib_job(app.btn_yolo_test, "Probando.", lambda cancelled: 1 / 0, shown.append)
    run_until_idle(app)
    assert shown == [] and "No se pudo probar el perfil" in app.status_var.set.call_args[0][0]
