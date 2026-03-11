# Tareas Pendientes

Backlog de mejoras para el proyecto Car Counter (glorieta).
Cada tarea tiene criterios de aceptacion claros para validacion.

**Prioridad:** P0 = critico para demo, P1 = mejora importante, P2 = nice-to-have

---

## TODO-009: Scoreboard grande en la visualizacion

**Prioridad:** P2
**Archivo:** `main_glorieta.py`
**Funcion:** `draw_routes_panel()`

### Problema

El panel de rutas actual es pequeno (280px) y dificil de leer en demos o presentaciones.

### Que hacer

- Agregar un flag `--big-panel` o `--demo-mode`
- En ese modo, el panel de rutas ocupa mas espacio, usa fuentes mas grandes
- Mostrar un contador total grande estilo "scoreboard": `TOTAL: 42 vehiculos`
- Los colores de cada ruta deben coincidir con los colores de las zonas origen

### Criterios de aceptacion

- [ ] `--demo-mode` activa el panel grande
- [ ] Sin el flag, la visualizacion es identica a la actual
- [ ] El contador total es visible a distancia en una pantalla 1080p
- [ ] Los colores de ruta corresponden a los colores de zona
- [ ] No se superpone con las zonas ni con los bounding boxes

---

## TODO-010: NMS adicional post-SAHI

**Prioridad:** P2
**Archivo:** `main_glorieta.py`

### Problema

El NMS interno de SAHI a veces deja detecciones duplicadas borderline (IoU ~0.4-0.5) que generan dos tracks para el mismo vehiculo.

### Que hacer

- Despues de recolectar las detecciones de SAHI, aplicar un segundo paso de NMS con umbral mas agresivo (ej. IoU 0.3)
- Usar la funcion `bbox_iou` que ya existe en el archivo
- Solo aplicar en el path SAHI, no en el path nativo de ByteTrack

### Criterios de aceptacion

- [ ] Existe funcion `apply_nms(detections, iou_threshold)` o similar
- [ ] Se aplica solo en el path SAHI
- [ ] El umbral es configurable desde el config JSON (campo `sahi.nms_threshold`)
- [ ] Reduce duplicados sin eliminar detecciones legitimas cercanas
- [ ] Smoke test pasa

---

