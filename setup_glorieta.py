"""
setup_glorieta.py
=================
Herramienta interactiva de configuración para el contador de glorietas.

Flujo guiado en 3 pasos:
  PASO 1 - CALIBRACIÓN: Dibuja un recuadro sobre un auto → YOLO lo valida → ajusta hasta confirmar
  PASO 2 - ZONAS: Dibuja polígonos de entrada/salida para cada calle de la glorieta
  PASO 3 - SAHI: Previsualiza la cuadrícula de tiles y ajusta parámetros → Guardar config.json

Genera: config_glorieta.json con zonas, calibración y parámetros SAHI/tracker.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import json
import os
import math
import numpy as np
from PIL import Image, ImageTk
from ultralytics import YOLO

# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────
MODEL_PATH = "models/yolo/yolov11l.pt"
DEFAULT_VIDEO = "assets/glorieta_normal.mp4"
OUTPUT_CONFIG = "config_glorieta.json"
VEHICLE_CLASS_IDS = [2, 3, 5, 7]  # car, motorbike, bus, truck
CALIB_MIN_CONTEXT_PX = 24
CALIB_CONTEXT_RATIO = 0.75
CALIB_TARGET_BOX_SIDE = 160
CALIB_MAX_UPSCALE = 4.0

VEHICLE_CLASSES = {"car", "truck", "bus", "motorbike"}
COCO_NAMES = [
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
    "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa", "pottedplant", "bed",
    "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush"
]

ZONE_COLORS = [
    "#00FF88", "#FF6B6B", "#4ECDC4", "#FFE66D",
    "#A8E6CF", "#FF8B94", "#B8B8FF", "#FFA07A",
]

STEP_TITLES = [
    "PASO 1 — Calibración de Detección",
    "PASO 2 — Definición de Zonas de Calle",
    "PASO 3 — Configuración SAHI y Guardar",
]


# ─────────────────────────────────────────────
# Aplicación principal
# ─────────────────────────────────────────────
class SetupGlorieta(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Configurador de Glorieta — Car Counter")
        self.geometry("1500x900")
        self.configure(bg="#1E1E2E")
        self.resizable(True, True)

        # ── Estado ──────────────────────────────────
        self.video_path = DEFAULT_VIDEO
        self.model = None
        self.sahi_model = None
        self.frame_orig = None   # BGR original del primer frame
        self.frame_rgb = None    # RGB para mostrar
        self.img_h = self.img_w = 0
        self.total_frames = 0
        self.current_frame_idx = 0

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

        # Zonas
        self.zones = {}               # { name: [(x,y)...] }
        self.current_zone_pts = []
        self.zone_drawing = False
        self.current_zone_name = tk.StringVar(value="Norte")
        self.display_frame_zones = None  # Frame con zonas dibujadas para mostrar

        # Preview en movimiento (TODO-007)
        self._preview_playing = False
        self._preview_job = None
        self._preview_cap = None
        self._preview_frame_idx = 0

        # SAHI
        self.slice_w = tk.IntVar(value=512)
        self.slice_h = tk.IntVar(value=512)
        self.overlap = tk.DoubleVar(value=0.2)
        self.nms_threshold = tk.DoubleVar(value=0.3)
        self.max_age = tk.IntVar(value=40)
        self.min_hits = tk.IntVar(value=3)
        self.iou_thresh = tk.DoubleVar(value=0.2)

        # Paso actual
        self.current_step = 0

        # ── UI ──────────────────────────────────────
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)  # OBS-3: liberar recursos al cerrar
        self._load_video_and_model()

    # ──────────────────────────────────────────────
    # Construcción de la UI
    # ──────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#11111B", pady=8)
        header.pack(fill="x")
        tk.Label(header, text="🎯  Configurador de Glorieta — Car Counter Demo",
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

        # Content area (sidebar + canvas)
        self.content = tk.Frame(self, bg="#1E1E2E")
        self.content.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(self.content, bg="#181825", width=300)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Canvas area
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

        self._build_step_panels()
        self._activate_step(0)

    def _build_step_panels(self):
        """Construye los paneles laterales de cada paso (ocultos por defecto)."""
        # ── Panel PASO 1: Calibración ──────────────────────────────────────────
        self.panel_step0 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step0, "CALIBRACIÓN DE DETECCIÓN", bold=True, color="#CDD6F4")
        self._lbl(self.panel_step0,
                  "1. Haz clic y arrastra sobre un\nauto para definir su tamaño.\n"
                  "2. Presiona [Probar YOLO].\n"
                  "3. Ajusta confianza si es necesario.\n"
                  "4. Confirma cuando se detecte\n   ese auto correctamente.\n\n"
                  "Zoom: rueda del mouse\n"
                  "Mover vista: clic der o ESPACIO + arrastrar", color="#A6ADC8")
        self._lbl(self.panel_step0,
                  "Tip aéreo: selecciona un solo auto con un recuadro ajustado.\n"
                  "El test reescala ese recorte para encontrar autos pequeños.",
                  color="#89B4FA")

        tk.Frame(self.panel_step0, bg="#313244", height=1).pack(fill="x", pady=8)

        self._lbl(self.panel_step0, "Frame actual:", color="#CDD6F4")
        self.lbl_frame_info = tk.Label(self.panel_step0, text="Frame 1/1",
                                       bg="#181825", fg="#A6E3A1", font=("Arial", 10))
        self.lbl_frame_info.pack(anchor="w")

        nav_row = tk.Frame(self.panel_step0, bg="#181825")
        nav_row.pack(fill="x", pady=4)
        tk.Button(nav_row, text="⏮ -25", command=lambda: self._step_frame(-25),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=(0, 4))
        tk.Button(nav_row, text="◀ -1", command=lambda: self._step_frame(-1),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=4)
        tk.Button(nav_row, text="+1 ▶", command=lambda: self._step_frame(1),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=4)
        tk.Button(nav_row, text="+25 ⏭", command=lambda: self._step_frame(25),
                  bg="#313244", fg="#CDD6F4", relief="flat", padx=8).pack(side="left", padx=4)

        self._lbl(self.panel_step0, "Umbral de confianza:", color="#CDD6F4")
        row = tk.Frame(self.panel_step0, bg="#181825")
        row.pack(fill="x")
        tk.Scale(row, from_=0.05, to=0.95, resolution=0.05,
                 variable=self.conf_threshold, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(side="left", fill="x", expand=True)
        tk.Label(row, textvariable=tk.StringVar(), bg="#181825", fg="#89B4FA",
                 font=("Arial", 10)).pack(side="right")
        # Live label for conf
        self.lbl_conf_val = tk.Label(self.panel_step0, bg="#181825", fg="#89B4FA",
                                     font=("Arial", 10))
        self.lbl_conf_val.pack()
        self.conf_threshold.trace_add("write", self._update_conf_label)
        self._update_conf_label()

        self._lbl(self.panel_step0, "Resolución de inferencia (imgsz):", color="#CDD6F4")
        tk.Scale(self.panel_step0, from_=640, to=1920, resolution=160,
                 variable=self.infer_imgsz, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")
        self.lbl_imgsz_val = tk.Label(self.panel_step0, bg="#181825", fg="#89B4FA",
                                      font=("Arial", 10))
        self.lbl_imgsz_val.pack()
        self.infer_imgsz.trace_add("write", self._update_imgsz_label)
        self._update_imgsz_label()

        self._lbl(self.panel_step0, "Área mínima detectada:", color="#A6ADC8")
        self.lbl_min_area = tk.Label(self.panel_step0, text="0 px²",
                                     bg="#181825", fg="#A6E3A1", font=("Arial", 10))
        self.lbl_min_area.pack(anchor="w")
        self._lbl(self.panel_step0, "Área máxima detectada:", color="#A6ADC8")
        self.lbl_max_area = tk.Label(self.panel_step0, text="999999 px²",
                                     bg="#181825", fg="#A6E3A1", font=("Arial", 10))
        self.lbl_max_area.pack(anchor="w")
        self.lbl_samples_info = tk.Label(self.panel_step0, text="Muestras: 0",
                                         bg="#181825", fg="#89B4FA", font=("Arial", 10))
        self.lbl_samples_info.pack(anchor="w", pady=(2, 0))

        tk.Frame(self.panel_step0, bg="#313244", height=1).pack(fill="x", pady=8)

        self.btn_yolo_test = tk.Button(self.panel_step0, text="👁  Probar YOLO",
                                       command=self._run_calib_test,
                                       bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"),
                                       relief="flat", pady=6)
        self.btn_yolo_test.pack(fill="x", pady=4)

        self.btn_global_test = tk.Button(self.panel_step0, text="🛰  Vista Global",
                                         command=self._run_global_detection_test,
                                         bg="#F9E2AF", fg="#11111B", font=("Arial", 10, "bold"),
                                         relief="flat", pady=6)
        self.btn_global_test.pack(fill="x", pady=2)

        self.btn_add_sample = tk.Button(self.panel_step0, text="📌 Agregar muestra vehículo",
                                        command=self._add_vehicle_sample,
                                        bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                        relief="flat", pady=6)
        self.btn_add_sample.pack(fill="x", pady=2)

        self.btn_clear_samples = tk.Button(self.panel_step0, text="🧹 Limpiar muestras",
                                           command=self._clear_vehicle_samples,
                                           bg="#313244", fg="#CDD6F4", relief="flat", pady=4)
        self.btn_clear_samples.pack(fill="x", pady=2)

        self.btn_calib_reset = tk.Button(self.panel_step0, text="↺  Limpiar recuadro",
                                         command=self._reset_calib,
                                         bg="#313244", fg="#CDD6F4", relief="flat", pady=4)
        self.btn_calib_reset.pack(fill="x", pady=2)

        self.lbl_calib_status = tk.Label(self.panel_step0, text="⚠  Pendiente de confirmar",
                                          bg="#181825", fg="#F38BA8", font=("Arial", 9))
        self.lbl_calib_status.pack(pady=4)

        self.btn_calib_ok = tk.Button(self.panel_step0, text="✅  Confirmar y continuar →",
                                      command=self._confirm_calib,
                                      bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_calib_ok.pack(fill="x", pady=8)

        # ── Panel PASO 2: Zonas ────────────────────────────────────────────────
        self.panel_step1 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step1, "ZONAS DE CALLE", bold=True, color="#CDD6F4")
        self._lbl(self.panel_step1,
                  "Dibuja un polígono en cada boca\n"
                  "de entrada/salida de la glorieta.\n\n"
                  "• Clic izq: agregar punto\n"
                  "• Clic cerca del primero: cerrar\n"
                  "• Clic der (arrastrar): mover vista\n"
                  "• Rueda: zoom", color="#A6ADC8")

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=8)

        self._lbl(self.panel_step1, "Nombre de la zona:", color="#CDD6F4")
        self.zone_name_entry = ttk.Entry(self.panel_step1,
                                         textvariable=self.current_zone_name,
                                         font=("Arial", 11))
        self.zone_name_entry.pack(fill="x", pady=4)

        self.btn_new_zone = tk.Button(self.panel_step1, text="✏  Nueva Zona (dibujar)",
                                      command=self._start_zone_draw,
                                      bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_new_zone.pack(fill="x", pady=4)

        self.btn_del_zone = tk.Button(self.panel_step1, text="🗑  Eliminar zona seleccionada",
                                      command=self._delete_selected_zone,
                                      bg="#313244", fg="#F38BA8", relief="flat", pady=4)
        self.btn_del_zone.pack(fill="x", pady=2)

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=8)
        self.btn_preview = tk.Button(self.panel_step1, text="▶  Reproducir zonas",
                                     command=self._toggle_zone_preview,
                                     bg="#F9E2AF", fg="#11111B", font=("Arial", 10, "bold"),
                                     relief="flat", pady=6)
        self.btn_preview.pack(fill="x", pady=4)

        tk.Frame(self.panel_step1, bg="#313244", height=1).pack(fill="x", pady=8)
        self._lbl(self.panel_step1, "Zonas guardadas:", color="#CDD6F4")

        self.zones_frame = tk.Frame(self.panel_step1, bg="#181825")
        self.zones_frame.pack(fill="both", expand=True)

        self.selected_zone = tk.StringVar(value="")
        self.zones_listbox = tk.Listbox(self.zones_frame, bg="#11111B", fg="#CDD6F4",
                                         selectbackground="#45475A", font=("Arial", 10),
                                         height=8, relief="flat", bd=0)
        self.zones_listbox.pack(fill="both", expand=True)
        self.zones_listbox.bind("<<ListboxSelect>>", self._on_zone_select)

        self.btn_zones_ok = tk.Button(self.panel_step1, text="✅  Continuar →",
                                      command=self._confirm_zones,
                                      bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_zones_ok.pack(fill="x", pady=8)

        # ── Panel PASO 3: SAHI + Guardar ──────────────────────────────────────
        self.panel_step2 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step2, "PARÁMETROS SAHI", bold=True, color="#CDD6F4")
        self._lbl(self.panel_step2,
                  "SAHI divide el frame en tiles para\n"
                  "detectar autos pequeños/lejanos.\n"
                  "Tiles más pequeños = más precisión\nbut más lento.",
                  color="#A6ADC8")

        tk.Frame(self.panel_step2, bg="#313244", height=1).pack(fill="x", pady=6)

        # Slice size
        params = [
            ("Ancho de tile (px):", self.slice_w, 128, 1024, 128),
            ("Alto de tile (px):", self.slice_h, 128, 1024, 128),
        ]
        for lbl, var, mn, mx, res in params:
            self._lbl(self.panel_step2, lbl, color="#CDD6F4")
            tk.Scale(self.panel_step2, from_=mn, to=mx, resolution=res,
                     variable=var, orient="horizontal",
                     bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                     highlightthickness=0, command=lambda _: self._update_tile_preview()
                     ).pack(fill="x")

        self._lbl(self.panel_step2, "Overlap entre tiles:", color="#CDD6F4")
        tk.Scale(self.panel_step2, from_=0.0, to=0.5, resolution=0.05,
                 variable=self.overlap, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0, command=lambda _: self._update_tile_preview()
                 ).pack(fill="x")

        self._lbl(self.panel_step2, "NMS post-SAHI (IoU threshold):", color="#CDD6F4")
        tk.Scale(self.panel_step2, from_=0.0, to=0.9, resolution=0.05,
                 variable=self.nms_threshold, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")

        self.lbl_tiles = tk.Label(self.panel_step2, text="Tiles por frame: —",
                                   bg="#181825", fg="#89B4FA", font=("Arial", 10))
        self.lbl_tiles.pack(pady=4)

        tk.Frame(self.panel_step2, bg="#313244", height=1).pack(fill="x", pady=6)
        self._lbl(self.panel_step2, "PARÁMETROS SORT FALLBACK", bold=True, color="#CDD6F4")

        tracker_params = [
            ("Max age (frames):", self.max_age, 10, 100, 5),
            ("Min hits:", self.min_hits, 1, 10, 1),
        ]
        for lbl, var, mn, mx, res in tracker_params:
            self._lbl(self.panel_step2, lbl, color="#CDD6F4")
            tk.Scale(self.panel_step2, from_=mn, to=mx, resolution=res,
                     variable=var, orient="horizontal",
                     bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                     highlightthickness=0).pack(fill="x")

        self._lbl(self.panel_step2, "IOU threshold tracker:", color="#CDD6F4")
        tk.Scale(self.panel_step2, from_=0.05, to=0.5, resolution=0.05,
                 variable=self.iou_thresh, orient="horizontal",
                 bg="#181825", fg="#CDD6F4", troughcolor="#313244",
                 highlightthickness=0).pack(fill="x")

        tk.Frame(self.panel_step2, bg="#313244", height=1).pack(fill="x", pady=6)

        tk.Button(self.panel_step2, text="🔲  Ver cuadrícula de tiles",
                  command=self._update_tile_preview,
                  bg="#313244", fg="#CDD6F4", relief="flat", pady=4).pack(fill="x", pady=2)

        self.btn_save = tk.Button(self.panel_step2, text="💾  GUARDAR config_glorieta.json",
                                  command=self._save_config,
                                  bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                  relief="flat", pady=8)
        self.btn_save.pack(fill="x", pady=8)

        self.lbl_save_status = tk.Label(self.panel_step2, text="",
                                         bg="#181825", fg="#A6E3A1", font=("Arial", 9))
        self.lbl_save_status.pack()

    # ──────────────────────────────────────────────
    # Helpers UI
    # ──────────────────────────────────────────────
    def _lbl(self, parent, text, bold=False, color="#A6ADC8"):
        font = ("Arial", 9, "bold") if bold else ("Arial", 9)
        tk.Label(parent, text=text, bg="#181825", fg=color,
                 font=font, justify="left", anchor="w",
                 wraplength=270).pack(fill="x", pady=2)

    def _update_conf_label(self, *_):
        self.lbl_conf_val.config(text=f"Valor: {self.conf_threshold.get():.2f}")

    def _update_imgsz_label(self, *_):
        self.lbl_imgsz_val.config(text=f"Valor: {self.infer_imgsz.get()} px")

    def _update_samples_label(self):
        if not self.vehicle_samples:
            self.lbl_samples_info.config(text="Muestras: 0")
            return
        areas = [s["area"] for s in self.vehicle_samples]
        self.lbl_samples_info.config(
            text=(
                f"Muestras: {len(self.vehicle_samples)}  "
                f"areas {min(areas)}-{max(areas)} px²"
            )
        )

    # ──────────────────────────────────────────────
    # Carga de video y modelo
    # ──────────────────────────────────────────────
    def _load_video_and_model(self):
        self.status_var.set("Cargando modelo YOLO…")
        self.update()
        try:
            self.model = YOLO(MODEL_PATH)
            self.status_var.set(f"✅ Modelo cargado: {MODEL_PATH}")
        except Exception as e:
            self.status_var.set(f"❌ Error cargando modelo: {e}")
            messagebox.showerror("Error", f"No se pudo cargar el modelo YOLO:\n{e}\nVerifica que existe: {MODEL_PATH}")

        self._load_frame()

    def _load_frame(self):
        self._load_frame_at(0)

    def _load_frame_at(self, frame_idx):
        cap = cv2.VideoCapture(self.video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            frame_idx = max(0, min(total_frames - 1, frame_idx))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            messagebox.showerror("Error", f"No se pudo leer el video:\n{self.video_path}")
            return
        self.frame_orig = frame.copy()
        self.frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.img_h, self.img_w = frame.shape[:2]
        self.total_frames = max(1, total_frames)
        self.current_frame_idx = frame_idx
        # Reset zoom/pan
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0
        self.lbl_video.config(text=f"Video: {os.path.basename(self.video_path)}  ({self.img_w}×{self.img_h})")
        self.lbl_frame_info.config(text=f"Frame {self.current_frame_idx + 1}/{self.total_frames}")
        self.display_frame_zones = self.frame_rgb.copy()
        self._redraw()
        self.status_var.set(f"✅ Video cargado: {self.img_w}×{self.img_h}")

    def _step_frame(self, delta):
        self._load_frame_at(self.current_frame_idx + delta)
        self._reset_calib()
        self.status_var.set(
            f"Frame {self.current_frame_idx + 1}/{self.total_frames} cargado. "
            "Repite la calibración en este frame."
        )

    def _load_from_config(self, path):
        """Carga zonas, settings y parámetros SAHI/tracker de un JSON existente (TODO-008)."""
        try:
            with open(path) as f:
                cfg = json.load(f)
        except Exception as e:
            messagebox.showerror("Error cargando config", str(e))
            return

        # ── Video (solo si el usuario no pasó --video explícitamente) ────────────
        cfg_video = cfg.get("video_path", "")
        if cfg_video and cfg_video != self.video_path \
                and os.path.isfile(cfg_video) and self.video_path == DEFAULT_VIDEO:
            self.video_path = cfg_video
            self._load_frame()

        # ── Zonas ──────────────────────────────────────────────────
        raw_zones = cfg.get("zones", {})
        if raw_zones:
            self.zones = {name: [list(p) for p in pts] for name, pts in raw_zones.items()}
            self._refresh_zones_list()
            self._redraw_zones()

        # ── Preservar config completo para merge al guardar (OBS-2) ──────
        self._loaded_config = cfg

        # ── Settings ─────────────────────────────────────────────
        s = cfg.get("settings", {})
        sc = s.get("sample_constraints")
        if sc:
            self._loaded_sample_constraints = sc  # OBS-1: guardar para fallback
        if "min_area" in s:
            self.min_area.set(int(s["min_area"]))
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        if "max_area" in s:
            self.max_area.set(int(s["max_area"]))
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
        if "conf_threshold" in s:
            self.conf_threshold.set(float(s["conf_threshold"]))
        if "imgsz" in s:
            self.infer_imgsz.set(int(s["imgsz"]))

        # ── SAHI ────────────────────────────────────────────────
        sahi = cfg.get("sahi", {})
        if "slice_width" in sahi:    self.slice_w.set(int(sahi["slice_width"]))
        if "slice_height" in sahi:   self.slice_h.set(int(sahi["slice_height"]))
        if "overlap_ratio" in sahi:  self.overlap.set(float(sahi["overlap_ratio"]))
        if "nms_threshold" in sahi:  self.nms_threshold.set(float(sahi["nms_threshold"]))

        # ── Tracker ──────────────────────────────────────────────
        t = cfg.get("tracker", {})
        if "max_age" in t:       self.max_age.set(int(t["max_age"]))
        if "min_hits" in t:      self.min_hits.set(int(t["min_hits"]))
        if "iou_threshold" in t: self.iou_thresh.set(float(t["iou_threshold"]))

        n = len(self.zones)
        self.status_var.set(
            f"✅ Config cargada: {n} zona{'s' if n != 1 else ''} — {os.path.basename(path)}"
        )

    def _choose_video(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV"), ("Todos", "*.*")]
        )
        if path:
            self.video_path = path
            self._load_frame()
            self._reset_calib()

    # ──────────────────────────────────────────────
    # Navegación entre pasos
    # ──────────────────────────────────────────────
    def _on_close(self):
        """Libera el VideoCapture del preview antes de destruir la ventana (OBS-3)."""
        self._stop_zone_preview()
        self.destroy()

    def _go_to_step(self, idx):
        self._activate_step(idx)

    def _activate_step(self, idx):
        self._stop_zone_preview()  # TODO-007: detener preview al cambiar de paso
        self.current_step = idx
        # Highlight active tab
        for i, btn in enumerate(self.tab_btns):
            if i == idx:
                btn.config(bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"))
            else:
                btn.config(bg="#313244", fg="#A6ADC8", font=("Arial", 10))

        # Show correct panel
        for panel in [self.panel_step0, self.panel_step1, self.panel_step2]:
            panel.pack_forget()
        panels = [self.panel_step0, self.panel_step1, self.panel_step2]
        panels[idx].pack(fill="both", expand=True)

        # Update canvas behavior
        if idx == 0:
            self.canvas.config(cursor="crosshair")
            self.calib_drawing = False
            self.zone_drawing = False
        elif idx == 1:
            self.canvas.config(cursor="crosshair")
            self.calib_drawing = False
            self.zone_drawing = False
            self._redraw_zones()
        elif idx == 2:
            self.canvas.config(cursor="arrow")
            self.zone_drawing = False
            self.calib_drawing = False
            self._update_tile_preview()

        self._redraw()

    # ──────────────────────────────────────────────
    # Zoom / Pan
    # ──────────────────────────────────────────────
    def _clamp_pan(self):
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        img_w = self.img_w * self.zoom
        img_h = self.img_h * self.zoom

        if img_w <= cw:
            self.pan_x = (cw - img_w) / 2
        else:
            self.pan_x = min(0, max(cw - img_w, self.pan_x))

        if img_h <= ch:
            self.pan_y = (ch - img_h) / 2
        else:
            self.pan_y = min(0, max(ch - img_h, self.pan_y))

    def _enter_pan_mode(self, _event=None):
        self.pan_mode = True
        self.canvas.config(cursor="fleur")

    def _exit_pan_mode(self, _event=None):
        self.pan_mode = False
        self.drag_start = None
        if self.current_step in (0, 1):
            self.canvas.config(cursor="crosshair")
        else:
            self.canvas.config(cursor="arrow")

    def _on_zoom(self, event):
        factor = 1.1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", None) == 4) else 0.9
        anchor_x = getattr(event, "x", self.canvas.winfo_width() / 2)
        anchor_y = getattr(event, "y", self.canvas.winfo_height() / 2)
        img_x = (anchor_x - self.pan_x) / self.zoom
        img_y = (anchor_y - self.pan_y) / self.zoom

        self.zoom = max(0.1, min(8.0, self.zoom * factor))
        self.pan_x = anchor_x - img_x * self.zoom
        self.pan_y = anchor_y - img_y * self.zoom
        self._clamp_pan()
        self._redraw()

    def _on_rpress(self, event):
        self.drag_start = (event.x, event.y)

    def _on_rpan(self, event):
        if self.drag_start:
            self.pan_x += event.x - self.drag_start[0]
            self.pan_y += event.y - self.drag_start[1]
            self.drag_start = (event.x, event.y)
            self._clamp_pan()
            self._redraw()

    def _on_rrelease(self, event):
        self.drag_start = None

    # ──────────────────────────────────────────────
    # Canvas draw helpers
    # ──────────────────────────────────────────────
    def _img_to_screen(self, x, y):
        return x * self.zoom + self.pan_x, y * self.zoom + self.pan_y

    def _screen_to_img(self, sx, sy):
        return int((sx - self.pan_x) / self.zoom), int((sy - self.pan_y) / self.zoom)

    def _redraw(self):
        if self.frame_rgb is None:
            return
        self.canvas.delete("all")
        cw = self.canvas.winfo_width() or 1000
        ch = self.canvas.winfo_height() or 700

        # Visible region in image coords
        vx = -self.pan_x / self.zoom
        vy = -self.pan_y / self.zoom
        vw = cw / self.zoom
        vh = ch / self.zoom

        x1 = max(0, int(vx))
        y1 = max(0, int(vy))
        x2 = min(self.img_w, int(vx + vw) + 1)
        y2 = min(self.img_h, int(vy + vh) + 1)

        if x2 <= x1 or y2 <= y1:
            return

        # Choose display frame based on step
        src = self.frame_rgb
        if self.current_step == 1 and self.display_frame_zones is not None:
            src = self.display_frame_zones
        elif self.current_step == 2 and self.display_frame_zones is not None:
            src = self.display_frame_zones

        crop = src[y1:y2, x1:x2]
        fw = max(1, int((x2 - x1) * self.zoom))
        fh = max(1, int((y2 - y1) * self.zoom))
        pil = Image.fromarray(crop).resize((fw, fh), Image.Resampling.NEAREST)
        self._tk_img = ImageTk.PhotoImage(pil)

        dx = max(0, self.pan_x) if self.pan_x > 0 else 0
        dy = max(0, self.pan_y) if self.pan_y > 0 else 0
        self.canvas.create_image(dx, dy, image=self._tk_img, anchor="nw")

        # Draw overlays depending on step
        if self.current_step == 0:
            self._draw_calib_overlay()
        elif self.current_step == 1:
            self._draw_zones_overlay()
        elif self.current_step == 2:
            self._draw_tile_overlay()

    def _draw_calib_overlay(self):
        """Dibuja el recuadro de calibración en el canvas."""
        if self.calib_rect_start and self.calib_rect_end:
            sx1, sy1 = self._img_to_screen(*self.calib_rect_start)
            sx2, sy2 = self._img_to_screen(*self.calib_rect_end)
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                          outline="#FFE66D", width=2, dash=(6, 3))
            # Area label
            w = abs(self.calib_rect_end[0] - self.calib_rect_start[0])
            h = abs(self.calib_rect_end[1] - self.calib_rect_start[1])
            area = w * h
            self.canvas.create_text(
                (sx1 + sx2) / 2, min(sy1, sy2) - 10,
                text=f"Area: {area} px²",
                fill="#FFE66D", font=("Arial", 9, "bold")
            )

    def _draw_zones_overlay(self):
        """Dibuja zonas guardadas + polígono actual."""
        for idx, (name, pts) in enumerate(self.zones.items()):
            color = ZONE_COLORS[idx % len(ZONE_COLORS)]
            screen_pts = [self._img_to_screen(p[0], p[1]) for p in pts]
            flat = [coord for pt in screen_pts for coord in pt]
            if len(flat) >= 4:
                self.canvas.create_polygon(flat, outline=color, fill=color + "44", width=2)
                cx = sum(p[0] for p in screen_pts) / len(screen_pts)
                cy = sum(p[1] for p in screen_pts) / len(screen_pts)
                self.canvas.create_text(cx, cy, text=name, fill=color,
                                         font=("Arial", 11, "bold"))

        # Current polygon being drawn
        if self.current_zone_pts:
            screen_pts = [self._img_to_screen(p[0], p[1]) for p in self.current_zone_pts]
            for i in range(len(screen_pts) - 1):
                self.canvas.create_line(screen_pts[i][0], screen_pts[i][1],
                                         screen_pts[i+1][0], screen_pts[i+1][1],
                                         fill="#FF6B6B", width=2)
            for pt in screen_pts:
                self.canvas.create_oval(pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5,
                                         fill="#FF6B6B", outline="white", width=1)
            # Close hint
            if len(screen_pts) > 2:
                p0 = screen_pts[0]
                self.canvas.create_oval(p0[0]-8, p0[1]-8, p0[0]+8, p0[1]+8,
                                         outline="#FFE66D", width=2)

    def _draw_tile_overlay(self):
        """Dibuja la cuadrícula SAHI."""
        if not self.img_w:
            return
        sw = self.slice_w.get()
        sh = self.slice_h.get()
        ov = self.overlap.get()
        step_x = int(sw * (1 - ov))
        step_y = int(sh * (1 - ov))
        if step_x <= 0 or step_y <= 0:
            return

        x = 0
        cols = 0
        while x < self.img_w:
            y = 0
            rows = 0
            while y < self.img_h:
                sx1, sy1 = self._img_to_screen(x, y)
                sx2, sy2 = self._img_to_screen(min(x + sw, self.img_w), min(y + sh, self.img_h))
                self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                              outline="#89B4FA", fill="", width=1, dash=(4, 4))
                y += step_y
                rows += 1
            x += step_x
            cols += 1

        count = cols * rows if rows > 0 else 0
        # Also draw zones on this view
        self._draw_zones_overlay()

    # ──────────────────────────────────────────────
    # PASO 1: Calibración
    # ──────────────────────────────────────────────
    def _on_press(self, event):
        if self.current_step == 0:
            if self.pan_mode:
                self.drag_start = (event.x, event.y)
                return
            ix, iy = self._screen_to_img(event.x, event.y)
            self.calib_rect_start = (ix, iy)
            self.calib_rect_end = (ix, iy)
            self.calib_drawing = True
        elif self.current_step == 1 and self.zone_drawing:
            ix, iy = self._screen_to_img(event.x, event.y)
            # Check if close to first point → close polygon
            if len(self.current_zone_pts) > 2:
                p0 = self.current_zone_pts[0]
                dist = math.hypot(ix - p0[0], iy - p0[1])
                if dist < 20 / self.zoom:
                    self._close_current_zone()
                    return
            self.current_zone_pts.append((ix, iy))
            self._redraw()

    def _on_drag(self, event):
        if self.pan_mode and self.drag_start:
            self.pan_x += event.x - self.drag_start[0]
            self.pan_y += event.y - self.drag_start[1]
            self.drag_start = (event.x, event.y)
            self._clamp_pan()
            self._redraw()
            return
        if self.current_step == 0 and self.calib_drawing:
            ix, iy = self._screen_to_img(event.x, event.y)
            self.calib_rect_end = (ix, iy)
            self._redraw()

    def _on_release(self, event):
        if self.pan_mode:
            self.drag_start = None
            return
        if self.current_step == 0 and self.calib_drawing:
            ix, iy = self._screen_to_img(event.x, event.y)
            self.calib_rect_end = (ix, iy)
            self.calib_drawing = False
            # Update area labels
            if self.calib_rect_start and self.calib_rect_end:
                x1 = min(self.calib_rect_start[0], self.calib_rect_end[0])
                y1 = min(self.calib_rect_start[1], self.calib_rect_end[1])
                x2 = max(self.calib_rect_start[0], self.calib_rect_end[0])
                y2 = max(self.calib_rect_start[1], self.calib_rect_end[1])
                area = max(0, (x2 - x1) * (y2 - y1))
                self.min_area.set(int(area * 0.5))
                self.max_area.set(int(area * 4.0))
                self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
                self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
            self.calib_test_passed = False
            self.calib_confirmed = False
            self.lbl_calib_status.config(text="⚠  Pendiente de confirmar", fg="#F38BA8")
            self._redraw()

    def _reset_calib(self):
        self.calib_rect_start = None
        self.calib_rect_end = None
        self.calib_drawing = False
        self.calib_confirmed = False
        self.calib_test_passed = False
        self.frame_rgb = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB)
        self.lbl_calib_status.config(text="⚠  Pendiente de confirmar", fg="#F38BA8")
        self._redraw()

    def _add_vehicle_sample(self):
        if not (self.calib_rect_start and self.calib_rect_end):
            messagebox.showwarning("Muestras", "Primero dibuja un recuadro sobre un vehículo.")
            return
        x1 = min(self.calib_rect_start[0], self.calib_rect_end[0])
        y1 = min(self.calib_rect_start[1], self.calib_rect_end[1])
        x2 = max(self.calib_rect_start[0], self.calib_rect_end[0])
        y2 = max(self.calib_rect_start[1], self.calib_rect_end[1])
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        aspect = width / float(height)
        self.vehicle_samples.append({
            "bbox": (x1, y1, x2, y2),
            "width": width,
            "height": height,
            "area": area,
            "aspect": aspect,
        })
        self._apply_sample_constraints()
        self._update_samples_label()
        self.lbl_calib_status.config(
            text=f"✅ Muestra agregada ({len(self.vehicle_samples)})",
            fg="#A6E3A1",
        )
        self.status_var.set(
            "Muestra agregada. Marca 5 autos y 1-2 vehículos grandes para afinar filtros."
        )

    def _clear_vehicle_samples(self):
        self.vehicle_samples = []
        self._update_samples_label()
        self.lbl_calib_status.config(text="⚠  Muestras limpiadas", fg="#F9E2AF")
        self.status_var.set("Muestras limpiadas")

    def _sample_constraints(self):
        if not self.vehicle_samples:
            return getattr(self, "_loaded_sample_constraints", None)  # OBS-1: fallback a constraints cargadas
        widths = [s["width"] for s in self.vehicle_samples]
        heights = [s["height"] for s in self.vehicle_samples]
        areas = [s["area"] for s in self.vehicle_samples]
        aspects = [s["aspect"] for s in self.vehicle_samples]
        return {
            "min_width": max(1, int(min(widths) * 0.70)),
            "max_width": int(max(widths) * 1.45),
            "min_height": max(1, int(min(heights) * 0.70)),
            "max_height": int(max(heights) * 1.45),
            "min_area": max(1, int(min(areas) * 0.55)),
            "max_area": int(max(areas) * 1.55),
            "min_aspect": max(0.20, min(aspects) * 0.70),
            "max_aspect": min(6.0, max(aspects) * 1.30),
        }

    def _passes_sample_constraints(self, bbox):
        constraints = self._sample_constraints()
        if constraints is None:
            return True
        x1, y1, x2, y2 = bbox
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        aspect = width / float(height)
        return (
            constraints["min_width"] <= width <= constraints["max_width"]
            and constraints["min_height"] <= height <= constraints["max_height"]
            and constraints["min_area"] <= area <= constraints["max_area"]
            and constraints["min_aspect"] <= aspect <= constraints["max_aspect"]
        )

    def _apply_sample_constraints(self):
        constraints = self._sample_constraints()
        if constraints is None:
            return
        self.min_area.set(constraints["min_area"])
        self.max_area.set(constraints["max_area"])
        self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
        self.lbl_max_area.config(text=f"{self.max_area.get()} px²")

    @staticmethod
    def _bbox_iou(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        denom = area_a + area_b - inter_area
        return inter_area / denom if denom > 0 else 0.0

    @staticmethod
    def _point_in_box(px, py, box):
        x1, y1, x2, y2 = box
        return x1 <= px <= x2 and y1 <= py <= y2

    def _get_calibration_roi(self, selected_box):
        box_w = max(1, selected_box[2] - selected_box[0])
        box_h = max(1, selected_box[3] - selected_box[1])
        pad_x = max(CALIB_MIN_CONTEXT_PX, int(box_w * CALIB_CONTEXT_RATIO))
        pad_y = max(CALIB_MIN_CONTEXT_PX, int(box_h * CALIB_CONTEXT_RATIO))
        return (
            max(0, selected_box[0] - pad_x),
            max(0, selected_box[1] - pad_y),
            min(self.img_w, selected_box[2] + pad_x),
            min(self.img_h, selected_box[3] + pad_y),
        )

    def _get_calibration_scale(self, selected_box):
        box_w = max(1, selected_box[2] - selected_box[0])
        box_h = max(1, selected_box[3] - selected_box[1])
        min_side = max(1, min(box_w, box_h))
        scale = CALIB_TARGET_BOX_SIDE / float(min_side)
        return max(1.0, min(CALIB_MAX_UPSCALE, scale))

    def _ensure_sahi_model(self, conf):
        if self.sahi_model is not None:
            return self.sahi_model
        try:
            from sahi import AutoDetectionModel
        except ImportError:
            return None
        self.sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8",
            model_path=MODEL_PATH,
            confidence_threshold=conf,
            device="cpu",
        )
        return self.sahi_model

    def _predict_roi_boxes(self, roi_frame, conf, scale, use_sahi=False, force_imgsz=None):
        scaled_w = max(1, int(roi_frame.shape[1] * scale))
        scaled_h = max(1, int(roi_frame.shape[0] * scale))
        scaled_frame = cv2.resize(roi_frame, (scaled_w, scaled_h), interpolation=cv2.INTER_CUBIC)
        detections = []

        if use_sahi:
            sahi_model = self._ensure_sahi_model(conf)
            if sahi_model is None:
                return [], "sahi_unavailable"
            from sahi.predict import get_sliced_prediction
            result = get_sliced_prediction(
                scaled_frame,
                sahi_model,
                slice_height=min(512, scaled_h),
                slice_width=min(512, scaled_w),
                overlap_height_ratio=0.2,
                overlap_width_ratio=0.2,
                postprocess_type="NMS",
                postprocess_match_threshold=0.5,
                postprocess_match_metric="IOS",
                verbose=0,
            )
            for pred in result.object_prediction_list:
                cls_name = pred.category.name
                if cls_name not in VEHICLE_CLASSES:
                    continue
                bbox = pred.bbox
                detections.append({
                    "bbox": (
                        int(bbox.minx / scale),
                        int(bbox.miny / scale),
                        int(bbox.maxx / scale),
                        int(bbox.maxy / scale),
                    ),
                    "cls_name": cls_name,
                    "conf": float(pred.score.value),
                })
            return detections, "sahi"

        results = self.model(
            scaled_frame,
            conf=conf,
            verbose=False,
            classes=VEHICLE_CLASS_IDS,
            imgsz=force_imgsz or max(640, max(scaled_w, scaled_h)),
        )
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else "?"
                if cls_name not in VEHICLE_CLASSES:
                    continue
                detections.append({
                    "bbox": (
                        int(x1 / scale),
                        int(y1 / scale),
                        int(x2 / scale),
                        int(y2 / scale),
                    ),
                    "cls_name": cls_name,
                    "conf": float(box.conf[0]),
                })
        return detections, "yolo-upscaled"

    def _draw_detection_overlay(self, detections, frame_origin=(0, 0), frame_base=None, highlight_box=None):
        display = self.frame_orig.copy() if frame_base is None else frame_base.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            x1 += frame_origin[0]
            x2 += frame_origin[0]
            y1 += frame_origin[1]
            y2 += frame_origin[1]
            area = max(0, (x2 - x1) * (y2 - y1))
            color = (90, 130, 255)
            thickness = 2
            if not self._passes_sample_constraints((x1, y1, x2, y2)):
                color = (70, 70, 180)
                thickness = 1
            if highlight_box:
                overlap_iou = self._bbox_iou((x1, y1, x2, y2), highlight_box)
                if overlap_iou >= 0.10:
                    color = (0, 255, 80)
                    thickness = 3
            cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(display, f"{det['cls_name']} {det['conf']:.2f} ({area}px²)",
                        (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        return display

    def _run_global_detection_test(self):
        if self.model is None:
            messagebox.showwarning("Modelo", "El modelo YOLO no está cargado.")
            return

        conf = self.conf_threshold.get()
        preview_conf = 0.05
        self.status_var.set("Ejecutando vista global con SAHI…")
        self.update()

        yolo_detections, _ = self._predict_roi_boxes(
            self.frame_orig,
            preview_conf,
            scale=1.0,
            use_sahi=False,
            force_imgsz=self.infer_imgsz.get(),
        )
        sahi_detections, _ = self._predict_roi_boxes(
            self.frame_orig,
            preview_conf,
            scale=1.0,
            use_sahi=True,
        )

        filtered_yolo = [d for d in yolo_detections if self._passes_sample_constraints(d["bbox"])]
        filtered_sahi = [d for d in sahi_detections if self._passes_sample_constraints(d["bbox"])]

        if len(filtered_yolo) >= len(filtered_sahi):
            detections = filtered_yolo
            detector_used = f"yolo-imgsz{self.infer_imgsz.get()}"
        else:
            detections = filtered_sahi
            detector_used = "sahi"

        display = self._draw_detection_overlay(detections)
        self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._redraw()

        if detections:
            areas = sorted(
                max(0, (det["bbox"][2] - det["bbox"][0]) * (det["bbox"][3] - det["bbox"][1]))
                for det in detections
            )
            suggested_min = int(max(0, areas[max(0, int(len(areas) * 0.10) - 1)] * 0.6))
            suggested_max = int(areas[min(len(areas) - 1, int(len(areas) * 0.95))] * 1.5)
            self.min_area.set(suggested_min)
            self.max_area.set(max(suggested_min + 1, suggested_max))
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
            self.lbl_calib_status.config(
                text=f"✅ Vista global: {len(detections)} vehículos detectados [{detector_used} @ {preview_conf:.2f}]",
                fg="#A6E3A1",
            )
            self.status_var.set(
                f"Vista global completada: {len(detections)} vehículos detectados. "
                "Ajusta el recuadro sobre un auto y valida uno específico."
            )
        else:
            self.lbl_calib_status.config(
                text="⚠  Vista global sin detecciones. Baja confianza o cambia de frame.",
                fg="#F38BA8",
            )
            self.status_var.set("Vista global sin detecciones")

        self.after(5000, self._restore_original_frame)

    def _run_calib_test(self):
        if self.model is None:
            messagebox.showwarning("Modelo", "El modelo YOLO no está cargado.")
            return
        if not (self.calib_rect_start and self.calib_rect_end):
            messagebox.showwarning("Calibración", "Primero dibuja un recuadro sobre un auto.")
            return
        self.status_var.set("Ejecutando inferencia YOLO…")
        self.update()

        conf = self.conf_threshold.get()
        selected_box = (
            min(self.calib_rect_start[0], self.calib_rect_end[0]),
            min(self.calib_rect_start[1], self.calib_rect_end[1]),
            max(self.calib_rect_start[0], self.calib_rect_end[0]),
            max(self.calib_rect_start[1], self.calib_rect_end[1]),
        )
        roi_box = self._get_calibration_roi(selected_box)
        scale = self._get_calibration_scale(selected_box)
        roi_frame = self.frame_orig[roi_box[1]:roi_box[3], roi_box[0]:roi_box[2]]
        candidates, detector_used = self._predict_roi_boxes(roi_frame, conf, scale, use_sahi=False)

        display = self.frame_orig.copy()
        selected_center = (
            (selected_box[0] + selected_box[2]) / 2.0,
            (selected_box[1] + selected_box[3]) / 2.0,
        )
        best_match = None

        def evaluate_candidates(candidate_list):
            nonlocal best_match
            for cand in candidate_list:
                x1, y1, x2, y2 = cand["bbox"]
                x1 += roi_box[0]
                x2 += roi_box[0]
                y1 += roi_box[1]
                y2 += roi_box[1]
                area = (x2 - x1) * (y2 - y1)
                conf_val = cand["conf"]
                cls_name = cand["cls_name"]
                det_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                overlap_iou = self._bbox_iou((x1, y1, x2, y2), selected_box)
                overlaps_selection = (
                    overlap_iou >= 0.10
                    or self._point_in_box(det_center[0], det_center[1], selected_box)
                    or self._point_in_box(selected_center[0], selected_center[1], (x1, y1, x2, y2))
                )

                color = (100, 100, 255)
                thickness = 2
                if overlaps_selection:
                    color = (0, 255, 80)
                    thickness = 3
                    score = (overlap_iou, conf_val)
                    if self._passes_sample_constraints((x1, y1, x2, y2)) and (best_match is None or score > best_match["score"]):
                        best_match = {
                            "bbox": (x1, y1, x2, y2),
                            "area": area,
                            "conf": conf_val,
                            "cls_name": cls_name,
                            "score": score,
                        }

                cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
                cv2.putText(display, f"{cls_name} {conf_val:.2f} ({area}px²)",
                            (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        evaluate_candidates(candidates)

        if best_match is None:
            sahi_candidates, sahi_mode = self._predict_roi_boxes(roi_frame, max(0.10, conf - 0.05), scale, use_sahi=True)
            evaluate_candidates(sahi_candidates)
            if best_match is not None:
                detector_used = sahi_mode

        # Show calibration box on result
        cv2.rectangle(display, (roi_box[0], roi_box[1]), (roi_box[2], roi_box[3]), (0, 180, 255), 2)
        cv2.rectangle(display, (selected_box[0], selected_box[1]), (selected_box[2], selected_box[3]), (255, 230, 0), 2)

        if best_match:
            bx1, by1, bx2, by2 = best_match["bbox"]
            cv2.rectangle(display, (bx1, by1), (bx2, by2), (0, 255, 0), 4)
            self.min_area.set(int(best_match["area"] * 0.5))
            self.max_area.set(int(best_match["area"] * 4.0))
            self.lbl_min_area.config(text=f"{self.min_area.get()} px²")
            self.lbl_max_area.config(text=f"{self.max_area.get()} px²")
            self.calib_test_passed = True
            self.calib_confirmed = False
            status_msg = (
                f"✅ Auto validado: {best_match['cls_name']} "
                f"conf={best_match['conf']:.2f} área={best_match['area']}px² "
                f"[{detector_used} x{scale:.1f}]"
            )
        else:
            self.calib_test_passed = False
            self.calib_confirmed = False
            status_msg = (
                "⚠  El recuadro no coincide con un vehículo detectado. "
                "Prueba con un recuadro más justo o baja el umbral."
            )

        self.frame_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self._redraw()

        self.lbl_calib_status.config(
            text=status_msg,
            fg="#A6E3A1" if best_match else "#F38BA8"
        )
        self.status_var.set("YOLO test completado: calibración válida" if best_match else "YOLO test completado: calibración no válida")

        # Auto-restore after 5 seconds
        self.after(5000, self._restore_original_frame)

    def _restore_original_frame(self):
        self.frame_rgb = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB)
        if self.current_step == 0:
            self._redraw()

    def _confirm_calib(self):
        if not self.calib_test_passed:
            messagebox.showwarning(
                "Calibración",
                "Primero ejecuta [Probar YOLO] y confirma que el recuadro sí coincide con un vehículo detectado."
            )
            return
        self.calib_confirmed = True
        self.lbl_calib_status.config(text="✅  Calibración confirmada", fg="#A6E3A1")
        self.status_var.set("Calibración confirmada — pasando a Paso 2")
        self.after(500, lambda: self._activate_step(1))

    # ──────────────────────────────────────────────
    # PASO 2: Zonas
    # ──────────────────────────────────────────────
    def _start_zone_draw(self):
        self._stop_zone_preview()  # TODO-007: pausar preview al empezar a dibujar
        name = self.current_zone_name.get().strip()
        if not name:
            messagebox.showwarning("Zona", "Escribe un nombre para la zona.")
            return
        if name in self.zones:
            if not messagebox.askyesno("Zona existe", f"La zona '{name}' ya existe. ¿Sobreescribir?"):
                return
            del self.zones[name]
            self._refresh_zones_list()

        self.current_zone_pts = []
        self.zone_drawing = True
        self.canvas.config(cursor="crosshair")
        self.status_var.set(f"Dibujando zona '{name}' — clic para agregar puntos, clic cerca del primero para cerrar")
        self._redraw()

    def _close_current_zone(self):
        name = self.current_zone_name.get().strip()
        if len(self.current_zone_pts) < 3:
            messagebox.showwarning("Zona", "Se necesitan al menos 3 puntos para una zona.")
            return
        self.zones[name] = list(self.current_zone_pts)
        self.current_zone_pts = []
        self.zone_drawing = False
        self.canvas.config(cursor="arrow")
        self._refresh_zones_list()
        self._redraw_zones()
        self.status_var.set(f"Zona '{name}' guardada. ({len(self.zones)} zonas en total)")

        # Suggest next zone name
        suggestions = ["Norte", "Sur", "Este", "Oeste", "Noreste", "Noroeste", "Sureste", "Suroeste"]
        for s in suggestions:
            if s not in self.zones:
                self.current_zone_name.set(s)
                break

    def _refresh_zones_list(self):
        self.zones_listbox.delete(0, "end")
        for idx, name in enumerate(self.zones):
            color_tag = f"color{idx}"
            self.zones_listbox.insert("end", f"  {name}  ({len(self.zones[name])} pts)")

    def _on_zone_select(self, event):
        sel = self.zones_listbox.curselection()
        if sel:
            name = list(self.zones.keys())[sel[0]]
            self.selected_zone.set(name)

    def _delete_selected_zone(self):
        name = self.selected_zone.get()
        if name and name in self.zones:
            if messagebox.askyesno("Eliminar", f"¿Eliminar zona '{name}'?"):
                del self.zones[name]
                self._refresh_zones_list()
                self._redraw_zones()

    def _redraw_zones(self):
        """Actualiza display_frame_zones con las zonas dibujadas."""
        base = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB).copy()
        for idx, (name, pts) in enumerate(self.zones.items()):
            color_hex = ZONE_COLORS[idx % len(ZONE_COLORS)].lstrip("#")
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            np_pts = np.array(pts, dtype=np.int32)
            overlay = base.copy()
            cv2.fillPoly(overlay, [np_pts], (r, g, b))
            base = cv2.addWeighted(base, 0.75, overlay, 0.25, 0)
            cv2.polylines(base, [np_pts], True, (r, g, b), 2)
            cx = int(np.mean([p[0] for p in pts]))
            cy = int(np.mean([p[1] for p in pts]))
            cv2.putText(base, name, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (r, g, b), 2)
        self.display_frame_zones = base
        self._redraw()

    def _toggle_zone_preview(self):
        """Inicia o pausa el preview de zonas en movimiento (TODO-007)."""
        if self._preview_playing:
            self._stop_zone_preview()
        else:
            self._start_zone_preview()

    def _start_zone_preview(self):
        """Abre el video y empieza a avanzar frames con las zonas superpuestas."""
        if self.zone_drawing:
            self.status_var.set("⚠ Termina de dibujar la zona actual antes de reproducir.")
            return
        self._preview_playing = True
        self._preview_frame_idx = self.current_frame_idx
        self._preview_cap = cv2.VideoCapture(self.video_path)
        self._preview_cap.set(cv2.CAP_PROP_POS_FRAMES, self._preview_frame_idx)
        self.btn_preview.config(text="⏸  Pausar", bg="#F38BA8", fg="#11111B")
        self.status_var.set("▶ Reproduciendo con zonas — ⏸ para pausar")
        self._zone_preview_tick()

    def _stop_zone_preview(self):
        """Pausa el preview y restaura el frame estático con zonas."""
        if not self._preview_playing and self._preview_job is None:
            return
        self._preview_playing = False
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        if self._preview_cap is not None:
            self._preview_cap.release()
            self._preview_cap = None
        if hasattr(self, "btn_preview") and self.btn_preview:
            self.btn_preview.config(text="▶  Reproducir zonas", bg="#F9E2AF", fg="#11111B")
        self._redraw_zones()

    def _zone_preview_tick(self):
        """Avanza el video 5 frames y actualiza el canvas (llamado vía after())."""
        if not self._preview_playing or self._preview_cap is None:
            return
        SKIP = 5  # frames a saltar por tick para mayor fluidez en Tkinter
        for _ in range(SKIP - 1):
            self._preview_cap.grab()
        ret, frame = self._preview_cap.read()
        self._preview_frame_idx += SKIP

        if not ret or self._preview_frame_idx >= self.total_frames:
            # Llegó al final → reiniciar en loop
            self._preview_frame_idx = 0
            self._preview_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._preview_job = self.after(80, self._zone_preview_tick)
            return

        # Renderizar frame con zonas superpuestas (OBS-2: un solo overlay + un solo addWeighted)
        base = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        overlay = base.copy()
        zone_meta = []
        for idx, (name, pts) in enumerate(self.zones.items()):
            color_hex = ZONE_COLORS[idx % len(ZONE_COLORS)].lstrip("#")
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            np_pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(overlay, [np_pts], (r, g, b))
            zone_meta.append((name, pts, (r, g, b)))
        base = cv2.addWeighted(base, 0.75, overlay, 0.25, 0)
        for name, pts, color in zone_meta:
            np_pts = np.array(pts, dtype=np.int32)
            cv2.polylines(base, [np_pts], True, color, 2)
            cx = int(np.mean([p[0] for p in pts]))
            cy = int(np.mean([p[1] for p in pts]))
            cv2.putText(base, name, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        self.display_frame_zones = base
        self._redraw()
        self.status_var.set(f"▶ Frame {self._preview_frame_idx}/{self.total_frames}  |  ⏸ para pausar")
        self._preview_job = self.after(80, self._zone_preview_tick)  # ~12 fps efectivos

    def _confirm_zones(self):
        if not self.zones:
            messagebox.showwarning("Zonas", "Define al menos 2 zonas (una entrada, una salida).")
            return
        if len(self.zones) < 2:
            messagebox.showwarning("Zonas", "Necesitas al menos 2 zonas para detectar rutas.")
            return
        self.status_var.set(f"{len(self.zones)} zonas confirmadas — pasando a Paso 3")
        self.after(300, lambda: self._activate_step(2))

    # ──────────────────────────────────────────────
    # PASO 3: SAHI + Guardar
    # ──────────────────────────────────────────────
    def _update_tile_preview(self, *_):
        if not self.img_w:
            return
        sw = self.slice_w.get()
        sh = self.slice_h.get()
        ov = self.overlap.get()
        step_x = max(1, int(sw * (1 - ov)))
        step_y = max(1, int(sh * (1 - ov)))
        cols = math.ceil((self.img_w - sw) / step_x) + 1 if sw < self.img_w else 1
        rows = math.ceil((self.img_h - sh) / step_y) + 1 if sh < self.img_h else 1
        total = cols * rows
        self.lbl_tiles.config(text=f"Tiles por frame: {total}  ({cols}×{rows})")
        self._redraw_zones()  # also redraws tile overlay via _redraw → step 2

    def _save_config(self):
        if not self.zones:
            messagebox.showwarning("Guardar", "No hay zonas definidas. Configura las zonas primero.")
            return

        config = {
            "zones": {name: pts for name, pts in self.zones.items()},
            "settings": {
                "min_area": self.min_area.get(),
                "max_area": self.max_area.get(),
                "conf_threshold": round(self.conf_threshold.get(), 2),
                "imgsz": self.infer_imgsz.get(),
                "sample_constraints": self._sample_constraints(),
                "sample_count": len(self.vehicle_samples),
            },
            "sahi": {
                "slice_width": self.slice_w.get(),
                "slice_height": self.slice_h.get(),
                "overlap_ratio": round(self.overlap.get(), 2),
                "nms_threshold": round(self.nms_threshold.get(), 2),
            },
            "tracker": {
                "max_age": self.max_age.get(),
                "min_hits": self.min_hits.get(),
                "iou_threshold": round(self.iou_thresh.get(), 2),
            },
            "video_path": self.video_path,
            "model_path": MODEL_PATH,
        }

        # OBS-2: preservar campos extra del JSON original que el configurador no gestiona
        if hasattr(self, "_loaded_config"):
            for section in ("settings", "sahi", "tracker"):
                loaded = self._loaded_config.get(section, {})
                for key, val in loaded.items():
                    if key not in config.get(section, {}):
                        config.setdefault(section, {})[key] = val

        try:
            with open(OUTPUT_CONFIG, "w") as f:
                json.dump(config, f, indent=2)
            self.lbl_save_status.config(
                text=f"✅ Guardado: {OUTPUT_CONFIG}\n{len(self.zones)} zonas · SAHI {self.slice_w.get()}×{self.slice_h.get()}",
                fg="#A6E3A1"
            )
            self.status_var.set(f"✅ Configuración guardada en {OUTPUT_CONFIG}")
            messagebox.showinfo("Guardado",
                                f"Configuración guardada exitosamente en:\n{OUTPUT_CONFIG}\n\n"
                                f"Zonas: {', '.join(self.zones.keys())}\n\n"
                                f"Siguiente paso:\n  python main_glorieta.py")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Configurador interactivo de glorieta")
    parser.add_argument("--video", type=str, default=DEFAULT_VIDEO,
                        help="Ruta al video de la glorieta")
    parser.add_argument("--config", type=str, default=OUTPUT_CONFIG,
                        help="Archivo de configuración (entrada y salida). Si existe, se carga automáticamente.")
    args = parser.parse_args()

    OUTPUT_CONFIG = args.config
    app = SetupGlorieta()
    if args.video != DEFAULT_VIDEO:
        app.video_path = args.video
        app._load_frame()
    if os.path.isfile(args.config):  # TODO-008: cargar config existente
        app._load_from_config(args.config)

    app.mainloop()
