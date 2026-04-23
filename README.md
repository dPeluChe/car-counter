# Car Counter

Conteo y tracking de vehiculos con YOLO/RF-DETR + tracking para videos de trafico.
Soporta glorietas, intersecciones, aforo por cruce de linea, clasificacion por direccion, y tomas aereas.

## Arquitectura

```
main.py                      # Orquestador del pipeline (CLI + loop)
setup.py                     # Configurador interactivo (Tkinter)

carcounter/                  # Paquete core
  runtime.py                 #   Helpers de init/process/export (usados por main.py)
  engine.py                  #   ProcessingEngine event-driven (pause/resume/callbacks)
  detection.py               #   Pipeline YOLO/RF-DETR + SAHI + filtros
  counting.py                #   Maquina de estados (zones + lines + directions)
  tracking.py                #   Asociacion clase-track
  drawing.py                 #   Dibujo OpenCV (zonas, HUD, trails, heatmap, direction vectors)
  geometry.py                #   Zone masks, point-in-polygon, IoU, NMS, cosine similarity
  constants.py               #   Clases COCO, colores, IDs
  calibration.py             #   ROI, escala, muestras, constraints geometricos
  config_io.py               #   Lectura/escritura de config.json
  app_config.py              #   Dataclasses tipadas (SettingsConfig, SampleConstraints)
  export.py                  #   Export JSON/CSV/OD-matrix/benchmark
  profiler.py                #   Medicion por etapa (detection/counting/viz/writing)
  device.py                  #   Auto-deteccion GPU (CUDA/MPS/CPU)
  paths.py                   #   Resolucion centralizada de rutas
  db.py                      #   libSQL local (historial de runs, opcional)
  api.py                     #   FastAPI REST + MJPEG stream (--serve, opcional)
  validation.py              #   pHash dedup, LabelMe JSON, IoU matching, metricas
  rfdetr_detector.py         #   RF-DETR wrapper (opcional)
  ocsort_wrapper.py          #   OC-SORT wrapper (opcional)
  sort.py                    #   SORT tracker (fallback)
  app.py                     #   Wizard GUI principal (python -m carcounter)
  app_theme.py               #   Constantes visuales + helper btn()
  app_steps/                 #   Mixins del wizard (step_model/step_video/step_launch)

setup_panels/                # Mixins del configurador
  canvas.py                  #   Zoom, pan, redraw, overlays compartidos
  state.py                   #   init_state() con todas las variables de Tk
  step0_exclusion.py         #   Paso 0: zonas de exclusion
  step1_calibration.py       #   Paso 1: calibracion YOLO
  calib_tests.py             #   Paso 1: pruebas YOLO/SAHI (vista global + recuadro)
  step2_zones.py             #   Paso 2: panel compartido + modo zonas
  step2_lines.py             #   Paso 2: modo lineas de cruce
  step2_directions.py        #   Paso 2: modo vectores de direccion
  step2_preview.py           #   Paso 2: preview con YOLO overlay
  step3_sahi.py              #   Paso 3: SAHI + guardado

scripts/                     # Utilidades CLI
  benchmark_pipeline.py      #   Benchmark por etapa sobre un video
  export_model.py            #   .pt -> .onnx (con --half para FP16)
  extract_validation_frames.py  # Frames candidatos + dedup pHash
  pre_label_frames.py        #   YOLO teacher -> anotaciones LabelMe
  evaluate_pipeline.py       #   Metricas precision/recall/F1 vs ground truth

tests/                       # 204 tests unitarios (15 skip sin deps opcionales)
docs/                        # Documentacion
  GUIDES/                    #   Guias paso a paso
  RESEARCH/                  #   Evaluaciones de libs externas
```

## Features

### Core
- Detectores: YOLO (ultralytics) o RF-DETR (Roboflow, +9.5 AP50 en COCO)
- Tres modos de conteo: zonas A->B (rutas), cruce de linea (aforo), y direcciones (cosine similarity)
- Tracking con ByteTrack, BoT-SORT, OC-SORT o SORT
- Auto-deteccion de GPU (CUDA/MPS) con `--device auto`
- SAHI para vehiculos pequenos en tomas aereas
- Zonas de exclusion para vehiculos estacionados
- Multi-anchor line crossing con threshold anti-jitter
- Polygon zone masks pre-computadas (O(1) lookup)
- Trail visualization por vehiculo (historial de trayectoria)
- Density heatmap overlay
- Visualizacion de direction vectors en modo `directions`

### Observabilidad
- **Profiler por etapa**: detection/counting/visualization/writing en ms/frame con `--benchmark`
- **FastAPI REST API** (opcional): endpoints `/api/stats`, `/api/runs`, `/api/runs/{id}`, `/api/stream` (MJPEG) con `--serve`
- **libSQL DB local** (opcional): historial automatico de runs en `data/carcounter.db`
- CLI para listar runs: `python -m carcounter.db list`

### Exportacion
- JSON, CSV, per-track CSV, OD matrix CSV
- Benchmark detallado con desglose por etapa
- OD matrix nested con breakdown por clase de vehiculo

### Validacion
- Workflow completo para medir precision real vs ground truth humano
- Perceptual hashing DCT 64-bit para dedup de frames
- Pre-labeling con YOLO teacher (3-5x mas rapido que anotar desde cero)
- Metricas: precision, recall, F1, counting accuracy (global y por clase)
- Integracion con [LabelMe v6.1+](https://labelme.io) (herramienta externa)

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### Dependencias opcionales

```bash
# RF-DETR
pip install rfdetr

# FastAPI REST API (--serve)
pip install fastapi uvicorn httpx

# DB local de runs
pip install libsql-experimental
```

## Flujo basico

1. **Configurar** (una vez por video):

```bash
python setup.py --video assets/mi_video.mp4
```

- Paso 0: zonas de exclusion (opcional)
- Paso 1: calibracion YOLO (vista global, muestras, confianza por clase)
- Paso 2: zonas poligonales, lineas de cruce, o vectores de direccion
- Paso 3: parametros SAHI -> guardar `config/config.json`

2. **Ejecutar**:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4
```

3. **Consultar historial** (si libSQL instalado):

```bash
python -m carcounter.db list
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
Los vectores se dibujan como flechas con su nombre en el frame.

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

### Export ONNX para inferencia mas rapida

```bash
python scripts/export_model.py --model models/yolo/yolov11l.pt
python main.py --model models/yolo/yolov11l.onnx --config config/config.json
```

## Benchmark y profiling

```bash
# Benchmark standalone con desglose por etapa
python scripts/benchmark_pipeline.py --video assets/glorieta_fast.MP4 --max-frames 200

# Benchmark durante un run normal
python main.py --benchmark --config config/config.json --video assets/video.mp4
# → genera output/benchmarks/*.txt con ms/frame por etapa
```

Etapas medidas: `detection`, `counting`, `visualization`, `writing`.

## FastAPI server (opcional)

```bash
# Requiere: pip install fastapi uvicorn
python main.py --serve --serve-port 8000 --config config/config.json --video assets/video.mp4
```

Endpoints (read-only, localhost):

| Endpoint | Descripcion |
|----------|-------------|
| `GET /api/health` | Status del server |
| `GET /api/stats` | Stats del run actual (frame_count, fps, routes_matrix) |
| `GET /api/runs?limit=N` | Historial de runs desde libSQL |
| `GET /api/runs/{id}` | Detalle + OD matrix |
| `GET /api/stream` | MJPEG stream del frame actual |

## Validacion del pipeline

Workflow completo para medir precision real contra anotaciones humanas:

```bash
# 1. Extraer frames candidatos con dedup pHash
python scripts/extract_validation_frames.py --video assets/glorieta_fast.MP4

# 2. Pre-etiquetar con YOLO teacher (ahorra tiempo al anotador)
python scripts/pre_label_frames.py

# 3. [Manual] Corregir anotaciones en LabelMe v6.1+

# 4. Evaluar: precision/recall/F1/counting accuracy por clase
python scripts/evaluate_pipeline.py
```

Ver [docs/GUIDES/validation_workflow.md](docs/GUIDES/validation_workflow.md) para detalles.

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
| `--show-fps` | Mostrar HUD con FPS |
| `--benchmark` | Exportar metricas por etapa |
| `--serve` | Arrancar FastAPI server en thread separado |
| `--serve-port PORT` | Puerto del server (default: 8000) |
| `--output-json PATH` | Resultados JSON |
| `--output-csv PATH` | Rutas CSV |
| `--output-tracks-csv PATH` | Trayectorias per-track |
| `--output-od-csv PATH` | OD matrix como tabla |
| `--log-level DEBUG\|INFO\|WARNING\|ERROR` | Nivel de logging |

## Tests

```bash
source env/bin/activate
python -m pytest tests/ -v
```

**204 tests passing + 15 skipped** (skips requieren `fastapi` y/o `libsql-experimental` instalados).

Cobertura: geometry, counting (3 modos), shape metrics, heatmap, config I/O, tracking,
device detection, profiler, db, api, drawing, validation (pHash + LabelMe + metricas),
state machine e integracion end-to-end.

## Documentacion

- [Guia de validacion (pHash + LabelMe + metricas)](docs/GUIDES/validation_workflow.md)
- [Guia de optimizacion y parametros](docs/OPTIMIZATION_GUIDE.md)
- [Guia paso a paso para glorietas](docs/ROUNDABOUT_GUIDE.md)
- [Evaluacion de supervision library](docs/RESEARCH/supervision_eval.md)
- [Tareas pendientes](docs/TASK_TODO.md)
- [Historial de tareas](docs/TASK_COMPLETED.md)

## Dependencias

**Core (requirements.txt):**

- `ultralytics` (YOLO v8/v11)
- `opencv-python`
- `sahi`
- `lap`
- `filterpy`
- `torch` (auto-detect CUDA/MPS)

**Opcionales** (instalar segun feature):

- `rfdetr` — detector RF-DETR
- `fastapi uvicorn httpx` — REST API (`--serve`)
- `libsql-experimental` — DB local de runs
- `trackers` — OC-SORT tracker
