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
| Tramo propuesto | **3:00 a 4:00**, igual a `assets/glorieta_test1min.mp4` (empieza en el frame 5394 del video completo) |
| Alternativa | 1:00 a 2:00 |

El dron cambia de encuadre a lo largo del video. Comparado con el 3:00, el minuto 1:00 a 2:00 difiere en imagen entre 15 y 26 (0 es idéntico), así que usarlo exige rehacer zonas, perfil y caché. El 3:00 a 4:00 ya tiene perfil, caché de detecciones y medición de cámara. **Pendiente de confirmar cuál queda como tramo oficial.**

## Criterio de aceptación (propuesta)

Objetivo inicial: ±20 %. En conteos chicos un porcentaje fijo castiga de más (1 error sobre 3 vehículos ya es 33 %), por eso la regla combina vehículos y porcentaje:

| Nivel | Criterio |
|---|---|
| Celda ruta × grupo | `abs(pred − real) ≤ max(2 vehículos, 20 % de real)` |
| Total por acceso de origen | WMAPE ≤ 20 % |
| Total del tramo | WMAPE ≤ 20 % |
| Eventos (complementario) | F1 ≥ 0.80 con `validate_routes.py --events --by-group` |

WMAPE = `Σ|pred − real| / Σ real` sobre las celdas del nivel. Un minuto de video da pocos vehículos por ruta; la precisión solo es estadísticamente sólida con tramos más largos (las guías revisadas validan en bloques de 15 minutos). La propuesta se confirma o ajusta con la primera referencia humana y se endurece (10 %, luego 5 %) cuando el sistema la cumpla.
