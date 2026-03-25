"""
setup.py — Car Counter Configurator
====================================
Herramienta interactiva de configuracion para el contador de vehiculos.

Flujo guiado en 4 pasos:
  PASO 0 - EXCLUSION: Define zonas donde no contar vehiculos (estacionados, etc.)
  PASO 1 - CALIBRACION: Dibuja un recuadro sobre un auto -> YOLO lo valida
  PASO 2 - ZONAS/LINEAS: Define zonas poligonales A->B o lineas de cruce
  PASO 3 - SAHI: Previsualiza la cuadricula de tiles -> Guardar config.json

Genera: config.json con zonas, calibracion y parametros SAHI/tracker.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import cv2
import os
from ultralytics import YOLO

from carcounter.paths import paths
from carcounter.config_io import load_config, parse_exclusion_zones, parse_zones, parse_lines, parse_settings

from setup_panels.canvas import CanvasMixin
from setup_panels.step0_exclusion import ExclusionMixin
from setup_panels.step1_calibration import CalibrationMixin
from setup_panels.step2_zones import ZonesMixin
from setup_panels.step3_sahi import SAHIMixin

# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────
MODEL_PATH = str(paths.default_model)
DEFAULT_VIDEO = str(paths.default_video)
OUTPUT_CONFIG = str(paths.default_config)

STEP_TITLES = [
    "PASO 0 — Zonas de Exclusión",
    "PASO 1 — Calibración de Detección",
    "PASO 2 — Zonas / Líneas de Conteo",
    "PASO 3 — Configuración SAHI y Guardar",
]


# ─────────────────────────────────────────────
# Aplicación principal (compone los mixins)
# ─────────────────────────────────────────────
class SetupApp(CanvasMixin, ExclusionMixin, CalibrationMixin, ZonesMixin, SAHIMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Car Counter — Configurador")
        self.geometry("1500x900")
        self.configure(bg="#1E1E2E")
        self.resizable(True, True)

        # Rutas (accesibles por mixins via self._model_path, self._output_config)
        self._model_path = MODEL_PATH
        self._output_config = OUTPUT_CONFIG

        # ── Estado general ────────────────────────
        self.video_path = DEFAULT_VIDEO
        self.model = None
        self.sahi_model = None
        self.frame_orig = None
        self.frame_rgb = None
        self.img_h = self.img_w = 0
        self.total_frames = 0
        self.current_frame_idx = 0
        self._nav_cap = None  # VideoCapture persistente para navegacion de frames

        # Zoom / pan
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0
        self.drag_start = None
        self.pan_mode = False

        # Calibración
        self.calib_rect_start = None
        self.calib_rect_end = None
        self.calib_drawing = False
        self.conf_threshold = tk.DoubleVar(value=0.10)
        self.infer_imgsz = tk.IntVar(value=1600)
        self.min_area = tk.IntVar(value=0)
        self.max_area = tk.IntVar(value=999999)
        self.vehicle_samples = []
        self.calib_confirmed = False
        self.calib_test_passed = False
        self.conf_car = tk.DoubleVar(value=0.10)
        self.conf_motorbike = tk.DoubleVar(value=0.10)
        self.conf_bus = tk.DoubleVar(value=0.10)
        self.conf_truck = tk.DoubleVar(value=0.10)
        self._conf_per_class_modified = False

        # Zonas de exclusión
        self.exclusion_zones = {}
        self._excl_np_cached = None
        self.excl_current_pts = []
        self.excl_drawing = False
        self.excl_zone_name = tk.StringVar(value="Exclusion 1")
        self.excl_selected = tk.StringVar(value="")

        # Modo de conteo
        self.counting_mode = tk.StringVar(value="zones")

        # Zonas de tránsito
        self.zones = {}
        self.current_zone_pts = []
        self.zone_drawing = False
        self.current_zone_name = tk.StringVar(value="Norte")

        # Líneas de cruce
        self.counting_lines = {}
        self.line_drawing = False
        self.line_start = None
        self.current_line_name = tk.StringVar(value="Línea 1")
        self.display_frame_zones = None

        # Preview
        self._preview_playing = False
        self._preview_job = None
        self._preview_cap = None
        self._preview_frame_idx = 0
        self._preview_show_detections = False

        # SAHI / tracker
        self.slice_w = tk.IntVar(value=512)
        self.slice_h = tk.IntVar(value=512)
        self.overlap = tk.DoubleVar(value=0.2)
        self.nms_threshold = tk.DoubleVar(value=0.3)
        self.max_age = tk.IntVar(value=40)
        self.min_hits = tk.IntVar(value=3)
        self.iou_thresh = tk.DoubleVar(value=0.2)
        self._tile_grid_visible = True

        # Config cargada (para merge al guardar)
        self._loaded_config = None
        self._loaded_sample_constraints = None

        # Paso actual
        self.current_step = 0

        # ── UI ────────────────────────────────────
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-z>", lambda e: self._undo_last_point())
        self._load_video_and_model()

    # ──────────────────────────────────────────────
    # UI principal
    # ──────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#11111B", pady=8)
        header.pack(fill="x")
        tk.Label(header, text="🎯  Car Counter — Configurador",
                 bg="#11111B", fg="#CDD6F4", font=("Arial", 15, "bold")).pack(side="left", padx=20)
        tk.Button(header, text="📂  Cambiar Video", command=self._choose_video,
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=10).pack(side="right", padx=20, pady=4)
        self.lbl_video = tk.Label(header, text=f"Video: {self.video_path}",
                                  bg="#11111B", fg="#A6ADC8", font=("Arial", 9))
        self.lbl_video.pack(side="right", padx=10)

        # Step tabs
        self.tab_bar = tk.Frame(self, bg="#181825", pady=6)
        self.tab_bar.pack(fill="x")
        self.tab_btns = []
        for i, title in enumerate(STEP_TITLES):
            btn = tk.Button(self.tab_bar, text=f"  {title}  ",
                            command=lambda idx=i: self._go_to_step(idx),
                            bg="#313244", fg="#A6ADC8", relief="flat",
                            font=("Arial", 10), padx=12, pady=6)
            btn.pack(side="left", padx=4)
            self.tab_btns.append(btn)

        # Content area
        self.content = tk.Frame(self, bg="#1E1E2E")
        self.content.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(self.content, bg="#181825", width=300)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Canvas
        canvas_wrap = tk.Frame(self.content, bg="#1E1E2E")
        canvas_wrap.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_wrap, bg="#11111B", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        # Canvas events
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>", self._on_rpress)
        self.canvas.bind("<B3-Motion>", self._on_rpan)
        self.canvas.bind("<ButtonRelease-3>", self._on_rrelease)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<Button-4>", self._on_zoom)
        self.canvas.bind("<Button-5>", self._on_zoom)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.bind_all("<KeyPress-space>", self._enter_pan_mode)
        self.bind_all("<KeyRelease-space>", self._exit_pan_mode)

        # Status bar
        self.status_var = tk.StringVar(value="Cargando modelo YOLO…")
        tk.Label(self, textvariable=self.status_var, bg="#11111B", fg="#A6E3A1",
                 font=("Courier", 9), anchor="w", padx=12).pack(fill="x", side="bottom")

        # Paneles de cada paso (delegados a mixins)
        self._build_panel_excl()     # Paso 0
        self._build_panel_calib()    # Paso 1
        self._build_panel_zones()    # Paso 2
        self._build_panel_sahi()     # Paso 3
        self._activate_step(0)

    def _lbl(self, parent, text, bold=False, color="#A6ADC8"):
        font = ("Arial", 9, "bold") if bold else ("Arial", 9)
        tk.Label(parent, text=text, bg="#181825", fg=color,
                 font=font, justify="left", anchor="w",
                 wraplength=270).pack(fill="x", pady=2)

    # ──────────────────────────────────────────────
    # Video y modelo
    # ──────────────────────────────────────────────
    def _load_video_and_model(self):
        self.status_var.set("Cargando modelo YOLO…")
        self.update()
        try:
            self.model = YOLO(self._model_path)
            self.status_var.set(f"✅ Modelo cargado: {self._model_path}")
        except Exception as e:
            self.status_var.set(f"❌ Error cargando modelo: {e}")
            messagebox.showerror("Error", f"No se pudo cargar el modelo YOLO:\n{e}")
        self._load_frame()

    def _load_frame(self):
        self._load_frame_at(0)

    def _ensure_nav_cap(self):
        """Abre o reutiliza el VideoCapture para navegacion."""
        if self._nav_cap is None or not self._nav_cap.isOpened():
            self._nav_cap = cv2.VideoCapture(self.video_path)
        return self._nav_cap

    def _release_nav_cap(self):
        if self._nav_cap is not None:
            self._nav_cap.release()
            self._nav_cap = None

    def _load_frame_at(self, frame_idx):
        cap = self._ensure_nav_cap()
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            frame_idx = max(0, min(total_frames - 1, frame_idx))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            self._release_nav_cap()
            messagebox.showerror("Error", f"No se pudo leer el video:\n{self.video_path}")
            return
        self.frame_orig = frame.copy()
        self.frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.img_h, self.img_w = frame.shape[:2]
        self.total_frames = max(1, total_frames)
        self.current_frame_idx = frame_idx
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0
        self.lbl_video.config(text=f"Video: {os.path.basename(self.video_path)}  ({self.img_w}×{self.img_h})")
        self.lbl_frame_info.config(text=f"Frame {self.current_frame_idx + 1}/{self.total_frames}")
        self.display_frame_zones = self.frame_rgb.copy()
        self._redraw()
        self.status_var.set(f"Video cargado: {self.img_w}x{self.img_h}")

    def _step_frame(self, delta):
        self._load_frame_at(self.current_frame_idx + delta)
        self._reset_calib()
        self.status_var.set(
            f"Frame {self.current_frame_idx + 1}/{self.total_frames} cargado. "
            "Repite la calibración en este frame.")

    def _choose_video(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV"), ("Todos", "*.*")])
        if path:
            self._release_nav_cap()
            self.video_path = path
            self._load_frame()
            self._reset_calib()

    # ──────────────────────────────────────────────
    # Config load
    # ──────────────────────────────────────────────
    def _load_from_config(self, path):
        try:
            cfg = load_config(path)
        except Exception as e:
            messagebox.showerror("Error cargando config", str(e))
            return

        excl = parse_exclusion_zones(cfg)
        if excl:
            self.exclusion_zones = excl
            self._invalidate_excl_cache()
            self._refresh_excl_list()
            n = len(self.exclusion_zones) + 1
            while f"Exclusion {n}" in self.exclusion_zones:
                n += 1
            self.excl_zone_name.set(f"Exclusion {n}")

        cfg_video = cfg.get("video_path", "")
        if cfg_video and cfg_video != self.video_path \
                and os.path.isfile(cfg_video) and self.video_path == DEFAULT_VIDEO:
            self.video_path = cfg_video
            self._load_frame()

        loaded_mode = cfg.get("counting_mode", "zones")
        self.counting_mode.set(loaded_mode)
        self._set_counting_mode(loaded_mode)

        zones = parse_zones(cfg)
        if zones:
            self.zones = zones
        lines = parse_lines(cfg)
        if lines:
            self.counting_lines = lines

        self._refresh_zones_list()
        self._redraw_zones()

        self._loaded_config = cfg

        # Aplicar settings/sahi/tracker al estado Tk
        p = parse_settings(cfg)
        sc = p["sample_constraints"]
        if sc:
            self._loaded_sample_constraints = sc
            self.lbl_samples_info.config(
                text=f"Muestras: cargadas  w[{sc['min_width']}–{sc['max_width']}] h[{sc['min_height']}–{sc['max_height']}]")
        # Mapeo campo → (tk_var, label_widget_opcional)
        _set = lambda var, val: var.set(val) if val is not None else None
        _set(self.min_area, p["min_area"])
        _set(self.max_area, p["max_area"])
        _set(self.conf_threshold, p["conf_threshold"])
        _set(self.infer_imgsz, p["imgsz"])
        _set(self.slice_w, p["slice_width"])
        _set(self.slice_h, p["slice_height"])
        _set(self.overlap, p["overlap_ratio"])
        _set(self.nms_threshold, p["nms_threshold"])
        _set(self.max_age, p["max_age"])
        _set(self.min_hits, p["min_hits"])
        _set(self.iou_thresh, p["iou_threshold"])
        if p["min_area"] is not None:
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        if p["max_area"] is not None:
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
        cp = p["conf_per_class"]
        if cp:
            _set(self.conf_car, cp.get("car"))
            _set(self.conf_motorbike, cp.get("motorbike"))
            _set(self.conf_bus, cp.get("bus"))
            _set(self.conf_truck, cp.get("truck"))
            self._conf_per_class_modified = True

        n = len(self.zones)
        self.status_var.set(
            f"✅ Config cargada: {n} zona{'s' if n != 1 else ''} — {os.path.basename(path)}")

    # ──────────────────────────────────────────────
    # Navegación entre pasos
    # ──────────────────────────────────────────────
    def _on_close(self):
        self._stop_zone_preview()
        self._release_nav_cap()
        self.destroy()

    def _go_to_step(self, idx):
        self._activate_step(idx)

    def _activate_step(self, idx):
        self._stop_zone_preview()
        self.current_step = idx
        for i, btn in enumerate(self.tab_btns):
            if i == idx:
                btn.config(bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"))
            else:
                btn.config(bg="#313244", fg="#A6ADC8", font=("Arial", 10))

        for panel in [self.panel_step0, self.panel_step1, self.panel_step2, self.panel_step3]:
            panel.pack_forget()
        panels = [self.panel_step0, self.panel_step1, self.panel_step2, self.panel_step3]
        panels[idx].pack(fill="both", expand=True)

        if idx == 0:
            self.canvas.config(cursor="crosshair")
            self.calib_drawing = False
            self.zone_drawing = False
            self.line_drawing = False
            self.excl_drawing = False
        elif idx == 1:
            self.canvas.config(cursor="crosshair")
            self.calib_drawing = False
            self.zone_drawing = False
        elif idx == 2:
            self.canvas.config(cursor="crosshair")
            self.calib_drawing = False
            self.zone_drawing = False
            self._redraw_zones()
        elif idx == 3:
            self.canvas.config(cursor="arrow")
            self.zone_drawing = False
            self.calib_drawing = False
            self._update_tile_preview()

        self._redraw()

    # ──────────────────────────────────────────────
    # Eventos de canvas (dispatcher)
    # ──────────────────────────────────────────────
    def _on_press(self, event):
        if self.pan_mode:
            self.drag_start = (event.x, event.y)
            return
        if self.current_step == 0:
            self._on_excl_press(event)
        elif self.current_step == 1:
            self._on_calib_press(event)
        elif self.current_step == 2:
            self._on_zones_press(event)

    def _on_drag(self, event):
        if self.pan_mode and self.drag_start:
            self.pan_x += event.x - self.drag_start[0]
            self.pan_y += event.y - self.drag_start[1]
            self.drag_start = (event.x, event.y)
            self._clamp_pan()
            self._redraw()
            return
        if self.current_step == 1:
            self._on_calib_drag(event)

    def _on_release(self, event):
        if self.pan_mode:
            self.drag_start = None
            return
        if self.current_step == 1:
            self._on_calib_release(event)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Car Counter — Configurador interactivo")
    parser.add_argument("--video", type=str, default=DEFAULT_VIDEO, help="Ruta al video")
    parser.add_argument("--config", type=str, default=OUTPUT_CONFIG,
                        help="Archivo de configuración (entrada y salida).")
    args = parser.parse_args()

    OUTPUT_CONFIG = args.config
    app = SetupApp()
    app._output_config = OUTPUT_CONFIG
    if args.video != DEFAULT_VIDEO:
        app.video_path = args.video
        app._load_frame()
    if os.path.isfile(args.config):
        app._load_from_config(args.config)
    app.mainloop()
