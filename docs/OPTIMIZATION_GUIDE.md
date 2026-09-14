# Optimización basada en errores medidos

Usa el [protocolo manual](GUIDES/MANUAL_VALIDATION.md) y registra resultados antes de modificar el perfil. El backlog detalla el trabajo de detección, tracking y rendimiento; esta guía describe cómo comparar variantes sin cambiar el problema evaluado.

## Perfil y parámetros efectivos

El caso de referencia es [aerial_counting.example.json](GUIDES/aerial_counting.example.json), no una recomendación universal. Usa VisDrone, ROI de 280×400 píxeles, `imgsz=640`, confianza 0.10 y SAHI desactivado. Los flags `--tracker`, `--imgsz`, `--model`, `--video` y `--no-sahi` pueden modificar la ejecución; registra comando y metadatos además del JSON.

| Parámetro | Efecto a probar | Riesgo de una comparación incorrecta |
|---|---|---|
| `settings.conf_threshold`, `conf_per_class` | Filtrado por confianza antes del tracker | Subir el piso elimina cajas débiles que ByteTrack podría recuperar |
| `settings.imgsz` | Resolución entregada al detector | Más resolución no garantiza mejor exactitud; cambia costo y firma de caché |
| `settings.inference_roi` | Recorte de inferencia en coordenadas originales | Una ROI que no cubre el trayecto puede impedir rutas completas |
| `settings.sample_constraints`, `min_area`, `max_area` | Filtros geométricos | Un filtro que elimina buses/autos reales puede reducir cajas y empeorar recall |
| `exclusion_zones` | Descarte por centro de detección | No ocultar vehículos válidos para mejorar métricas |
| `sahi.enabled`, tamaño/solapamiento de tiles | Inferencia por recortes y fusión global | Probar bordes y autos próximos; no contar cajas duplicadas como recuperación |
| `sahi.nms_threshold` | Supresión global tras SAHI | Una supresión excesiva puede fusionar autos diferentes |
| `settings.min_origin_frames`, `min_dest_frames` | Confirmación de zonas | Subirlos puede omitir autos que pasan rápido; corregir primero geometría |
| `settings.min_crossing_frames` | Confirmación del cambio de lado | Cambia cuándo se registra el evento; considerar margen temporal |

Los filtros de muestras se aplican con una acción explícita y al menos cinco muestras. Ejecutar la vista global o marcar un solo auto no los activa. Las muestras parciales sirven para comprobar recuperación de esos vehículos; no miden recall de toda la escena.

## Asociación de tracks

ByteTrack y BoT-SORT reciben una sola actualización global por frame, también con SAHI. No se fuerza SORT por activar tiles. El wrapper actual no entrega características de apariencia y rechaza `with_reid=true`; no presentar BoT-SORT como ReID disponible.

Los parámetros nativos son `track_low_thresh`, `track_high_thresh`, `new_track_thresh`, `track_buffer`, `match_thresh` y `fuse_score`. `max_age`, `min_hits` e `iou_threshold` corresponden a SORT/OC-SORT, no sustituyen a los anteriores. La [guía de calibración](GUIDES/DETECTION_CALIBRATION_REPLAY.md) explica el caso observado de asociación débil en la versión instalada.

Compara cambios de ID, duplicaciones y eventos perdidos contra el mismo video y referencia humana. Un tracker con menos IDs o más cruces no es automáticamente mejor. La compensación de cámara dentro de BoT-SORT no corrige las zonas/líneas fijas.

## Orden de un experimento

1. Conserva perfil y salida de referencia; selecciona un fallo confirmado por revisión humana.
2. Cambia un factor y explica qué resultado esperas: recuperar un auto, eliminar una caja falsa o conservar un ID.
3. Usa replay cuando solo cambias tracking, geometría o filtros compatibles. Cambiar pesos, ROI, resolución, SAHI o bajar el piso grabado exige inferencia nueva.
4. Compara TP/FP/FN, precisión/recall/F1 por clase y eventos por ruta sobre el mismo alcance. Incluye casos de fondo, bordes y oclusión.
5. Conserva el cambio solo con evidencia y revisa un tramo reservado que no se utilizó para ajustar parámetros.

Los resultados locales existentes y sus límites están en [VERIFIED_STATE.md](GUIDES/VERIFIED_STATE.md). La prueba SAHI de 12 frames verifica integración, no exactitud del aforo completo. El replay evita ejecutar el detector y no demuestra una aceleración de inferencia.

## Rendimiento y formatos

Para medir el perfil real usa `main.py --benchmark` con los mismos argumentos de la corrida, rutas de salida nuevas y dispositivo registrado. La etapa `detection` incluye tracking. El script standalone `scripts/benchmark_pipeline.py` usa parámetros propios, zonas vacías y operaciones aproximadas de dibujo/escritura; no utilizarlo para atribuir tiempos de producción a cada etapa real.

`scripts/export_model.py` admite `--model` y `--imgsz` y exporta ONNX. No admite `--half` ni `--format`. La disponibilidad de un archivo ONNX no acredita paridad de clases/cajas ni más FPS. Debe compararse con `.pt` y el mismo perfil antes de adoptarse. No hay benchmark local de TensorRT.

Las mejoras de rendimiento se aceptan con exactitud conservada, no a cambio de omisiones invisibles. Los criterios concretos se registran en [TASK_TODO.md](TASK_TODO.md).
