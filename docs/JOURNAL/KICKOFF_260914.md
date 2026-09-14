# Kickoff 2026-09-14

Retomado tras el trabajo de otro agente (Codex) del 6 al 14 de septiembre.

## Cómo se encontró

- `main` en `332b79b` (2026-07-02). PRs #1-#3 mergeados; ninguno abierto.
- **Todo el trabajo de septiembre estaba sin commitear**: 32 archivos modificados y 27 nuevos (unas 4,000 líneas). Causa: el prompt del agente prohibía commits y PRs.
- Suite: 316 aprobados, 15 omitidos (DB/API por dependencias opcionales).
- Evidencia (`output/aerial_*`, cachés `.sqlite`, `config/`) solo local, ignorada por git.

## Qué había mejorado (verificado en código)

- Conteo: cruces con confirmación sobre el segmento real, orígenes no confirmados reemplazables, sin IDs fabricados sin tracker.
- Detección: calibración y runtime comparten detector; clases desde los pesos (VisDrone); SAHI entrega cajas al tracker elegido.
- Eventos `counting_events`, consenso de clase por track, evaluador por evento con referencia revisada y SHA-256.
- Caché SQLite de detecciones para replay; monitor de deriva de cámara (solo detiene).
- Docs corregidos contra el código: sin cifras de RF-DETR, sin `--half` en ONNX, sin ReID.

## Estado real

Una línea, 300 frames, 6 cruces predichos, sin ground truth humano. Rutas completas, GUI Tk y cron sin validar. Orden del backlog: TODO-028 → 032 → 030 → 031.

## Acciones de esta sesión

- PR #4 `feat/detection-routes-audit`: el trabajo de septiembre en 3 commits (código+tests, cron, docs). Rutas absolutas locales retiradas antes de publicar (repo público).
- Rama `docs/reorganize`: guías fusionadas (11 → 7), duplicados eliminados, `CLAUDE.md` y `.doctos.yml`.

## Pendiente de ramas

`dev/tasks-improvements` (local y remota) y `origin/claude/organize-dev-tasks-8qthz` ya están mergeadas; se pueden borrar.
