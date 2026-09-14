# Revisar detección de autos y rutas

El resultado de `main.py` contiene `counting_events`: un registro por cruce, ruta entre zonas o dirección confirmada. Conserva los totales anteriores e incluye ID del evento, ID del track, clase, ruta, frame de confirmación, posición y origen/destino o línea/sentido según el modo.

Los frames empiezan en 1. Para localizar un evento en el video usa `(frame - 1) / run.source_fps`. El frame corresponde a la confirmación del contador, que puede ocurrir después del contacto físico con la línea. Las confirmaciones de varias líneas del mismo vehículo se conservan por separado. Los eventos sobreviven a la eliminación de tracks inactivos.

La clase se decide por mayoría de observaciones del track, manteniendo la anterior en los empates. Una vez contado se conserva esa clase para no cambiar retrospectivamente el resultado. Esto reduce el efecto de una clasificación aislada; no cambia las cajas ni demuestra mayor precisión del detector.

## Referencia humana del mismo tramo

La plantilla local `output/aerial_events_truth_template.json` corresponde a los 300 frames usados en la demo. Está vacía y tiene `reviewed=false`. Trabaja en una copia dentro del directorio creado por el [protocolo manual](MANUAL_VALIDATION.md):

```bash
cp output/aerial_events_truth_template.json "$CARCOUNTER_REVIEW_DIR/truth.json"
```

Completa sus eventos mirando el video original, incluidos los autos que el sistema omitió. Cada evento requiere `frame`, `route` y `class`. Copia los nombres de ruta del perfil y marca `reviewed=true` únicamente después de revisar todo el tramo declarado. No repitas la copia encima de una referencia que ya editaste.

El SHA-256 debe coincidir con `run.video_sha256` del resultado. `start_frame` y `end_frame` delimitan el tramo humano revisado. No copies las predicciones como si fueran referencias humanas.

```bash
env/bin/python scripts/validate_routes.py \
  --results "$CARCOUNTER_REVIEW_DIR/replay.json" \
  --truth "$CARCOUNTER_REVIEW_DIR/truth.json" \
  --events --tolerance-frames 15 \
  --output "$CARCOUNTER_REVIEW_DIR/event_validation.json"
```

El evaluador empareja eventos uno a uno por ruta, clase y proximidad temporal. Devuelve precisión, recall, F1, predicciones sin pareja y eventos omitidos. Por ejemplo, dos predicciones cerca del primer auto y ninguna para el segundo producen un falso positivo y una omisión, aunque el total de la ruta sea correcto.

Una predicción sin pareja puede ser un duplicado, una detección falsa, una clase equivocada o un desajuste temporal. El reporte conserva los datos para revisar la causa. No comprueba identidad física: dos autos de la misma clase que pasan muy juntos pueden ser ambiguos.

Los 15 frames son un valor inicial configurable. Ajusta la tolerancia al FPS, separación entre autos y criterio humano de cruce; ampliarla demasiado oculta errores. `--min-f1` permite establecer un criterio de aceptación acordado. Una referencia vacía no puede aprobar ese criterio.

## Alcance de la presentación actual

`output/aerial_demo_20260914.mp4` muestra 300 frames con detecciones, trayectorias y conteo confirmado en **una línea**. El sistema registra cinco autos y un bus. No es todavía una demostración del aforo completo ni de todas las rutas origen/destino de la glorieta.

Para presentar rutas completas falta calibrar entradas y salidas dentro de la región donde se detectan vehículos, resolver el desplazamiento de cámara y comparar contra anotaciones humanas del mismo tramo.
