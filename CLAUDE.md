# CLAUDE.md: car-counter

Conteo de vehículos en video de glorieta para el cliente EPS. Python, OpenCV, Ultralytics, SAHI; entorno en `env/`. `AGENTS.md` es un enlace a este archivo para que Codex lea las mismas reglas.

Estado probado: `docs/GUIDES/VERIFIED_STATE.md`. Pendientes: `docs/TASK_TODO.md`. Índice y reglas de documentación: `docs/README.md`.

## Comandos

- Tests: `env/bin/python -m pytest -q`.
- Demo sin inferencia: `make replay-aerial` (caché local `output/aerial_low_conf.sqlite`). `make run-aerial` corre inferencia completa.
- Entradas: `main.py` (pipeline), `setup.py` (configurador Tk), `python -m carcounter` (wizard).

## Reglas

1. **Siempre rama + PR.** Nunca terminar una sesión con trabajo sin commitear. No hacer merge sin que el usuario lo pida.
2. **Repo público** (`dPeluChe/car-counter`): sin rutas absolutas locales, credenciales, videos, pesos ni datos del cliente.
3. Un ID no es un vehículo. `reviewed=true` en anotaciones o referencias solo lo marca el revisor humano.
4. Archivos de `carcounter/`, `setup_panels/`, `scripts/`, `main.py` y `setup.py` por debajo de 400 líneas.
5. Cambios de tracking o conteo: comparar JSON/CSV sobre el mismo tramo con replay antes de gastar inferencia.
