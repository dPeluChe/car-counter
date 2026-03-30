# Car Counter

Conteo y tracking de vehiculos con YOLO + tracking para videos de trafico.
Soporta glorietas, intersecciones, aforo por cruce de linea, clasificacion por direccion, y tomas aereas.

## Arquitectura

```
main.py              # Motor de conteo (entry point)
setup.py             # Configurador interactivo (Tkinter)
carcounter/          # Paquete core
  constants.py       #   Clases COCO, colores, IDs
  geometry.py        #   Zone masks, point-in-polygon, IoU, NMS, cosine similarity
  counting.py        #   Maquina de estados (zones + lines + directions)
  tracking.py        #   Asociacion clase-track
  drawing.py         #   Dibujo OpenCV (zonas, HUD, scoreboard, trails, heatmap)
  detection.py       #   Pipeline YOLO/RF-DETR + SAHI + filtros
  rfdetr_detector.py #   RF-DETR wrapper (opcional)
  calibration.py     #   ROI, escala, muestras, constraints geometricos
  config_io.py       #   Lectura/escritura de config.json
  export.py          #   Export JSON/CSV/OD-matrix de resultados
  device.py          #   Auto-deteccion GPU (CUDA/MPS/CPU)
  paths.py           #   Resolucion centralizada de rutas
  ocsort_wrapper.py  #   OC-SORT tracker wrapper (opcional)
  sort.py            #   SORT tracker (fallback)
setup_panels/        # Mixins del configurador GUI
  canvas.py          #   Zoom, pan, redraw, overlays compartidos
  step0_exclusion.py #   Paso 0: zonas de exclusion
  step1_calibration.py # Paso 1: calibracion YOLO
  step2_zones.py     #   Paso 2: zonas/lineas de conteo
  step3_sahi.py      #   Paso 3: SAHI + guardado
tests/               # Tests unitarios (103 tests, pytest)
docs/                # Documentacion
```

## Features

- Detectores: YOLO (ultralytics) o RF-DETR (Roboflow, +9.5 AP50 en COCO)
- Tres modos de conteo: zonas A->B (rutas), cruce de linea (aforo), y direcciones (cosine similarity)
- Tracking con ByteTrack, BoT-SORT, OC-SORT o SORT
- Auto-deteccion de GPU (CUDA/MPS) con `--device auto`
- SAHI para vehiculos pequenos en tomas aereas
- Zonas de exclusion para vehiculos estacionados
- Multi-anchor line crossing con threshold anti-jitter
- Polygon zone masks pre-computadas (O(1) lookup)
- Trail visualization por vehiculo (historial de trayectoria)
- OD matrix nested con breakdown por clase de vehiculo
- Umbrales de confianza por clase (car, moto, bus, truck)
- Filtros geometricos aprendidos del configurador
- NMS post-SAHI configurable
- Modo demo con scoreboard grande
- Shape metrics per-track (elongacion, area, aspect ratio)
- Density heatmap overlay de actividad vehicular
- Exportacion JSON, CSV, per-track CSV, OD matrix CSV
- Preview de zonas con detecciones YOLO en vivo
- 114 tests unitarios

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## Flujo

1. Configurar:

```bash
python setup.py --video assets/mi_video.mp4
```

Cargar config existente:

```bash
python setup.py --video assets/mi_video.mp4 --config config/config.json
```

2. Paso 0: zonas de exclusion (opcional)
3. Paso 1: calibracion YOLO (vista global, muestras, confianza por clase)
4. Paso 2: zonas poligonales o lineas de cruce
5. Paso 3: parametros SAHI -> guardar config.json

6. Ejecutar:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4
```

## Modos de conteo

### Zonas A->B (default)

Rutas entre zonas poligonales. Ideal para glorietas e intersecciones.

```bash
python main.py --config config/config.json --video assets/video.mp4
```

Config: `"counting_mode": "zones"` con `"zones": {"Norte": [...], "Sur": [...]}`

### Cruce de linea

Aforo simple con deteccion de direccion (arriba/abajo).

Config: `"counting_mode": "lines"` con `"lines": [{"name": "L1", "points": [...]}]`

### Direcciones (cosine similarity)

Clasifica vehiculos por vector de movimiento. Ideal para carreteras rectas.

Config: `"counting_mode": "directions"` con `"directions": {"Norte": [[100,200], [100,0]], "Sur": [[100,0], [100,200]]}`

## Detectores

### YOLO (default)

```bash
python main.py --config config/config.json --video assets/video.mp4
```

### RF-DETR (mayor precision, +9.5 AP50 vs YOLO11)

```bash
# Requiere: pip install rfdetr
python main.py --config config/config.json --video assets/video.mp4 \
  --detector rfdetr --rfdetr-variant medium --tracker sort
```

Variantes: `nano` (2.3ms), `small`, `medium` (4.4ms), `base`, `large` (6.8ms).
RF-DETR usa SORT/OC-SORT para tracking (no soporta ByteTrack nativo).

## Exportacion

```bash
# JSON + CSV de rutas
python main.py --config config/config.json --video assets/video.mp4 \
  --output-json results.json --output-csv routes.csv

# Per-track trajectories + OD matrix
python main.py --config config/config.json --video assets/video.mp4 \
  --output-tracks-csv tracks.csv --output-od-csv od_matrix.csv
```

## CLI flags

| Flag | Descripcion |
|------|-------------|
| `--detector yolo\|rfdetr` | Motor de deteccion (default: yolo) |
| `--rfdetr-variant nano\|small\|medium\|base\|large` | Tamaño RF-DETR (default: base) |
| `--device auto\|cpu\|cuda\|mps` | Device para inferencia (default: auto) |
| `--no-sahi` | Sin SAHI (mas rapido) |
| `--tracker bytetrack\|botsort\|sort\|ocsort` | Algoritmo de tracking |
| `--heatmap` | Density heatmap overlay de actividad |
| `--demo-mode` | Scoreboard grande |
| `--headless` | Sin ventana |
| `--max-frames N` | Limitar frames |
| `--no-save` | No guardar video |
| `--show-fps` | Mostrar FPS |
| `--benchmark` | Guardar metricas |
| `--output-json PATH` | Resultados JSON |
| `--output-csv PATH` | Rutas CSV |
| `--output-tracks-csv PATH` | Trayectorias per-track |
| `--output-od-csv PATH` | OD matrix como tabla |

## Tests

```bash
source env/bin/activate
python -m pytest tests/ -v
```

114 tests cubriendo: geometry, counting (3 modos), shape metrics, heatmap, config I/O, tracking, device detection.

## Documentacion

- [Guia de optimizacion y parametros](docs/OPTIMIZATION_GUIDE.md)
- [Guia paso a paso para glorietas](docs/ROUNDABOUT_GUIDE.md)
- [Tareas pendientes](docs/TASK_TODO.md)
- [Historial de tareas](docs/TASK_COMPLETED.md)

## Dependencias

- `ultralytics` (YOLO v8/v11)
- `opencv-python`
- `sahi`
- `lap`
- `filterpy`
- `torch` (auto-detect CUDA/MPS)
