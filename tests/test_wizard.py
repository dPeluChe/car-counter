"""Wizard: selección de modelo sin fallback, comandos de subproceso, salidas por corrida y perfil."""

from datetime import datetime
import json
from pathlib import Path
import sys

import pytest

from carcounter import models
from carcounter.paths import Paths
from carcounter.wizard_actions import (
    CUSTOM_MODEL, PROFILE_MODEL, build_run_command, build_setup_command, make_run_dir, profile_errors,
    profile_rows, resolve_model, results_summary, tail,
)

ZONAS = {"Norte": [[0, 0], [10, 0], [10, 10]], "Sur": [[0, 50], [10, 50], [10, 60]]}


def weights(path, size=models.MIN_WEIGHTS_BYTES):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * size)
    return path


def test_profile_model_is_used_without_passing_model(tmp_path):
    model = weights(tmp_path / "visdrone.pt")
    choice = resolve_model(PROFILE_MODEL, profile={"model_path": str(model)})
    assert choice.error is None and choice.args == [] and choice.setup_model == str(model)


@pytest.mark.parametrize("profile", [{}, {"model_path": "no/existe.pt"}])
def test_profile_model_missing_blocks_instead_of_falling_back(profile, tmp_path):
    choice = resolve_model(PROFILE_MODEL, profile=profile)
    assert choice.error and choice.args is None


def test_catalog_model_missing_blocks_and_placeholder_is_not_weights(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "MODELS_DIR", tmp_path)
    weights(tmp_path / "yolo/yolov11l.pt", size=46)
    assert models.get_model_path("yolov11l") is None
    assert not models.is_downloaded("yolov11l")
    assert resolve_model("yolov11l").error
    weights(tmp_path / "yolo/yolov11l.pt")
    assert resolve_model("yolov11l").args == ["--model", str(tmp_path / "yolo/yolov11l.pt")]


def test_custom_weights_and_rfdetr_choices(tmp_path):
    pt, pth = weights(tmp_path / "mio.pt"), weights(tmp_path / "mio.pth")
    assert resolve_model(CUSTOM_MODEL, custom_path=str(pt)).args == ["--model", str(pt)]
    rfdetr_custom = resolve_model(CUSTOM_MODEL, custom_path=str(pth))
    assert rfdetr_custom.args == ["--detector", "rfdetr", "--model", str(pth)]
    assert rfdetr_custom.setup_model is None
    assert resolve_model("rfdetr-medium").args == ["--detector", "rfdetr", "--rfdetr-variant", "medium"]
    assert resolve_model(CUSTOM_MODEL, custom_path=str(tmp_path / "falta.pt")).error


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
                       ("--output-tracks-csv", "tracks.csv"), ("--output-od-csv", "od_matrix.csv"),
                       ("--output-od-group-csv", "od_by_group.csv")):
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
    assert "Por grupo EPS" not in results_summary(results)


def test_profile_errors_reports_unreadable_json_and_missing_geometry(tmp_path):
    broken = tmp_path / "roto.json"
    broken.write_text("{")
    assert profile_errors(broken)[0].startswith("No se pudo leer")
    assert profile_errors(tmp_path / "no_existe.json")
    empty = tmp_path / "vacio.json"
    empty.write_text(json.dumps({"counting_mode": "zones", "zones": {}}))
    assert any("2 zonas" in error for error in profile_errors(empty))
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"counting_mode": "zones", "zones": ZONAS}))
    assert profile_errors(ok) == []


def test_profile_rows_show_mode_geometry_video_model_and_roi():
    assert profile_rows({}) == []
    rows = dict(profile_rows({"counting_mode": "lines", "lines": [{"name": "A", "points": [[0, 0], [1, 1]]}],
                              "exclusion_zones": {"Banqueta": []}, "model_path": "models/yolo/x.pt",
                              "video_path": "assets/clip.mp4", "settings": {"inference_roi": [1, 2, 3, 4]}}))
    assert "líneas de cruce" in rows["Conteo"] and "1 líneas" in rows["Conteo"]
    assert "1 exclusiones" in rows["Conteo"] and "zonas" not in rows["Conteo"]
    assert rows["Video perfil"] == "clip.mp4" and rows["Modelo perfil"] == "x.pt"
    assert rows["Región"].startswith("[1, 2, 3, 4]")


# ── App oculta ────────────────────────────────

class FakeProcess:
    instances = []

    def __init__(self, command, cwd=None, stdout=None, stderr=None, start_new_session=False):
        self.command, self.cwd, self.codes, self.terminated = command, cwd, [None], False
        self.session = start_new_session
        if stdout is not None:
            stdout.write("Traceback\nValueError: perfil inválido\n")
            stdout.flush()
        FakeProcess.instances.append(self)

    def poll(self):
        return self.codes[0]

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.codes[0] = -15
        return self.codes[0]


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
    monkeypatch.setattr(Paths, "output_dir", property(lambda self: tmp_path / "output"))
    import carcounter.app_steps.run_control as run_control
    FakeProcess.instances.clear()
    monkeypatch.setattr(run_control.subprocess, "Popen", FakeProcess)
    from carcounter.app import CarCounterApp
    app = CarCounterApp()
    app.calls = calls
    yield app
    app.destroy()


@pytest.fixture
def listo(wizard, tmp_path):
    """Wizard en el paso 3 con perfil, modelo del perfil y video elegidos."""
    model, video = weights(tmp_path / "visdrone.pt"), tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    profile = tmp_path / "perfil_eps.json"
    profile.write_text(json.dumps({"counting_mode": "zones", "zones": ZONAS,
                                   "model_path": str(model), "video_path": str(video)}))
    wizard._selected_config.set(str(profile))
    wizard._selected_model.set(PROFILE_MODEL)
    wizard._selected_video.set(str(video))
    wizard._show_step(2)
    return wizard, profile, video


def _labels(widget):
    texts = []
    for child in widget.winfo_children():
        try:
            texts.append(str(child.cget("text")))
        except Exception:
            pass
        texts.extend(_labels(child))
    return texts


def test_starts_without_profile_and_summary_describes_the_loaded_one(listo, tmp_path):
    wizard, profile, _ = listo
    assert wizard._selected_config.get() == str(profile)
    labels = _labels(wizard._content)
    assert any("2 zonas" in text for text in labels)
    assert any("clip.mp4" in text for text in labels)
    from carcounter.app import CarCounterApp
    nuevo = CarCounterApp()
    try:
        assert nuevo._selected_config.get() == ""
    finally:
        nuevo.destroy()


def test_selected_profile_survives_redraw_and_label_shows_it(listo):
    wizard, profile, _ = listo
    wizard._show_step(1)
    wizard._show_step(2)
    assert wizard._selected_config.get() == str(profile)
    assert any("perfil_eps.json" in text for text in _labels(wizard._content))
    assert not any("RECOMENDADO" in text or "mayor precision" in text for text in _labels(wizard))


def test_open_setup_runs_subprocess_and_detects_saved_profile(listo, tmp_path):
    wizard, profile, video = listo
    wizard._open_setup()
    process = FakeProcess.instances[-1]
    assert process.command == [sys.executable, "setup.py", "--video", str(video), "--config", str(profile),
                               "--model", str(tmp_path / "visdrone.pt")]
    assert process.session
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


def test_run_processing_writes_outputs_and_shows_log_on_error(listo, tmp_path):
    wizard, _, _ = listo
    wizard._run_processing()
    process = FakeProcess.instances[-1]
    run_dir = wizard._run_dir
    assert run_dir.parent == tmp_path / "output"
    assert "--video" not in process.command and "--model" not in process.command
    assert process.command[process.command.index("--output-tracks-csv") + 1] == str(run_dir / "tracks.csv")
    assert (run_dir / "command.txt").exists()
    assert str(wizard._cancel_btn.cget("state")) == "normal"
    process.codes[0] = 1
    wizard._poll_process()
    errors = [args for name, args in wizard.calls if name == "showerror"]
    assert errors and "perfil inválido" in errors[-1][1]


def test_cancelling_a_run_says_cancelled_without_an_error_dialog(listo):
    wizard, _, _ = listo
    wizard._run_processing()
    process = FakeProcess.instances[-1]
    wizard._cancel_run()
    assert process.terminated
    process.codes[0] = -15
    wizard._poll_process()
    assert wizard._status.get().startswith("Cancelado: quedan salidas parciales")
    assert not [name for name, _ in wizard.calls if name == "showerror"]
    assert not wizard._busy()
    wizard._run_processing()
    FakeProcess.instances[-1].codes[0] = 1
    wizard._poll_process()
    assert [name for name, _ in wizard.calls if name == "showerror"], "un fallo posterior sí es un error"


def test_a_process_that_cannot_start_is_reported_and_leaves_the_wizard_free(listo, monkeypatch):
    wizard, _, _ = listo
    import carcounter.app_steps.run_control as run_control

    def broken(*args, **kwargs):
        raise FileNotFoundError("python no existe")
    monkeypatch.setattr(run_control.subprocess, "Popen", broken)
    wizard._run_processing()
    assert not wizard._busy() and wizard._log_file is None
    assert "No se pudo iniciar" in wizard._status.get() and "python no existe" in wizard._status.get()
    assert wizard.calls[-1][0] == "showerror"


def test_last_run_summary_can_be_reopened_from_the_wizard(listo):
    wizard, _, _ = listo
    assert "Ver resumen" not in _labels(wizard._content)
    wizard._run_processing()
    FakeProcess.instances[-1].codes[0] = 0
    (wizard._run_dir / "results.json").write_text(json.dumps({
        "frames_processed": 20, "total_vehicles_tracked": 5, "total_routes_completed": 3,
        "routes": {"Norte → Sur": 3}, "routes_by_group": {"Norte → Sur": {"ligeros": 2, "pesados": 1}}}))
    wizard._poll_process()
    wizard._show_step(2)
    assert "Ver resumen" in _labels(wizard._content)
    wizard.calls.clear()
    wizard._show_run_summary()
    name, args = wizard.calls[-1]
    assert name == "showinfo" and "Conteos: 3" in args[1] and "Norte → Sur: ligeros 2, pesados 1" in args[1]


def test_buttons_show_keyboard_focus_and_bind_enter(listo):
    wizard, _, _ = listo
    from carcounter.app_theme import btn
    button = btn(wizard._content, "Probar", lambda: None)
    assert str(button.cget("highlightcolor")) != str(button.cget("highlightbackground"))
    assert int(str(button.cget("highlightthickness"))) >= 2
    assert button.bind("<Return>")


def test_focus_scrolls_the_model_list_to_a_button_below_the_fold(wizard):
    from carcounter.app_steps.step_model import reveal_in_view
    wizard.geometry("820x420")
    wizard.deiconify()
    wizard._show_step(0)
    wizard.update()
    downloads = [w for w in wizard._model_btns.values() if str(w.cget("state")) == "normal"]
    canvas = next(w for w in wizard._content.winfo_children()[-1].winfo_children() if w.winfo_class() == "Canvas")
    inner = downloads[-1].master
    while inner.master is not canvas:
        inner = inner.master
    assert downloads and canvas.yview()[0] == 0.0
    reveal_in_view(canvas, inner, downloads[-1])
    wizard.update()
    assert canvas.yview()[0] > 0.0
    assert 0 <= downloads[-1].winfo_rooty() - canvas.winfo_rooty() <= canvas.winfo_height()
    wizard.withdraw()


def test_cancelling_the_configurator_asks_before_closing_it(listo):
    wizard, _, _ = listo
    wizard._open_setup()
    process = FakeProcess.instances[-1]
    wizard._cancel_run()  # askyesno responde que no en el fixture
    assert not process.terminated


def test_invalid_profile_blocks_the_run_before_launching(listo):
    wizard, profile, _ = listo
    profile.write_text(json.dumps({"counting_mode": "zones", "zones": {}}))
    wizard._run_processing()
    assert not FakeProcess.instances
    name, args = wizard.calls[-1]
    assert name == "showwarning" and args[0] == "Perfil inválido" and "2 zonas" in args[1]


def test_run_requires_existing_profile_and_valid_model(listo, tmp_path):
    wizard, _, _ = listo
    wizard._selected_config.set("")
    wizard._selected_model.set("yolov11l")
    wizard._run_processing()
    assert not FakeProcess.instances
    assert wizard.calls[-1][0] == "showwarning"
