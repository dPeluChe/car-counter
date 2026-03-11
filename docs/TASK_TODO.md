# Tareas Pendientes

Backlog de mejoras para el proyecto Car Counter (glorieta).
Cada tarea tiene criterios de aceptacion claros para validacion.

**Prioridad:** P0 = critico para demo, P1 = mejora importante, P2 = nice-to-have

---

## TODO-001: Optimizar acumulacion de detecciones (np.vstack en loop)

**Prioridad:** P1
**Archivo:** `main_glorieta.py`
**Lineas:** ~544, ~558 (paths SAHI y SORT)

### Problema

El patron actual hace `np.vstack` dentro del loop de detecciones. Cada vstack crea un array nuevo y copia todo — es O(n^2) en memoria.

### Que hacer

- Acumular las detecciones en una lista de Python normal
- Al final del loop, convertir a numpy con un solo `np.array(lista)` o `np.vstack(lista)` si la lista no esta vacia
- Aplicar el mismo patron para `det_classes`

### Criterios de aceptacion

- [ ] No existe `np.vstack` dentro de ningun `for` loop en el archivo
- [ ] Las detecciones se acumulan en lista y se convierten una sola vez
- [ ] El comportamiento de deteccion es identico (mismos resultados con el mismo video)
- [ ] Smoke test pasa: `python main_glorieta.py --headless --max-frames 100 --no-save`

---

## TODO-002: Purga de tracks viejos en tracks_info

**Prioridad:** P1
**Archivo:** `main_glorieta.py`
**Lineas:** ~294 (diccionario `tracks_info`)

### Problema

`tracks_info` crece indefinidamente. En videos largos acumula miles de IDs que ya no aparecen en el frame, consumiendo memoria y haciendo mas lento el lookup.

### Que hacer

- Agregar un campo `last_seen_frame` a cada entrada de `tracks_info`
- Actualizar `last_seen_frame` cada vez que el ID aparece en un frame
- Cada N frames (ej. cada 120), purgar entradas cuyo `last_seen_frame` sea mayor a un umbral (ej. 200 frames sin aparecer)
- No purgar entradas con estado `done` que aun son recientes (para que el resumen final sea correcto)

### Criterios de aceptacion

- [ ] `tracks_info` tiene campo `last_seen_frame` por cada ID
- [ ] Existe logica de purga que se ejecuta periodicamente
- [ ] El conteo final de rutas es identico al actual (no se pierden rutas ya completadas)
- [ ] En un video de 5+ min, `len(tracks_info)` no crece sin limite
- [ ] Smoke test pasa

---

## TODO-003: Anti-rebote en zona destino

**Prioridad:** P0
**Archivo:** `main_glorieta.py`
**Funcion:** `update_route_state()`

### Problema

El origen ya tiene anti-rebote (`MIN_ZONE_FRAMES = 3`), pero el destino no. Un vehiculo que roza brevemente una zona al pasar por el borde se registra como ruta completada aunque no realmente entre a esa calle.

### Que hacer

- Agregar un estado intermedio o contador similar al origen para confirmar destino
- Cuando un vehiculo en estado `transit` entra a una zona destino, no registrar inmediatamente
- Acumular N frames consecutivos en esa zona destino antes de llamar `_register_route`
- Si sale de la zona antes de alcanzar el umbral, mantenerlo en `transit`

### Criterios de aceptacion

- [ ] Existe un umbral configurable `MIN_DEST_FRAMES` (default 3)
- [ ] Un vehiculo que roza una zona por 1-2 frames no genera ruta
- [ ] Un vehiculo que permanece 3+ frames en zona destino si genera ruta
- [ ] El estado `transit` se mantiene si el vehiculo sale antes del umbral
- [ ] El resumen final sigue siendo correcto
- [ ] Smoke test pasa

---

## TODO-004: Overlay de zonas optimizado (un solo overlay)

**Prioridad:** P2
**Archivo:** `main_glorieta.py`
**Funcion:** `draw_zones()`

### Problema

`draw_zones()` hace `frame.copy()` + `cv2.addWeighted` por cada zona. Con 4+ zonas son 4 copias completas del frame por frame de video.

### Que hacer

- Crear un solo overlay al inicio
- Dibujar todos los poligonos rellenos en ese unico overlay
- Hacer un solo `addWeighted` al final
- Dibujar los contornos y labels directamente sobre el frame despues del blend

### Criterios de aceptacion

- [ ] Solo existe un `frame.copy()` y un `addWeighted` en `draw_zones`, sin importar cuantas zonas haya
- [ ] La visualizacion es visualmente igual (colores semi-transparentes por zona)
- [ ] Smoke test pasa

---

## TODO-005: Filtro de confianza diferenciado por clase

**Prioridad:** P1
**Archivo:** `main_glorieta.py`

### Problema

Se usa un solo `conf_threshold` para todas las clases. Las motos suelen tener confianza mas baja que los camiones, y los camiones generan mas falsos positivos a confianza baja.

### Que hacer

- Permitir en `config_glorieta.json` un campo opcional `conf_per_class`:
  ```json
  "conf_per_class": {
    "car": 0.10,
    "motorbike": 0.08,
    "bus": 0.15,
    "truck": 0.15
  }
  ```
- Si no existe el campo, usar el `conf_threshold` global como antes (backward compatible)
- Aplicar el filtro en los 3 paths de deteccion (SAHI, SORT, ByteTrack nativo)

### Criterios de aceptacion

- [ ] Configs existentes sin `conf_per_class` siguen funcionando igual
- [ ] Con `conf_per_class` definido, cada clase usa su propio umbral
- [ ] El filtro se aplica en los 3 paths de deteccion
- [ ] Se imprime en consola los umbrales por clase al inicio
- [ ] Smoke test pasa

---

## TODO-006: Export de resultados a JSON/CSV

**Prioridad:** P0
**Archivo:** `main_glorieta.py`

### Problema

El resumen final solo se imprime en consola. No hay forma de consumir los resultados programaticamente o pasarlos a otro sistema.

### Que hacer

- Al finalizar el procesamiento, guardar automaticamente un archivo `results_glorieta.json` con:
  ```json
  {
    "video": "assets/glorieta_fast.MP4",
    "config": "config_glorieta.json",
    "mode": "SAHI",
    "tracker": "bytetrack",
    "frames_processed": 1500,
    "total_frames": 3000,
    "duration_seconds": 50.0,
    "processing_time_seconds": 120.5,
    "fps_avg": 12.5,
    "total_vehicles_tracked": 85,
    "total_routes_completed": 42,
    "routes": {
      "Norte → Sur": 15,
      "Este → Oeste": 12,
      "Sur → Norte": 8,
      "Oeste → Este": 7
    },
    "zones": ["Norte", "Sur", "Este", "Oeste"]
  }
  ```
- Flag `--output-json` para especificar ruta (default: `results_glorieta.json`)
- Opcionalmente un CSV simple con una fila por ruta

### Criterios de aceptacion

- [ ] Se genera `results_glorieta.json` al terminar el procesamiento
- [ ] El JSON es valido y parseable
- [ ] Contiene todos los campos listados arriba
- [ ] `--output-json custom_name.json` funciona
- [ ] Smoke test pasa y genera el archivo

---

## TODO-007: Preview de zonas sobre video en movimiento (configurador)

**Prioridad:** P1
**Archivo:** `setup_glorieta.py`

### Problema

El configurador muestra un solo frame estatico. Es dificil saber si las zonas cubren bien la entrada/salida de vehiculos sin ver el video en movimiento.

### Que hacer

- En el paso 2 (Zonas), agregar un boton "Reproducir" que avance el video frame a frame mostrando las zonas dibujadas encima
- Permitir pausar y volver a modo estatico
- No necesita ser en tiempo real — puede ser cada 5-10 frames para que sea fluido en Tkinter

### Criterios de aceptacion

- [ ] Existe boton de reproduccion en el paso de zonas
- [ ] El video avanza mostrando las zonas superpuestas
- [ ] Se puede pausar y retomar
- [ ] Las zonas ya dibujadas se mantienen visibles durante la reproduccion
- [ ] No crashea si se llega al final del video

---

## TODO-008: Cargar configuracion existente en el configurador

**Prioridad:** P1
**Archivo:** `setup_glorieta.py`

### Problema

Si ya tienes un `config_glorieta.json` y quieres ajustar una zona o agregar una muestra, hay que empezar desde cero.

### Que hacer

- Agregar flag `--config` al configurador: `python setup_glorieta.py --video ... --config config_glorieta.json`
- Si se pasa un config existente:
  - Cargar las zonas y dibujarlas en el canvas
  - Cargar las muestras y los filtros geometricos
  - Cargar parametros SAHI
  - Permitir editar/eliminar zonas existentes
- Si no se pasa config, comportamiento actual (empezar de cero)

### Criterios de aceptacion

- [ ] `--config` carga correctamente zonas, settings, sahi de un JSON existente
- [ ] Las zonas cargadas se visualizan en el canvas
- [ ] Se pueden agregar nuevas zonas o eliminar existentes
- [ ] Guardar genera un JSON valido con los cambios
- [ ] Sin `--config` el comportamiento es identico al actual

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

## TODO-011: Documentar README con estado actual post-limpieza

**Prioridad:** P1
**Archivo:** `README.md`

### Problema

El README aun referencia `SAHI.md` y `QUICKSTART_SAHI.md` que ahora estan en `docs/archived/`. Tambien menciona "Documentacion relacionada" con archivos movidos.

### Que hacer

- Actualizar la seccion "Documentacion relacionada" del README
- Quitar referencias a archivos que ya no estan en raiz
- Agregar referencia a `docs/TASK_TODO.md` y `docs/TASK_COMPLETED.md`
- Verificar que todos los comandos de ejemplo en el README siguen siendo correctos

### Criterios de aceptacion

- [ ] No hay links rotos a archivos que no existen en su ubicacion referenciada
- [ ] Los comandos de ejemplo funcionan tal cual estan escritos
- [ ] La seccion de documentacion refleja la estructura actual del repo
