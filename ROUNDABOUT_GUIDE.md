# Guia de uso: Glorieta A→B

## Objetivo

El flujo actual de glorieta ya no es solo una prueba de deteccion. Ahora permite:

- calibrar deteccion sobre vista aerea
- definir zonas poligonales por calle
- rastrear vehiculos con IDs
- contar rutas A→B entre zonas

Los archivos principales son:

- `setup_glorieta.py`
- `main_glorieta.py`

## Paso 1: Configuracion

```bash
source env/bin/activate
python setup_glorieta.py --video assets/glorieta_fast.MP4
```

### Que hace el configurador

- permite cambiar de frame para elegir un momento util del video
- tiene `Vista Global` para medir recall en toda la glorieta
- usa `imgsz` alto para mejorar deteccion en vista aerea
- permite agregar varias muestras de vehiculos
- deriva filtros geometricos a partir de esas muestras
- valida localmente un auto especifico antes de pasar a zonas

### Flujo recomendado de calibracion

1. Presiona `Vista Global`
2. Ajusta `imgsz` si la escena sigue corta de recall
3. Marca 5 autos y 1-2 camiones con `Agregar muestra vehiculo`
4. Vuelve a presionar `Vista Global`
5. Repite hasta bajar falsos positivos grandes
6. Marca un auto puntual y usa `Probar YOLO`
7. Confirma y continua

## Paso 2: Zonas

Dibuja un poligono por cada boca calle relevante de la glorieta.

Regla practica:

- la zona debe cubrir el tramo donde ya sabes que el auto esta entrando o saliendo
- evita zonas demasiado grandes que invadan el anillo interno

## Paso 3: SAHI

El configurador tambien guarda parametros para deteccion por tiles.

Valores utiles para vista aerea:

- `slice_width`: 256 a 512
- `slice_height`: 256 a 512
- `overlap_ratio`: 0.2 a 0.3

## Ejecucion del conteo

Con la config guardada:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4
```

Modo rapido sin SAHI:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --no-sahi
```

Smoke test:

```bash
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4 --headless --max-frames 50 --no-save
```

## Filtros que hoy usa el conteo

`main_glorieta.py` ya respeta:

- `conf_threshold`
- `imgsz`
- `min_area`
- `max_area`
- restricciones geometricas derivadas de muestras:
  - ancho
  - alto
  - aspect ratio

Eso ayuda a quitar techos, arboles o objetos grandes que no parecen vehiculos.

## Estado actual del prototipo

Ya esta implementado:

- ByteTrack / BoT-SORT nativo
- fallback SORT
- SAHI
- calibracion local reescalada
- vista global de deteccion
- filtros multi-muestra
- conteo A→B por zonas

Todavia requiere validacion manual sobre videos reales para ajustar:

- recall vs falsos positivos
- tamano de tiles SAHI
- zonas de entrada/salida
- estabilidad del tracking en escenas con oclusion
