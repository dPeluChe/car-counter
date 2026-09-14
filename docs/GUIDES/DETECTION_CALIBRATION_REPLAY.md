# Calibración, tracking y repetición de pruebas

El perfil aéreo usa VisDrone, resolución 640 y una ROI de 280 × 400 píxeles del video normal. Cuenta una línea durante 300 frames. Es un caso reproducible de unos diez segundos, no el aforo completo de la glorieta.

## Calibrar el perfil que se ejecutará

```bash
env/bin/python setup.py --config docs/GUIDES/aerial_counting.example.json
```

La vista global, la prueba del recuadro, las muestras guardadas y la vista previa usan el mismo detector, clases del modelo, resolución, ROI, SAHI, confianza, geometría y exclusiones que `main.py`. Los argumentos de CLI pueden sobreescribir el perfil; compara ejecuciones con los mismos valores.

- Marca vehículos pequeños y grandes en varios frames. Guarda las muestras y pulsa **Probar muestras guardadas**. La correspondencia exige IoU ≥ 0.50 y una detección no puede validar dos muestras del mismo frame.
- La prueba informa cuántas muestras recupera. Las muestras son parciales: no miden falsos positivos, IDs ni exactitud del conteo.
- Dibujar un auto o ejecutar la vista global ya no modifica filtros geométricos. **Aplicar filtros de las muestras** es una acción separada, disponible desde cinco muestras. Revisa después los buses, vehículos lejanos y ocluidos.
- **Limpiar muestras** elimina también los filtros derivados cargados. Cambiar de modelo invalida la calibración y recarga SAHI cuando se necesita.
- La barra lateral tiene desplazamiento vertical. El paso 3 permite ajustar ByteTrack/BoT-SORT y conserva parámetros adicionales del archivo.

La ROI utiliza coordenadas del video original. Debe contener todo el recorrido necesario para el conteo. Una cámara que cambia de encuadre requiere revisar la geometría; BoT-SORT compensa movimiento para asociar tracks, pero no estabiliza las líneas ni las zonas.

## Comprobar movimiento antes del aforo

```bash
env/bin/python scripts/audit_camera_motion.py \
  --config docs/GUIDES/aerial_counting.example.json \
  --every 30 --max-drift-px 5 --output-json output/camera_audit.json
```

Compara el fondo de cada muestra con el primer frame mediante ORB y RANSAC. Excluye la ROI de inferencia y mide el desplazamiento estimado en los extremos de líneas y vértices de zonas y direcciones. Exige suficientes correspondencias distribuidas en la imagen. Devuelve código 2 si detecta movimiento excesivo o no puede comprobarlo; el JSON conserva las muestras para revisión. Muestrear cada 30 frames puede omitir movimientos entre muestras.

Para comprobar **cada frame** durante el conteo, agrega `--camera-max-drift-px 5` a `main.py`, o guarda `settings.camera_max_drift_px` en el perfil. Si excede el umbral o pierde las correspondencias, detiene la ejecución con código 1 y no exporta un resultado terminado. Los resultados exitosos incluyen `run.camera_check`.

El control es opcional y agrega trabajo de CPU. Los 5 píxeles son un umbral de prueba, pendiente de calibrar contra la geometría y el conteo humano. No estabiliza imágenes ni corrige las líneas. La transformación de similitud admite traslación, rotación y escala; perspectiva, paralaje y fondos móviles requieren validación adicional. La estimación usa [OpenCV `estimateAffinePartial2D`](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html).

## Separar detección, asociación y creación de IDs

Valores del perfil de ejemplo:

| Parámetro | Valor | Función |
|---|---:|---|
| `settings.conf_threshold` | 0.10 | Piso de confianza para detección y filtrado |
| `tracker.track_low_thresh` | 0.10 | Límite inferior de la asociación secundaria |
| `tracker.track_high_thresh` | 0.25 | Detecciones de la primera asociación |
| `tracker.new_track_thresh` | 0.25 | Confianza mínima para crear un ID |
| `tracker.track_buffer` | 30 | Retención de tracks perdidos, escalada por FPS respecto a 30 FPS |
| `tracker.match_thresh` | 0.80 | Límite del costo de asociación de Ultralytics |
| `tracker.fuse_score` | false | Asociación geométrica sin multiplicar IoU por confianza |
| `sahi.enabled` | false | SAHI desactivado en este perfil |

En Ultralytics 8.4.21 instalado, `BYTETracker.update()` aplica `fuse_score` también a la segunda asociación. Con confianza menor de 0.25, el costo fusionado supera 0.75 incluso con IoU perfecto; no puede pasar su límite de 0.50. El perfil desactiva esa fusión y una prueba verifica que una caja de confianza 0.15 conserva un ID existente sin iniciar otro.

Los umbrales por clase siguen siendo filtros anteriores al tracker. Subirlos por encima del límite bajo elimina esas detecciones de recuperación. `max_age`, `min_hits` e `iou_threshold` pertenecen a SORT/OC-SORT; no reemplazan los parámetros de ByteTrack.

SAHI fusiona sus cajas antes de una sola actualización del tracker global. Ya no fuerza SORT si seleccionas ByteTrack o BoT-SORT. La confianza y resolución de SAHI se actualizan también durante la calibración.

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

El archivo guarda cajas, clases y confianza antes de los filtros geométricos y del tracking. Puedes cambiar tracker, zonas, líneas y filtros sin ejecutar de nuevo la red neuronal. El replay sigue leyendo el video para dibujar y para la compensación de movimiento de BoT-SORT.

La firma comprueba SHA-256 del video y pesos, resolución, ROI, detector y SAHI. Permite subir la confianza, pero rechaza bajarla por debajo del piso grabado. Cambiar ROI, modelo o parámetros SAHI requiere otra grabación. Usa una ruta nueva: la grabación no sobrescribe archivos existentes. Una caché incompleta o con frames faltantes se rechaza. `--max-frames` del replay no puede exceder el tramo grabado.

Un error de detección, tracking o lectura hace terminar la ejecución con código distinto de cero y evita exportar el resultado como completado. Los JSON exitosos incluyen el perfil, parámetros efectivos del tracker, origen de las detecciones y duración del tramo procesado. El marcador muestra el conteo confirmado; los IDs se presentan por separado.

## Validar contra anotaciones humanas

`pre_label_frames.py` obtiene las clases del modelo y conserva los JSON existentes. Las preetiquetas nuevas tienen `flags.reviewed=false`. Corrige las cajas y clases en LabelMe y marca `reviewed` únicamente después de revisar cada imagen.

```bash
env/bin/python scripts/evaluate_pipeline.py \
  --config docs/GUIDES/aerial_counting.example.json \
  --frames-dir data/validation/frames \
  --annotations-dir data/validation/annotations \
  --output-json output/detection_evaluation.json
```

El evaluador exige `flags.reviewed=true`, rechaza imágenes faltantes y anotaciones duplicadas, y aplica el perfil real. Evalúa vehículos cuyo centro está dentro de la ROI y fuera de exclusiones. No elimina del ground truth los vehículos grandes que un mal filtro geométrico descartó.

Reporta métricas de localización y de clase por separado. Una clase equivocada genera un falso positivo y un falso negativo en la evaluación por clase. Los errores de cantidad se suman por frame para evitar que un exceso y una omisión se compensen. Estas métricas de cajas no sustituyen la [validación de cruces o rutas](route_validation.md).

Los resultados también exportan eventos individuales de conteo. La [guía de revisión temporal](ROUTE_EVENT_REVIEW.md) explica cómo detectar errores que un total por ruta puede ocultar.
