# Tareas Pendientes

Backlog de mejoras para el proyecto Car Counter.
Cada tarea tiene criterios de aceptacion claros para validacion.

**Prioridad:** P0 = critico para demo, P1 = mejora importante, P2 = nice-to-have

---

## TODO-019: Integrar libSQL como DB local del proyecto

**Prioridad:** P1
**Dependencia:** Smoke test manual completado

### Objetivo

Reemplazar archivos sueltos (config.json, results.json) con una DB local libSQL que
organice proyectos, configuraciones y resultados. libSQL soporta vectores nativos,
habilitando a futuro busqueda por similitud de detecciones y patrones de trafico.

### Contexto tecnico

- Solo trabajamos con videos grabados (sin streams en vivo)
- La DB debe vivir en `data/carcounter.db` (gitignored)
- JSON sigue funcionando como fallback (no romper compatibilidad hacia atras)
- `main.py` ya genera resultados en JSON/CSV via `carcounter/export.py`

### Esquema base

```sql
projects  -> id, name, video_path, model_path, created_at
configs   -> id, project_id, json_blob, notes, created_at
runs      -> id, config_id, frames, duration, vehicles, routes_json, created_at
od_entries -> run_id, origin, destination, count, vehicle_class
```

### Fase futura (vectores — no implementar ahora)

- Embeddings de vehiculos detectados para re-identificacion
- Busqueda por similitud ("vehiculos parecidos a este")

### Criterios de aceptacion

- [ ] `libsql-experimental` en requirements.txt
- [ ] Nuevo modulo `carcounter/db.py` con funciones: `init_db()`, `save_run()`, `list_runs()`
- [ ] Esquema base creado automaticamente al primer run (migrations simples con CREATE TABLE IF NOT EXISTS)
- [ ] `main.py` llama `db.save_run()` al finalizar, registrando metricas del run
- [ ] CLI: `python -m carcounter.db list` muestra runs anteriores
- [ ] DB local en `data/carcounter.db` (agregar a .gitignore)
- [ ] JSON sigue funcionando como antes (no romper `export.py`)
- [ ] Tests: al menos test_db.py con test de init, save y list

---

## TODO-022: Evaluar supervision library (Roboflow)

**Prioridad:** P2

### Hallazgos del analisis (2026-03-24)

Se analizo el repo roboflow/supervision (36.8k stars). Patrones ya adoptados:
- [x] Polygon masks pre-computadas (O(1) zone lookup) -> implementado
- [x] Multi-anchor line crossing + crossing threshold -> implementado
- [x] Trail visualization -> implementado

### Objetivo concreto para esta tarea

Evaluar si migrar a `supervision` reduce codigo en 3 modulos especificos:

1. **`carcounter/drawing.py`** — comparar con `sv.BoxAnnotator`, `sv.TraceAnnotator`, `sv.HeatMapAnnotator`
2. **`carcounter/counting.py`** — comparar con `sv.LineZone`, `sv.PolygonZone`
3. **`carcounter/tracking.py`** — comparar overhead de `sv.Detections` vs tuplas actuales

### Criterios de aceptacion

- [ ] Documento `docs/RESEARCH/supervision_eval.md` con analisis comparativo
- [ ] Prototipo funcional en rama separada usando supervision para drawing.py (solo dibujo)
- [ ] Benchmark: comparar FPS con drawing actual vs supervision annotators en `glorieta_fast.MP4`
- [ ] Decision documentada: migrar / adoptar parcial / descartar con justificacion

---

## TODO-023: Video batching para inferencia GPU

**Prioridad:** P2
**Dependencia:** GPU disponible (MPS en Mac o CUDA en Linux)

### Contexto

- YOLO de ultralytics ya gestiona batching interno en GPU
- El batching manual en el pipeline actual rompe la secuencialidad del tracker
- El cuello de botella real es la interaccion deteccion-tracker: el tracker necesita frames en orden

### Objetivo

Medir primero, optimizar despues. Identificar el verdadero cuello de botella del pipeline
en videos largos (los `.mp4` de 2-3GB en `assets/`).

### Criterios de aceptacion

- [ ] Script `scripts/benchmark_pipeline.py` que corre el pipeline completo en `glorieta_fast.MP4` y reporta:
  - FPS promedio por etapa: deteccion / tracking / conteo / drawing / escritura video
  - Uso de memoria GPU/CPU
  - Tiempo total
- [ ] `--benchmark` flag en `main.py` ya existe — extenderlo para desglosar por etapa
- [ ] Si deteccion > 60% del tiempo: implementar pre-fetch de frames en thread separado (producer-consumer)
- [ ] Si escritura video > 20% del tiempo: mover VideoWriter a thread separado
- [ ] Resultado documentado en `docs/OPTIMIZATION_GUIDE.md`
- [ ] No romper tests existentes (153 tests deben seguir pasando)

---

## TODO-024: Export modelo ONNX/TensorRT

**Prioridad:** P2
**Dependencia:** TODO-023 completado (saber donde esta el cuello de botella)

### Contexto

Los videos grandes (`glorieta_normal.mp4` = 1.9GB, `glorieta_normal_2.MP4` = 3.2GB)
son lentos con modelos `.pt`. ONNX puede dar 2-3x speedup en CPU. TensorRT es solo para CUDA.

### Criterios de aceptacion

- [ ] Script `scripts/export_model.py --model models/yolo/yolov11l.pt --format onnx`
- [ ] `main.py` acepta modelos `.onnx` sin cambios al CLI (ya detecta por extension)
- [ ] Verificar que `carcounter/detection.py` funciona con modelo ONNX cargado via YOLO wrapper
- [ ] Benchmark comparativo documentado: `.pt` vs `.onnx` FPS en `glorieta_fast.MP4`
- [ ] TensorRT: solo si hay GPU CUDA disponible, documentar como opcional
- [ ] `paths.py` no necesita cambios (el usuario pasa `--model` con la ruta)

---

## TODO-025: Visualizacion de direction vectors

**Prioridad:** P2
**Origen:** Analisis de repos

### Objetivo

En modo `directions`, los vectores de direccion configurados no son visibles en el frame.
El usuario no puede verificar visualmente si las flechas estan bien colocadas.

### Contexto tecnico

- `directions_config` viene del `config.json` como dict: `{name: [[x0,y0],[x1,y1]]}`
- `VehicleCounter` ya tiene `self._dir_vectors` computados
- `drawing.py` tiene `draw_zones` y `draw_lines` pero no `draw_directions`

### Criterios de aceptacion

- [ ] Nueva funcion `draw_direction_vectors(frame, directions_config)` en `carcounter/drawing.py`
- [ ] Dibuja una flecha por direccion con su nombre encima
- [ ] `main.py` la llama cuando `COUNTING_MODE == "directions"` (junto al bloque de visualizacion existente)
- [ ] `setup.py` paso 2 muestra las flechas al definir/editar direcciones
- [ ] Tests unitarios en `tests/test_drawing.py` (o nuevo archivo si no existe)
- [ ] No afectar modos `zones` ni `lines`

---

## TODO-026: FastAPI REST API minimo

**Prioridad:** P2
**Dependencia:** TODO-019 (libSQL) para el endpoint de runs historicos

### Objetivo

API REST read-only para exponer datos de runs y consultar resultados desde herramientas externas.

### Endpoints requeridos

```
GET  /api/stats          -> estadisticas del run actual (en memoria)
GET  /api/runs           -> lista de runs desde libSQL (requiere TODO-019)
GET  /api/runs/{id}      -> detalle + routes_matrix + od_matrix
GET  /api/stream         -> MJPEG stream del video procesado (frame actual)
```

### Contexto tecnico

- `ProcessingEngine` en `carcounter/engine.py` ya tiene estado observable y callbacks
- El engine corre en thread separado — la API debe leer estado via callbacks, no bloquear
- Solo lectura, no escritura (no se configura via API)

### Criterios de aceptacion

- [ ] `fastapi` y `uvicorn` en requirements.txt (como dependencias opcionales)
- [ ] Nuevo modulo `carcounter/api.py` con los 4 endpoints
- [ ] `main.py` acepta `--serve` flag para arrancar la API en paralelo al procesamiento
- [ ] El stream MJPEG funciona mientras el video se procesa
- [ ] Sin autenticacion (es localhost only)
- [ ] Tests: `tests/test_api.py` con test de cada endpoint usando `httpx` + `TestClient`
