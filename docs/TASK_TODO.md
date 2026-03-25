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

## ~~TODO-020: Tests unitarios para modulos core~~ COMPLETADO

Movido a TASK_COMPLETED.md (DONE-024). 81 tests en 4 archivos, 0.2s.

---

## ~~TODO-021: Soporte GPU en inferencia~~ COMPLETADO

Movido a TASK_COMPLETED.md (DONE-025). Auto-detect CPU/CUDA/MPS, `--device auto`.

---

## TODO-022: Investigar supervision library (Roboflow)

**Prioridad:** P2
**Dependencia:** Ninguna

### Objetivo

Evaluar si `supervision` puede simplificar `detection.py` + `drawing.py` + `tracking.py`. La libreria unifica tracking, counting por lineas/zonas, y annotators de visualizacion.

### Criterios de aceptacion

- [ ] Documento de evaluacion con pros/cons vs implementacion actual
- [ ] Prototipo minimo con supervision que replique el flujo zones
- [ ] Comparativa de precision y rendimiento
- [ ] Decision documentada: adoptar, adoptar parcialmente, o descartar

---

## TODO-023: Video batching para inferencia GPU

**Prioridad:** P2
**Dependencia:** TODO-021

### Objetivo

Procesar N frames en batch para la inferencia YOLO en vez de 1 por 1. Mejora throughput significativamente en GPU.

### Criterios de aceptacion

- [ ] Flag `--batch-size N` (default 1)
- [ ] Acumulacion de frames y envio en batch a YOLO
- [ ] Tracking se aplica post-batch con correspondencia correcta
- [ ] Benchmark comparativo batch=1 vs batch=4 vs batch=8

---

## TODO-024: Export modelo ONNX/TensorRT

**Prioridad:** P2
**Dependencia:** Ninguna

### Objetivo

Soportar modelos exportados a ONNX o TensorRT para inferencia mas rapida sin dependencia completa de PyTorch.

### Criterios de aceptacion

- [ ] Script `scripts/export_model.py` para convertir .pt a .onnx
- [ ] `main.py` acepta modelos .onnx y .engine ademas de .pt
- [ ] Benchmark comparativo .pt vs .onnx vs .engine
- [ ] Documentado en OPTIMIZATION_GUIDE.md
