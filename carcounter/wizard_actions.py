"""Lógica del wizard sin Tk: perfil, modelo, comandos de subproceso y salidas de cada corrida."""

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from carcounter.app_config import AppConfig
from carcounter.config_io import load_config
from carcounter.models import MODEL_CATALOG, get_model_path, is_valid_weights
from carcounter.paths import paths

PROFILE_MODEL = "__profile__"
CUSTOM_MODEL = "__custom__"
MODE_LABELS = {"zones": "zonas (origen a destino)", "lines": "líneas de cruce", "directions": "direcciones"}


class ModelChoice(NamedTuple):
    """Modelo elegido: args de main.py y modelo del configurador. Con error no se debe lanzar nada."""
    args: list | None
    setup_model: str | None
    label: str
    error: str | None


def load_json(path):
    """Contenido del JSON, o {} si no existe o no se puede leer."""
    try:
        data = load_config(path)
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def profile_errors(config_path):
    """Errores del perfil antes de gastar una corrida; main.py lo vuelve a validar al arrancar."""
    try:
        data = load_config(config_path)
    except (OSError, ValueError, TypeError) as error:
        return [f"No se pudo leer el perfil: {error}"]
    if not isinstance(data, dict):
        return ["El perfil no es un objeto JSON"]
    return AppConfig.from_dict(data).validate()


def profile_rows(profile):
    """Filas (etiqueta, valor) con lo que el perfil manda en la corrida."""
    if not profile:
        return []
    geometry = ", ".join(part for part in (
        f"{len(profile.get('zones') or {})} zonas",
        f"{len(profile.get('lines') or [])} líneas",
        f"{len(profile.get('directions') or {})} direcciones",
        f"{len(profile.get('exclusion_zones') or {})} exclusiones",
    ) if not part.startswith("0 "))
    mode = profile.get("counting_mode", "zones")
    rows = [("Conteo", f"{MODE_LABELS.get(mode, mode)} · {geometry or 'sin geometría'}")]
    for label, key in (("Video perfil", "video_path"), ("Modelo perfil", "model_path")):
        if profile.get(key):
            rows.append((label, Path(profile[key]).name))
    roi = (profile.get("settings") or {}).get("inference_roi")
    if roi:
        rows.append(("Región", f"{list(roi)}: lo de fuera no se detecta"))
    return rows


def resolve_path(value):
    return str(paths.resolve(value)) if value else ""


def resolve_model(choice, custom_path="", profile=None):
    """Elección de modelo sin cambios silenciosos: el perfil, un archivo propio o el catálogo."""
    profile = profile or {}
    if choice == PROFILE_MODEL:
        model = resolve_path(profile.get("model_path", ""))
        if not model:
            return _model_error("El perfil no indica model_path: elige un modelo o un archivo")
        if not is_valid_weights(model):
            return _model_error(f"El modelo del perfil no existe o está incompleto:\n{model}")
        return ModelChoice([], model, f"del perfil ({Path(model).name})", None)
    if choice == CUSTOM_MODEL:
        if not is_valid_weights(custom_path):
            return _model_error(f"El archivo de pesos no existe o está incompleto:\n{custom_path}")
        if custom_path.endswith(".pth"):
            return ModelChoice(["--detector", "rfdetr", "--model", custom_path], None,
                               Path(custom_path).name, None)
        return ModelChoice(["--model", custom_path], custom_path, Path(custom_path).name, None)
    info = MODEL_CATALOG.get(choice)
    if not info:
        return _model_error("Selecciona un modelo")
    if info["family"] == "rfdetr":
        return ModelChoice(["--detector", "rfdetr", "--rfdetr-variant", info.get("variant", "base")],
                           None, choice, None)
    model = get_model_path(choice)
    if not model:
        return _model_error(f"{choice} no está descargado en models/{info['file']}")
    return ModelChoice(["--model", model], model, choice, None)


def _model_error(message):
    return ModelChoice(None, None, "", message)


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
    data = load_json(results_path)
    if not data:
        return "Sin results.json"
    routes = data.get("routes", {})
    top = ", ".join(f"{route}: {count}" for route, count in list(routes.items())[:5])
    return (f"Frames: {data.get('frames_processed', '?')}  |  IDs: {data.get('total_vehicles_tracked', '?')}  |  "
            f"Conteos: {data.get('total_routes_completed', '?')}" + (f"\n{top}" if top else ""))


def open_folder_command(folder, platform):
    return ["open", str(folder)] if platform == "darwin" else ["xdg-open", str(folder)]
