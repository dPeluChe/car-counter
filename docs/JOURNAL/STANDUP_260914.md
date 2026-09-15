# Standup 2026-09-14: ciclo de estabilización

Punto de partida: [KICKOFF_260914.md](KICKOFF_260914.md). Todo el trabajo de septiembre estaba sin commitear.

## Qué se cerró

| PR | Resultado |
|---|---|
| #4 | Trabajo local del 6 al 14 de septiembre recuperado en git: conteo corregido, detector compartido, eventos, replay, monitor de cámara |
| #5 | Docs reorganizados (11 → 7 guías), `CLAUDE.md` + `AGENTS.md`, `.doctos.yml`, backlog archivado por mes, prompt del cron exige rama + PR |
| #6 | Archivos de más de 400 líneas divididos en mixins sin cambio de comportamiento |
| #7 | RF-DETR: nombres de clase corregidos (autos salían como moto, buses y camiones se descartaban) |
| #8 | Rama heredada de detección, calibración muerta y `ProcessingEngine` eliminados; ROI validada en un solo lugar; perfil validado al arrancar; tracker efectivo en metadata; eventos en DB y API; wizard con BoT-SORT |

## Decisiones

- `ProcessingEngine` se eliminó en vez de actualizarse: duplicaba el loop de `main.py` sin sus mejoras y ningún flujo usaba pausa ni callbacks.
- Las dependencias opcionales (`fastapi`, `httpx`, `libsql-experimental`) quedaron instaladas en `env/` para que DB y API se prueben siempre en esta máquina.
- El prompt del cron se corrigió pero el cron sigue sin instalar (TODO-034).

## Estado verificable

- Suite: 337 pruebas, sin omisiones en `env/` local.
- `make replay-aerial`: 6 eventos, IDs 24/60/19/67/47/146.
- Sin ground truth humano: ninguna precisión es presentable todavía.

## Pendiente, en orden

1. TODO-028: acordar clases y umbrales con EPS y contar a mano un tramo.
2. TODO-033: abrir el configurador en escritorio (también valida el split del PR #6).
3. TODO-032 / TODO-030 / TODO-031 sobre esa referencia humana.
4. Opcionales: TODO-036 (replay y cámara en el wizard), TODO-034 (cron).

## Tarde: alcance EPS

- Grupos definidos con el responsable: `ligeros` (autos, vans, pickups, taxis, mototaxis), `pesados` (autobuses, combis, microbuses, camiones, remolques), `dos_ruedas` (motos, bicicletas, patines). Implementados en código y validador (`--by-group`).
- Objetivo confirmado: matriz origen/destino por acceso y grupo, siguiendo cada vehículo hasta su salida; aplica también a calles de uno y dos sentidos.
- Margen propuesto ±20 % con regla para conteos chicos, respaldado en [la investigación](../RESEARCH/COUNTING_ACCURACY_2026_09_14.md).
- Hallazgo: `glorieta_test1min.mp4` es el minuto 3:00 a 4:00 de `glorieta_normal.mp4`; el 1:00 a 2:00 tiene otro encuadre. Tramo oficial pendiente de confirmar.

## Cierre: dron y metadatos

- Tramo oficial confirmado: 3:00 a 4:00 de `glorieta_normal.mp4`.
- La deriva del encuadre es movimiento del dron en una sola toma continua (sin cortes): estable entre 1:30 y 9:30, se mueve al inicio y desde 9:44.
- Ningún video tiene telemetría por frame; las exportaciones la eliminaron. Pedir originales DJI con `.SRT`.
- Decisión: la geometría (zonas y exclusiones) debe servir para todo el video, por tramos estables o con ajuste por frame (TODO-029). El responsable revisará el marcaje completo de rutas y exclusiones.

## Tramos de cámara estable (opción 1)

- `segment_video.py` divide el video por estabilidad; con 10 px, `glorieta_normal.mp4` queda en 7 tramos estables y 3 transiciones cortas. El tramo 2:00 a 6:25 es uno solo y contiene el oficial.
- `main.py --start-frame` corre un tramo con su perfil; el seek es exacto. El clip de prueba empieza en el frame 5396, no en el 5394.
- Siguiente: perfil con varios tramos para contar el video completo en una sola pasada.

## Fuera del repo

`env/bin/pip` apunta a la ruta anterior del proyecto; usar `env/bin/python -m pip` o recrear el entorno.
