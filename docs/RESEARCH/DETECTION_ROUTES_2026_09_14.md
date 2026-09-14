# Detección de autos y rutas, 14 de septiembre de 2026

El trabajo queda enfocado en detección de autos y rutas verificables para la presentación. Se añadieron registros de eventos, validación temporal y consenso de clase por track. No se cambiaron los pesos del detector ni se añadieron dependencias.

## Cambios comprobados

- Cada cruce o ruta exporta frame, ID, clase, ruta, posición y sentido u origen/destino. Los eventos sobreviven a la purga de tracks. Los cruces de varias líneas conservan sus frames individuales.
- La clase ya no depende de la primera observación en rutas entre zonas ni de una detección aislada en cruces. Se acumulan votos por track y se conserva la clase después del primer conteo.
- El evaluador compara eventos por ruta, clase y tolerancia temporal, con correspondencia uno a uno. Un total correcto ya no oculta una omisión compensada por otro evento sin pareja.
- La referencia debe estar revisada y pertenecer al mismo SHA-256 y tramo de video. Las referencias vacías no aprueban el umbral de aceptación.

## Replay del video real

Se reutilizó `output/aerial_low_conf.sqlite` sobre el perfil VisDrone y sus 300 frames. La adición de eventos produjo un CSV idéntico al anterior. Después de activar consenso de clase cambiaron 44 clases del resumen de tracks, pero las posiciones, IDs, frames y demás datos de trayectorias permanecieron iguales. Sin revisión humana no se puede afirmar que esas 44 clases sean correcciones.

| ID | Frame confirmado | Clase | Cruce |
|---:|---:|---|---|
| 24 | 79 | bus | Anillo oeste ↓ |
| 60 | 81 | car | Anillo oeste ↓ |
| 19 | 131 | car | Anillo oeste ↓ |
| 67 | 186 | car | Anillo oeste ↓ |
| 47 | 285 | car | Anillo oeste ↓ |
| 146 | 291 | car | Anillo oeste ↓ |

Los seis eventos conservaron clase, ruta, ID y frame. El replay final registró 121.90 FPS de loop en CPU; no mide velocidad de inferencia porque reutiliza cajas grabadas.

Artefactos locales:

- `output/aerial_events_consensus.json` y CSV de tracks: resultado final del replay.
- `output/aerial_demo_20260914.mp4` y JSON: demo renderizada del mismo tramo. Se verificaron 300 frames, igualdad de los seis eventos y el último frame con marcador `CONTEO: 6`.
- `output/aerial_events_truth_template.json`: plantilla sin revisar, no es ground truth.

## Pruebas y límites

Pasaron 316 pruebas, con 15 omitidas por dependencias opcionales. Se comprobaron cruces y rutas sintéticos, rechazo de duplicados temporales, omisiones con totales iguales, clases equivocadas, procedencia de referencias, supervivencia de eventos y consenso independiente por vehículo. Pasaron compilación de Python y `git diff --check`.

La demo sigue siendo parcial y cuenta una línea. No demuestra todavía rutas completas origen/destino ni exactitud de aforo. El movimiento de cámara continúa siendo un pendiente. La [guía de eventos](../GUIDES/ROUTE_VALIDATION.md) explica cómo obtener una comparación válida contra anotaciones humanas.

También se preparó un [cron local](../GUIDES/RECURRING_CODE_REVIEW_CRON.md) enfocado exclusivamente en este objetivo. Sus decisiones se probaron sin lanzar otro agente. No está instalado: el entorno bloquea `crontab` y el arranque del servicio local necesario para consultar cuota.
