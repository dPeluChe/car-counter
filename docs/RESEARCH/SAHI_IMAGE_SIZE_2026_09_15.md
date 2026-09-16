# Costo de SAHI por tile y efecto en las clases

Fecha: 2026-09-15. Motivo: el preview y las corridas con SAHI eran inusables por lentitud. Respalda [TODO-038](../TASK_TODO.md) y la fila de Detección de [VERIFIED_STATE.md](../GUIDES/VERIFIED_STATE.md).

## Hallazgo

SAHI reescala cada tile al `imgsz` del perfil, no al tamaño del tile. Con el valor por defecto un tile de 512 px se amplía a 1600, o sea 3.1x. El valor se fija en tres lugares y gana el último:

1. `carcounter/runtime.py:load_sahi` crea el `AutoDetectionModel` con `image_size=cfg["imgsz"]`.
2. `carcounter/detection.py:detect_objects` reasigna `sahi_model.image_size = imgsz` en cada frame.
3. `setup_panels/step1_calibration.py:_ensure_sahi_model` hace lo mismo en el configurador.

La corrida real de `main.py` pasa por el punto 2, así que cualquier ajuste que no lo toque no cambia el costo.

## Método

Video `assets/glorieta_test1min.mp4`, modelo `models/yolo/yolov8l-visdrone.pt`, CPU. Tile 512x512, overlap 0.2, confianza 0.10, NMS post-SAHI 0.3. Las tres configuraciones se midieron seguidas en la misma sesión, una corrida cada una. Las cajas se cuentan a la salida de `detect_objects`, o sea ya filtradas por `VEHICLE_CLASSES`, piso de confianza y NMS.

Dos mediciones distintas: frame completo sobre 5 frames (0, 360, 720, 1080, 1440) y el tramo de 300 frames del perfil de referencia, con ROI `[680,350,960,750]`, modo `lines` y ByteTrack.

## Resultados

| `image_size` | Frame completo | Tramo de 300 frames con ROI | Eventos | Ligeros | Pesados |
|---|---|---|---|---|---|
| 1600 (actual) | 61 602 ms/frame | 73.6 s (4.08 FPS) | 5 | 3 | 2 |
| 640 | 9 316 ms/frame | 19.8 s (15.12 FPS) | 6 | 5 | 1 |
| 512 | 6 805 ms/frame | 17.1 s (17.53 FPS) | 6 | 5 | 1 |

## Por qué no se cambió el valor por defecto

Bajar `image_size` no solo detecta menos, reasigna clases. De los 5 eventos de 1600, con 640 coinciden 3 (corridos uno o dos frames, ruido normal de confirmación). El `truck` del frame 187 aparece como `car`, y esa reclasificación lo mueve de `pesados` a `ligeros`; además sale un cruce extra donde 1600 no contó ninguno. El aforo del tramo pasa de 3 ligeros y 2 pesados a 5 y 1.

Como la clase define el grupo EPS ([COUNTING_SCOPE.md](../GUIDES/COUNTING_SCOPE.md)), el cambio altera justo lo que se entrega.

## Qué no dice esta medición

- La comparación a frame completo no decide: de las 1022 cajas que 640 pierde contra 1600 (confianza ≥ 0.25), solo 68 caen dentro de la ROI. El resto del desacuerdo ocurre en zonas que nunca llegan a evento.
- Las cajas que 640 pierde no son ruido de baja confianza: en 1600 la confianza mediana es 0.726 y 2545 de 3748 cajas superan 0.50. Tampoco son las más chicas: área mediana 170 px² las perdidas contra 187 px² las conservadas.
- Es una corrida por configuración, sin repetición, y comparada contra la salida de 1600, no contra referencia humana. Sirve para no cambiar el valor; no sirve para elegir uno nuevo.

## Efecto sobre el grupo `dos_ruedas`

Con 1600 salen 245 cajas `motor`, 11 `bicycle`, 6 `tricycle` y 5 `awning-tricycle`. Con 640 quedan 99 `motor` y ninguna `bicycle` ni `tricycle`. En este tramo no hubo eventos de ese grupo, así que no alteró el resultado, pero el grupo desaparecería casi entero si se cuenta en otro tramo.
