> **ARCHIVED**: 2026-09-14
> Registro de un ciclo de documentación ya aplicado. Sus correcciones están incorporadas en las guías y la reorganización posterior fusionó varias de ellas.
> Referencia actual: [docs/README.md](../README.md), [VERIFIED_STATE.md](../GUIDES/VERIFIED_STATE.md)

---

# Revisión documental del flujo, 14 de septiembre de 2026

Se contrastaron README, backlog y guías operativas contra la implementación y los artefactos locales. Este ciclo modifica documentación; los cambios de algoritmos existentes corresponden a ciclos anteriores.

## Correcciones

| Afirmación o instrucción previa | Estado confirmado |
|---|---|
| RF-DETR tiene mayor precisión y tiempos concretos en este proyecto | No hay benchmark humano local que lo demuestre; se retiraron las cifras promocionales |
| SAHI obliga a usar SORT | El flujo compartido entrega cajas globales al tracker seleccionado |
| BoT-SORT proporciona ReID de apariencia | El wrapper actual rechaza `with_reid=true` |
| Exportador ONNX con `--half` | Solo existen `--model` y `--imgsz`; otros formatos/precisiones requieren implementación y medición |
| Benchmark standalone representa todas las etapas reales | Usa zonas vacías y aproximaciones de dibujo/escritura; no carga el perfil de aforo |
| Vista global mide recall de toda la escena | Sin referencia completa solo muestra predicciones; las muestras son parciales |
| Marcar muestras aplica filtros automáticamente | Se requiere acción explícita y al menos cinco muestras |
| Ejemplo de evaluación sin perfil | Se documentó `--config` para conservar ROI, filtros, resolución y SAHI |
| Extracción entrega un número predecible de imágenes útiles | Número aproximado; además pierde índice/tiempo original, pendiente de manifiesto |
| Cualquier asistencia de segmentación sirve como anotación | El parser solo acepta rectángulos; ignora polígonos y máscaras |
| Un total igual demuestra exactitud | La validación por evento puede revelar omisiones y predicciones sin pareja; identidad física aún necesita revisión |

## Documentación entregada

- Backlog con prioridad, evidencia existente, dependencias, especificaciones, entregables y criterios de cierre. Se conservaron las claves históricas y se identificaron las fechas desconocidas.
- Índice documental, estado verificado y protocolo de ocho pruebas manuales con salidas separadas y registro de incidencias.
- Guías vigentes de detección, optimización, glorietas y eventos corregidas. Tres originales se preservaron en `docs/ARCHIVED/` con advertencia histórica.
- Historial de tareas e informes anteriores conservados; sus afirmaciones no se convierten por ello en hechos actuales.

## Verificación

La suite ejecutada en este ciclo aprobó 316 pruebas y omitió 15 por dependencias opcionales. La comprobación de comandos, enlaces y replay se registra al terminar la verificación documental.

## Alcance restante

Las pruebas humanas, la apertura de la GUI, la calibración de rutas completas y la activación del cron siguen pendientes. No se modificaron referencias para marcarlas artificialmente como revisadas. No hay una precisión humana aprobada para presentar ni un despliegue verificado.
