# Protocolo de pruebas manuales

Este procedimiento valida detección de autos y rutas sobre información verificable. El [estado comprobado](VERIFIED_STATE.md) identifica el caso de referencia y sus límites. Las mejoras pendientes y su aceptación están en [TASK_TODO.md](../TASK_TODO.md).

## Preparación

Abre una terminal en la raíz de `labs-eps-carcounter`:

```bash
mkdir -p output
CARCOUNTER_REVIEW_DIR=$(mktemp -d "$PWD/output/manual-review.XXXXXX")
cp docs/GUIDES/aerial_counting.example.json "$CARCOUNTER_REVIEW_DIR/profile.json"
printf '%s\n' "$CARCOUNTER_REVIEW_DIR"
```

Conserva la ruta mostrada. Los comandos siguientes usan esa variable en la misma terminal. En otra computadora sustituye únicamente la ruta del repositorio y comprueba que estén disponibles entorno Python, video y pesos. No uses `make clean` durante la validación: elimina resultados de `output/`.

Registra nombre del revisor, fecha, video/tramo, perfil, modelo y comando de cada corrida. `run.video_sha256`, `run.source_fps`, `run.config_snapshot` y los valores efectivos de CLI en el resultado ayudan a comprobar qué se ejecutó. La configuración guardada por sí sola no documenta todos los overrides de CLI.

## PRUEBA-01: reproducir la referencia sin cambiar el detector

Precondición: existe `output/aerial_low_conf.sqlite`. Ejecuta:

```bash
env/bin/python main.py --config "$CARCOUNTER_REVIEW_DIR/profile.json" \
  --headless --demo-mode --device cpu --max-frames 300 \
  --replay-detections output/aerial_low_conf.sqlite \
  --output "$CARCOUNTER_REVIEW_DIR/replay.mp4" \
  --output-json "$CARCOUNTER_REVIEW_DIR/replay.json" \
  --output-tracks-csv "$CARCOUNTER_REVIEW_DIR/replay_tracks.csv"
```

Resultado de regresión esperado con los mismos archivos y versión: seis eventos, IDs 24/60/19/67/47/146, frames 79/81/131/186/285/291, un bus y cinco autos. Si cambia, conserva ambas salidas y revisa diferencias antes de ajustar parámetros. Esta igualdad prueba reproducibilidad, no exactitud humana.

Si la caché no existe, graba una nueva corrida del mismo perfil. Usa salidas diferentes de las anteriores:

```bash
env/bin/python main.py --config "$CARCOUNTER_REVIEW_DIR/profile.json" \
  --headless --demo-mode --device cpu --max-frames 300 \
  --record-detections "$CARCOUNTER_REVIEW_DIR/detections.sqlite" \
  --output "$CARCOUNTER_REVIEW_DIR/inference.mp4" \
  --output-json "$CARCOUNTER_REVIEW_DIR/inference.json" \
  --output-tracks-csv "$CARCOUNTER_REVIEW_DIR/inference_tracks.csv"
```

Una segunda grabación sobre la misma ruta SQLite se rechaza. Cada experimento debe tener ruta nueva. Inferencia nueva puede variar con versión o dispositivo: registra esas diferencias.

## PRUEBA-02: detectar autos, no objetos del fondo

Mira primero el video original `assets/glorieta_test1min.mp4`, frames 1-300, y después la corrida correspondiente. Examina únicamente la región `[680,350,960,750]`; el resto de la imagen no está siendo inferido en este perfil.

Selecciona al menos diez imágenes de revisión como punto de partida, incluyendo tráfico denso, autos pequeños, oclusiones y vehículos cerca del borde de la región. Ese tamaño es una muestra inicial, no garantía estadística. Sigue la [guía de anotación de cajas](validation_workflow.md) para evaluar precisión y recuperación de autos. Cuenta también omisiones, no solo cajas que ya mostró el modelo.

Anota cajas sobre edificios, árboles o calzada vacía; autos sin caja; dos cajas sobre un auto; y clases equivocadas. Un auto estacionado es un vehículo real y puede tener caja: el error sería contar un cruce que no ocurrió. No añadas exclusiones que oculten autos válidos para mejorar la métrica.

## PRUEBA-03: continuidad del mismo auto

Sigue autos individuales antes, durante y después de una oclusión. Registra segundo/frame y el ID previo/nuevo. Distingue ausencia de detección, cambio de ID y duplicación simultánea. Incluye un caso con dos autos próximos de la misma clase.

El historial dibujado tiene longitud limitada; que se acorte una línea de trayectoria no prueba un cambio de ID. El número acumulado de IDs tampoco equivale al número de autos. Para comparar trackers utiliza el mismo video, tramo y caché; cambia solo `--tracker` y guarda salidas nuevas. BoT-SORT no corrige las zonas ni activa ReID de apariencia en este wrapper.

## PRUEBA-04: cruce de línea y conteo humano

Cuenta de manera independiente cada cruce de Anillo oeste y su sentido. Comprueba que rozar la línea, circular por fuera de su extremo o permanecer detenido no agregue un evento. Revisa un cruce completo y, si existe en el video, un regreso en sentido contrario. El comportamiento actual es una vez por ID, línea y sentido, no una vez por auto para toda su vida.

Los autos ya sobre la línea al comenzar el clip, que terminan cortados por el final o que se ocultan justo al cruzar deben registrarse como casos de borde. Mantén margen de video antes y después del intervalo evaluado. El evento del sistema usa frame de confirmación; puede ir después del contacto físico por el tamaño de la caja y `min_crossing_frames`.

Completa una copia de `output/aerial_events_truth_template.json` para la corrida compatible. Si usaste otro video o tramo, actualiza su SHA-256 y límites a partir del resultado. Marca `reviewed=true` solo después de revisar todo el intervalo. Las instrucciones y el comando del evaluador están en [ROUTE_EVENT_REVIEW.md](ROUTE_EVENT_REVIEW.md).

## PRUEBA-05: calibración y persistencia de configuración

```bash
env/bin/python setup.py --config "$CARCOUNTER_REVIEW_DIR/profile.json"
```

La interfaz Tk requiere prueba en el escritorio: aquí no se logró abrir. Comprueba que carga el video y modelo del perfil, que todos los controles sean alcanzables y que la barra lateral se desplace. Cambia de frame, dibuja muestras pequeñas y grandes y usa **Probar muestras guardadas**.

Con menos de cinco muestras no debe aplicarse un filtro geométrico derivado. Dibujar una muestra o ejecutar la vista global no debe cambiar filtros sin la acción explícita. **Limpiar muestras** también debe retirar restricciones cargadas. Revisa autos válidos y buses después de aplicar filtros.

Guarda la copia, cierra y vuelve a abrir ese mismo archivo. Comprueba modelo, ROI, confianza, muestras, clases, SAHI y parámetros de tracking. El control de deriva de cámara se configura por JSON/CLI; no se afirma que exista un control visual para él.

## PRUEBA-06: rutas completas origen/destino

Trabaja en otra copia del perfil y selecciona `counting_mode=zones`. Dibuja al menos dos zonas de entrada/salida visibles, sin invadir la trayectoria de quienes siguen circulando. Verifica que ambas y el trayecto intermedio estén cubiertos por la región de detección. Una zona fuera del recorte no producirá observaciones válidas por sí sola.

Revisa un auto que complete A→B, otro que salga por una tercera zona si está configurada, y uno que pase cerca de una salida sin tomarla. El contador confirma la primera zona distinta al origen que cumpla permanencia; la geometría debe evitar destinos prematuros. Registra incompletos por borde de video o pérdida de ID y acuerda cómo tratarlos antes de publicar totales.

Cambiar ROI, modelo, resolución o SAHI exige inferencia nueva y otra caché. Para el minuto completo usa `--max-frames 1799` con el video de referencia; la caché de 300 frames no lo cubre. No reutilices la referencia humana de una línea como validación de rutas A→B.

## PRUEBA-07: movimiento de cámara

```bash
env/bin/python scripts/audit_camera_motion.py \
  --config "$CARCOUNTER_REVIEW_DIR/profile.json" \
  --every 30 --max-drift-px 5 \
  --output-json "$CARCOUNTER_REVIEW_DIR/camera.json"
```

Este comando no ejecuta el detector. Código 0 significa estable dentro del umbral en las muestras; código 2 indica deriva excesiva o estimación no fiable. Un muestreo puede omitir movimientos entre frames. Compara las líneas y zonas con referencias fijas del pavimento en el inicio y final.

Para comprobar cada frame en una corrida, agrega `--camera-max-drift-px 5` a `main.py`. La ejecución se detiene con código 1 y sin resultado final si no puede validar la cámara. No subas el umbral únicamente para hacer pasar el video; los 5 px requieren calibración. Esta prueba no estabiliza nada automáticamente.

## PRUEBA-08: evidencia y criterio de cierre

Completa una fila por incidencia; puede ser una tabla de texto, sin editar JSON inicialmente:

| Video/tramo | Frame o segundo | ID previo/nuevo | Observado | Esperado | Evidencia | Estado |
|---|---|---|---|---|---|---|
| Por completar | Por completar | Si se ve | Omisión, duplicado, clase, ruta o cámara | Descripción del hecho humano | Captura o referencia al video | Sin revisar / confirmado / resuelto / no reproducible |

Conserva originales, perfil de cada variante, comando, salidas, anotaciones y reporte de métricas. El evaluador de eventos requiere frames desde 1; convierte tiempo mediante `frame = round(segundos * FPS) + 1` y verifica visualmente el redondeo. Los nombres `frame_0000.jpg` del extractor son números de exportación, no frames originales del video.

Para cerrar una mejora exige reproducción del fallo, comparación antes/después con el mismo alcance y ausencia de regresión en los casos revisados. Los umbrales de precisión, recall y F1 por ruta/clase deben quedar acordados antes de elegir un ganador. Un total igual, más cajas, más IDs o más FPS no bastan.

La aprobación de la presentación debe decir qué tramo, región, clases y rutas fueron revisados por quién. Lo pendiente se conserva en `TASK_TODO.md`; no marcar como aprobado lo que solo pasó pruebas sintéticas.
