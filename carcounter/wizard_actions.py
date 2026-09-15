"""Lógica del wizard sin Tk: perfil, modelo, comandos de subproceso y salidas de cada corrida."""

from collections import deque
from datetime import datetime
import json
from pathlib import Path

from carcounter.models import MODEL_CATALOG, get_model_path, is_valid_weights
from carcounter.paths import paths

PROFILE_MODEL = "__profile__"
CUSTOM_MODEL = "__custom__"


def load_profile(config_path):
    """Contenido del perfil JSON, o {} si no existe o no se puede leer."""
    try:
        return json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def resolve_path(value):
    return str(paths.resolve(value)) if value else ""


def resolve_model(choice, custom_path="", profile=None):
    """Argumentos de main.py y modelo para el configurador; nunca cambia de modelo en silencio.

    Devuelve dict(args, setup_model, label, error). Con error no se debe lanzar nada.
    """
    profile = profile or {}
    if choice == PROFILE_MODEL:
        model = resolve_path(profile.get("model_path", ""))
        if not model:
            return _model_error("El perfil no indica model_path: elige un modelo o un archivo")
        if not is_valid_weights(model):
            return _model_error(f"El modelo del perfil no existe o está incompleto:\n{model}")
        return dict(args=[], setup_model=model, label=f"del perfil ({Path(model).name})", error=None)
    if choice == CUSTOM_MODEL:
        if not is_valid_weights(custom_path):
            return _model_error(f"El archivo de pesos no existe o está incompleto:\n{custom_path}")
        if custom_path.endswith(".pth"):
            return dict(args=["--detector", "rfdetr", "--model", custom_path], setup_model=None,
                        label=Path(custom_path).name, error=None)
        return dict(args=["--model", custom_path], setup_model=custom_path,
                    label=Path(custom_path).name, error=None)
    info = MODEL_CATALOG.get(choice)
    if not info:
        return _model_error("Selecciona un modelo")
    if info["family"] == "rfdetr":
        return dict(args=["--detector", "rfdetr", "--rfdetr-variant", info.get("variant", "base")],
                    setup_model=None, label=choice, error=None)
    model = get_model_path(choice)
    if not model:
        return _model_error(f"{choice} no está descargado en models/{info['file']}")
    return dict(args=["--model", model], setup_model=model, label=choice, error=None)


def _model_error(message):
    return dict(args=None, setup_model=None, label="", error=message)


def same_file(first, second):
    return bool(first and second) and Path(first).resolve() == Path(second).resolve()


def build_setup_command(python, video, config, model_path=None):
    command = [python, "setup.py", "--video", video, "--config", config]
    return command + (["--model", model_path] if model_path else [])


def make_run_dir(video, now=None, root=None):
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return Path(root or paths.output_dir) / f"{stamp}_{Path(video).stem}"


def build_run_command(python, config, video, profile_video, tracker, model_args, run_dir):
    """Comando de main.py con todas las salidas en la carpeta de la corrida.

    --video solo se pasa si el usuario eligió un video distinto al del perfil.
    """
    run_dir = Path(run_dir)
    command = [python, "main.py", "--config", config, "--tracker", tracker, "--show-fps", *model_args,
               "--output", str(run_dir / "video.mp4"), "--output-json", str(run_dir / "results.json"),
               "--output-tracks-csv", str(run_dir / "tracks.csv"),
               "--output-od-csv", str(run_dir / "od_matrix.csv")]
    if video and not same_file(video, profile_video):
        command += ["--video", video]
    return command


def video_resolution(path):
    import cv2
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()


def tail(path, lines=20):
    try:
        with open(path, encoding="utf-8", errors="replace") as source:
            return "".join(deque(source, maxlen=lines))
    except OSError:
        return ""


def results_summary(results_path):
    """Texto corto con frames, vehículos y rutas de results.json."""
    data = load_profile(results_path)
    if not data:
        return "Sin results.json"
    routes = data.get("routes", {})
    top = ", ".join(f"{route}: {count}" for route, count in list(routes.items())[:5])
    return (f"Frames: {data.get('frames_processed', '?')}  |  IDs: {data.get('total_vehicles_tracked', '?')}  |  "
            f"Conteos: {data.get('total_routes_completed', '?')}" + (f"\n{top}" if top else ""))


def open_folder_command(folder, platform):
    return ["open", str(folder)] if platform == "darwin" else ["xdg-open", str(folder)]
