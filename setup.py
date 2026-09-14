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
from carcounter.autosave import AutoSaveManager, has_checkpoint, load_checkpoint, get_checkpoint_age

from setup_panels.canvas import CanvasMixin
from setup_panels.step0_exclusion import ExclusionMixin
from setup_panels.step1_calibration import CalibrationMixin
from setup_panels.calib_tests import CalibTestsMixin
from setup_panels.step2_zones import ZonesMixin
from setup_panels.step2_lines import LinesMixin
from setup_panels.step2_directions import DirectionsMixin
from setup_panels.step2_preview import PreviewMixin
from setup_panels.step3_sahi import SAHIMixin
from setup_panels.state import init_state

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
class SetupApp(CanvasMixin, ExclusionMixin, CalibrationMixin, CalibTestsMixin,
               ZonesMixin, LinesMixin, DirectionsMixin, PreviewMixin,
               SAHIMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Car Counter — Configurador")
        self.geometry("1500x900")
        self.configure(bg="#1E1E2E")
        self.resizable(True, True)

        # Inicializacion de estado (variables de Tk por dominio) — ver setup_panels/state.py
        init_state(self, video_path=DEFAULT_VIDEO, model_path=MODEL_PATH,
                   output_config=OUTPUT_CONFIG)

        self._autosave = AutoSaveManager(self)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-z>", lambda e: self._undo_last_point())
        self._load_video_and_model()
        self._check_autosave_checkpoint()
        self._autosave.start()

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
        tk.Button(header, text="🧠  Modelos", command=self._show_model_manager,
                  bg="#313244", fg="#A6E3A1", relief="flat", padx=10,
                  font=("Arial", 10, "bold")).pack(side="right", padx=4, pady=4)
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
        sidebar_wrap = tk.Frame(self.content, bg="#181825", width=320)
        sidebar_wrap.pack(side="left", fill="y")
        sidebar_wrap.pack_propagate(False)
        self._sidebar_canvas = tk.Canvas(sidebar_wrap, bg="#181825", highlightthickness=0)
        scrollbar = tk.Scrollbar(sidebar_wrap, orient="vertical", command=self._sidebar_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self._sidebar_canvas.pack(side="left", fill="both", expand=True)
        self._sidebar_canvas.configure(yscrollcommand=scrollbar.set)
        self.sidebar = tk.Frame(self._sidebar_canvas, bg="#181825")
        sidebar_window = self._sidebar_canvas.create_window((0, 0), window=self.sidebar, anchor="nw")
        self.sidebar.bind("<Configure>", lambda event: self._sidebar_canvas.configure(
            scrollregion=self._sidebar_canvas.bbox("all")))
        self._sidebar_canvas.bind("<Configure>", lambda event: self._sidebar_canvas.itemconfigure(
            sidebar_window, width=event.width))

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
        self.bind_all("<Escape>", self._on_escape)

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
            self._clear_vehicle_samples()
            self._reset_calib()

    # ──────────────────────────────────────────────
    # Model Manager Dialog
    # ──────────────────────────────────────────────
    def _show_model_manager(self):
        from carcounter.ui_models import show_model_dialog
        show_model_dialog(self, on_select=self._on_model_selected)

    def _on_model_selected(self, name, path):
        """Callback cuando se selecciona un modelo en el dialogo."""
        if path:
            model = YOLO(path)
            self._model_path = path
            self.model = model
            self.sahi_model = None
            self.calib_test_passed = self.calib_confirmed = False
            self.status_var.set(f"Modelo cambiado a {name}")

    # ──────────────────────────────────────────────
    # Config load
    # ──────────────────────────────────────────────
    def _load_from_config(self, path):
        try:
            cfg = load_config(path)
        except Exception as e:
            messagebox.showerror("Error cargando config", str(e))
            return

        cfg_model = cfg.get("model_path")
        if cfg_model and cfg_model != self._model_path:
            try:
                self._on_model_selected(os.path.basename(cfg_model), cfg_model)
            except Exception as error:
                messagebox.showerror("Modelo de configuración", str(error))
                return
        self.sahi_enabled.set(cfg.get("sahi", {}).get("enabled", True))
        self.vehicle_samples = cfg.get("settings", {}).get("vehicle_samples", [])
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
            self._release_nav_cap()
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
        for key in ("track_low_thresh", "track_high_thresh", "new_track_thresh", "track_buffer", "fuse_score"):
            _set(getattr(self, key), cfg.get("tracker", {}).get(key))
        if p["min_area"] is not None:
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        if p["max_area"] is not None:
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
        cp = p["conf_per_class"]
        if cp:
            _set(self.conf_car, cp.get("car"))
            _set(self.conf_motorbike, cp.get("motorbike", cp.get("motor", cp.get("motorcycle"))))
            _set(self.conf_bus, cp.get("bus"))
            _set(self.conf_truck, cp.get("truck"))
            _set(self.conf_van, cp.get("van"))
            self._conf_per_class_modified = True

        n = len(self.zones)
        self.status_var.set(
            f"✅ Config cargada: {n} zona{'s' if n != 1 else ''} — {os.path.basename(path)}")

    # ──────────────────────────────────────────────
    # Navegación entre pasos
    # ──────────────────────────────────────────────
    def _check_autosave_checkpoint(self):
        """Ofrece restaurar desde checkpoint si existe."""
        if not has_checkpoint():
            return
        age = get_checkpoint_age()
        if age is None or age > 86400:  # > 24h, ignorar
            return
        age_str = f"{int(age // 60)} min" if age < 3600 else f"{int(age // 3600)}h"
        if messagebox.askyesno(
            "Sesion anterior",
            f"Se encontro un checkpoint de hace {age_str}.\n"
            "¿Restaurar la sesion anterior?",
        ):
            state = load_checkpoint()
            if state:
                AutoSaveManager.restore_state(self, state)
                self.status_var.set("Sesion restaurada desde checkpoint")

    def _on_close(self):
        self._autosave.stop()
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
        self._sidebar_canvas.yview_moveto(0)

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
