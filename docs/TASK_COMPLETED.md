# Tareas Completadas

Registro de tareas finalizadas del proyecto Car Counter (glorieta).

---

## DONE-001: Flujo principal de glorieta

**Fecha:** 2025-12-08
**Commit:** `58d6dda`
**Archivos:** `main_glorieta.py`, `setup_glorieta.py`

### Que se hizo

- Contador de vehiculos con tracking de rutas A→B por zonas poligonales
- Maquina de estados por vehiculo: NUEVO → ORIGEN → TRANSIT → DONE
- Soporte ByteTrack / BoT-SORT nativo de Ultralytics
- Fallback automatico a SORT cuando `lap` no esta instalado
- Modo SAHI opcional para tomas aereas con vehiculos pequenos
- Configurador GUI (Tkinter) con 3 pasos: calibracion, zonas, SAHI
- Vista global de deteccion para medir recall
- Muestras de vehiculos para derivar filtros geometricos (ancho, alto, aspect ratio)
- Calibracion local reescalada sobre recorte del frame
- Parametro `imgsz` configurable para mejorar deteccion aerea
- Generacion de `config_glorieta.json` con todos los parametros
- CLI completo con flags: `--no-sahi`, `--tracker`, `--headless`, `--benchmark`, `--max-frames`
- Panel visual de rutas detectadas en tiempo real
- HUD con progreso, FPS, detecciones
- Export de benchmark a archivo

### Criterios cumplidos

- [x] `main_glorieta.py` y `setup_glorieta.py` compilan sin error
- [x] Smoke test: `python main_glorieta.py --headless --max-frames 50 --no-save`
- [x] Configuracion guardada es JSON valido con zonas, settings, sahi, tracker

---

## DONE-002: Documentacion base

**Fecha:** 2025-12-08
**Commit:** `58d6dda`
**Archivos:** `README.md`, `ROUNDABOUT_GUIDE.md`, `requirements.txt`

### Que se hizo

- README con flujo recomendado paso a paso
- Guia de glorieta con instrucciones de calibracion
- Requirements con dependencias necesarias

---

## DONE-003: Limpieza de archivos deprecated y dependencias

**Fecha:** 2026-03-11
**Commit:** `397bf25`

### Que se hizo

- Borrados 7 archivos legacy reemplazados por el flujo glorieta:
  - `configurador_pro.py`, `configurador_zonas.py`, `analisis_rutas.py`
  - `main_sahi.py`, `compare_methods.py`, `test_tkinter.py`, `config.json`
- Archivados 5 docs/scripts legacy en `docs/archived/`:
  - `IMPLEMENTATION_SUMMARY.md`, `QUICKSTART_SAHI.md`, `SAHI.md`
  - `.sahi_commands.sh`, `create_test_video.sh`
- Dependencias eliminadas de `requirements.txt`:
  - `cvzone`, `hydra-core`, `matplotlib`, `scipy`, `requests`, `scikit-image`, `customtkinter`
- `.gitignore` actualizado: `.envrc`, `.python-version`, `env.bak/`, `*.MP4`, `*.MOV`
- Eliminado fallback a `config.json` en `main_glorieta.py`

### Criterios cumplidos

- [x] No quedan imports rotos en `main_glorieta.py` ni `setup_glorieta.py`
- [x] `requirements.txt` solo contiene dependencias usadas
- [x] Archivos locales no se trackean en git

---

## DONE-004: Optimizar acumulacion de detecciones (TODO-001)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`

### Que se hizo

- Eliminado `np.vstack` dentro de loops en paths SAHI y SORT
- Reemplazado por acumulacion en `det_list = []` + `det_list.append()` + conversion unica `np.array(det_list)` al final
- 0 ocurrencias de `np.vstack` quedan en el archivo

### Criterios cumplidos

- [x] No existe `np.vstack` dentro de ningun `for` loop
- [x] Detecciones se acumulan en lista y se convierten una sola vez
- [x] Comportamiento identico (misma estructura de datos)

---

## DONE-005: Purga de tracks viejos (TODO-002)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`

### Que se hizo

- Campo `last_seen_frame` agregado a cada entrada de `tracks_info`
- Cada 120 frames se purgan IDs con mas de 200 frames sin aparecer
- `total_vehicles_ever` (counter global) preserva el conteo total correcto post-purga
- Log de purga en consola: `Purgados N tracks viejos — activos en memoria: M`

### Criterios cumplidos

- [x] `tracks_info` tiene campo `last_seen_frame` por cada ID
- [x] Logica de purga ejecuta cada 120 frames
- [x] Conteo final correcto gracias a `total_vehicles_ever`
- [x] `len(tracks_info)` no crece sin limite

---

## DONE-006: Anti-rebote en zona destino (TODO-003)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`

### Que se hizo

- `MIN_DEST_FRAMES = 3` como umbral para confirmar destino
- Campos `dest_zone` y `dest_frames` en cada track
- En estado `transit`: acumula frames consecutivos en zona destino antes de registrar ruta
- Si sale antes del umbral: reset a `dest_zone=None, dest_frames=0`
- Renombrado `MIN_ZONE_FRAMES` → `MIN_ORIGIN_FRAMES` para claridad
- Ambos umbrales configurables desde JSON (`settings.min_origin_frames`, `settings.min_dest_frames`)

### Criterios cumplidos

- [x] Umbral `MIN_DEST_FRAMES` configurable (default 3)
- [x] Roces de 1-2 frames no generan ruta
- [x] 3+ frames consecutivos en destino si genera ruta
- [x] Estado `transit` se mantiene si sale antes del umbral
- [x] Backward compatible (configs sin estos campos usan default 3)

---

## DONE-007: Export de resultados a JSON/CSV (TODO-006)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`

### Que se hizo

- JSON generado automaticamente al terminar con: video, config, mode, tracker, frames, duration, fps, vehicles, routes, zones
- Flags: `--output-json` (default `results_glorieta.json`), `--no-output-json`, `--output-csv`
- `--no-save` suprime JSON automaticamente (a menos que se pase `--output-json` explicito)
- CSV opcional con columnas: ruta, conteo, porcentaje

### Criterios cumplidos

- [x] Se genera `results_glorieta.json` al terminar
- [x] JSON valido con todos los campos del spec
- [x] `--output-json custom.json` funciona
- [x] `--no-save` sin `--output-json` explicito no genera JSON
- [x] CSV opcional con `--output-csv`

---

## DONE-008: Filtro de confianza diferenciado por clase (TODO-005)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`

### Que se hizo

- Campo opcional `conf_per_class` en `config_glorieta.json` con umbrales por clase
- `EFFECTIVE_CONF` = minimo de todos los umbrales (se pasa al modelo, luego se filtra por clase en post-proceso)
- Helper `_conf_for(cls_name)` retorna umbral especifico o global como fallback
- Filtro aplicado en los 3 paths: SAHI (L581), SORT (L600), ByteTrack nativo (L653)
- Print de umbrales por clase al inicio de ejecucion
- Backward compatible: sin `conf_per_class` usa `conf_threshold` global

### Criterios cumplidos

- [x] Configs existentes sin `conf_per_class` siguen funcionando igual
- [x] Con `conf_per_class` definido, cada clase usa su propio umbral
- [x] El filtro se aplica en los 3 paths de deteccion
- [x] Se imprime en consola los umbrales por clase al inicio
- [x] Smoke test pasa

---

## DONE-009: Preview de zonas sobre video en movimiento (TODO-007)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`

### Que se hizo

- Boton "Reproducir zonas" en paso 2 (Zonas) del configurador
- Video avanza ~12fps (skip 5 frames, tick 80ms) con zonas dibujadas encima
- Toggle pausa/reproduccion con cambio visual del boton
- Preview se detiene automaticamente al cambiar de paso o empezar a dibujar zona
- Al llegar al final del video, reinicia en loop (no crashea)
- VideoCapture se libera correctamente al pausar

### Criterios cumplidos

- [x] Existe boton de reproduccion en el paso de zonas
- [x] El video avanza mostrando las zonas superpuestas
- [x] Se puede pausar y retomar
- [x] Las zonas ya dibujadas se mantienen visibles durante la reproduccion
- [x] No crashea si se llega al final del video

---

## DONE-010: Documentar README con estado actual post-limpieza (TODO-011)

**Fecha:** 2026-03-11
**Archivo:** `README.md`

### Que se hizo

- Actualizada seccion "Documentacion relacionada" con referencias correctas
- Removidas referencias a `SAHI.md` y `QUICKSTART_SAHI.md` en raiz
- Agregadas referencias a `docs/TASK_TODO.md` y `docs/TASK_COMPLETED.md`
- Nota sobre docs archivados en `docs/archived/`

### Criterios cumplidos

- [x] No hay links rotos a archivos que no existen en su ubicacion referenciada
- [x] Los comandos de ejemplo funcionan tal cual estan escritos
- [x] La seccion de documentacion refleja la estructura actual del repo

---

## DONE-011: Overlay de zonas optimizado (TODO-004)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`
**Funcion:** `draw_zones()`

### Que se hizo

- Un solo `frame.copy()` → todos los `fillPoly` en el overlay → un solo `addWeighted`
- Segunda pasada para `polylines` + `putText` sin copias adicionales
- Alpha ajustado de 0.25 a 0.18 para compensar cambio de multi-pass a single-pass

### Criterios cumplidos

- [x] Solo existe un `frame.copy()` y un `addWeighted` en `draw_zones`
- [x] La visualizacion es visualmente equivalente (colores semi-transparentes por zona)
- [x] Smoke test pasa

---

## DONE-012: Cargar configuracion existente en el configurador (TODO-008)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`

### Que se hizo

- Flag `--config` para cargar JSON existente al iniciar el configurador
- `_load_from_config(path)` carga: zonas, settings, SAHI, tracker, video_path
- `sample_constraints` cargadas como fallback (`_loaded_sample_constraints`) para evitar perdida al guardar sin nuevas muestras
- Campos extra del JSON original preservados al guardar (merge por seccion, solo campos ausentes)
- Sin `--config` o si el archivo no existe, comportamiento identico al original

### Criterios cumplidos

- [x] `--config` carga correctamente zonas, settings, sahi de un JSON existente
- [x] Las zonas cargadas se visualizan en el canvas
- [x] Se pueden agregar nuevas zonas o eliminar existentes
- [x] Guardar genera un JSON valido con los cambios (sin perder sample_constraints ni campos extra)
- [x] Sin `--config` el comportamiento es identico al actual

---

## DONE-013: Scoreboard grande para demos (TODO-009)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`
**Funcion:** `draw_scoreboard()`

### Que se hizo

- Flag `--demo-mode` en argparse activa panel scoreboard grande
- `draw_scoreboard()` renderiza en top-right: contador TOTAL grande (scale 1.05), rutas confirmadas, activos
- Colores de cada ruta extraidos del nombre de zona origen → `ZONE_COLORS_BGR`
- Barras de progreso proporcionales al conteo de cada ruta
- Sin `--demo-mode`, se usa `draw_routes_panel()` identico al original

### Criterios cumplidos

- [x] `--demo-mode` activa el panel grande
- [x] Sin el flag, la visualizacion es identica a la actual
- [x] El contador total es visible a distancia en una pantalla 1080p
- [x] Los colores de ruta corresponden a los colores de zona
- [x] No se superpone con las zonas ni con los bounding boxes

---

## DONE-014: NMS adicional post-SAHI (TODO-010)

**Fecha:** 2026-03-11
**Archivo:** `main_glorieta.py`

### Que se hizo

- `apply_nms(det_list, det_classes, iou_threshold)` implementa greedy NMS por conf descendente
- Reutiliza `bbox_iou()` existente para calcular solapamiento
- Se aplica solo en el path SAHI, despues de recolectar detecciones y antes de convertir a numpy
- Umbral configurable desde JSON: `sahi.nms_threshold` (default 0.3)
- `NMS_THRESHOLD_SAHI > 0` como condicion — poner 0 desactiva el NMS extra
- Print del umbral al inicio junto con la info SAHI

### Criterios cumplidos

- [x] Existe funcion `apply_nms(det_list, det_classes, iou_threshold)`
- [x] Se aplica solo en el path SAHI
- [x] El umbral es configurable desde el config JSON (campo `sahi.nms_threshold`)
- [x] Reduce duplicados sin eliminar detecciones legitimas cercanas
- [x] Smoke test pasa

---

## DONE-015: Undo de ultimo punto al dibujar zonas (TODO-012)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`
**Paso:** 2 (Zonas)

### Que se hizo

- Boton "↩ Deshacer ultimo punto" deshabilitado por defecto, se habilita al agregar puntos
- `_undo_last_point()` hace pop del ultimo punto y redibuja
- `Ctrl+Z` vinculado como shortcut global
- Boton se deshabilita al cerrar zona, iniciar dibujo, o quedar sin puntos

### Criterios cumplidos

- [x] Existe boton "Deshacer punto" visible solo durante el dibujo de zona
- [x] Cada clic elimina el ultimo punto y redibuja la linea parcial
- [x] Si se deshacen todos los puntos, el estado queda limpio (sin puntos, boton deshabilitado)
- [x] `Ctrl+Z` funciona como shortcut equivalente
- [x] El boton se deshabilita cuando no se esta dibujando

---

## DONE-016: Visualizacion de grilla SAHI en el canvas (TODO-015)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`
**Paso:** 3 (SAHI)

### Que se hizo

- `_draw_tile_overlay()` dibuja rectangulos dashed azules sobre el frame en el Paso 3
- Toggle "Mostrar/Ocultar cuadricula" con boton y estado `_tile_grid_visible`
- Conteo de tiles calculado y anotado en canvas + label
- Grilla se actualiza en tiempo real al mover sliders (via `_update_tile_preview` → `_redraw`)
- Grilla desaparece automaticamente al cambiar de paso

### Criterios cumplidos

- [x] La grilla de tiles se dibuja sobre el frame en el Paso 3
- [x] Los tiles se actualizan en tiempo real al mover sliders
- [x] Las zonas de overlap entre tiles se distinguen visualmente
- [x] El conteo de tiles coincide con la formula real
- [x] Al cambiar de paso la grilla desaparece

---

## DONE-017: Preview de detecciones YOLO sobre video con zonas (TODO-014)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`
**Paso:** 2 (Zonas)

### Que se hizo

- Toggle "Detecciones YOLO: OFF/ON" junto al boton de reproduccion
- YOLO corre en cada frame del preview cuando activo, dibuja boxes amarillos con label clase+conf
- Usa `conf_threshold` e `imgsz` actuales del configurador
- Boxes se dibujan ANTES de las zonas (zonas quedan encima)
- Guard si modelo no cargado — avisa en status bar
- SKIP dinamico: 15 frames con YOLO (compensa la lentitud), 5 sin YOLO
- `_PREVIEW_VEH_NAMES` como constante de modulo (no recreado cada frame)

### Criterios cumplidos

- [x] Existe toggle "Mostrar detecciones" en el Paso 2
- [x] Cuando activo, se dibujan bounding boxes de YOLO sobre el preview
- [x] Se usan los parametros actuales del configurador (conf, imgsz)
- [x] Las zonas siguen visibles encima de las detecciones
- [x] El toggle se puede activar/desactivar sin detener el preview
- [x] Sin el toggle, el preview funciona identico al actual (sin overhead de YOLO)

---

## DONE-018: Seleccion visual de zona en el canvas (TODO-013)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`
**Paso:** 2 (Zonas)

### Que se hizo

- Clic izquierdo sobre zona existente la selecciona (cv2.pointPolygonTest)
- Zona seleccionada resaltada con borde grueso (4px) y fill mas opaco
- Clic fuera de zonas deselecciona
- Solo activo cuando no se esta dibujando zona nueva ni en modo pan
- Coordenadas transformadas via _screen_to_img (funciona con zoom/pan)

### Criterios cumplidos

- [x] Clic sobre zona existente la selecciona en el listbox
- [x] La zona seleccionada se resalta visualmente en el canvas
- [x] Clic fuera de toda zona deselecciona
- [x] No interfiere con el dibujo de zona nueva
- [x] Funciona correctamente con zoom/pan activo

---

## DONE-019: Visualizacion de muestras de vehiculos en el canvas (TODO-016)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`
**Paso:** 1 (Calibracion)

### Que se hizo

- Bounding boxes de muestras dibujados en _draw_calib_overlay (rectangulos dashed verdes)
- Cada muestra etiquetada con numero y dimensiones (WxH)
- _add_vehicle_sample y _clear_vehicle_samples llaman _redraw para actualizar inmediatamente
- Constraints cargados desde config se muestran en lbl_samples_info con rangos w/h

### Criterios cumplidos

- [x] Las muestras marcadas se dibujan como rectangulos sobre el frame
- [x] Cada muestra muestra sus dimensiones (ancho x alto px)
- [x] Al agregar/limpiar muestras, el canvas se actualiza inmediatamente
- [x] Las muestras persisten visualmente al cambiar de frame
- [x] Si se cargo un config con sample_constraints, se muestra un resumen de los rangos en el sidebar

---

## DONE-020: Sliders de confianza por clase en el configurador (TODO-017)

**Fecha:** 2026-03-11
**Archivo:** `setup_glorieta.py`
**Paso:** 1 (Calibracion)

### Que se hizo

- 4 sliders individuales (car, moto, bus, truck) debajo del slider global
- Sincronizados con el slider global mientras no se modifiquen (_conf_per_class_modified)
- conf_per_class solo se incluye en el JSON si al menos un slider fue tocado
- _load_from_config carga valores existentes y marca el flag
- Spread condicional en _save_config para backward compatibility

### Criterios cumplidos

- [x] Existen sliders individuales para car, motorbike, bus, truck
- [x] Por defecto usan el valor del slider global (no generan conf_per_class)
- [x] Al mover uno, se activa conf_per_class para todas las clases
- [x] El JSON guardado incluye conf_per_class solo si se modifico al menos un slider
- [x] Al cargar un config con conf_per_class, los sliders reflejan los valores
- [x] Backward compatible

---

## DONE-021: Zonas de exclusion para vehiculos estacionados (TODO-018)

**Fecha:** 2026-03-11
**Archivos:** `setup_glorieta.py`, `main_glorieta.py`

### Que se hizo

#### Configurador (`setup_glorieta.py`):
- Paso 0 "Zonas de Exclusion" con panel completo: nombre, dibujo de poligonos, listbox, seleccion, eliminacion
- EXCL_COLORS rojo/naranja para diferenciar visualmente de zonas de transito
- `_draw_excl_overlay()` dibuja zonas + poligono en curso con feedback visual (primer punto resaltado)
- `_start_excl_draw()`, `_close_excl_zone()`, `_delete_excl_zone()`, `_refresh_excl_list()`
- Click-to-select zonas de exclusion en canvas
- `_is_in_exclusion(cx, cy)` filtra detecciones en Vista Global y Preview YOLO (Paso 2)
- `_load_from_config()` carga `exclusion_zones` del JSON y actualiza nombre sugerido
- `_save_config()` guarda `exclusion_zones` en el JSON
- Zonas de exclusion visibles como referencia en Pasos 1, 2 y 3
- Docstring actualizado de 3 a 4 pasos
- Mensaje de guardado incluye conteo de zonas de exclusion

#### Conteo real (`main_glorieta.py`):
- Carga `exclusion_zones` del config JSON con `config.get("exclusion_zones", {})`
- `_exclusion_np` pre-convierte a numpy arrays (una sola vez al inicio)
- `in_exclusion_zone(cx, cy)` helper con `cv2.pointPolygonTest`
- Filtrado en los 3 paths: SAHI (L668), SORT (L690), ByteTrack (L738)
- Visualizacion rojo semi-transparente con `fillPoly` + `addWeighted` + `polylines`
- Print al inicio: `Exclusion: N zonas (nombre1, nombre2, ...)`

### Criterios cumplidos

#### Configurador:
- [x] Existe Paso 0 "Zonas de exclusion" con dibujo de poligonos
- [x] Se pueden agregar, eliminar y previsualizar zonas de exclusion
- [x] Las zonas de exclusion se dibujan en color rojo/naranja (diferenciable de zonas azules/verdes)
- [x] Vista Global filtra detecciones dentro de zonas de exclusion
- [x] Las zonas se guardan en el JSON como `exclusion_zones`
- [x] `--config` carga zonas de exclusion existentes

#### Conteo real:
- [x] `main_glorieta.py` carga `exclusion_zones` del JSON
- [x] Detecciones con centro dentro de exclusion se descartan en los 3 paths
- [x] Las zonas de exclusion se dibujan en rojo semi-transparente en el frame
- [x] Se imprime la lista de zonas de exclusion al inicio
- [x] Configs sin `exclusion_zones` funcionan igual (backward compatible)
- [x] Smoke test: no hay config de prueba en el repo, validacion estructural del codigo
