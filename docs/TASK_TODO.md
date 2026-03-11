# Tareas Pendientes

Backlog de mejoras para el proyecto Car Counter (glorieta).
Cada tarea tiene criterios de aceptacion claros para validacion.

**Prioridad:** P0 = critico para demo, P1 = mejora importante, P2 = nice-to-have

---

## TODO-018: Zonas de exclusion para vehiculos estacionados

**Prioridad:** P0
**Archivos:** `setup_glorieta.py`, `main_glorieta.py`

### Problema

YOLO detecta todos los vehiculos visibles, incluyendo estacionados que no forman parte del flujo de transito. Estos generan tracks innecesarios, ensucian la visualizacion, y consumen recursos de tracking. La maquina de estados no los cuenta como ruta, pero no hay forma de eliminarlos de la deteccion.

### Que hacer

#### En el configurador (`setup_glorieta.py`):

- Agregar un **Paso 0: Zonas de exclusion** antes del paso de Calibracion
  - Misma mecanica de dibujo de poligonos que las zonas de calle (Paso 2)
  - Color rojo/naranja para diferenciar visualmente de las zonas de entrada/salida
  - Nombre por defecto: "Exclusion 1", "Exclusion 2", etc.
  - Se pueden agregar, eliminar y editar
  - Preview del video con las zonas de exclusion dibujadas (reutilizar patron del Paso 2)
- Guardar las zonas de exclusion en el JSON como campo `exclusion_zones`:
  ```json
  "exclusion_zones": {
    "Estacionamiento Norte": [[x1,y1], [x2,y2], ...],
    "Estacionamiento Sur": [[x1,y1], [x2,y2], ...]
  }
  ```
- **Vista Global** (Paso 1): filtrar detecciones cuyo centro caiga dentro de una zona de exclusion
- **Preview con YOLO** (Paso 2): misma logica de filtrado

#### En el conteo real (`main_glorieta.py`):

- Cargar `exclusion_zones` del config JSON
- Convertir a arrays numpy (mismo patron que `zones_np`)
- En los 3 paths de deteccion (SAHI, SORT, ByteTrack), despues de pasar el filtro geometrico y antes de agregar a `det_list`/`tracked_boxes`: descartar detecciones cuyo centro `(cx, cy)` caiga dentro de cualquier zona de exclusion via `cv2.pointPolygonTest`
- Dibujar las zonas de exclusion en el frame con color rojo semi-transparente (similar a `draw_zones` pero con color distinto)
- Print al inicio: `Exclusion: N zonas (nombre1, nombre2, ...)`

### Criterios de aceptacion

#### Configurador:
- [ ] Existe Paso 0 "Zonas de exclusion" con dibujo de poligonos
- [ ] Se pueden agregar, eliminar y previsualizar zonas de exclusion
- [ ] Las zonas de exclusion se dibujan en color rojo/naranja (diferenciable de zonas azules/verdes)
- [ ] Vista Global filtra detecciones dentro de zonas de exclusion
- [ ] Las zonas se guardan en el JSON como `exclusion_zones`
- [ ] `--config` carga zonas de exclusion existentes

#### Conteo real:
- [ ] `main_glorieta.py` carga `exclusion_zones` del JSON
- [ ] Detecciones con centro dentro de exclusion se descartan en los 3 paths
- [ ] Las zonas de exclusion se dibujan en rojo semi-transparente en el frame
- [ ] Se imprime la lista de zonas de exclusion al inicio
- [ ] Configs sin `exclusion_zones` funcionan igual (backward compatible)
- [ ] Smoke test pasa

---

_Tareas P2 completadas en iteracion 7 (TODO-013, TODO-016, TODO-017). Ver `TASK_COMPLETED.md`._
