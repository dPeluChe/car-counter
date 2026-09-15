# Car Counter

Conteo y tracking de vehículos en video de tráfico con YOLO o RF-DETR y trackers persistentes. Cuenta rutas entre zonas (glorietas, intersecciones), cruces de línea y direcciones.

**Estado:** la demo verificada cuenta una línea durante 300 frames; sus seis cruces son predicciones, no un conteo humano. Antes de presentar resultados lee [VERIFIED_STATE.md](docs/GUIDES/VERIFIED_STATE.md).

## Setup

```bash
python -m venv env
env/bin/pip install -r requirements.txt
```

Opcionales según la función: `rfdetr` (detector RF-DETR), `trackers` (OC-SORT), `fastapi uvicorn httpx` (`--serve`), `libsql-experimental` (historial de runs).

## Uso

```bash
make help              # todos los atajos
make setup             # configurador Tk: exclusiones, calibración, zonas/líneas -> config/config.json
make run               # pipeline en clip corto -> output/results.json
make run-aerial        # demo aérea: VisDrone + ROI, una línea, 300 frames (inferencia)
make replay-aerial     # misma demo desde la caché local, sin inferencia
make segment-video VIDEO=assets/glorieta_normal.mp4   # tramos de cámara estable + frame de referencia
make validate-routes   # conteo por ruta contra referencia humana
make test
```

Sin make:

```bash
python setup.py --video assets/mi_video.mp4                          # configurar una vez por video
python main.py --config config/config.json --video assets/mi_video.mp4
python main.py --help                                                # todos los flags
python -m carcounter                                                 # wizard: modelo, video, lanzamiento
```

Repetir pruebas sin inferencia, ajustar tracker y vigilar la cámara: [DETECTION_TUNING.md](docs/GUIDES/DETECTION_TUNING.md).

La demo aérea necesita los archivos locales `assets/glorieta_test1min.mp4` y `models/yolo/yolov8l-visdrone.pt`, y usa [aerial_counting.example.json](docs/GUIDES/aerial_counting.example.json).

## Modos de conteo

| Modo | Config | Resultado |
|---|---|---|
| `zones` (default) | `"zones": {"Norte": [...], "Sur": [...]}` | Rutas A→B y matriz origen/destino |
| `lines` | `"lines": [{"name": "L1", "points": [...]}]` | Cruces por línea y sentido |
| `directions` | `"directions": {"Norte": [[100,200],[100,0]]}` | Clasificación por vector de movimiento |

`settings.inference_roi` limita la inferencia a `[x1, y1, x2, y2]` del video original; zonas, líneas y salidas siguen en coordenadas completas. Cada conteo se exporta en `counting_events` con frame, ID, clase, grupo EPS (`ligeros`, `pesados`, `dos_ruedas`) y ruta; `routes_by_group` resume cada ruta por grupo ([alcance del aforo](docs/GUIDES/COUNTING_SCOPE.md)).

## Arquitectura

```
main.py                  CLI del pipeline
setup.py                 configurador Tk (paneles en setup_panels/)
carcounter/
  runtime.py             inicialización, loop y export usados por main.py
  detection.py           detección + SAHI + filtros, entrega cajas al tracker
  detector.py            interfaz y backends YOLO, RF-DETR y SAHI; filtros de detección
  detection_cache.py     caché SQLite para replay
  counting.py            máquina de zonas, eventos y consenso de clase; lines/directions en counting_modes.py
  tracking.py            wrapper de ByteTrack/BoT-SORT y clase por track; sort.py y ocsort_wrapper.py
  camera_motion.py       monitor ORB/RANSAC de deriva de cámara
  calibration.py         calibración del configurador
  geometry.py            polígonos, IoU, NMS, cruce de línea
  export.py              JSON, CSV, matriz OD, benchmark
  validation.py          pHash, LabelMe, métricas contra ground truth
  app_config.py          configuración tipada con validación
  app.py, app_steps/     wizard GUI (python -m carcounter)
  models.py, ui_models.py  catálogo y descarga de modelos
  api.py, db.py          REST/MJPEG y libSQL (opcionales)
scripts/                 evaluate_pipeline, validate_routes, extract_validation_frames,
                         pre_label_frames, audit_camera_motion, benchmark_pipeline,
                         export_model, recurring_review
tests/                   pytest
```

## API opcional

`python main.py --serve --serve-port 8000 ...` expone en localhost, solo lectura: `/api/health`, `/api/stats`, `/api/runs?limit=N`, `/api/runs/{id}` y `/api/stream` (MJPEG). El historial requiere libSQL.

## Tests

```bash
env/bin/python -m pytest -q
```

Último resultado registrado en [VERIFIED_STATE.md](docs/GUIDES/VERIFIED_STATE.md#validación-automática-y-límites). Los tests no miden exactitud humana del conteo.

## Documentación

Estructura declarada en [`.doctos.yml`](.doctos.yml), índice en [docs/README.md](docs/README.md). Pendientes en [docs/TASK_TODO.md](docs/TASK_TODO.md).
