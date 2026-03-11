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
