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
from tkinter import messagebox
import os

from carcounter.paths import paths
from carcounter.autosave import AutoSaveManager, usable_checkpoint

from setup_panels.canvas import CanvasMixin
from setup_panels.video_model import VideoModelMixin
from setup_panels.config_loader import ConfigLoaderMixin
from setup_panels.step0_exclusion import ExclusionMixin
from setup_panels.step1_calibration import CalibrationMixin
from setup_panels.calib_tests import CalibTestsMixin
from setup_panels.step2_zones import ZonesMixin
from setup_panels.step2_lines import LinesMixin
from setup_panels.step2_directions import DirectionsMixin
from setup_panels.step2_preview import PreviewMixin
from setup_panels.step2_validation import ZoneValidationMixin
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
class SetupApp(CanvasMixin, VideoModelMixin, ConfigLoaderMixin, ExclusionMixin,
               CalibrationMixin, CalibTestsMixin, ZonesMixin, LinesMixin, DirectionsMixin,
               PreviewMixin, ZoneValidationMixin, SAHIMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Car Counter — Configurador")
        self.geometry("1500x900")
        self.configure(bg="#1E1E2E")
        self.resizable(True, True)

        # carcounter/app.py sobreescribe DEFAULT_VIDEO antes de instanciar; se lee aqui, no al importar
        self._default_video = DEFAULT_VIDEO
        # Inicializacion de estado (variables de Tk por dominio) — ver setup_panels/state.py
        init_state(self, video_path=DEFAULT_VIDEO, model_path=MODEL_PATH,
                   output_config=OUTPUT_CONFIG)

        self._autosave = AutoSaveManager(self)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-z>", lambda e: self._undo_last_point())
        self._load_video_and_model()
        # after_idle corre al entrar a mainloop, ya con el --config cargado
        self.after_idle(self._check_autosave_checkpoint)

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
        self.canvas.bind("<Configure>", self._on_canvas_configure)
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
    # Navegación entre pasos
    # ──────────────────────────────────────────────
    def _check_autosave_checkpoint(self):
        """Ofrece restaurar el checkpoint de este perfil y video; si se rechaza, se descarta."""
        state = usable_checkpoint(self._output_config, self.video_path)
        restore = state is not None and messagebox.askyesno(
            "Sesión anterior",
            f"Hay cambios sin guardar de {os.path.basename(self._output_config)} "
            "de una sesión anterior.\n\n¿Restaurarlos? Reemplazan la geometría y los parámetros cargados.")
        self._autosave.mark_clean(clear=not restore)
        if restore:
            AutoSaveManager.restore_state(self, state)
            self.status_var.set("Sesión restaurada desde el checkpoint (aún sin guardar)")
        self._autosave.start()

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

        # Cambiar de pestaña cancela el dibujo a medias; el elemento original sigue intacto
        self.calib_drawing = self.zone_drawing = self.excl_drawing = False
        self.line_drawing = self.direction_drawing = False
        self.current_zone_pts, self.excl_current_pts = [], []
        self.line_start = self.direction_start = None
        self.canvas.config(cursor="arrow" if idx == 3 else "crosshair")
        if idx == 2:
            self._redraw_zones()
        elif idx == 3:
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
