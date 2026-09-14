# Documentación de Car Counter

Referencia operativa revisada el 2026-09-14 contra código local, pruebas y artefactos. La demo disponible cubre una línea durante 300 frames; no acredita el aforo completo de la glorieta.

## Por dónde empezar

| Necesidad | Documento |
|---|---|
| Qué falta y cómo se acepta una mejora | [TASK_TODO.md](TASK_TODO.md) |
| Ejecutar y registrar pruebas manuales | [Protocolo manual](GUIDES/MANUAL_VALIDATION.md) |
| Saber qué se comprobó realmente | [Estado verificado](GUIDES/VERIFIED_STATE.md) |
| Configurar detector, filtros, tracker y replay | [Calibración y replay](GUIDES/DETECTION_CALIBRATION_REPLAY.md) |
| Medir cajas contra anotaciones | [Validación de detección](GUIDES/validation_workflow.md) |
| Medir rutas y eventos contra conteo humano | [Totales de rutas](GUIDES/route_validation.md), [eventos](GUIDES/ROUTE_EVENT_REVIEW.md) |
| Configurar rutas origen/destino | [Guía de glorietas](ROUNDABOUT_GUIDE.md) |
| Elegir un experimento de optimización | [Guía de optimización](OPTIMIZATION_GUIDE.md) |
| Activar ejecuciones programadas | [Cron local](GUIDES/RECURRING_CODE_REVIEW_CRON.md) |

## Evidencia e historia

- [Auditoría inicial de conteo](RESEARCH/COUNTING_AUDIT_2026_09_06.md).
- [Mediciones de detector, replay y cámara](RESEARCH/DETECTION_IMPROVEMENTS_2026_09_07.md).
- [Eventos y consenso de clase](RESEARCH/DETECTION_ROUTES_2026_09_14.md).
- [Revisión documental](RESEARCH/DOCUMENTATION_AUDIT_2026_09_14.md).
- [Historial de tareas](TASK_COMPLETED.md): registro heredado, no es el estado actual del producto.
- [Evaluación histórica de supervision](RESEARCH/supervision_eval.md): contiene estimaciones sin benchmark; no usar sus tiempos como mediciones.

## Convenciones

`TASK_TODO.md` es la única lista de trabajo pendiente. Las guías contienen procedimientos; sus pasos no acreditan que se hayan ejecutado. `GUIDES/` contiene instrucciones vigentes y `RESEARCH/` conserva informes fechados. Los originales de guías sustituidas quedan en `ARCHIVED/`, identificados como históricos.

Se conservan las rutas existentes de las guías para no romper referencias. Los documentos nuevos usan nombres UPPERCASE_SNAKE_CASE. No se modifica el registro histórico para simular que una prueba pendiente ya pasó.

Cada resultado debe indicar video y tramo, configuración, modelo, dispositivo, comando y archivo de salida. Distinguir siempre prueba sintética, replay de cajas, inferencia nueva y revisión humana. Los archivos de `output/`, `assets/`, `models/` y `data/` son locales o están ignorados por Git; comprobar su presencia en otra máquina.

Los números de ejemplos no son resultados medidos. Los porcentajes de aceptación deben acordarse para el caso de uso y registrarse antes de comparar variantes.
