# Guia de uso: Conteo por zonas A→B

## Objetivo

El flujo de conteo por zonas permite:

- calibrar deteccion sobre vista aerea
- excluir zonas con vehiculos estacionados
- definir zonas poligonales por calle
- rastrear vehiculos con IDs (ByteTrack / BoT-SORT)
- contar rutas A→B entre zonas
- exportar resultados en JSON y CSV

Los archivos principales son:

- `setup.py` — configurador interactivo (Tkinter)
- `main.py` — contador de rutas

## Paso 0: Zonas de Exclusion (opcional)

Al abrir el configurador, el primer paso permite definir poligonos sobre areas que no deben contar:

- estacionamientos con vehiculos fijos
- zonas con objetos que YOLO detecta como vehiculos (techos, etc.)

Las detecciones cuyo centro caiga dentro de estas zonas se descartan en Vista Global, preview YOLO, y el conteo real.

Se dibujan en rojo/naranja para diferenciarlas de las zonas de transito.

## Paso 1: Configuracion

```bash
source env/bin/activate
python setup.py --video assets/mi_video.mp4
```

Para cargar una configuracion previa:

```bash
python setup.py --video assets/mi_video.mp4 --config config/config.json
```

### Que hace el configurador

- permite cambiar de frame para elegir un momento util del video
- tiene `Vista Global` para medir recall en toda la escena (con feedback de progreso)
- usa `imgsz` alto para mejorar deteccion en vista aerea
- permite agregar varias muestras de vehiculos
- deriva filtros geometricos a partir de esas muestras
- soporta umbrales de confianza por clase (car, moto, bus, truck)
- filtra detecciones en zonas de exclusion automaticamente
- valida localmente un auto especifico antes de pasar a zonas

### Flujo recomendado de calibracion

1. Si hay vehiculos estacionados, dibuja zonas de exclusion en el Paso 0
2. Presiona `Vista Global`
3. Ajusta `imgsz` si la escena sigue corta de recall
4. Marca 5 autos y 1-2 camiones con `Agregar muestra vehiculo`
5. Si una clase tiene muchos falsos positivos, ajusta su slider de confianza
6. Vuelve a presionar `Vista Global`
7. Repite hasta bajar falsos positivos grandes
8. Marca un auto puntual y usa `Probar YOLO`
9. Confirma y continua

## Paso 2: Zonas

Dibuja un poligono por cada boca calle relevante de la glorieta.

Regla practica:

- la zona debe cubrir el tramo donde ya sabes que el auto esta entrando o saliendo
- evita zonas demasiado grandes que invadan el anillo interno

### Preview de video

El configurador permite reproducir el video con las zonas superpuestas:

- `Play/Pausa` para ver el video en vivo
- `YOLO` para activar detecciones sobre el video (mas lento pero valida las zonas)
- las zonas de exclusion se muestran como referencia visual
- clic en una zona para seleccionarla

## Paso 3: SAHI

El configurador tambien guarda parametros para deteccion por tiles.

Valores utiles para vista aerea:

- `slice_width`: 256 a 512
- `slice_height`: 256 a 512
- `overlap_ratio`: 0.2 a 0.3
- `nms_threshold`: 0.3 (NMS post-SAHI para eliminar duplicados)

## Ejecucion del conteo

Con la config guardada:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4
```

Modo rapido sin SAHI:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4 --no-sahi
```

Modo demo con scoreboard grande:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4 --demo-mode
```

Smoke test:

```bash
python main.py --config config/config.json --video assets/mi_video.mp4 --headless --max-frames 50 --no-save
```

## Lo que usa el conteo

`main.py` respeta todo lo que el configurador guarda:

- `conf_threshold` (global)
- `conf_per_class` (por clase, si se configuro)
- `imgsz`
- `min_area` / `max_area`
- `exclusion_zones` (se dibujan en rojo semi-transparente)
- restricciones geometricas derivadas de muestras (ancho, alto, aspect ratio)
- NMS post-SAHI configurable
- `min_origin_frames` / `min_dest_frames` para anti-bounce

## Resultados

Al terminar, `main.py` genera:

- `result.mp4`: video con visualizacion de tracking y rutas
- `results.json`: resumen de rutas contadas, configuracion, metricas
- CSV opcional con `--output-csv routes.csv`

## Validacion manual

Todavia requiere validacion manual sobre videos reales para ajustar:

- recall vs falsos positivos
- tamano de tiles SAHI
- zonas de entrada/salida
- zonas de exclusion para vehiculos estacionados
- estabilidad del tracking en escenas con oclusion
