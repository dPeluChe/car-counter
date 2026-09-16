"""Auto-save progresivo del configurador: un checkpoint por perfil.

Guarda el estado cada N segundos solo si cambió desde la última carga o guardado.
"""

import hashlib
import json
import time
from pathlib import Path
from carcounter.logging_config import get_logger

log = get_logger("autosave")

AUTOSAVE_DIR = Path(__file__).resolve().parent.parent / "config"
AUTOSAVE_INTERVAL_MS = 30_000
CHECKPOINT_TTL_S = 86400

# Variables escalares de Tk que se guardan y restauran; setup_panels/state.py las crea leyendo esta lista
SCALAR_VARS = (
    "conf_threshold", "infer_imgsz", "min_area", "max_area", "slice_w", "slice_h", "overlap",
    "nms_threshold", "max_age", "min_hits", "iou_thresh", "conf_car", "conf_motorbike", "conf_bus",
    "conf_truck", "conf_van", "sahi_enabled", "track_low_thresh", "track_high_thresh",
    "new_track_thresh", "track_buffer", "fuse_score",
)


def checkpoint_path(profile_path):
    """Un archivo por perfil: evita mezclar geometría de perfiles o videos distintos."""
    digest = hashlib.sha1(str(Path(profile_path).resolve()).encode("utf-8")).hexdigest()[:12]
    return AUTOSAVE_DIR / f".autosave_{digest}.json"


def load_checkpoint(profile_path):
    try:
        return json.loads(checkpoint_path(profile_path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_checkpoint(profile_path, state):
    path = checkpoint_path(profile_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(state, _autosave_timestamp=time.time()), indent=2))
    except OSError as error:
        log.warning("Error guardando checkpoint: %s", error)


def clear_checkpoint(profile_path):
    checkpoint_path(profile_path).unlink(missing_ok=True)


def usable_checkpoint(profile_path, video_path):
    """Checkpoint reciente del mismo perfil y video, o None."""
    state = load_checkpoint(profile_path)
    if not state or time.time() - state.get("_autosave_timestamp", 0) > CHECKPOINT_TTL_S:
        return None
    return state if state.get("video_path") == video_path else None


def _geometry(elements):
    return {name: [list(point) for point in points] for name, points in elements.items()}


class AutoSaveManager:
    """Autosave periódico integrado con Tkinter."""

    def __init__(self, app, interval_ms=AUTOSAVE_INTERVAL_MS):
        self._app = app
        self._interval_ms = interval_ms
        self._job = None
        self._clean = None

    def start(self):
        self.stop()
        self._job = self._app.after(self._interval_ms, self._tick)

    def stop(self):
        if self._job is not None:
            self._app.after_cancel(self._job)
            self._job = None

    def _tick(self):
        self.save_if_dirty()
        self._job = self._app.after(self._interval_ms, self._tick)

    def mark_clean(self, clear=True):
        """El estado actual quedó guardado o recién cargado: no hay checkpoint hasta el próximo cambio."""
        self._clean = self._fingerprint(self.capture_state())
        if clear:
            clear_checkpoint(self._app._output_config)

    def save_if_dirty(self):
        try:
            state = self.capture_state()
            if self._fingerprint(state) == self._clean:
                return False
            save_checkpoint(self._app._output_config, state)
            return True
        except Exception as error:
            log.warning("Error en autosave: %s", error)
            return False

    @staticmethod
    def _fingerprint(state):
        return json.dumps({k: v for k, v in state.items() if k != "current_step"}, sort_keys=True, default=str)

    def capture_state(self):
        app = self._app
        state = dict(
            current_step=app.current_step, video_path=app.video_path, model_path=app._model_path,
            counting_mode=app.counting_mode.get(),
            exclusion_zones=_geometry(app.exclusion_zones), zones=_geometry(app.zones),
            counting_lines=_geometry(app.counting_lines), directions=_geometry(app.directions),
            vehicle_samples=[dict(sample, bbox=list(sample["bbox"])) for sample in app.vehicle_samples],
            sample_constraints=app._loaded_sample_constraints,
            conf_per_class_modified=app._conf_per_class_modified,
            inference_roi=list(app.inference_roi) if app.inference_roi else None,
        )
        state.update({name: getattr(app, name).get() for name in SCALAR_VARS})
        return state

    @classmethod
    def restore_state(cls, app, state):
        """Reemplaza por completo geometría y parámetros con los del checkpoint."""
        app.exclusion_zones = _geometry(state.get("exclusion_zones", {}))
        app.zones = _geometry(state.get("zones", {}))
        app.counting_lines = _geometry(state.get("counting_lines", {}))
        app.directions = _geometry(state.get("directions", {}))
        app._invalidate_excl_cache()
        app._refresh_excl_list()
        app._conf_per_class_modified = state.get("conf_per_class_modified", app._conf_per_class_modified)
        roi = state.get("inference_roi")
        app.inference_roi = [int(v) for v in roi] if roi else None
        for name in SCALAR_VARS:
            if name in state:
                getattr(app, name).set(state[name])
        app.vehicle_samples = list(state.get("vehicle_samples", []))
        app._loaded_sample_constraints = state.get("sample_constraints")
        app.lbl_min_area.config(text=f"{app.min_area.get()} px²")
        app.lbl_max_area.config(text=f"{app.max_area.get()} px²")
        app._update_samples_label()
        mode = state.get("counting_mode", "zones")
        app.counting_mode.set(mode)
        app._set_counting_mode(mode)
        app._activate_step(state.get("current_step", 0))
        app._redraw_zones()
        log.info("Estado restaurado desde checkpoint")
