# Standup 2026-09-14: ciclo de estabilización

Punto de partida: [KICKOFF_260914.md](KICKOFF_260914.md). Todo el trabajo de septiembre estaba sin commitear.

## Qué se cerró

| PR | Resultado |
|---|---|
| #4 | Trabajo local del 6 al 14 de septiembre recuperado en git: conteo corregido, detector compartido, eventos, replay, monitor de cámara |
| #5 | Docs reorganizados (11 → 7 guías), `CLAUDE.md` + `AGENTS.md`, `.doctos.yml`, backlog archivado por mes, prompt del cron exige rama + PR |
| #6 | Archivos de más de 400 líneas divididos en mixins sin cambio de comportamiento |
| #7 | RF-DETR: nombres de clase corregidos (autos salían como moto, buses y camiones se descartaban) |
| `fix/todo-036-inherited-wiring` | Rama heredada de detección, calibración muerta y `ProcessingEngine` eliminados; ROI validada en un solo lugar; perfil validado al arrancar; tracker efectivo en metadata; eventos en DB y API; wizard con BoT-SORT |

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

## Fuera del repo

`env/bin/pip` apunta a la ruta anterior del proyecto; usar `env/bin/python -m pip` o recrear el entorno.
