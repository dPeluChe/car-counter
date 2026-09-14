# Protocolo de pruebas manuales

Ocho pruebas para validar detección de autos y rutas con evidencia humana. El caso de referencia y sus límites están en [VERIFIED_STATE.md](VERIFIED_STATE.md); los criterios de cierre de cada tarea, en [TASK_TODO.md](../TASK_TODO.md). Los comandos detallados viven en las guías enlazadas.

## Preparación

Desde la raíz de `labs-eps-carcounter`:

```bash
mkdir -p output
CARCOUNTER_REVIEW_DIR=$(mktemp -d "$PWD/output/manual-review.XXXXXX")
cp docs/GUIDES/aerial_counting.example.json "$CARCOUNTER_REVIEW_DIR/profile.json"
printf '%s\n' "$CARCOUNTER_REVIEW_DIR"
```

Usa la variable en la misma terminal. En otra máquina comprueba que existan entorno Python, video y pesos. No uses `make clean` durante la validación: borra `output/`.

Registra revisor, fecha, video/tramo, perfil, modelo y comando de cada corrida. `run.video_sha256`, `run.source_fps` y `run.config_snapshot` del resultado ayudan, pero no documentan todos los overrides de CLI.

## PRUEBA-01: reproducir la referencia

Precondición: existe `output/aerial_low_conf.sqlite`.

```bash
env/bin/python main.py --config "$CARCOUNTER_REVIEW_DIR/profile.json" \
  --headless --demo-mode --device cpu --max-frames 300 \
  --replay-detections output/aerial_low_conf.sqlite \
  --output "$CARCOUNTER_REVIEW_DIR/replay.mp4" \
  --output-json "$CARCOUNTER_REVIEW_DIR/replay.json" \
  --output-tracks-csv "$CARCOUNTER_REVIEW_DIR/replay_tracks.csv"
```

Esperado con los mismos archivos y versión: seis eventos, IDs 24/60/19/67/47/146, frames 79/81/131/186/285/291, un bus y cinco autos. Si cambia, conserva ambas salidas y revisa antes de ajustar. Prueba reproducibilidad, no exactitud. Si falta la caché, grábala con `--record-detections` en una ruta nueva ([DETECTION_TUNING.md](DETECTION_TUNING.md#grabar-una-vez-y-repetir-sin-inferencia)).

## PRUEBA-02: detectar autos, no fondo

Revisa `assets/glorieta_test1min.mp4`, frames 1-300, solo dentro de `[680,350,960,750]`. Elige al menos diez imágenes con tráfico denso, autos pequeños, oclusiones y bordes de la región (muestra inicial, no garantía estadística). Anota y evalúa con [DETECTION_VALIDATION.md](DETECTION_VALIDATION.md).

Registra cajas sobre edificios, árboles o calzada vacía; autos sin caja; dos cajas sobre un auto; y clases equivocadas. Un auto estacionado es un vehículo real: el error sería contar un cruce que no ocurrió. No añadas exclusiones para mejorar la métrica.

## PRUEBA-03: continuidad del mismo auto

Sigue autos antes, durante y después de una oclusión. Registra frame e ID previo/nuevo. Distingue ausencia de detección, cambio de ID y duplicación simultánea. Incluye dos autos próximos de la misma clase.

Una trayectoria dibujada que se acorta no prueba un cambio de ID (el historial tiene longitud limitada). Para comparar trackers usa el mismo video, tramo y caché, cambia solo `--tracker` y guarda salidas nuevas.

## PRUEBA-04: cruce de línea contra conteo humano

Cuenta cada cruce de Anillo oeste y su sentido de forma independiente. Rozar la línea, pasar por fuera del extremo o quedarse detenido no debe sumar. Revisa un regreso en sentido contrario si existe. Registra como casos de borde los autos ya sobre la línea al inicio, cortados al final u ocultos al cruzar.

Llena la referencia de eventos y evalúa con [ROUTE_VALIDATION.md](ROUTE_VALIDATION.md#método-principal-eventos).

## PRUEBA-05: calibración y persistencia

```bash
env/bin/python setup.py --config "$CARCOUNTER_REVIEW_DIR/profile.json"
```

La GUI Tk no se ha podido abrir en las sesiones de agente: esta prueba es en escritorio.

- [ ] Carga video y modelo del perfil; todos los controles son alcanzables y la barra lateral se desplaza.
- [ ] Muestras de varios frames y **Probar muestras guardadas** funcionan.
- [ ] Con menos de cinco muestras no se aplica filtro; dibujar o correr la vista global no cambia filtros; **Limpiar muestras** retira los cargados.
- [ ] Guardar, cerrar y reabrir conserva modelo, ROI, confianza, muestras, clases, SAHI y tracker.

El control de deriva de cámara se configura por JSON/CLI; no hay control visual para él.

## PRUEBA-06: rutas completas origen/destino

En otra copia del perfil, con `counting_mode=zones`, dibuja al menos dos zonas siguiendo [ROUNDABOUT_GUIDE.md](ROUNDABOUT_GUIDE.md). Revisa un auto que complete A→B, uno que salga por una tercera zona y uno que pase junto a una salida sin tomarla. Registra incompletos por borde de video o pérdida de ID.

Cambiar ROI, modelo, resolución o SAHI exige inferencia nueva. Para el minuto completo usa `--max-frames 1799`; la caché de 300 frames no lo cubre. La referencia humana de una línea no valida rutas A→B.

## PRUEBA-07: movimiento de cámara

Corre la auditoría de [DETECTION_TUNING.md](DETECTION_TUNING.md#movimiento-de-cámara) con `--config "$CARCOUNTER_REVIEW_DIR/profile.json"` y salida en el mismo directorio. Compara líneas y zonas con referencias fijas del pavimento al inicio y al final del tramo.

## PRUEBA-08: evidencia y cierre

Una fila por incidencia:

| Video/tramo | Frame | ID previo/nuevo | Observado | Esperado | Evidencia | Estado |
|---|---|---|---|---|---|---|
| | | | Omisión, duplicado, clase, ruta o cámara | Hecho humano | Captura o referencia | Sin revisar / confirmado / resuelto / no reproducible |

Conserva originales, perfil de cada variante, comando, salidas, anotaciones y reporte. El evaluador de eventos usa frames desde 1: `frame = round(segundos * FPS) + 1`, verificando el redondeo. Los `frame_0000.jpg` del extractor son números de exportación, no frames del video.

Una mejora se cierra con reproducción del fallo, comparación antes/después con el mismo alcance y sin regresión. Los umbrales de precisión, recall y F1 por ruta/clase se acuerdan antes de elegir ganador. La aprobación dice qué tramo, región, clases y rutas revisó quién.
