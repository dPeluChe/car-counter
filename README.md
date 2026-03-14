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
- vista global de deteccion con feedback de progreso
- calibracion local reescalada
- filtros geometricos derivados de multiples muestras de vehiculos
- zonas de exclusion para vehiculos estacionados (Paso 0)
- umbrales de confianza por clase (car, moto, bus, truck)
- NMS post-SAHI configurable
- modo demo con scoreboard grande
- exportacion de resultados en JSON y CSV
- preview de zonas con video en vivo y detecciones YOLO opcionales

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

Para cargar una configuracion existente:

```bash
python setup_glorieta.py --video assets/glorieta_fast.MP4 --config config_glorieta.json
```

2. En el paso 0 (opcional):

- dibuja poligonos sobre areas con vehiculos estacionados u objetos fijos
- estas zonas se excluiran de la deteccion en todos los pasos siguientes

3. En el paso 1:

- usa `Vista Global`
- ajusta `imgsz` si hace falta
- marca varios autos y 1-2 camiones con `Agregar muestra vehiculo`
- ajusta confianza por clase si una clase tiene muchos falsos positivos
- valida un auto puntual con `Probar YOLO`

4. En el paso 2:

- dibuja un poligono por cada boca calle de entrada/salida
- usa el preview de video para validar que las zonas capturan el flujo
- activa `YOLO` en el preview para ver detecciones en vivo

5. En el paso 3:

- revisa tiles SAHI
- ajusta NMS threshold si hay detecciones duplicadas
- guarda `config_glorieta.json`

6. Ejecutar el conteo:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4
```

## Modos utiles

Demo recomendado para vista aerea:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4
```

Modo demo con scoreboard grande:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --demo-mode
```

Modo rapido sin SAHI:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --no-sahi
```

Smoke test sin ventana:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --headless --max-frames 50 --no-save
```

Exportar resultados:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --output-json results.json --output-csv routes.csv
```

## Parametros importantes

### En el JSON config (generado por el configurador)

- `conf_threshold`: recall vs precision (global)
- `conf_per_class`: umbrales individuales por clase (car, motorbike, bus, truck)
- `imgsz`: resolucion de inferencia YOLO
- `sample_constraints`: filtros geometricos aprendidos de las muestras del configurador
- `exclusion_zones`: poligonos donde no se cuentan vehiculos
- `min_origin_frames` / `min_dest_frames`: anti-bounce para zonas origen/destino
- `slice_width` / `slice_height`: tamano de tile SAHI
- `overlap_ratio`: solapamiento SAHI
- `nms_threshold`: NMS post-SAHI para eliminar duplicados

### CLI flags de main_glorieta.py

- `--no-sahi`: desactivar SAHI (mas rapido)
- `--tracker bytetrack|botsort|sort`: algoritmo de tracking
- `--demo-mode`: scoreboard grande para presentaciones
- `--headless`: sin ventana (para servidores o CI)
- `--max-frames N`: procesar solo N frames
- `--no-save`: no guardar video de salida
- `--show-fps`: mostrar FPS en pantalla
- `--benchmark`: guardar metricas de rendimiento

## Notas practicas

- Para glorietas aereas, `imgsz` alto mejora mucho la deteccion.
- La vista global prioriza recall; luego las muestras ayudan a quitar techos, arboles u objetos grandes.
- Las zonas de exclusion eliminan vehiculos estacionados de la deteccion y el tracking.
- El conteo real usa los filtros geometricos guardados por el configurador.
- Configs anteriores (sin `exclusion_zones` o `conf_per_class`) siguen siendo compatibles.

## Documentacion relacionada

- `ROUNDABOUT_GUIDE.md` — Guia de uso para glorietas
- `OPTIMIZATION_GUIDE.md` — Ajuste de rendimiento y parametros
- `docs/TASK_TODO.md` — Backlog de mejoras pendientes
- `docs/TASK_COMPLETED.md` — Historial de cambios completados

## Dependencias clave

- `ultralytics`
- `opencv-python`
- `sahi`
- `lap`
- `filterpy`
