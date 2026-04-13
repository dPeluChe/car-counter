# Tareas Pendientes

Backlog de mejoras para el proyecto Car Counter.
Cada tarea tiene criterios de aceptacion claros para validacion.

**Prioridad:** P0 = critico para demo, P1 = mejora importante, P2 = nice-to-have

---

## TODO-019: Integrar libSQL como DB local del proyecto

**Prioridad:** P1
**Dependencia:** Validacion funcional post-refactor

### Objetivo

Reemplazar archivos sueltos (config.json, results.json) con una DB local libSQL que organice proyectos, configuraciones y resultados. libSQL soporta vectores nativos, lo cual habilita a futuro busqueda por similitud de detecciones y patrones de trafico.

### Esquema base

```sql
projects  -> id, name, video_path, model_path, created_at
configs   -> id, project_id, json_blob, notes, created_at
runs      -> id, config_id, frames, duration, vehicles, routes_json, created_at
od_entries -> run_id, origin, destination, count, vehicle_class
```

### Fase futura (vectores)

- Embeddings de vehiculos detectados para re-identificacion
- Busqueda por similitud ("vehiculos parecidos a este")
- Patrones de trafico como vectores para comparar sesiones

### Criterios de aceptacion

- [ ] `libsql-experimental` o `libsql-client` en requirements.txt
- [ ] Esquema base creado al primer run (migrations automaticas)
- [ ] `setup.py` guarda config en DB al guardar (ademas del JSON)
- [ ] `main.py` registra cada run con metricas en DB
- [ ] CLI para listar proyectos/runs: `python -m carcounter.db list`
- [ ] DB local en `data/carcounter.db` (gitignored)
- [ ] JSON sigue funcionando como fallback (backward compatible)

---

## ~~TODO-020: Tests unitarios~~ COMPLETADO -> DONE-024
## ~~TODO-021: Soporte GPU~~ COMPLETADO -> DONE-025

---

## TODO-022: Evaluar supervision library (Roboflow)

**Prioridad:** P2

### Hallazgos del analisis (2026-03-24)

Se analizo el repo roboflow/supervision (36.8k stars). Patrones ya adoptados:
- [x] Polygon masks pre-computadas (O(1) zone lookup) -> implementado
- [x] Multi-anchor line crossing + crossing threshold -> implementado
- [x] Trail visualization -> implementado

Patrones pendientes de evaluar:
- [ ] Detections dataclass unificado (reemplaza tuplas)
- [ ] Annotator base class con composicion
- [ ] Callback-based slicer para SAHI
- [ ] Migrar completamente a supervision (elimina counting.py + tracking.py + drawing.py parcial)

---

## TODO-023: Video batching para inferencia GPU

**Prioridad:** P2
**Dependencia:** TODO-021 (completado)
**Nota:** YOLO de ultralytics ya gestiona batching interno en GPU. El batching manual requiere diseño cuidadoso por interaccion con tracker secuencial.

---

## TODO-024: Export modelo ONNX/TensorRT

**Prioridad:** P2

### Criterios de aceptacion

- [ ] Script `scripts/export_model.py` para convertir .pt a .onnx
- [ ] `main.py` acepta modelos .onnx y .engine ademas de .pt
- [ ] Benchmark comparativo .pt vs .onnx vs .engine

---

## ~~TODO-025: Config tipado con dataclass~~ COMPLETADO -> DONE-027

---

## TODO-026: Visualizacion de direction vectors

**Prioridad:** P2
**Origen:** Analisis de repos

### Objetivo

Dibujar los vectores de direccion configurados en modo `directions` sobre el frame para feedback visual.

### Criterios de aceptacion

- [ ] Flechas dibujadas con nombre de direccion sobre el frame
- [ ] Visibles en main.py cuando `counting_mode == "directions"`
- [ ] Soporte en setup.py para dibujar/editar direction vectors (paso nuevo o extension del paso 2)

---

## TODO-027: FastAPI REST API minimo

**Prioridad:** P2
**Dependencia:** TODO-019 (libSQL)
**Origen:** Analisis de rust-road-traffic

### Objetivo

API REST read-only para exponer datos de runs y zonas.

### Endpoints

```
GET  /api/zones          -> zonas configuradas
GET  /api/stats          -> estadisticas del run actual
GET  /api/runs           -> lista de runs desde libSQL
GET  /api/runs/{id}      -> detalle + routes + OD matrix
GET  /api/stream         -> MJPEG stream del video procesado
```
