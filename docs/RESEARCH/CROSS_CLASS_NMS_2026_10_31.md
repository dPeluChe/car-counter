# Duplicados entre clases y supresión sin clase

Fecha: 2026-10-31. Respalda el punto de NMS sin clase de [TODO-030](../TASK_TODO.md).

## Hallazgo

El modelo VisDrone con confianza mínima 0.10 devuelve a veces dos cajas casi idénticas sobre el mismo vehículo con clases distintas (`car` y `van`). YOLO hace NMS por clase, así que ambas sobreviven. ByteTrack las trata como dos objetos y abre un ID por cada una, lo que fragmenta los tracks y produce cambios de clase que no son errores de identidad.

## Cambio

`settings.cross_class_nms_iou` (0 = apagado, por defecto). Después de los filtros de clase, confianza, tamaño y exclusión, una caja se suprime si otra de **distinta clase** y mayor confianza la solapa con IoU mayor al umbral. Cajas de la misma clase no se tocan. Actúa sobre la caché, así que **no cambia la firma ni exige otra grabación**, y el preview, la evaluación de detección y `main.py` usan la misma regla. El diagnóstico del configurador marca las cajas suprimidas como `duplicado`.

## Método

`scripts/compare_cross_class_nms.py` corre el replay de una misma caché por cada umbral y resume eventos, tracks, tracks cortos (≤10 observaciones) y candidatos a cambio de ID (`carcounter/track_review.py`). Perfil `docs/GUIDES/aerial_counting.example.json`, video `glorieta_test1min.mp4`, caché de 300 frames (`output/aerial_low_conf.sqlite`), sin SAHI, ByteTrack.

```bash
env/bin/python scripts/compare_cross_class_nms.py --config docs/GUIDES/aerial_counting.example.json \
  --video assets/glorieta_test1min.mp4 --cache output/aerial_low_conf.sqlite --max-frames 300
```

## Resultados

| Umbral | Eventos | Tracks | Cortos | Candidatos a cambio de ID | Con cambio de clase |
|---|---|---|---|---|---|
| 0 (actual) | 6 | 282 | 150 | 83 | 38 |
| 0.2 a 0.8 | 6 | 120 | 5 | 0 | 0 |
| 0.9 | 6 | 126 | 10 | 3 | 1 |
| 0.95 | 6 | 161 | 45 | 10 | 4 |
| 0.99 | 6 | 162 | 46 | 11 | 4 |

La línea base reproduce las cifras de [VERIFIED_STATE.md](../GUIDES/VERIFIED_STATE.md) (282 tracks, 150 cortos, 83 candidatos, 38 con cambio de clase). Con BoT-SORT: 283 tracks, 157 cortos y 78 candidatos sin supresión; con 0.7, 120 tracks, 6 cortos y 0 candidatos. Los seis eventos (frame, ruta y clase) son idénticos en todos los umbrales y las dos variantes de tracker.

## Qué dice y qué no

- De 0.2 a 0.8 el resultado es idéntico: las parejas entre clases solapan casi por completo, así que el umbral no es sensible en ese rango y 0.7 deja margen.
- Menos tracks no prueba mejor exactitud. Los 162 tracks que desaparecen no se revisaron uno a uno; sin referencia humana no se sabe si alguno era un auto distinto. El tramo solo tiene seis eventos en una línea.
- Gana la clase de mayor confianza; si es la errónea, el error se conserva. La matriz de confusión sigue pendiente en TODO-032.
- No se probó tráfico denso con autos pegados de clases distintas, donde un umbral bajo podría suprimir un vehículo real.

**Decisión:** queda apagado por defecto. Candidato `0.7` para validar contra la referencia humana de TODO-028 antes de activarlo en el perfil de presentación.
