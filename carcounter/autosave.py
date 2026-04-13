"""Auto-save progresivo para el configurador.

Guarda checkpoints cada N segundos para prevenir perdida de trabajo.
Al arrancar, ofrece resumir desde el ultimo checkpoint.
"""

import json
import os
import time
from pathlib import Path
from carcounter.logging_config import get_logger

log = get_logger("autosave")

AUTOSAVE_DIR = Path(__file__).resolve().parent.parent / "config"
AUTOSAVE_FILE = AUTOSAVE_DIR / ".autosave_checkpoint.json"
AUTOSAVE_INTERVAL_MS = 30_000  # 30 segundos


def _get_autosave_path():
    """Retorna la ruta del archivo de autosave."""
    return AUTOSAVE_FILE


def has_checkpoint():
    """Verifica si existe un checkpoint de autosave."""
    path = _get_autosave_path()
    return path.exists() and path.stat().st_size > 0


def load_checkpoint():
    """Carga el checkpoint de autosave.

    Returns:
        dict con el estado guardado, o None si no existe
    """
    path = _get_autosave_path()
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        log.info("Checkpoint cargado: %s", path)
        return data
    except (json.JSONDecodeError, IOError) as e:
        log.warning("Error leyendo checkpoint: %s", e)
        return None


def save_checkpoint(state):
    """Guarda un checkpoint con el estado actual.

    Args:
        state: dict con el estado a persistir
    """
    path = _get_autosave_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        state["_autosave_timestamp"] = time.time()
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        log.debug("Checkpoint guardado: %s", path)
    except IOError as e:
        log.warning("Error guardando checkpoint: %s", e)


def clear_checkpoint():
    """Elimina el checkpoint de autosave."""
    path = _get_autosave_path()
    if path.exists():
        path.unlink()
        log.debug("Checkpoint eliminado")


def get_checkpoint_age():
    """Retorna la edad del checkpoint en segundos, o None si no existe."""
    path = _get_autosave_path()
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        ts = data.get("_autosave_timestamp", 0)
        return time.time() - ts
    except (json.JSONDecodeError, IOError):
        return None


class AutoSaveManager:
    """Gestiona autosave periodico integrado con Tkinter.

    Uso:
        manager = AutoSaveManager(app)
        manager.start()
        # ... al guardar config oficial:
        manager.clear()
    """

    def __init__(self, app, interval_ms=AUTOSAVE_INTERVAL_MS):
        self._app = app
        self._interval_ms = interval_ms
        self._job = None

    def start(self):
        """Inicia el ciclo de autosave."""
        self._schedule()

    def stop(self):
        """Detiene el ciclo de autosave."""
        if self._job is not None:
            self._app.after_cancel(self._job)
            self._job = None

    def clear(self):
        """Limpia el checkpoint (llamar despues de guardar config oficial)."""
        clear_checkpoint()

    def _schedule(self):
        """Programa el siguiente checkpoint."""
        self._save_now()
        self._job = self._app.after(self._interval_ms, self._schedule)

    def _save_now(self):
        """Captura y guarda el estado actual de la app."""
        try:
            state = self._capture_state()
            save_checkpoint(state)
        except Exception as e:
            log.warning("Error en autosave: %s", e)

    def _capture_state(self):
        """Extrae el estado relevante de la aplicacion."""
        app = self._app
        state = {
            "current_step": app.current_step,
            "video_path": app.video_path,
            "counting_mode": app.counting_mode.get(),
            "exclusion_zones": dict(app.exclusion_zones),
            "zones": dict(app.zones),
            "counting_lines": {
                name: [list(p) for p in pts]
                for name, pts in app.counting_lines.items()
            },
            "conf_threshold": app.conf_threshold.get(),
            "infer_imgsz": app.infer_imgsz.get(),
            "min_area": app.min_area.get(),
            "max_area": app.max_area.get(),
            "vehicle_samples": app.vehicle_samples,
            "slice_w": app.slice_w.get(),
            "slice_h": app.slice_h.get(),
            "overlap": app.overlap.get(),
            "nms_threshold": app.nms_threshold.get(),
            "max_age": app.max_age.get(),
            "min_hits": app.min_hits.get(),
            "iou_thresh": app.iou_thresh.get(),
            "conf_car": app.conf_car.get(),
            "conf_motorbike": app.conf_motorbike.get(),
            "conf_bus": app.conf_bus.get(),
            "conf_truck": app.conf_truck.get(),
        }
        return state

    @staticmethod
    def restore_state(app, state):
        """Restaura el estado desde un checkpoint al app.

        Args:
            app: SetupApp instance
            state: dict del checkpoint
        """
        if "exclusion_zones" in state:
            app.exclusion_zones = state["exclusion_zones"]
            app._invalidate_excl_cache()
            app._refresh_excl_list()

        if "counting_mode" in state:
            app.counting_mode.set(state["counting_mode"])
            app._set_counting_mode(state["counting_mode"])

        if "zones" in state:
            app.zones = state["zones"]

        if "counting_lines" in state:
            app.counting_lines = state["counting_lines"]

        app._refresh_zones_list()

        # Restore scalar values
        _set = lambda var, key: var.set(state[key]) if key in state else None
        _set(app.conf_threshold, "conf_threshold")
        _set(app.infer_imgsz, "infer_imgsz")
        _set(app.min_area, "min_area")
        _set(app.max_area, "max_area")
        _set(app.slice_w, "slice_w")
        _set(app.slice_h, "slice_h")
        _set(app.overlap, "overlap")
        _set(app.nms_threshold, "nms_threshold")
        _set(app.max_age, "max_age")
        _set(app.min_hits, "min_hits")
        _set(app.iou_thresh, "iou_thresh")
        _set(app.conf_car, "conf_car")
        _set(app.conf_motorbike, "conf_motorbike")
        _set(app.conf_bus, "conf_bus")
        _set(app.conf_truck, "conf_truck")

        if "vehicle_samples" in state:
            app.vehicle_samples = state["vehicle_samples"]

        # Navigate to the step the user was on
        step = state.get("current_step", 0)
        app._activate_step(step)
        app._redraw_zones()

        log.info("Estado restaurado desde checkpoint (paso %d)", step)
