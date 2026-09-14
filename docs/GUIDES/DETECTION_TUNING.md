# Ajuste de detección, tracking y replay

Cómo calibrar el perfil, comparar variantes y repetir pruebas sin volver a correr inferencia. Lo que ya está comprobado, y sus límites, vive en [VERIFIED_STATE.md](VERIFIED_STATE.md).

Perfil de referencia: [aerial_counting.example.json](aerial_counting.example.json). Es un caso de prueba, no una recomendación universal. Los flags `--tracker`, `--imgsz`, `--model`, `--video` y `--no-sahi` sobreescriben el perfil: registra el comando además del JSON.

## Calibrar en el configurador

```bash
env/bin/python setup.py --config docs/GUIDES/aerial_counting.example.json
```

Vista global, prueba del recuadro, muestras y preview usan el mismo detector, clases del modelo, resolución, ROI, SAHI, confianza, geometría y exclusiones que `main.py`.

- Marca vehículos pequeños y grandes en varios frames y pulsa **Probar muestras guardadas**. La correspondencia exige IoU ≥ 0.50 y una detección no valida dos muestras del mismo frame. Las muestras son parciales: no miden falsos positivos, IDs ni recall de la escena.
- **Aplicar filtros de las muestras** es una acción explícita, disponible desde cinco muestras. Dibujar un auto o correr la vista global no cambia filtros. **Limpiar muestras** retira también los filtros cargados.
- Cambiar de modelo invalida la calibración y recarga SAHI si hace falta.
- La barra lateral tiene desplazamiento vertical. El paso 3 ajusta ByteTrack/BoT-SORT y conserva parámetros adicionales del archivo.

## Parámetros

| Parámetro | Referencia | Efecto | Riesgo al compararlo |
|---|---:|---|---|
| `settings.conf_threshold` | 0.10 | Piso de confianza antes del tracker | Subirlo elimina cajas débiles que ByteTrack podría recuperar |
| `settings.conf_per_class` | | Umbral por clase, también previo al tracker | Por encima de `track_low_thresh` elimina detecciones de recuperación |
| `settings.imgsz` | 640 | Resolución entregada al detector | Más resolución no garantiza exactitud; cambia costo y firma de caché |
| `settings.inference_roi` | `[680,350,960,750]` | Recorte en coordenadas del video original | Si no cubre el trayecto, no hay rutas completas |
| `settings.sample_constraints`, `min_area`, `max_area` | | Filtros geométricos | Pueden quitar buses o autos reales y bajar recall |
| `exclusion_zones` | | Descarte por centro de la caja | No ocultar vehículos válidos para mejorar métricas |
| `sahi.enabled`, tiles y solapamiento | false | Inferencia por recortes con fusión global | Revisar bordes y autos próximos; un duplicado no es recuperación |
| `sahi.nms_threshold` | | Supresión global tras SAHI | Excesiva fusiona autos distintos |
| `settings.min_origin_frames`, `min_dest_frames` | | Confirmación de zonas | Subirlos pierde autos rápidos; corregir primero la geometría |
| `settings.min_crossing_frames` | | Confirmación del cambio de lado | Mueve el frame del evento |
| `tracker.track_low_thresh` | 0.10 | Límite inferior de la asociación secundaria | |
| `tracker.track_high_thresh` | 0.25 | Detecciones de la primera asociación | |
| `tracker.new_track_thresh` | 0.25 | Confianza mínima para crear un ID | |
| `tracker.track_buffer` | 30 | Retención de tracks perdidos, escalada por FPS respecto a 30 | |
| `tracker.match_thresh` | 0.80 | Límite del costo de asociación | |
| `tracker.fuse_score` | false | Asociación sin multiplicar IoU por confianza | Ver abajo |

## Tracking

En Ultralytics 8.4.21, `BYTETracker.update()` aplica `fuse_score` también a la segunda asociación. Con confianza menor a 0.25 el costo fusionado supera 0.75 aun con IoU perfecto y nunca pasa el límite de 0.50. Por eso el perfil usa `fuse_score=false`; una prueba verifica que una caja de 0.15 conserva un ID existente sin crear otro.

- ByteTrack y BoT-SORT reciben una sola actualización global por frame, también con SAHI. Activar tiles ya no fuerza SORT.
- El wrapper no entrega características de apariencia y rechaza `with_reid=true`: BoT-SORT aquí no es ReID.
- `max_age`, `min_hits` e `iou_threshold` son de SORT/OC-SORT; no reemplazan los parámetros de ByteTrack.
- La compensación de cámara de BoT-SORT ayuda a asociar tracks, pero no mueve zonas ni líneas.

Compara cambios de ID, duplicados y eventos perdidos contra el mismo video y referencia humana. Menos IDs o más cruces no significa mejor tracker.

## Grabar una vez y repetir sin inferencia

```bash
env/bin/python main.py --config docs/GUIDES/aerial_counting.example.json \
  --headless --no-save --max-frames 300 \
  --record-detections output/mi_prueba.sqlite \
  --output-json output/mi_prueba.json

env/bin/python main.py --config docs/GUIDES/aerial_counting.example.json \
  --headless --no-save --tracker botsort \
  --replay-detections output/mi_prueba.sqlite \
  --output-json output/mi_prueba_botsort.json
```

La caché guarda cajas, clases y confianza antes de filtros geométricos y tracking. Con replay puedes cambiar tracker, zonas, líneas y filtros; sigue leyendo el video para dibujar y para la compensación de BoT-SORT.

- La firma comprueba SHA-256 del video y pesos, resolución, ROI, detector y SAHI. Cambiar ROI, modelo o SAHI exige otra grabación.
- Permite subir la confianza, pero no bajarla del piso grabado: el replay no crea detecciones ausentes.
- No sobrescribe archivos existentes; usa una ruta nueva por experimento. Una caché incompleta se rechaza y `--max-frames` no puede exceder el tramo grabado.
- Los FPS de replay excluyen inferencia: no miden velocidad del detector.

Un error de detección, tracking o lectura termina con código distinto de cero y no exporta el resultado como completado. Los JSON exitosos incluyen perfil, parámetros efectivos del tracker, origen de las detecciones y duración del tramo.

## Movimiento de cámara

```bash
env/bin/python scripts/audit_camera_motion.py \
  --config docs/GUIDES/aerial_counting.example.json \
  --every 30 --max-drift-px 5 --output-json output/camera_audit.json
```

No ejecuta el detector. Compara el fondo de cada muestra con el primer frame mediante ORB y RANSAC ([`estimateAffinePartial2D`](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)), excluye la ROI de inferencia y mide el desplazamiento en extremos de líneas y vértices de zonas. Código 0: estable en las muestras. Código 2: deriva excesiva o estimación no fiable. Muestrear cada 30 frames puede omitir movimientos intermedios.

Para comprobar **cada frame** durante el conteo, agrega `--camera-max-drift-px 5` a `main.py` o guarda `settings.camera_max_drift_px`. Si se excede o pierde correspondencias, termina con código 1 y sin resultado final; los resultados exitosos incluyen `run.camera_check`.

El control es opcional, cuesta CPU y **no estabiliza ni corrige geometría**. Los 5 px son un umbral experimental: no subirlo solo para que pase un video. La similitud cubre traslación, rotación y escala; perspectiva, paralaje y fondos móviles requieren más validación.

## Orden de un experimento

1. Conserva perfil y salida de referencia; elige un fallo confirmado por revisión humana.
2. Cambia un solo factor y anota qué esperas: recuperar un auto, quitar una caja falsa o conservar un ID.
3. Usa replay si solo cambias tracking, geometría o filtros compatibles. Pesos, ROI, resolución, SAHI o bajar el piso exigen inferencia nueva.
4. Compara TP/FP/FN, precisión/recall/F1 por clase y eventos por ruta sobre el mismo alcance, incluyendo fondo, bordes y oclusión.
5. Conserva el cambio solo con evidencia y confírmalo en un tramo reservado que no se usó para ajustar.

Para medir contra anotaciones: [DETECTION_VALIDATION.md](DETECTION_VALIDATION.md) (cajas) y [ROUTE_VALIDATION.md](ROUTE_VALIDATION.md) (eventos y rutas).

## Rendimiento y formatos

Mide el perfil real con `main.py --benchmark` y los mismos argumentos de la corrida; la etapa `detection` incluye tracking. `scripts/benchmark_pipeline.py` usa parámetros propios, zonas vacías y dibujo/escritura aproximados: no sirve para atribuir tiempos de producción.

`scripts/export_model.py` solo admite `--model` e `--imgsz` y exporta ONNX. Un `.onnx` no acredita paridad de clases/cajas ni más FPS: compáralo con el `.pt` y el mismo perfil. No hay benchmark local de TensorRT. Una mejora de rendimiento se acepta solo con exactitud conservada; criterios en TODO-023/024 de [TASK_TODO.md](../TASK_TODO.md).
