# Guia de Optimizacion para Deteccion de Vehiculos

## Flujo actual

Todos los parametros se configuran con el configurador interactivo y se guardan en el JSON:

```bash
python setup_glorieta.py --video assets/glorieta_fast.MP4
python main_glorieta.py --config config_glorieta.json --video assets/glorieta_fast.MP4
```

Ya no se usan flags CLI para confianza, tracker, etc. — todo va en el JSON config.

---

## Parametros clave y como ajustarlos

### `conf_threshold` (default: 0.10)

Umbral global de confianza para YOLO.

- **Bajar** (0.05-0.10): mas recall, detecta vehiculos pequenos pero mas falsos positivos
- **Subir** (0.20-0.35): menos falsos positivos, puede perder autos pequenos

Para glorietas aereas: empezar en 0.10 y subir solo si hay demasiado ruido.

### `conf_per_class`

Umbrales individuales por clase. Se configuran con los sliders del Paso 1.

Util cuando una clase tiene mas falsos positivos que otra:

- `car`: generalmente el mas confiable, puede quedar bajo (0.10)
- `motorbike`: suele tener mas falsos positivos en aereas, subir a 0.20-0.30
- `bus` / `truck`: depende del video

### `imgsz` (default: 1600)

Resolucion de inferencia YOLO. Mayor = mejor deteccion de objetos pequenos pero mas lento.

- Vista aerea alta (drone >50m): 1600-2560
- Vista aerea media (20-50m): 1280-1600
- Vista a nivel de calle: 640-1280

### `exclusion_zones`

Poligonos donde no se cuentan vehiculos. Se configuran en el Paso 0 del configurador.

Usar para:

- estacionamientos con vehiculos fijos
- areas laterales donde YOLO detecta techos o arboles como vehiculos
- zonas fuera del flujo de transito

### `sample_constraints`

Filtros geometricos derivados de las muestras de vehiculos del Paso 1.

Rango automatico: el configurador toma el min/max de ancho, alto y aspect ratio de todas las muestras, con un margen del 30%.

Mas muestras = filtro mas representativo. Marcar al menos 5 vehiculos de distintos tamanos.

### `slice_width` / `slice_height` (SAHI)

Tamano de los tiles para SAHI (Slicing Aided Hyper Inference).

- Tiles chicos (256): mejor para autos muy pequenos, mas tiles, mas lento
- Tiles grandes (512): mas rapido, menos granularidad

### `overlap_ratio` (SAHI)

Solapamiento entre tiles SAHI. Mayor overlap = menos chances de cortar un vehiculo en el borde.

- 0.2: balance general
- 0.3: si hay vehiculos justo en los bordes de tiles

### `nms_threshold` (SAHI)

NMS post-SAHI para eliminar detecciones duplicadas entre tiles solapados.

- 0.3: valor por defecto, buen balance
- 0.2: mas agresivo, elimina mas duplicados
- 0.5: mas permisivo, menos supresion

### `min_origin_frames` / `min_dest_frames`

Frames consecutivos que un vehiculo debe permanecer en una zona para confirmar entrada/salida.

- 3 (default): buen balance anti-bounce
- 5+: para zonas muy grandes donde el vehiculo pasa lento
- 1-2: si las zonas son pequenas y el vehiculo pasa rapido

---

## Tracker

Opciones via CLI flag `--tracker`:

| Tracker | Ventajas | Cuando usar |
|---------|----------|-------------|
| `bytetrack` (default) | Estable, nativo de Ultralytics | General, recomendado |
| `botsort` | Mejor re-ID | Cuando hay muchas oclusiones |
| `sort` | Legacy, no requiere `lap` | Fallback si `lap` no instala |

Con SAHI activo, siempre se usa SORT legacy (SAHI no es compatible con `model.track()`).

---

## Modelos YOLO

| Modelo | Tamano | Velocidad | Precision | Recomendacion |
|--------|--------|-----------|-----------|---------------|
| **yolov11l** | ~85MB | ~280ms | Muy Alta | Mejor para objetos pequenos |
| **yolov11m** | ~50MB | ~200ms | Media-Alta | Balance velocidad/precision |
| yolov8l | ~80MB | ~300ms | Alta | Buena opcion general |
| yolov8m | ~50MB | ~220ms | Media | Alternativa rapida |

Recomendacion: `yolov11l` para glorietas aereas.

---

## Proceso de calibracion recomendado

### 1. Zonas de exclusion (Paso 0)

Si hay vehiculos estacionados visibles en el frame, dibuja poligonos sobre ellos. Esto evita tracks innecesarios y ahorra recursos de tracking.

### 2. Vista Global + muestras (Paso 1)

1. Presiona `Vista Global` con conf bajo (0.10) para ver todo lo que detecta
2. Marca 5+ vehiculos representativos como muestras
3. Presiona `Vista Global` otra vez — los filtros geometricos ya eliminan objetos grandes
4. Si una clase tiene falsos positivos, sube su slider individual
5. Valida con `Probar YOLO` sobre un auto puntual

### 3. Zonas de transito (Paso 2)

1. Dibuja zonas que cubran cada boca calle
2. Usa el preview de video para validar
3. Activa YOLO en el preview para ver detecciones en vivo
4. Las zonas de exclusion se muestran como referencia

### 4. SAHI (Paso 3)

1. Revisa la cuadricula de tiles sobre el frame
2. Ajusta `nms_threshold` si hay duplicados
3. Guarda la configuracion

---

## Problemas comunes y soluciones

### Vehiculos estacionados generan tracks

Solucion: definir zonas de exclusion en el Paso 0 del configurador.

### Autos pequenos no se detectan

- Subir `imgsz` a 1600-2560
- Bajar `conf_threshold` a 0.05-0.10
- Ajustar tiles SAHI a 256x256

### Demasiados falsos positivos

- Marcar mas muestras de vehiculos para ajustar filtros geometricos
- Subir `conf_threshold` o el slider de la clase problematica
- Agregar zonas de exclusion sobre areas problematicas

### Detecciones duplicadas con SAHI

- Bajar `nms_threshold` a 0.2-0.25

### IDs de tracking cambian constantemente

- Usar `bytetrack` (default) en vez de `sort`
- Los parametros del tracker (max_age, min_hits, iou_threshold) se ajustan en el Paso 3

### Rutas contadas incorrectamente

- Verificar que las zonas no sean demasiado grandes (invadiendo el anillo)
- Subir `min_origin_frames` / `min_dest_frames` si hay conteos falsos por vehiculos que rozan la zona
