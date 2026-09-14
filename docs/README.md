# Car Counter: documentación

Estado real de lo comprobado: [GUIDES/VERIFIED_STATE.md](GUIDES/VERIFIED_STATE.md). Es la única fuente para "qué funciona y con qué evidencia"; los demás documentos la enlazan en vez de repetirla.

## Estructura

> Derivada de [`.doctos.yml`](../.doctos.yml). Edita ese archivo, no esta tabla.

| Ruta | Contenido |
|---|---|
| `TASK_TODO.md` | Única lista de pendientes, con criterios de cierre |
| `GUIDES/` | Procedimientos vigentes |
| `RESEARCH/` | Informes fechados con mediciones y hallazgos |
| `JOURNAL/` | Bitácora fechada (`KICKOFF_`, `STANDUP_`); no se edita después |
| `ARCHIVED/` | Documentos sustituidos, con nota |
| `TASK_COMPLETED/` | Historial de tareas cerradas |

## Guías

| Necesidad | Documento |
|---|---|
| Ejecutar las 8 pruebas manuales | [MANUAL_VALIDATION.md](GUIDES/MANUAL_VALIDATION.md) |
| Calibrar, ajustar tracker, replay, cámara, rendimiento | [DETECTION_TUNING.md](GUIDES/DETECTION_TUNING.md) |
| Medir cajas contra anotaciones LabelMe | [DETECTION_VALIDATION.md](GUIDES/DETECTION_VALIDATION.md) |
| Medir eventos y rutas contra conteo humano | [ROUTE_VALIDATION.md](GUIDES/ROUTE_VALIDATION.md) |
| Dibujar zonas origen/destino en una glorieta | [ROUNDABOUT_GUIDE.md](GUIDES/ROUNDABOUT_GUIDE.md) |
| Activar el cron de revisión con Codex | [RECURRING_CODE_REVIEW_CRON.md](GUIDES/RECURRING_CODE_REVIEW_CRON.md) |

Perfiles de ejemplo usados por código y guías: `GUIDES/aerial_counting.example.json` (Makefile `run-aerial`) y `GUIDES/route_truth.example.json`.

## Informes

Informes fechados en [RESEARCH/](RESEARCH/), nombrados `<TEMA>_<YYYY_MM_DD>.md`. Solo se crean con mediciones nuevas; cada guía o tarea enlaza el que la respalda.

## Reglas

1. Cada resultado indica video y tramo, perfil, modelo, dispositivo, comando y archivo de salida.
2. Distinguir siempre prueba sintética, replay de cajas, inferencia nueva y revisión humana.
3. Un procedimiento documentado no significa que se haya ejecutado; eso va en `VERIFIED_STATE.md` o en un informe fechado.
4. No repetir advertencias ni comandos de otra guía: enlazarla.
5. `output/`, `assets/`, `models/`, `data/` y `config/` están ignorados por Git; la evidencia ahí es local.
6. Nombres de archivo en `UPPERCASE_SNAKE_CASE`. Lo sustituido va a `ARCHIVED/` con nota, salvo que git ya guarde la versión idéntica.
