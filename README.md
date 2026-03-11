# Car Counter

Prototipo de conteo y tracking de vehiculos para videos de trafico, con foco actual en glorietas y tomas aereas.

## Estado actual

El flujo mas avanzado del repo hoy es:

- `setup_glorieta.py`: configurador interactivo para videos de glorieta
- `main_glorieta.py`: conteo de rutas A→B por zonas poligonales

Ese flujo ya incluye:

- tracking nativo con `ByteTrack` o `BoT-SORT`
- fallback a `SORT` cuando hace falta
- modo `SAHI` para autos pequenos en tomas aereas
- configuracion de `imgsz`
- vista global de deteccion
- calibracion local reescalada
- filtros geometricos derivados de multiples muestras de vehiculos

## Setup

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## Flujo recomendado para glorieta

1. Abrir el configurador:

```bash
python setup_glorieta.py --video assets/glorieta_fast.MP4
```

2. En el paso 1:

- usa `Vista Global`
- ajusta `imgsz` si hace falta
- marca varios autos y 1-2 camiones con `Agregar muestra vehiculo`
- valida un auto puntual con `Probar YOLO`

3. En el paso 2:

- dibuja un poligono por cada boca calle de entrada/salida

4. En el paso 3:

- revisa tiles SAHI
- guarda `config_glorieta.json`

5. Ejecutar el conteo:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4
```

## Modos utiles

Demo recomendado para vista aerea:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4
```

Modo rapido sin SAHI:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --no-sahi
```

Smoke test sin ventana:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --headless --max-frames 50 --no-save
```

## Parametros importantes

- `conf_threshold`: recall vs precision
- `imgsz`: resolucion de inferencia YOLO
- `slice_width` / `slice_height`: tamano de tile SAHI
- `overlap_ratio`: solapamiento SAHI
- `sample_constraints`: filtros geometricos aprendidos de las muestras del configurador

## Notas practicas

- Para esta glorieta aerea, `imgsz` alto mejora mucho la deteccion.
- La vista global prioriza recall; luego las muestras ayudan a quitar techos, arboles u objetos grandes.
- El conteo real usa los filtros geometricos guardados por el configurador.

## Documentacion relacionada

- `ROUNDABOUT_GUIDE.md` — Guia de uso para glorietas
- `OPTIMIZATION_GUIDE.md` — Ajuste de rendimiento y parametros
- `docs/TASK_TODO.md` — Backlog de mejoras pendientes
- `docs/TASK_COMPLETED.md` — Historial de cambios completados

> `SAHI.md` y `QUICKSTART_SAHI.md` están archivados en `docs/archived/`

## Dependencias clave

- `ultralytics`
- `opencv-python`
- `sahi`
- `lap`
- `filterpy`
