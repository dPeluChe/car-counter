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
