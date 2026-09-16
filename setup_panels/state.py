"""Estado del SetupApp: todas las variables de Tk agrupadas por dominio."""

import tkinter as tk

from carcounter.app_config import SAHIConfig, SettingsConfig, TrackerConfig
# Una sola lista de variables escalares; vive en autosave porque carcounter no puede depender de setup_panels
from carcounter.autosave import SCALAR_VARS


def init_state(app, *, video_path: str, model_path: str, output_config: str):
    """Inicializa los atributos del SetupApp; los valores por defecto salen del esquema."""
    settings, sahi, tracker = SettingsConfig(), SAHIConfig(), TrackerConfig()

    # Rutas (compartidas con mixins via self._model_path, self._output_config)
    app._model_path = model_path
    app._output_config = output_config
    # --model explicito gana sobre el model_path del perfil que se cargue despues
    app._model_override = False

    # Estado general
    app.video_path = video_path
    app.model = None
    app.sahi_model = None
    app.frame_orig = None
    app.frame_rgb = None
    app.img_h = app.img_w = 0
    app.total_frames = 0
    app.current_frame_idx = 0
    app._nav_cap = None  # VideoCapture persistente para navegacion

    # Zoom / pan
    app.zoom = 1.0
    app.pan_x = app.pan_y = 0
    app.drag_start = None
    app.pan_mode = False

    # Calibracion
    app.calib_rect_start = None
    app.calib_rect_end = None
    app.calib_drawing = False
    app.conf_threshold = tk.DoubleVar(value=settings.conf_threshold)
    app.infer_imgsz = tk.IntVar(value=settings.imgsz)
    app.min_area = tk.IntVar(value=settings.min_area)
    app.max_area = tk.IntVar(value=settings.max_area)
    app.vehicle_samples = []
    app.calib_test_passed = False
    app.conf_car = tk.DoubleVar(value=settings.conf_threshold)
    app.conf_motorbike = tk.DoubleVar(value=settings.conf_threshold)
    app.conf_bus = tk.DoubleVar(value=settings.conf_threshold)
    app.conf_truck = tk.DoubleVar(value=settings.conf_threshold)
    app.conf_van = tk.DoubleVar(value=settings.conf_threshold)
    app._conf_per_class_modified = False

    # ROI de inferencia: fuera de ella el pipeline no detecta nada
    app.inference_roi = None
    app.roi_drawing = False
    app.roi_start = None
    app.roi_end = None

    # Zonas de exclusion
    app.exclusion_zones = {}
    app._excl_np_cached = None
    app.excl_current_pts = []
    app.excl_drawing = False
    app.excl_zone_name = tk.StringVar(value="Exclusion 1")
    app.excl_selected = tk.StringVar(value="")

    # Modo de conteo
    app.counting_mode = tk.StringVar(value="zones")

    # Zonas de transito
    app.zones = {}
    app.current_zone_pts = []
    app.zone_drawing = False
    app.current_zone_name = tk.StringVar(value="Norte")

    # Lineas de cruce
    app.counting_lines = {}
    app.line_drawing = False
    app.line_start = None
    app.current_line_name = tk.StringVar(value="Línea 1")
    app.display_frame_zones = None

    # Direcciones (modo directions)
    app.directions = {}
    app.direction_drawing = False
    app.direction_start = None
    app.current_direction_name = tk.StringVar(value="Norte")

    # Preview
    app._preview_playing = False
    app._preview_job = None
    app._preview_cap = None
    app._preview_frame_idx = 0
    app._preview_show_detections = False
    app._preview_last_frame = None
    # La inferencia del preview corre en un hilo; estas cajas son del ultimo frame que alcanzo a terminar
    app._preview_detections = []
    app._preview_infer_busy = False
    app._preview_error = None

    # Nombre fijado al empezar cada dibujo: el original solo se reemplaza al cerrar el nuevo
    app._zone_draw_name = app._excl_draw_name = None
    app._line_draw_name = app._direction_draw_name = None
    app._fit_pending = True

    # SAHI / tracker
    # SAHI arranca apagado aunque el esquema lo traiga en True: encenderlo sin querer multiplica el costo por tile
    app.sahi_enabled = tk.BooleanVar(value=False)
    app.slice_w = tk.IntVar(value=sahi.slice_width)
    app.slice_h = tk.IntVar(value=sahi.slice_height)
    app.overlap = tk.DoubleVar(value=sahi.overlap_ratio)
    app.nms_threshold = tk.DoubleVar(value=sahi.nms_threshold)
    app.max_age = tk.IntVar(value=tracker.max_age)
    app.min_hits = tk.IntVar(value=tracker.min_hits)
    app.iou_thresh = tk.DoubleVar(value=tracker.iou_threshold)
    app.track_low_thresh = tk.DoubleVar(value=tracker.track_low_thresh)
    app.track_high_thresh = tk.DoubleVar(value=tracker.track_high_thresh)
    app.new_track_thresh = tk.DoubleVar(value=tracker.new_track_thresh)
    app.track_buffer = tk.IntVar(value=tracker.track_buffer)
    app.fuse_score = tk.BooleanVar(value=tracker.fuse_score)
    app._tile_grid_visible = True

    # Config cargada (para merge al guardar)
    app._loaded_config = None
    app._loaded_sample_constraints = None

    # Paso actual
    app.current_step = 0
