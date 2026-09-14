# Car Counter

Conteo y tracking de vehiculos con YOLO/RF-DETR + tracking para videos de trafico.
Soporta glorietas, intersecciones, aforo por cruce de linea, clasificacion por direccion, y tomas aereas.

La demo local verificada procesa una línea durante 300 frames. Los seis cruces reportados son predicciones, no un conteo humano aprobado. Consulta el [estado verificado](docs/GUIDES/VERIFIED_STATE.md) antes de preparar una presentación.

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
  export_model.py            #   .pt -> .onnx (--model y --imgsz)
  extract_validation_frames.py  # Frames candidatos + dedup pHash
  pre_label_frames.py        #   YOLO teacher -> anotaciones LabelMe
  evaluate_pipeline.py       #   Metricas precision/recall/F1 vs ground truth

tests/                       # 316 tests (15 skip sin deps opcionales)
docs/                        # Documentacion
  GUIDES/                    #   Guias paso a paso
  RESEARCH/                  #   Evaluaciones de libs externas
```

## Features

### Core
- Detectores: YOLO (ultralytics) o RF-DETR opcional; exactitud en este material sujeta a evaluación humana
- Tres modos de conteo: zonas A->B (rutas), cruce de linea (aforo), y direcciones (cosine similarity)
- Tracking con ByteTrack, BoT-SORT, OC-SORT o SORT
- Auto-deteccion de GPU (CUDA/MPS) con `--device auto`
- SAHI opcional para inferencia por tiles; su beneficio debe medirse en el video objetivo
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
- JSON con `counting_events`, CSV de totales, CSV de tracks y matriz origen/destino
- Metadatos del video, perfil y ejecución; eventos con frame de confirmación, ID, clase y sentido/ruta
- Benchmark detallado con desglose por etapa
- OD matrix nested con breakdown por clase de vehiculo

### Validacion
- Workflow completo para medir precision real vs ground truth humano
- Perceptual hashing DCT 64-bit para dedup de frames
- Preetiquetas YOLO conservadas para revisión humana, sin sobrescribir correcciones existentes
- Metricas: precision, recall, F1, counting accuracy (global y por clase)
- Formato de anotación LabelMe (editor externo; su interfaz y asistencia opcional requieren revisión manual)

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

## Atajos con make

```bash
make help              # lista todos los comandos
make setup             # dibuja zonas (GUI)      -> config/config.json
make run               # pipeline en clip corto  -> output/results.json
make run-aerial        # aforo de una linea, video normal + VisDrone + recorte
make validate-routes   # compara conteo vs humano por ruta
make test              # suite de tests
```

Ver [docs/GUIDES/route_validation.md](docs/GUIDES/route_validation.md) para validar el conteo A->B.

La demo aerea usa `glorieta_test1min.mp4`, el modelo local `yolov8l-visdrone.pt`
y [una configuracion de ejemplo](docs/GUIDES/aerial_counting.example.json).
Cuenta cruces en una linea del anillo oeste durante 300 frames; guarda el video,
JSON y CSV en `output/aerial_demo*`. Es una prueba de aforo parcial. Las rutas
de toda la glorieta requieren otra configuracion y validacion por ruta.

`settings.inference_roi` permite limitar la inferencia a `[x1, y1, x2, y2]` en
pixeles del video original. Las zonas, lineas, exclusiones y coordenadas exportadas
siguen usando el video completo. El recorte debe contener todo el trayecto que
se pretende contar. Ver [el analisis del conteo](docs/RESEARCH/COUNTING_AUDIT_2026_09_06.md).

La [guía de calibración y replay](docs/GUIDES/DETECTION_CALIBRATION_REPLAY.md) explica
las pruebas con varios frames, los umbrales de tracking y cómo reutilizar detecciones.

## Flujo basico

1. **Configurar** (una vez por video):

```bash
python setup.py --video assets/mi_video.mp4
```

- Paso 0: zonas de exclusion (opcional)
- Paso 1: calibracion YOLO (vista global, muestras, confianza por clase)
- Paso 2: zonas poligonales, lineas de cruce, o vectores de direccion
- Paso 3: activar SAHI y ajustar umbrales del tracker -> guardar `config/config.json`

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

### RF-DETR (opcional)

```bash
# Requiere: pip install rfdetr
python main.py --config config/config.json --video assets/video.mp4 \
  --detector rfdetr --rfdetr-variant medium --tracker sort
```

Variantes aceptadas por la CLI: `nano`, `small`, `medium`, `base`, `large`. Su disponibilidad depende del paquete instalado. El flujo compartido entrega sus cajas a ByteTrack, BoT-SORT, SORT u OC-SORT; no depende de `model.track()`. No hay un benchmark local que demuestre mayor precisión de RF-DETR.

### Export ONNX para evaluar rendimiento

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

En `main.py --benchmark`, las etapas son `detection` (incluye tracking), `counting`, `visualization` y `writing`. El script standalone no carga el perfil de aforo, usa zonas vacías y aproxima dibujo/escritura; no sustituye una medición del flujo real. Los FPS de replay excluyen inferencia.

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

# 3. [Manual] Corregir cajas/clases y marcar flags.reviewed=true tras revisar

# 4. Evaluar: precision/recall/F1/counting accuracy por clase
python scripts/evaluate_pipeline.py --config config/config.json
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
| `--no-sahi` | Desactiva SAHI aunque el perfil lo habilite |
| `--record-detections PATH` | Graba cajas anteriores a filtros/tracking en una caché nueva |
| `--replay-detections PATH` | Reutiliza una caché compatible y completa |
| `--camera-max-drift-px N` | Detiene si no puede validar la cámara dentro del umbral; no estabiliza |
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

**316 pruebas aprobadas y 15 omitidas**, comprobadas en la revisión documental del 2026-09-14. Las omisiones requieren dependencias opcionales; no prueban DB/API. Este resultado no mide exactitud humana del conteo.

Cobertura: geometry, counting (3 modos), shape metrics, heatmap, config I/O, tracking,
device detection, profiler, db, api, drawing, validation (pHash + LabelMe + metricas),
state machine e integracion end-to-end.

## Documentacion

Índice y convenciones: [docs/README.md](docs/README.md).

- [Estado verificado y límites](docs/GUIDES/VERIFIED_STATE.md)
- [Protocolo de pruebas manuales](docs/GUIDES/MANUAL_VALIDATION.md)
- [Validación de eventos por ruta, clase y tiempo](docs/GUIDES/ROUTE_EVENT_REVIEW.md)
- [Guia de validacion (pHash + LabelMe + metricas)](docs/GUIDES/validation_workflow.md)
- [Guia de optimizacion y parametros](docs/OPTIMIZATION_GUIDE.md)
- [Guia paso a paso para glorietas](docs/ROUNDABOUT_GUIDE.md)
- [Evaluación histórica de supervision, sin benchmark ejecutado](docs/RESEARCH/supervision_eval.md)
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
