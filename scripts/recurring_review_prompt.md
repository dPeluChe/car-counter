Trabaja en la raíz de este repositorio (`labs-eps-carcounter`). Objetivo: presentar detección de autos y rutas contadas correctamente. Prioriza autos pequeños u ocluidos, continuidad de IDs, origen/destino de rutas y menos duplicados u omisiones. Calibración y movimiento de cámara solo cuando afecten eso. No dediques ejecuciones a DB, API, infraestructura, limpieza general ni optimización sin efecto medido. Las reglas del proyecto están en `AGENTS.md`: síguelas.

En cada ejecución:

1. Revisa `git status`. Si hay cambios sin commit que no son tuyos, no los toques y termina informando el bloqueo. Crea una rama `auto/<tema-corto>` desde `main`.
2. Lee `docs/GUIDES/VERIFIED_STATE.md` y la tabla "Orden del ciclo" de `docs/TASK_TODO.md`. Elige la tarea pendiente de mayor prioridad, lee solo su sección y verifica en el código que siga pendiente. Abre informes de `docs/RESEARCH/` solo si esa tarea los enlaza.
3. Si requiere investigación, consulta documentación oficial o artículos originales. No cambies de detector ni añadas dependencias sin medir.
4. Implementa un incremento comprobable. Reutiliza `env/bin/python`, módulos existentes y cachés locales; perfil de referencia `docs/GUIDES/aerial_counting.example.json`.
5. Ejecuta las pruebas relevantes, la suite y `git diff --check`.
6. Marca el avance en la sección de la tarea en `docs/TASK_TODO.md` y, si cambió lo comprobado, actualiza `docs/GUIDES/VERIFIED_STATE.md`. Crea `docs/RESEARCH/<TEMA>_<YYYY_MM_DD>.md` solo si hay mediciones nuevas; el registro de la ejecución va en tu respuesta final.
7. Haz commits pequeños, push de la rama y abre un PR contra `main` con `gh pr create`. Si el push o el PR fallan por permisos, deja los commits en la rama y dilo en la respuesta final. Termina con un resumen en español.

No hagas merge, push a `main`, despliegues ni mensajes externos. No sobrescribas videos, pesos, anotaciones humanas ni cachés. No cambies el cron, sus límites ni sus archivos de control. Si otro proceso modifica estos archivos, no hagas cambios concurrentes. Si falta una decisión humana, acceso o datos, documenta el bloqueo y elige otra tarea; si no queda trabajo autorizado, pide pausar la automatización.
