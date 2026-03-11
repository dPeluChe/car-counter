"""
main_glorieta.py
================
Contador de vehículos para glorietas con tracking de rutas A→B.

Usa el tracker nativo de Ultralytics (ByteTrack o BoT-SORT) — mucho más estable
que el legacy SORT para vídeos aéreos con oclusiones.

Opcionalmente usa SAHI (Slicing Aided Hyper Inference) para detectar vehículos
pequeños/lejanos. Sin SAHI el procesamiento es en tiempo real.

Lee la configuración generada por setup_glorieta.py (config_glorieta.json) que contiene:
  - Zonas poligonales por calle (Norte, Sur, Este, Oeste, etc.)
  - Parámetros de calibración (min_area, max_area, conf_threshold)
  - Parámetros SAHI (slice_width, slice_height, overlap_ratio)
  - Parámetros del tracker

Lógica de rutas (máquina de estados por vehículo):
  NUEVO   → vehículo detectado sin zona conocida
  ORIGEN  → primer contacto con zona A (entrada registrada)
  TRANSIT → vehículo salió de zona A, circula por la glorieta
  DONE    → vehículo llegó a zona B distinta → ruta A→B contada

Uso:
  python main_glorieta.py
  python main_glorieta.py --config config_glorieta.json --video assets/glorieta_normal.mp4
  python main_glorieta.py --no-sahi      # Modo rápido sin SAHI (tiempo real)
  python main_glorieta.py --tracker bytetrack   # bytetrack (default) o botsort
  python main_glorieta.py --benchmark    # Guardar métricas de rendimiento
"""

import csv
import cv2
import json
import math
import time
import os
import argparse
import importlib.util
import numpy as np

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Contador de glorieta con tracking A→B y SAHI",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Ejemplos:
  python main_glorieta.py
  python main_glorieta.py --config config_glorieta.json
  python main_glorieta.py --no-sahi --video assets/glorieta_normal.mp4
  python main_glorieta.py --benchmark --show-fps
    """
)
parser.add_argument("--config", type=str, default="config_glorieta.json",
                    help="Ruta al archivo de configuración (generado por setup_glorieta.py)")
parser.add_argument("--video", type=str, default=None,
                    help="Ruta al video. Si no se especifica, se usa el del config.")
parser.add_argument("--model", type=str, default=None,
                    help="Ruta al modelo YOLO. Si no se especifica, se usa el del config.")
parser.add_argument("--imgsz", type=int, default=None,
                    help="Resolución de inferencia YOLO. Si no se especifica, se usa la del config.")
parser.add_argument("--no-sahi", dest="no_sahi", action="store_true",
                    help="Deshabilitar SAHI (más rápido, menos preciso para objetos pequeños)")
parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"],
                    help="Dispositivo de inferencia")
parser.add_argument("--show-fps", dest="show_fps", action="store_true",
                    help="Mostrar FPS en el video")
parser.add_argument("--benchmark", action="store_true",
                    help="Guardar métricas de rendimiento en benchmarks/")
parser.add_argument("--output", type=str, default="result_glorieta.mp4",
                    help="Archivo de video de salida")
parser.add_argument("--no-save", dest="no_save", action="store_true",
                    help="No guardar video de salida (más rápido)")
parser.add_argument("--headless", action="store_true",
                    help="Ejecutar sin ventana OpenCV (útil para servidores o smoke tests)")
parser.add_argument("--max-frames", type=int, default=None,
                    help="Procesar solo N frames y salir")
parser.add_argument("--tracker", type=str, default="bytetrack",
                    choices=["bytetrack", "botsort", "sort"],
                    help="Algoritmo de tracking: bytetrack (default), botsort o sort fallback")
parser.add_argument("--output-json", type=str, default="results_glorieta.json",
                    help="Ruta del JSON de resultados al terminar (default: results_glorieta.json)")
parser.add_argument("--no-output-json", dest="no_output_json", action="store_true",
                    help="No guardar JSON de resultados al terminar")
parser.add_argument("--output-csv", type=str, default=None,
                    help="Ruta del CSV de rutas (opcional)")
args = parser.parse_args()

# Si --no-save y --output-json no fue especificado explícitamente, suprimir JSON también
if args.no_save and args.output_json == "results_glorieta.json":
    args.no_output_json = True

# ─────────────────────────────────────────────
# Cargar configuración
# ─────────────────────────────────────────────
print("=" * 65)
print("🎯  CONTADOR DE GLORIETA — Car Counter Demo")
print("=" * 65)

config_path = args.config
if not os.path.exists(config_path):
    print(f"❌  No se encontró: {config_path}")
    print("   Ejecuta primero: python setup_glorieta.py")
    exit(1)

with open(config_path, "r") as f:
    config = json.load(f)

zones_config     = config.get("zones", {})
settings         = config.get("settings", {})
sahi_cfg         = config.get("sahi", {})
tracker_cfg      = config.get("tracker", {})

VIDEO_PATH   = args.video  or config.get("video_path", "assets/glorieta_normal.mp4")
MODEL_PATH   = args.model  or config.get("model_path", "models/yolo/yolov11l.pt")
CONF_THRESH  = settings.get("conf_threshold", 0.10)
INFER_IMGSZ  = args.imgsz or settings.get("imgsz", 1600)
MIN_AREA     = settings.get("min_area", 0)
MAX_AREA     = settings.get("max_area", 999999)
sample_constraints = settings.get("sample_constraints") or {}
MIN_WIDTH    = sample_constraints.get("min_width", 0)
MAX_WIDTH    = sample_constraints.get("max_width", 999999)
MIN_HEIGHT   = sample_constraints.get("min_height", 0)
MAX_HEIGHT   = sample_constraints.get("max_height", 999999)
MIN_ASPECT   = sample_constraints.get("min_aspect", 0.0)
MAX_ASPECT   = sample_constraints.get("max_aspect", 999999.0)
SLICE_W          = sahi_cfg.get("slice_width",  512)
SLICE_H          = sahi_cfg.get("slice_height", 512)
OVERLAP          = sahi_cfg.get("overlap_ratio", 0.2)
TRACKER_YAML     = f"{args.tracker}.yaml"
MIN_ORIGIN_FRAMES = settings.get("min_origin_frames", 3)  # frames para confirmar zona origen
MIN_DEST_FRAMES   = settings.get("min_dest_frames",   3)  # frames para confirmar zona destino (TODO-003)

USE_SAHI = not args.no_sahi

print(f"\n📄  Config:   {config_path}")
print(f"📹  Video:    {VIDEO_PATH}")
print(f"🤖  Modelo:   {MODEL_PATH}")
print(f"🎯  Tracker:  {args.tracker}")
print(f"🗺   Zonas:    {list(zones_config.keys())}")
print(f"\n⚙️   Detección:")
print(f"    Confianza: {CONF_THRESH}  |  ImgSz: {INFER_IMGSZ}  |  Área: [{MIN_AREA}–{MAX_AREA}] px²")
if sample_constraints:
    print(f"    Filtro geom: w[{MIN_WIDTH}–{MAX_WIDTH}] h[{MIN_HEIGHT}–{MAX_HEIGHT}] aspect[{MIN_ASPECT:.2f}–{MAX_ASPECT:.2f}]")
if USE_SAHI:
    print(f"\n🔬  SAHI:    tiles {SLICE_W}×{SLICE_H}  overlap {OVERLAP*100:.0f}%")
else:
    print(f"\n⚡  Modo rápido (sin SAHI)")
print("=" * 65)

DISPLAY_ENABLED = not args.headless

# ─────────────────────────────────────────────
# COCO class names
# ─────────────────────────────────────────────
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
VEHICLE_CLASSES = {"car", "truck", "bus", "motorbike"}

# ─────────────────────────────────────────────
# Colores por zona (BGR para OpenCV)
# ─────────────────────────────────────────────
ZONE_COLORS_BGR = [
    (136, 255, 0),    # verde
    (107, 107, 255),  # rojo-coral
    (205, 196, 78),   # cian
    (109, 230, 255),  # amarillo
    (207, 230, 168),  # verde menta
    (148, 139, 255),  # salmon
    (255, 184, 184),  # lavanda
    (122, 160, 255),  # azul claro
]

# ─────────────────────────────────────────────
# Cargar modelo YOLO (con tracker nativo)
# ByteTrack/BoT-SORT ya incluidos en ultralytics
# ─────────────────────────────────────────────
print("\nCargando modelo YOLO…")
from ultralytics import YOLO
model_yolo = YOLO(MODEL_PATH)
print(f"✅  Modelo cargado  —  tracker solicitado: {args.tracker}")

# ─────────────────────────────────────────────
# SAHI setup (para modo alta precisión)
# En modo sin SAHI se usa model.track() nativo
# ─────────────────────────────────────────────
detection_model_sahi = None
if USE_SAHI:
    print("Cargando wrapper SAHI…")
    try:
        from sahi import AutoDetectionModel
        from sahi.predict import get_sliced_prediction
        detection_model_sahi = AutoDetectionModel.from_pretrained(
            model_type="yolov8",
            model_path=MODEL_PATH,
            confidence_threshold=CONF_THRESH,
            device=args.device,
        )
        print("✅  SAHI listo")
        print("⚠️   Nota: En modo SAHI el tracking usa SORT interno por compatibilidad.")
        print("    Para máximo rendimiento usa --no-sahi con ByteTrack nativo.")
    except ImportError:
        print("⚠️   SAHI no instalado — fallback a modo rápido con ByteTrack")
        print("    pip install sahi")
        USE_SAHI = False

# ─────────────────────────────────────────────
# Video
# ─────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"❌  No se pudo abrir el video: {VIDEO_PATH}")
    exit(1)

VID_W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
VID_H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
VID_FPS = cap.get(cv2.CAP_PROP_FPS)
TOTAL_F = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
DURATION = TOTAL_F / VID_FPS if VID_FPS > 0 else 0

print(f"\n📹  {VID_W}×{VID_H} @ {VID_FPS:.1f}fps  —  {DURATION:.1f}s ({TOTAL_F} frames)")

# Calcular tiles para info
if USE_SAHI:
    step_x = max(1, int(SLICE_W * (1 - OVERLAP)))
    step_y = max(1, int(SLICE_H * (1 - OVERLAP)))
    tiles_h = math.ceil((VID_W - SLICE_W) / step_x) + 1 if SLICE_W < VID_W else 1
    tiles_v = math.ceil((VID_H - SLICE_H) / step_y) + 1 if SLICE_H < VID_H else 1
    TILES_PER_FRAME = tiles_h * tiles_v
    print(f"🔬  SAHI tiles por frame: {TILES_PER_FRAME} ({tiles_h}×{tiles_v})")
    est_time = (DURATION * TILES_PER_FRAME) if VID_FPS > 0 else 0
    print(f"    Tiempo estimado (CPU): ~{est_time/60:.1f} min")

# ─────────────────────────────────────────────
# SORT legacy — solo usado como fallback SAHI
# ─────────────────────────────────────────────
REQUESTED_TRACKER = args.tracker
TRACKER_BACKEND = REQUESTED_TRACKER
LAP_AVAILABLE = importlib.util.find_spec("lap") is not None

if TRACKER_BACKEND in {"bytetrack", "botsort"} and not LAP_AVAILABLE:
    print("⚠️   El paquete 'lap' no está instalado.")
    print("    Fallback automático a SORT para no bloquear el demo.")
    print("    Instala 'lap>=0.5.12' para usar ByteTrack/BoT-SORT nativo.")
    TRACKER_BACKEND = "sort"

SORT_MAX_AGE = tracker_cfg.get("max_age", 40)
SORT_MIN_HITS = tracker_cfg.get("min_hits", 3)
SORT_IOU = tracker_cfg.get("iou_threshold", 0.2)

if USE_SAHI or TRACKER_BACKEND == "sort":
    try:
        from sort import Sort as _Sort
        _sort_tracker = _Sort(
            max_age=SORT_MAX_AGE,
            min_hits=SORT_MIN_HITS,
            iou_threshold=SORT_IOU,
        )
    except ImportError:
        _sort_tracker = None
else:
    _sort_tracker = None

print(f"🧭  Backend efectivo de tracking: {TRACKER_BACKEND}")
if TRACKER_BACKEND in {"bytetrack", "botsort"} and tracker_cfg:
    print("ℹ️   Los parámetros 'tracker' del config aplican al fallback SORT;")
    print("    ByteTrack/BoT-SORT usan la configuración nativa de Ultralytics.")

# ─────────────────────────────────────────────
# Video writer
# ─────────────────────────────────────────────
writer = None
if not args.no_save:
    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        VID_FPS,
        (VID_W, VID_H)
    )

# ─────────────────────────────────────────────
# Zonas y estado de rutas
# ─────────────────────────────────────────────
zones_np = {name: np.array(pts, dtype=np.int32) for name, pts in zones_config.items()}
zone_names = list(zones_np.keys())

# Máquina de estados por vehículo:
#   state: 'origin' | 'transit' | 'done'
#   origin: nombre de zona de entrada
#   in_origin_frames: cuántos frames lleva en zona origen (umbral anti-rebote)
tracks_info = {}
routes_matrix = {}   # { 'Norte → Sur': count }

frame_count = 0
total_vehicles_ever = 0  # TODO-002: IDs únicos vistos (persiste tras purga de tracks_info)
start_time = time.time()
fps_samples = []
benchmark_data = []

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def point_in_zone(x, y, zone_pts):
    return cv2.pointPolygonTest(zone_pts, (float(x), float(y)), False) >= 0

def bbox_iou(box_a, box_b):
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

def passes_geometry_filter(x1, y1, x2, y2):
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    area = width * height
    aspect = width / float(height)
    if MIN_AREA > 0 and area < MIN_AREA:
        return False
    if MAX_AREA < 999999 and area > MAX_AREA:
        return False
    if MIN_WIDTH > 0 and width < MIN_WIDTH:
        return False
    if MAX_WIDTH < 999999 and width > MAX_WIDTH:
        return False
    if MIN_HEIGHT > 0 and height < MIN_HEIGHT:
        return False
    if MAX_HEIGHT < 999999 and height > MAX_HEIGHT:
        return False
    if MIN_ASPECT > 0 and aspect < MIN_ASPECT:
        return False
    if MAX_ASPECT < 999999 and aspect > MAX_ASPECT:
        return False
    return True

def attach_classes_to_tracks(track_rows, det_rows, det_classes):
    labeled_tracks = []
    for row in track_rows:
        x1, y1, x2, y2, tid = map(int, row)
        best_idx = -1
        best_iou = 0.0
        for idx, det in enumerate(det_rows):
            det_box = tuple(map(int, det[:4]))
            score = bbox_iou((x1, y1, x2, y2), det_box)
            if score > best_iou:
                best_iou = score
                best_idx = idx
        cls_name = det_classes[best_idx] if best_idx >= 0 and best_idx < len(det_classes) else "car"
        labeled_tracks.append((x1, y1, x2, y2, tid, cls_name))
    return labeled_tracks

def get_zone_for_point(x, y):
    for name, pts in zones_np.items():
        if point_in_zone(x, y, pts):
            return name
    return None

def update_route_state(trk_id, cx, cy, cls_name="unknown"):
    """
    Máquina de estados para tracking de rutas A→B.

    Estados:
      Sin registro    → primera vez que vemos este ID
      origin          → vehículo detectado en zona A, confirmado (≥MIN_ORIGIN_FRAMES)
      transit         → vehículo salió de zona A, circula por la glorieta
      done            → llegó a zona B → ruta A→B contada (no vuelve a contar)

    El umbral MIN_ORIGIN_FRAMES evita falsos positivos cuando un vehículo
    roza brevemente una zona al pasar (origen).
    El umbral MIN_DEST_FRAMES aplica el mismo anti-rebote al destino (TODO-003).
    """
    global total_vehicles_ever
    current_zone = get_zone_for_point(cx, cy)

    if trk_id not in tracks_info:
        total_vehicles_ever += 1
        tracks_info[trk_id] = {
            "state": "origin" if current_zone else "new",
            "origin": current_zone,
            "class": cls_name,
            "zone_frames": 1 if current_zone else 0,
            "last_seen_frame": frame_count,   # TODO-002
            "dest_zone": None,                # TODO-003
            "dest_frames": 0,                 # TODO-003
        }
        if current_zone:
            print(f"  🚗 ID={trk_id:>4}  entró en [{current_zone:>10}]  cls={cls_name}")
        return

    info = tracks_info[trk_id]
    info["last_seen_frame"] = frame_count  # TODO-002: actualizar cada frame visible

    if info["state"] == "done":
        return  # ya contado, nada más que hacer

    if info["state"] == "new":
        if current_zone:
            info["state"] = "origin"
            info["origin"] = current_zone
            info["zone_frames"] = 1
            print(f"  🚗 ID={trk_id:>4}  entró en [{current_zone:>10}]  cls={info['class']}")
        return

    if info["state"] == "origin":
        origin = info["origin"]
        if current_zone == origin:
            # Sigue en la misma zona de origen — acumular frames de confirmación
            info["zone_frames"] = info.get("zone_frames", 0) + 1
        elif current_zone is None:
            # Salió de la zona de origen → en tránsito
            if info.get("zone_frames", 0) >= MIN_ORIGIN_FRAMES:
                info["state"] = "transit"
                info["dest_zone"] = None
                info["dest_frames"] = 0
            else:
                # No tenía suficientes frames — descartamos como falso positivo
                info["state"] = "new"
                info["origin"] = None
        else:
            # Entró directamente en otra zona (glorieta pequeña) — contar
            if info.get("zone_frames", 0) >= MIN_ORIGIN_FRAMES:
                _register_route(trk_id, origin, current_zone)
        return

    if info["state"] == "transit":
        if current_zone and current_zone != info["origin"]:
            # TODO-003: Anti-rebote destino — confirmar MIN_DEST_FRAMES consecutivos
            if info.get("dest_zone") == current_zone:
                info["dest_frames"] = info.get("dest_frames", 0) + 1
                if info["dest_frames"] >= MIN_DEST_FRAMES:
                    _register_route(trk_id, info["origin"], current_zone)
            else:
                # Nueva zona candidata destino — reiniciar contador
                info["dest_zone"] = current_zone
                info["dest_frames"] = 1
        else:
            # Fuera de toda zona destino válida — resetear anti-rebote
            info["dest_zone"] = None
            info["dest_frames"] = 0

def _register_route(trk_id, origin, destination):
    route_key = f"{origin} → {destination}"
    routes_matrix[route_key] = routes_matrix.get(route_key, 0) + 1
    tracks_info[trk_id]["state"] = "done"
    print(f"  ✅ ID={trk_id:>4}  ruta: {route_key}  (total={routes_matrix[route_key]})")

def format_time(s):
    h, r = divmod(int(s), 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

def draw_zones(frame):
    for idx, (name, pts) in enumerate(zones_np.items()):
        color = ZONE_COLORS_BGR[idx % len(ZONE_COLORS_BGR)]
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
        cv2.polylines(frame, [pts], True, color, 2)
        cx = int(np.mean(pts[:, 0]))
        cy = int(np.mean(pts[:, 1]))
        cv2.putText(frame, name, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, color, 2, cv2.LINE_AA)

def draw_routes_panel(frame, routes, n_active):
    """Panel semitransparente con la matriz de rutas A→B."""
    if not routes:
        return

    pad = 10
    line_h = 22
    sorted_routes = sorted(routes.items(), key=lambda x: -x[1])
    panel_h = pad * 2 + line_h * (len(sorted_routes) + 2)
    panel_w = 280
    x0, y0 = 10, 10

    overlay = frame.copy()
    cv2.rectangle(overlay, (x0, y0), (x0 + panel_w, y0 + panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    cv2.rectangle(frame, (x0, y0), (x0 + panel_w, y0 + panel_h), (80, 80, 80), 1)

    cv2.putText(frame, "RUTAS DETECTADAS", (x0 + pad, y0 + pad + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Activos: {n_active}", (x0 + pad + 160, y0 + pad + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 100), 1, cv2.LINE_AA)

    y = y0 + pad + line_h + 4
    total = sum(routes.values())
    for route, count in sorted_routes:
        pct = count / total * 100 if total > 0 else 0
        bar_w = int((panel_w - pad * 2 - 90) * count / max(routes.values()))
        cv2.rectangle(frame, (x0 + pad, y + 4), (x0 + pad + bar_w, y + 16),
                      (60, 120, 60), -1)
        cv2.putText(frame, f"{route}:", (x0 + pad, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 255, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{count}  ({pct:.0f}%)",
                    (x0 + panel_w - 80, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 100), 1, cv2.LINE_AA)
        y += line_h

def draw_hud(frame, frame_num, total_f, fps_avg, detections, n_routes_total):
    """HUD inferior con info de procesamiento."""
    h = frame.shape[0]
    progress = frame_num / total_f if total_f > 0 else 0
    bar_w = int(VID_W * progress)
    cv2.rectangle(frame, (0, h - 6), (bar_w, h), (80, 200, 80), -1)

    info = f"Frame {frame_num}/{total_f}  FPS:{fps_avg:.1f}  Det:{detections}  Rutas:{n_routes_total}"
    cv2.putText(frame, info, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (200, 200, 200), 1, cv2.LINE_AA)

# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────
print(f"\n⚡  Iniciando procesamiento…  (presiona 'q' para salir)\n")

try:
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        frame_count += 1
        t0 = time.time()

        # ── Detección ────────────────────────────────────────────────────────
        detections = np.empty((0, 5))
        det_classes = []

        if USE_SAHI and detection_model_sahi is not None:
            result_sahi = get_sliced_prediction(
                frame,
                detection_model_sahi,
                slice_height=SLICE_H,
                slice_width=SLICE_W,
                overlap_height_ratio=OVERLAP,
                overlap_width_ratio=OVERLAP,
                postprocess_type="NMS",
                postprocess_match_threshold=0.5,
                postprocess_match_metric="IOS",
                verbose=0,
            )
            det_list = []  # TODO-001: acumular en lista, convertir una sola vez
            for pred in result_sahi.object_prediction_list:
                bbox = pred.bbox
                cls_name = pred.category.name
                conf_val = pred.score.value
                if cls_name not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = int(bbox.minx), int(bbox.miny), int(bbox.maxx), int(bbox.maxy)
                if not passes_geometry_filter(x1, y1, x2, y2):
                    continue
                det_list.append([x1, y1, x2, y2, conf_val])
                det_classes.append(cls_name)
            detections = np.array(det_list) if det_list else np.empty((0, 5))  # TODO-001
        elif TRACKER_BACKEND == "sort":
            results = model_yolo(frame, conf=CONF_THRESH, verbose=False, classes=[2, 3, 5, 7], imgsz=INFER_IMGSZ)
            det_list = []  # TODO-001: acumular en lista, convertir una sola vez
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cls_id = int(box.cls[0])
                    cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else ""
                    conf_val = float(box.conf[0])
                    if cls_name not in VEHICLE_CLASSES:
                        continue
                    if not passes_geometry_filter(x1, y1, x2, y2):
                        continue
                    det_list.append([x1, y1, x2, y2, conf_val])
                    det_classes.append(cls_name)
            detections = np.array(det_list) if det_list else np.empty((0, 5))  # TODO-001

        # ── Tracking ──────────────────────────────────────────────────────────
        # Modo sin SAHI: model.track() usa ByteTrack/BoT-SORT nativo de Ultralytics
        # Modo SAHI: detecciones vienen de tiles → tracker legacy SORT como fallback
        tracked_boxes = []   # lista de (x1, y1, x2, y2, id, cls_name)

        if USE_SAHI and detection_model_sahi is not None:
            # SAHI path: usamos SORT legacy porque SAHI no es compatible con model.track()
            if _sort_tracker is not None:
                sort_out = _sort_tracker.update(detections)
                tracked_boxes = attach_classes_to_tracks(sort_out, detections, det_classes)
            elif _sort_tracker is None:
                # Sin sort.py disponible, inferir IDs sintéticos del índice
                for i, det in enumerate(detections):
                    x1, y1, x2, y2, _ = map(int, det)
                    tracked_boxes.append((x1, y1, x2, y2, i + 1, det_classes[i] if i < len(det_classes) else "car"))
        elif TRACKER_BACKEND == "sort":
            if _sort_tracker is not None:
                sort_out = _sort_tracker.update(detections)
                tracked_boxes = attach_classes_to_tracks(sort_out, detections, det_classes)
            else:
                for i, det in enumerate(detections):
                    x1, y1, x2, y2, _ = map(int, det)
                    tracked_boxes.append((x1, y1, x2, y2, i + 1, det_classes[i] if i < len(det_classes) else "car"))
        else:
            # FastPath: ByteTrack/BoT-SORT nativo — model.track() con persist=True
            track_results = model_yolo.track(
                frame,
                conf=CONF_THRESH,
                imgsz=INFER_IMGSZ,
                tracker=TRACKER_YAML,
                persist=True,
                verbose=False,
                classes=[2, 3, 5, 7],  # car, motorbike, bus, truck
            )
            if track_results and track_results[0].boxes is not None:
                boxes = track_results[0].boxes
                for box in boxes:
                    if box.id is None:
                        continue
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    if not passes_geometry_filter(x1, y1, x2, y2):
                        continue
                    tid = int(box.id[0])
                    cls_id = int(box.cls[0])
                    cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else "car"
                    tracked_boxes.append((x1, y1, x2, y2, tid, cls_name))
            detections = np.array([[b[0], b[1], b[2], b[3], 1.0] for b in tracked_boxes]) \
                if tracked_boxes else np.empty((0, 5))

        # ── Lógica de rutas (máquina de estados) ─────────────────────────────
        for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            update_route_state(trk_id, cx, cy, cls_name)

        # ── Purga de tracks viejos (TODO-002) ──────────────────────────────────
        if frame_count % 120 == 0 and frame_count > 0:
            stale_ids = [
                tid for tid, tinfo in tracks_info.items()
                if frame_count - tinfo.get("last_seen_frame", 0) > 200
            ]
            for tid in stale_ids:
                del tracks_info[tid]
            if stale_ids:
                print(f"  🧹 Purgados {len(stale_ids)} tracks viejos — activos en memoria: {len(tracks_info)}")

        # ── Visualización ─────────────────────────────────────────────────────
        draw_zones(frame)

        for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            info  = tracks_info.get(trk_id, {})
            state  = info.get("state", "new")
            origin = info.get("origin", "")

            # Color por estado:
            #  done    → verde brillante
            #  transit → color de la zona de origen
            #  origin  → color de la zona (más brillante)
            #  new     → gris
            if state == "done":
                color = (60, 220, 60)
            elif state in ("origin", "transit") and origin in zone_names:
                zone_idx = zone_names.index(origin)
                color = ZONE_COLORS_BGR[zone_idx % len(ZONE_COLORS_BGR)]
                if state == "transit":
                    color = tuple(min(255, int(c * 1.3)) for c in color)
            else:
                color = (160, 160, 160)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, (cx, cy), 4, color, -1)

            state_icon = {"done": "✓", "transit": "→", "origin": "●", "new": "?"}.get(state, "")
            label = f"{state_icon}{trk_id}"
            if origin:
                label += f"[{origin}]"
            cv2.putText(frame, label, (x1, max(12, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

        draw_routes_panel(frame, routes_matrix, len(tracked_boxes))

        # FPS
        elapsed = time.time() - t0
        fps_now = 1.0 / elapsed if elapsed > 0 else 0
        fps_samples.append(fps_now)
        fps_avg = np.mean(fps_samples[-30:])

        if args.show_fps or USE_SAHI:
            draw_hud(frame, frame_count, TOTAL_F, fps_avg, len(tracked_boxes),
                     sum(routes_matrix.values()))

        # Progreso en consola cada 60 frames
        if frame_count % 60 == 0:
            elapsed_total = time.time() - start_time
            pct = frame_count / TOTAL_F * 100 if TOTAL_F > 0 else 0
            eta = (elapsed_total / frame_count) * (TOTAL_F - frame_count) if frame_count > 0 else 0
            print(f"  📊 {pct:.1f}%  frame {frame_count}/{TOTAL_F}  "
                  f"fps={fps_avg:.1f}  ETA={format_time(eta)}  "
                  f"rutas={sum(routes_matrix.values())}")

            if args.benchmark:
                benchmark_data.append({
                    "frame": frame_count,
                    "elapsed": elapsed_total,
                    "fps": fps_avg,
                    "detections": len(tracked_boxes),
                    "tracks": len(tracked_boxes),
                    "routes": sum(routes_matrix.values()),
                })

        if DISPLAY_ENABLED:
            cv2.imshow("Glorieta — Car Counter", frame)
        if writer:
            writer.write(frame)

        if args.max_frames and frame_count >= args.max_frames:
            print(f"\n⏹️   Límite alcanzado: {args.max_frames} frames")
            break

        if DISPLAY_ENABLED and cv2.waitKey(1) & 0xFF == ord("q"):
            print("\n⚠️   Procesamiento interrumpido por el usuario")
            break

except KeyboardInterrupt:
    print("\n⚠️   Interrumpido (Ctrl+C)")

# ─────────────────────────────────────────────
# Resumen final
# ─────────────────────────────────────────────
total_time = time.time() - start_time
avg_fps = frame_count / total_time if total_time > 0 else 0

print("\n" + "=" * 65)
print("📊  RESUMEN FINAL — CONTADOR DE GLORIETA")
print("=" * 65)
print(f"Video:   {VIDEO_PATH}")
print(f"Config:  {config_path}")
print(f"Modo:    {'SAHI' if USE_SAHI else 'YOLO estándar'}")
print(f"Tracker: {TRACKER_BACKEND}")
print(f"\nRenderizado:")
print(f"  Frames procesados: {frame_count}/{TOTAL_F}")
print(f"  Tiempo total:      {format_time(total_time)}")
print(f"  FPS promedio:      {avg_fps:.2f}")

print(f"\n🗺   Zonas configuradas: {', '.join(zone_names)}")
print(f"🚗  Vehículos rastreados: {total_vehicles_ever}")
print(f"✅  Rutas completadas:   {sum(routes_matrix.values())}")

if routes_matrix:
    print("\n📈  Matriz de Rutas:")
    sorted_routes = sorted(routes_matrix.items(), key=lambda x: -x[1])
    total_routes = sum(routes_matrix.values())
    for route, count in sorted_routes:
        pct = count / total_routes * 100
        bar = "█" * int(pct / 5)
        print(f"  {route:<30} {count:>4}  ({pct:5.1f}%)  {bar}")
else:
    print("\n⚠️   No se completaron rutas. Verifica:")
    print("   1. Las zonas cubren correctamente las bocacalles")
    print("   2. El video tiene suficiente duración")
    print("   3. El conf_threshold no es demasiado alto")

# ── Export de resultados (TODO-006) ───────────────────────────────────────────
if not args.no_output_json:
    results_data = {
        "video": VIDEO_PATH,
        "config": config_path,
        "mode": "SAHI" if USE_SAHI else "YOLO",
        "tracker": TRACKER_BACKEND,
        "frames_processed": frame_count,
        "total_frames": TOTAL_F,
        "duration_seconds": round(DURATION, 2),
        "processing_time_seconds": round(total_time, 2),
        "fps_avg": round(avg_fps, 2),
        "total_vehicles_tracked": total_vehicles_ever,
        "total_routes_completed": sum(routes_matrix.values()),
        "routes": dict(sorted(routes_matrix.items(), key=lambda x: -x[1])),
        "zones": zone_names,
    }
    json_path = args.output_json
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(results_data, jf, ensure_ascii=False, indent=2)
    print(f"\n📄  Resultados JSON guardados: {json_path}")

if args.output_csv:
    with open(args.output_csv, "w", newline="", encoding="utf-8") as cf:
        csv_writer = csv.writer(cf)
        csv_writer.writerow(["ruta", "conteo", "porcentaje"])
        total_r = sum(routes_matrix.values())
        for route, count in sorted(routes_matrix.items(), key=lambda x: -x[1]):
            pct = count / total_r * 100 if total_r > 0 else 0
            csv_writer.writerow([route, count, f"{pct:.1f}"])
    print(f"📊  Resultados CSV guardados: {args.output_csv}")

# Guardar benchmark
if args.benchmark and benchmark_data:
    os.makedirs("benchmarks", exist_ok=True)
    bfile = "benchmarks/glorieta_results.txt"
    with open(bfile, "w") as f:
        f.write("Glorieta Benchmark\n" + "=" * 50 + "\n")
        f.write(f"Video: {VIDEO_PATH}\n")
        f.write(f"Config: {args.config}\n")
        f.write(f"SAHI: {USE_SAHI}\n")
        f.write(f"Tiempo total: {format_time(total_time)}\n")
        f.write(f"FPS promedio: {avg_fps:.2f}\n")
        f.write(f"Rutas totales: {sum(routes_matrix.values())}\n\n")
        f.write("Rutas:\n")
        for route, count in sorted(routes_matrix.items(), key=lambda x: -x[1]):
            f.write(f"  {route}: {count}\n")
        f.write("\nFrame data:\n")
        f.write(f"{'Frame':<10}{'Elapsed':<12}{'FPS':<8}{'Det':<8}{'Tracks':<8}{'Routes':<8}\n")
        f.write("-" * 50 + "\n")
        for d in benchmark_data:
            f.write(f"{d['frame']:<10}{d['elapsed']:<12.2f}{d['fps']:<8.2f}"
                    f"{d['detections']:<8}{d['tracks']:<8}{d['routes']:<8}\n")
    print(f"\n📊  Benchmark guardado: {bfile}")

if writer:
    writer.release()
    print(f"\n💾  Video guardado: {args.output}")

cap.release()
cv2.destroyAllWindows()

print("=" * 65)
print("✅  Procesamiento completo")
print("=" * 65)
