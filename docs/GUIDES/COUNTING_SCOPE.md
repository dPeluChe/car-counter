# Alcance del aforo EPS

Definido con el responsable del proyecto el 2026-09-14. Es la referencia para configurar perfiles, contar a mano y aceptar resultados. La justificación del margen de error está en [COUNTING_ACCURACY_2026_09_14.md](../RESEARCH/COUNTING_ACCURACY_2026_09_14.md).

## Grupos que se reportan

| Grupo | Criterio humano (qué cuenta EPS) | Clases del modelo que caen ahí |
|---|---|---|
| `ligeros` | Autos, vans, pickups, taxis, mototaxis | `car`, `van`, `tricycle`, `awning-tricycle` |
| `pesados` | Autobuses, combis, microbuses, camiones, vehículos con remolque | `bus`, `truck` |
| `dos_ruedas` | Motos, bicicletas, patines o scooters | `motor` (`motorbike`/`motorcycle` en COCO), `bicycle` |

Peatones (`pedestrian`, `people`) no se cuentan. El mapeo vive en `carcounter/constants.py:CLASS_GROUPS`. Cada evento exportado trae `group` y el JSON incluye `routes_by_group`.

Los grupos son compatibles con la clasificación agregada de la SCT en Datos Viales (M motos, A automóviles, B autobuses, C/T camiones).

### Donde el modelo y el criterio EPS no coinciden

- **Combi o microbús:** VisDrone puede detectarla como `van` y quedaría en `ligeros`.
- **Pickup:** puede salir como `truck` y quedaría en `pesados`.
- **Auto con remolque:** el modelo ve el auto (`car`) y quizá el remolque por separado; EPS lo quiere en `pesados`.
- **Patines:** no hay clase en el modelo; probablemente salen como `pedestrian` y no se cuentan.

La referencia humana se hace con el criterio EPS. Estos cruces aparecen como errores de grupo al validar y se miden; no se corrigen editando la referencia.

## Qué se cuenta: origen y destino

Por cada vehículo que entra por un acceso (A) se sigue su trayectoria hasta que confirma salida por otro (B, C, D…). En ese momento se registra un evento `A → B` con su grupo y ese vehículo queda cerrado. Todas las salidas se miden en la misma pasada del video: no hace falta una ejecución por destino. El resultado es, por acceso de origen, cuántos vehículos de cada grupo fueron a cada destino.

Es el modo `zones` del contador (detalle en [ROUNDABOUT_GUIDE.md](ROUNDABOUT_GUIDE.md)). La glorieta es el caso base por ser el más difícil. El mismo modelo aplica a otras vías:

- **Calle de un sentido:** una línea de cruce o dos zonas (entrada y salida).
- **Calle de dos sentidos:** una línea con sentido (`↑/↓` o `←/→`) o zonas por sentido.
- **Intersección:** zonas por acceso, igual que la glorieta.

Condición crítica: el ID del tracker debe sobrevivir desde la entrada hasta la salida. Un cambio de ID a mitad del anillo pierde el origen y el vehículo no se cuenta o se cuenta mal (TODO-030).

## Tramo de validación

| Dato | Valor |
|---|---|
| Video completo de referencia | `assets/glorieta_normal.mp4`: 13:03, 29.97 fps, 23 472 frames |
| Tramo oficial | **3:00 a 4:00**, igual a `assets/glorieta_test1min.mp4` (su primer frame es el 5396 del video completo: `--start-frame 5396`). Confirmado el 2026-09-14 |

El video base se cuenta completo en este tramo antes de pasar a otros minutos o videos.

### Estabilidad del dron en el video completo

Medido con el monitor ORB/RANSAC contra el frame de las 3:00, cada 15 s, sobre la línea, la ROI y el centro de la glorieta. La deriva es movimiento del dron: la geometría del perfil no cambia.

| Periodo | Deriva estimada | Lectura |
|---|---|---|
| 0:00 a 1:15 | 19 px bajando a 5.5 px | El dron se acomoda; el encuadre no coincide con el perfil |
| 1:30 a 9:30 | casi siempre 5 px o menos | Toma estable, con picos de 6 a 10 px entre 2:00 y 2:30 |
| 3:00 a 4:00 (tramo oficial) | 0.1 a 9 px (6.1 px a las 3:14, 9 px a las 3:59) | Aceptable si las zonas tienen margen; no cuenta como estabilizado |
| 9:44 al final | 5 a 13 px | El dron vuelve a moverse |

### Tramos de cámara estable

`scripts/segment_video.py` (o `make segment-video VIDEO=...`) recorre el video cada 5 s y abre un tramo nuevo cuando el fondo se desplaza más de 10 px respecto al primer frame del tramo. Guarda `segments.json` y una imagen del frame de referencia de cada tramo estable. Los tramos de menos de 30 s son `transition`: el dron se está moviendo y no tienen geometría.

Resultado en `glorieta_normal.mp4` con 10 px:

| Tramo | Periodo | Frames | Referencia | Deriva máxima |
|---|---|---|---|---|
| 1 | 0:00 a 0:20 | 1-600 | transición | 9.0 px |
| 2 | 0:20 a 0:55 | 601-1650 | 601 | 9.4 px |
| 3 | 0:55 a 2:00 | 1651-3600 | 1651 | 9.5 px |
| 4 | **2:00 a 6:25** (incluye el tramo oficial) | 3601-11550 | 3601 | 9.8 px |
| 5 | 6:25 a 7:20 | 11551-13200 | 11551 | 8.2 px |
| 6 | 7:20 a 7:40 | 13201-13800 | transición | 7.6 px |
| 7 | 7:40 a 10:25 | 13801-18750 | 13801 | 8.8 px |
| 8 | 10:25 a 12:00 | 18751-21600 | 18751 | 7.5 px |
| 9 | 12:00 a 12:50 | 21601-23100 | 21601 | 9.4 px |
| 10 | 12:50 a 13:03 | 23101-23472 | transición | 3.7 px |

Con 5 px el umbral queda al nivel del ruido de la estimación (2 a 5 px en tomas quietas) y casi todo sale como transición. Con 8 px el tramo oficial queda partido en dos. Con 10 px, el mismo margen que se deja en las zonas, el tramo oficial cae dentro de un solo tramo estable.

Cómo usarlo:

1. Dibujar zonas y exclusiones sobre la imagen de referencia del tramo (`tramo04_frame3601.jpg` para el tramo oficial) y guardar un perfil por tramo.
2. Correr cada tramo con su perfil: `main.py --video assets/glorieta_normal.mp4 --start-frame <inicio> --max-frames <frames>`. Para el tramo oficial: `--start-frame 5396 --max-frames 1799`. Los frames de los eventos se cuentan desde `--start-frame`; el JSON guarda `run.start_frame`.
3. Los tramos `transition` no se cuentan hasta tener corrección geométrica (TODO-029).

La resolución es el intervalo de muestreo (5 s): el cambio real puede ocurrir entre la última muestra estable y la que abre el tramo siguiente.

### Metadatos del video

Revisado con `exiftool -ee` y `ffprobe` el 2026-09-14:

| Archivo | Origen | Telemetría del dron |
|---|---|---|
| `glorieta_normal.mp4` | Exportado con Adobe Media Encoder 2022; una sola toma, sin cortes de escena (ffmpeg, umbral 0.25) | No: la exportación la eliminó |
| `glorieta_normal_2.MP4` | Re-codificado con ffmpeg (`Lavf56`) | No |
| `patria_acueducto.mp4` | Edición en Premiere Pro con 7 clips DJI (`DJI_0496` a `DJI_0498`, `DJI_20241126…`), 854×480 | No |
| `glorieta_caballos.MOV` | Original DJI, cámara FC220 | Solo un registro fijo: GPS, 249.7 m sobre el nivel del mar, cámara a −89.3° (vertical) |

Ningún video disponible trae altura, posición o gimbal por frame, así que el movimiento del dron no se puede leer de los metadatos. Hoy solo se detecta por imagen (monitor ORB/RANSAC). Los archivos originales `DJI_*.MP4`, con su `.SRT` si el registro de subtítulos estaba activo, sí traen telemetría por frame; conviene pedirlos para los próximos vuelos (TODO-029). Aun con telemetría, el ajuste de zonas se valida por imagen: la altura y el gimbal explican la escala y el giro, pero no el desplazamiento exacto sobre el suelo.

Consecuencias:

- **Geometría para todo el video.** Las zonas y exclusiones se dibujan una vez sobre un frame de referencia y deben servir para todo el video. Hay dos formas de lograrlo: segmentar el video en tramos estables, cada uno con su referencia, o transformar la geometría frame a frame con la alineación estimada. Ambas están en TODO-029.
- Las zonas del tramo oficial deben dejar margen de al menos 10 px respecto a los bordes de calle. Para usar otros minutos hay que rehacer zonas o corregir la geometría (TODO-029).
- La ROI del perfil actual (`[680,350,960,750]`) cubre solo el lado oeste del anillo. El conteo origen/destino necesita ROI y zonas que cubran todos los accesos de la glorieta (TODO-031).

## Criterio de aceptación (propuesta)

Objetivo inicial: ±20 %. En conteos chicos un porcentaje fijo castiga de más (1 error sobre 3 vehículos ya es 33 %), por eso la regla combina vehículos y porcentaje:

| Nivel | Criterio |
|---|---|
| Celda ruta × grupo | `abs(pred − real) ≤ max(2 vehículos, 20 % de real)` |
| Total por acceso de origen | WMAPE ≤ 20 % |
| Total del tramo | WMAPE ≤ 20 % |
| Eventos (complementario) | F1 ≥ 0.80 con `validate_routes.py --events --by-group` |

WMAPE = `Σ|pred − real| / Σ real` sobre las celdas del nivel. Un minuto de video da pocos vehículos por ruta; la precisión solo es estadísticamente sólida con tramos más largos (las guías revisadas validan en bloques de 15 minutos). La propuesta se confirma o ajusta con la primera referencia humana y se endurece (10 %, luego 5 %) cuando el sistema la cumpla.
