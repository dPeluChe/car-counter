# Car Counter

Conteo y tracking de vehiculos con YOLO + tracking para videos de trafico.
Soporta glorietas, intersecciones, aforo simple por cruce de linea y tomas aereas.

## Arquitectura

```
main.py              # Motor de conteo (entry point)
setup.py             # Configurador interactivo (Tkinter)
carcounter/          # Paquete core
  constants.py       #   Clases COCO, colores, IDs
  geometry.py        #   Point-in-polygon, IoU, NMS, filtros
  counting.py        #   Maquina de estados (zones + lines)
  tracking.py        #   Asociacion clase-track
  drawing.py         #   Dibujo OpenCV (zonas, HUD, scoreboard)
  detection.py       #   Wrapper SAHI + filtros post-deteccion
  calibration.py     #   ROI, escala, muestras, constraints geometricos
  config_io.py       #   Lectura/escritura de config.json
  export.py          #   Export JSON/CSV de resultados
  paths.py           #   Resolucion centralizada de rutas
  sort.py            #   SORT tracker (fallback)
setup_panels/        # Mixins del configurador GUI
  canvas.py          #   Zoom, pan, redraw, overlays compartidos
  step0_exclusion.py #   Paso 0: zonas de exclusion
  step1_calibration.py # Paso 1: calibracion YOLO
  step2_zones.py     #   Paso 2: zonas/lineas de conteo
  step3_sahi.py      #   Paso 3: SAHI + guardado
docs/                # Documentacion
  OPTIMIZATION_GUIDE.md  # Guia de parametros y calibracion
  ROUNDABOUT_GUIDE.md    # Guia paso a paso para glorietas
  TASK_TODO.md           # Tareas pendientes
  TASK_COMPLETED.md      # Historial de tareas completadas
archive/             # Archivos legacy (no usados)
```

## Features

- Dos modos de conteo: zonas A->B (rutas) y cruce de linea (aforo)
- Tracking nativo con ByteTrack o BoT-SORT (fallback SORT)
- SAHI para vehiculos pequenos en tomas aereas
- Zonas de exclusion para vehiculos estacionados
- Umbrales de confianza por clase (car, moto, bus, truck)
- Filtros geometricos aprendidos del configurador
- NMS post-SAHI configurable
- Modo demo con scoreboard grande
- Exportacion JSON y CSV
- Preview de zonas con detecciones YOLO en vivo

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## Flujo

1. Configurar:

```bash
python setup.py --video assets/mi_video.mp4
```

Cargar config existente:

```bash
python setup.py --video assets/mi_video.mp4 --config config/config.json
```

2. Paso 0: zonas de exclusion (opcional)
3. Paso 1: calibracion YOLO (vista global, muestras, confianza por clase)
4. Paso 2: zonas poligonales o lineas de cruce
5. Paso 3: parametros SAHI -> guardar config.json

6. Ejecutar:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4
```

## Modos

```bash
# Estandar
python main.py --config config/config.json --video assets/video.mp4

# Demo (scoreboard grande)
python main.py --config config/config.json --video assets/video.mp4 --demo-mode

# Rapido sin SAHI
python main.py --config config/config.json --video assets/video.mp4 --no-sahi

# Smoke test
python main.py --config config/config.json --video assets/video.mp4 --headless --max-frames 50 --no-save

# Exportar
python main.py --config config/config.json --video assets/video.mp4 --output-json results.json --output-csv routes.csv
```

## Config JSON

Generado por el configurador:

- `counting_mode`: "zones" o "lines"
- `zones`: poligonos de entrada/salida
- `lines`: lineas de cruce con tolerancia
- `exclusion_zones`: areas excluidas
- `settings.conf_threshold`: umbral global
- `settings.conf_per_class`: umbrales por clase
- `settings.imgsz`: resolucion YOLO
- `settings.sample_constraints`: filtros geometricos
- `sahi.slice_width/height`: tamano de tile
- `sahi.nms_threshold`: NMS post-SAHI

## CLI flags (main.py)

- `--no-sahi`: sin SAHI (mas rapido)
- `--tracker bytetrack|botsort|sort`: algoritmo de tracking
- `--demo-mode`: scoreboard grande
- `--headless`: sin ventana
- `--max-frames N`: limitar frames
- `--no-save`: no guardar video
- `--show-fps`: mostrar FPS
- `--benchmark`: guardar metricas

## Documentacion

- [Guia de optimizacion y parametros](docs/OPTIMIZATION_GUIDE.md)
- [Guia paso a paso para glorietas](docs/ROUNDABOUT_GUIDE.md)
- [Tareas pendientes](docs/TASK_TODO.md)
- [Historial de tareas](docs/TASK_COMPLETED.md)

## Dependencias

- `ultralytics`
- `opencv-python`
- `sahi`
- `lap`
- `filterpy`
