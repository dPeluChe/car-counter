# Validación del conteo: eventos y rutas

Compara el conteo del sistema contra una referencia humana del mismo video y tramo. La detección por imagen se mide aparte con [DETECTION_VALIDATION.md](DETECTION_VALIDATION.md). El directorio de trabajo `$CARCOUNTER_REVIEW_DIR` se crea en el [protocolo manual](MANUAL_VALIDATION.md).

## Qué exporta el conteo

El JSON de `main.py` contiene `counting_events`: un registro por cruce, ruta entre zonas o dirección confirmada, con ID del evento, ID del track, clase, ruta, frame de confirmación, posición y origen/destino o línea/sentido.

- Los frames empiezan en 1. Tiempo en el video: `(frame - 1) / run.source_fps`. El frame es el de confirmación, que puede ir después del contacto físico.
- La clase es la mayoría de observaciones del track (empate: se mantiene la anterior) y se congela en el primer conteo.
- Los eventos sobreviven a la purga de tracks inactivos; los cruces de varias líneas del mismo vehículo se guardan por separado.
- `--output-tracks-csv` conserva tracks retirados con `first_seen_frame`, `observed_frames`, `destination` y `counted_frame`. Un ID es una trayectoria del tracker: un cambio de ID parte un auto en varias. **El número de IDs no es el aforo.**

## Reglas del conteo

**Líneas** (`counting_mode=lines`): el recorrido entre frames debe cruzar el segmento dibujado y confirmar el cambio de lado durante `min_crossing_frames` observaciones. Con bounding boxes, la caja debe terminar de pasar. Pasar alrededor de un extremo no cuenta. Las líneas horizontales usan `↑/↓` y las verticales `←/→`. Cada ID cuenta una vez por línea y sentido. El campo antiguo `tolerance` se acepta pero ya no limita.

**Zonas** (`counting_mode=zones`): el destino es la primera zona distinta al origen que cumple permanencia, y cada ID cuenta una ruta. Detalle y colocación de zonas en [ROUNDABOUT_GUIDE.md](ROUNDABOUT_GUIDE.md). Solo este modo produce rutas A→B y matriz OD.

## Método principal: eventos

1. Copia la plantilla vacía del tramo de la demo (300 frames, `reviewed=false`):

   ```bash
   cp output/aerial_events_truth_template.json "$CARCOUNTER_REVIEW_DIR/truth.json"
   ```

2. Mirando el video original, registra cada evento con `frame`, `route` y `class`, incluidos los autos que el sistema omitió. Usa los nombres de ruta del perfil. No copies predicciones como referencia.
3. El SHA-256 debe coincidir con `run.video_sha256` del resultado; `start_frame` y `end_frame` delimitan lo revisado. Marca `reviewed=true` solo al terminar todo el tramo.
4. Evalúa:

   ```bash
   env/bin/python scripts/validate_routes.py \
     --results "$CARCOUNTER_REVIEW_DIR/replay.json" \
     --truth "$CARCOUNTER_REVIEW_DIR/truth.json" \
     --events --tolerance-frames 15 \
     --output "$CARCOUNTER_REVIEW_DIR/event_validation.json"
   ```

Empareja uno a uno por ruta, clase y cercanía temporal, y devuelve precisión, recall, F1, predicciones sin pareja y omisiones. Dos predicciones sobre el primer auto y ninguna sobre el segundo dan un falso positivo y una omisión aunque el total cuadre. `--min-f1` fija el criterio acordado; una referencia vacía no lo aprueba.

Los 15 frames son un valor inicial: ajústalo al FPS, a la separación entre autos y al criterio humano de cruce. Ampliarlo demasiado oculta errores. Una predicción sin pareja puede ser duplicado, falso positivo, clase equivocada o desfase; el evaluador **no comprueba identidad física** cuando dos autos iguales pasan juntos.

## Resumen complementario: totales por ruta

Formato `{ "ruta": conteo }` ([plantilla](route_truth.example.json)), separador `->` o `→`, con los nombres de zona del perfil y conteos enteros no negativos. No lleva hash, tramo ni revisión: regístralos aparte.

```bash
env/bin/python scripts/validate_routes.py \
  --results "$CARCOUNTER_REVIEW_DIR/routes.json" \
  --truth data/validation/route_truth.json \
  --min-accuracy 0.95 --output "$CARCOUNTER_REVIEW_DIR/route_totals.json"
```

Atajo: `make validate-routes RESULTS=... TRUTH=... ARGS="--min-accuracy 0.95"`. Por ruta reporta `pred`, `real`, `err` y `acc`, y marca **rutas fantasma** (contadas sin ocurrir) y **faltantes**. Accuracy ponderada: `max(0, 1 - suma(|pred-real|) / max(total_real, 1))`. Termina con código 1 si no alcanza el umbral o la referencia no tiene autos. El 95% es un ejemplo: el criterio real se acuerda con EPS.

## Interpretar errores

- **Faltan autos en una ruta:** detección (autos chicos no detectados) o tracking (cambio de ID a media glorieta pierde el origen).
- **Rutas fantasma:** geometría, asociaciones incorrectas u observaciones de entrada/salida. Subir `min_origin_frames`/`min_dest_frames` es un experimento que también pierde autos rápidos.
- **Destino equivocado:** el auto pasa por varias salidas antes de la real y el conteo fija la primera distinta al origen.

## Evidencia de aceptación

Guarda perfil, comando, video/hash, intervalo, referencia humana y reporte.
