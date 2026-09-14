# CLAUDE.md: car-counter

Conteo de vehículos en video de glorieta para el cliente EPS. Python, OpenCV, Ultralytics, SAHI; entorno en `env/`.

## Antes de trabajar

- Qué está probado y qué no: `docs/GUIDES/VERIFIED_STATE.md`. Pendientes y criterios de cierre: `docs/TASK_TODO.md` (única lista).
- Índice de guías: `docs/README.md`. Estructura de docs declarada en `.doctos.yml`.

## Comandos

- Tests: `env/bin/python -m pytest -q` (base: 316 aprobados, 15 omitidos).
- Demo reproducible: `make run-aerial`. Replay sin inferencia: `--replay-detections output/aerial_low_conf.sqlite`.
- Entradas: `main.py` (pipeline), `setup.py` (configurador Tk), `python -m carcounter` (wizard).

## Reglas

1. **Siempre rama + PR.** Nunca terminar una sesión con trabajo sin commitear. No hacer merge sin que el usuario lo pida.
2. **Repo público** (`dPeluChe/car-counter`): sin rutas absolutas locales, credenciales, videos, pesos ni datos del cliente. `assets/`, `models/`, `output/`, `data/` y `config/` están ignorados.
3. **Evidencia honesta:** distinguir prueba sintética, replay, inferencia nueva y revisión humana. Un ID no es un vehículo. Nunca marcar `reviewed=true` en anotaciones o referencias.
4. Archivos de código por debajo de 400 líneas. Hoy lo exceden `setup.py`, `carcounter/counting.py` y `setup_panels/step2_zones.py`.
5. Cambios de tracking o conteo: comparar JSON/CSV sobre el mismo tramo con replay antes de gastar inferencia.
6. Docs: no repetir advertencias ni comandos de otra guía, enlazarla. Resultados medidos van a `docs/RESEARCH/<TEMA>_<YYYY_MM_DD>.md`.
