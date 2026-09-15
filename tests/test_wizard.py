"""Wizard: selección de modelo sin fallback, comandos de subproceso, salidas por corrida y perfil."""

from datetime import datetime
import json
from pathlib import Path
import sys

import pytest

from carcounter import models
from carcounter.paths import Paths
from carcounter.wizard_actions import (
    CUSTOM_MODEL, PROFILE_MODEL, build_run_command, build_setup_command, make_run_dir, resolve_model,
    results_summary, tail,
)


def weights(path, size=models.MIN_WEIGHTS_BYTES):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * size)
    return path


def test_profile_model_is_used_without_passing_model(tmp_path):
    model = weights(tmp_path / "visdrone.pt")
    choice = resolve_model(PROFILE_MODEL, profile={"model_path": str(model)})
    assert choice["error"] is None and choice["args"] == [] and choice["setup_model"] == str(model)


@pytest.mark.parametrize("profile", [{}, {"model_path": "no/existe.pt"}])
def test_profile_model_missing_blocks_instead_of_falling_back(profile, tmp_path):
    choice = resolve_model(PROFILE_MODEL, profile=profile)
    assert choice["error"] and choice["args"] is None


def test_catalog_model_missing_blocks_and_placeholder_is_not_weights(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "MODELS_DIR", tmp_path)
    weights(tmp_path / "yolo/yolov11l.pt", size=46)
    assert models.get_model_path("yolov11l") is None
    assert not models.is_downloaded("yolov11l")
    assert resolve_model("yolov11l")["error"]
    weights(tmp_path / "yolo/yolov11l.pt")
    assert resolve_model("yolov11l")["args"] == ["--model", str(tmp_path / "yolo/yolov11l.pt")]


def test_custom_weights_and_rfdetr_choices(tmp_path):
    pt, pth = weights(tmp_path / "mio.pt"), weights(tmp_path / "mio.pth")
    assert resolve_model(CUSTOM_MODEL, custom_path=str(pt))["args"] == ["--model", str(pt)]
    rfdetr_custom = resolve_model(CUSTOM_MODEL, custom_path=str(pth))
    assert rfdetr_custom["args"] == ["--detector", "rfdetr", "--model", str(pth)]
    assert rfdetr_custom["setup_model"] is None
    assert resolve_model("rfdetr-medium")["args"] == ["--detector", "rfdetr", "--rfdetr-variant", "medium"]
    assert resolve_model(CUSTOM_MODEL, custom_path=str(tmp_path / "falta.pt"))["error"]


def test_catalog_download_assets_and_local_visdrone_entry():
    from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES
    for name, info in models.MODEL_CATALOG.items():
        if info["source"] == "ultralytics":
            assert info["asset"] in GITHUB_ASSETS_NAMES, name
    visdrone = models.MODEL_CATALOG["yolov8l-visdrone"]
    assert visdrone["source"] == "local" and "asset" not in visdrone
    ok, error = models.download_model_with_error("yolov8l-visdrone") if not models.is_downloaded(
        "yolov8l-visdrone") else (False, "copia")
    assert not ok and "copia" in error


def test_run_command_outputs_and_video_override(tmp_path):
    run_dir = make_run_dir("assets/glorieta_test1min.mp4", now=datetime(2026, 9, 15, 11, 2, 3), root=tmp_path)
    assert run_dir == tmp_path / "20260915_110203_glorieta_test1min"
    profile_video = tmp_path / "clip.mp4"
    profile_video.write_bytes(b"x")
    same = build_run_command("py", "p.json", str(profile_video), str(profile_video), "botsort", ["--model", "m.pt"], run_dir)
    assert "--video" not in same
    for flag, name in (("--output", "video.mp4"), ("--output-json", "results.json"),
                       ("--output-tracks-csv", "tracks.csv"), ("--output-od-csv", "od_matrix.csv")):
        assert same[same.index(flag) + 1] == str(run_dir / name)
    assert same[:6] == ["py", "main.py", "--config", "p.json", "--tracker", "botsort"]
    other = build_run_command("py", "p.json", "otro.mp4", str(profile_video), "bytetrack", [], run_dir)
    assert other[-2:] == ["--video", "otro.mp4"]
    assert build_setup_command("py", "v.mp4", "p.json", "m.pt") == [
        "py", "setup.py", "--video", "v.mp4", "--config", "p.json", "--model", "m.pt"]
    assert "--model" not in build_setup_command("py", "v.mp4", "p.json")


def test_tail_and_results_summary(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("".join(f"linea {i}\n" for i in range(30)))
    assert tail(log, 3) == "linea 27\nlinea 28\nlinea 29\n"
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"frames_processed": 300, "total_vehicles_tracked": 282,
                                   "total_routes_completed": 6, "routes": {"Anillo oeste ↓": 6}}))
    assert "Conteos: 6" in results_summary(results) and "Anillo oeste ↓: 6" in results_summary(results)


# ── App oculta ────────────────────────────────

class FakeProcess:
    instances = []

    def __init__(self, command, cwd=None, stdout=None, stderr=None):
        self.command, self.cwd, self.codes, self.terminated = command, cwd, [None], False
        if stdout is not None:
            stdout.write("Traceback\nValueError: perfil inválido\n")
            stdout.flush()
        FakeProcess.instances.append(self)

    def poll(self):
        return self.codes[0]

    def terminate(self):
        self.terminated = True


@pytest.fixture
def wizard(monkeypatch, tmp_path):
    tk = pytest.importorskip("tkinter")
    try:
        tk.Tk().destroy()
    except tk.TclError:
        pytest.skip("Tk no disponible")
    original = tk.Tk.__init__

    def hidden(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.withdraw()
    monkeypatch.setattr(tk.Tk, "__init__", hidden)
    from tkinter import messagebox
    calls = []
    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(messagebox, name, lambda *a, _name=name, **k: calls.append((_name, a)))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    monkeypatch.setattr(Paths, "default_config", property(lambda self: tmp_path / "sin_config.json"))
    monkeypatch.setattr(Paths, "output_dir", property(lambda self: tmp_path / "output"))
    import carcounter.app_steps.run_control as run_control
    FakeProcess.instances.clear()
    monkeypatch.setattr(run_control.subprocess, "Popen", FakeProcess)
    from carcounter.app import CarCounterApp
    app = CarCounterApp()
    app.calls = calls
    yield app
    app.destroy()


def _labels(widget):
    texts = []
    for child in widget.winfo_children():
        try:
            texts.append(str(child.cget("text")))
        except Exception:
            pass
        texts.extend(_labels(child))
    return texts


def _profile(tmp_path):
    model, video = weights(tmp_path / "visdrone.pt"), tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    profile = tmp_path / "perfil_eps.json"
    profile.write_text(json.dumps({"model_path": str(model), "video_path": str(video)}))
    return profile, video


def test_selected_profile_survives_redraw_and_label_shows_it(wizard, tmp_path):
    profile, video = _profile(tmp_path)
    wizard._selected_config.set(str(profile))
    wizard._selected_model.set(PROFILE_MODEL)
    wizard._selected_video.set(str(video))
    wizard._show_step(2)
    wizard._show_step(1)
    wizard._show_step(2)
    assert wizard._selected_config.get() == str(profile)
    assert any("perfil_eps.json" in text for text in _labels(wizard._content))
    assert not any("RECOMENDADO" in text or "mayor precision" in text for text in _labels(wizard))


def test_open_setup_runs_subprocess_and_detects_saved_profile(wizard, tmp_path):
    profile, video = _profile(tmp_path)
    wizard._selected_config.set(str(profile))
    wizard._selected_model.set(PROFILE_MODEL)
    wizard._selected_video.set(str(video))
    wizard._show_step(2)
    wizard._open_setup()
    process = FakeProcess.instances[-1]
    assert process.command == [sys.executable, "setup.py", "--video", str(video), "--config", str(profile),
                               "--model", str(tmp_path / "visdrone.pt")]
    wizard._poll_process()
    assert wizard._busy()
    process.codes[0] = 0
    wizard._poll_process()
    assert "sin guardar" in wizard._status.get()

    wizard._open_setup()
    profile.write_text(profile.read_text() + " ")
    import os
    os.utime(profile, (1, 1))
    FakeProcess.instances[-1].codes[0] = 0
    wizard._poll_process()
    assert "Perfil guardado" in wizard._status.get()


def test_run_processing_writes_outputs_and_shows_log_on_error(wizard, tmp_path):
    profile, video = _profile(tmp_path)
    wizard._selected_config.set(str(profile))
    wizard._selected_model.set(PROFILE_MODEL)
    wizard._selected_video.set(str(video))
    wizard._show_step(2)
    wizard._run_processing()
    process = FakeProcess.instances[-1]
    run_dir = wizard._run_dir
    assert run_dir.parent == tmp_path / "output"
    assert "--video" not in process.command and "--model" not in process.command
    assert process.command[process.command.index("--output-tracks-csv") + 1] == str(run_dir / "tracks.csv")
    assert (run_dir / "command.txt").exists()
    assert str(wizard._cancel_btn.cget("state")) == "normal"
    wizard._cancel_run()
    assert process.terminated
    process.codes[0] = 1
    wizard._poll_process()
    errors = [args for name, args in wizard.calls if name == "showerror"]
    assert errors and "perfil inválido" in errors[-1][1]


def test_run_requires_existing_profile_and_valid_model(wizard, tmp_path):
    _, video = _profile(tmp_path)
    wizard._selected_video.set(str(video))
    wizard._selected_model.set("yolov11l")
    wizard._run_processing()
    assert not FakeProcess.instances
    assert wizard.calls[-1][0] == "showwarning"
