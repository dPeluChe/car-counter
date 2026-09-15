"""Inicializacion del estado del SetupApp.

Extraido de setup.py.__init__ — aqui viven todas las variables de Tk
agrupadas por dominio (calibracion, zonas, lineas, direcciones, SAHI, etc).

Uso:
    init_state(self)   # inicializa todos los atributos del SetupApp
"""

import tkinter as tk


def init_state(app, *, video_path: str, model_path: str, output_config: str):
    """Inicializa todos los atributos de estado del SetupApp.

    Args:
        app: instancia SetupApp (tk.Tk subclass)
        video_path: ruta al video por defecto
        model_path: ruta al modelo
        output_config: ruta al config.json a generar
    """
    # Rutas (compartidas con mixins via self._model_path, self._output_config)
    app._model_path = model_path
    app._output_config = output_config

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
    app.conf_threshold = tk.DoubleVar(value=0.10)
    app.infer_imgsz = tk.IntVar(value=1600)
    app.min_area = tk.IntVar(value=0)
    app.max_area = tk.IntVar(value=999999)
    app.vehicle_samples = []
    app.calib_confirmed = False
    app.calib_test_passed = False
    app.conf_car = tk.DoubleVar(value=0.10)
    app.conf_motorbike = tk.DoubleVar(value=0.10)
    app.conf_bus = tk.DoubleVar(value=0.10)
    app.conf_truck = tk.DoubleVar(value=0.10)
    app.conf_van = tk.DoubleVar(value=0.10)
    app._conf_per_class_modified = False

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

    # Nombre fijado al empezar cada dibujo: el original solo se reemplaza al cerrar el nuevo
    app._zone_draw_name = app._excl_draw_name = None
    app._line_draw_name = app._direction_draw_name = None
    app._fit_pending = True

    # SAHI / tracker
    app.sahi_enabled = tk.BooleanVar(value=False)
    app.slice_w = tk.IntVar(value=512)
    app.slice_h = tk.IntVar(value=512)
    app.overlap = tk.DoubleVar(value=0.2)
    app.nms_threshold = tk.DoubleVar(value=0.3)
    app.max_age = tk.IntVar(value=40)
    app.min_hits = tk.IntVar(value=3)
    app.iou_thresh = tk.DoubleVar(value=0.2)
    app.track_low_thresh = tk.DoubleVar(value=0.1)
    app.track_high_thresh = tk.DoubleVar(value=0.25)
    app.new_track_thresh = tk.DoubleVar(value=0.25)
    app.track_buffer = tk.IntVar(value=30)
    app.fuse_score = tk.BooleanVar(value=False)
    app._tile_grid_visible = True

    # Config cargada (para merge al guardar)
    app._loaded_config = None
    app._loaded_sample_constraints = None

    # Paso actual
    app.current_step = 0
