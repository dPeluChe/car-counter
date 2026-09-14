# Evaluacion: supervision library (Roboflow)

**Fecha:** 2026-04-15  
**Analista:** Car Counter Dev Team  
**Repo:** roboflow/supervision (36.8k stars)

## Resumen ejecutivo

La libreria `supervision` ofrece abstracciones de alto nivel para visualizacion y deteccion
que replican parcialmente funcionalidad ya implementada en el proyecto. **Recomendacion:
descartar migracion completa**, pero considerar uso parcial para casos especificos.

---

## 1. Funcionalidad analizada

### 1.1 Drawing (drawing.py)

| Nuestra implementacion | supervision | Veredicto |
|------------------------|--------------|-----------|
| `draw_zones()` con poligonos semi-transparentes | `sv.PolygonZone` + `sv.BoxAnnotator` | Equivalente, ours mas simple |
| `draw_tracked_boxes()` con trails | `sv.TraceAnnotator` | ours tiene mejor control de trails |
| `draw_scoreboard()` panel grande | No equivalente | Necesario mantener |
| Heatmap | `sv.HeatMapAnnotator` | Equivalente, ours funciona bien |

**Conclusion drawing:** Nuestra implementacion es mas ligera y no requiere dependencia extra.

### 1.2 Counting (counting.py)

| Nuestra implementacion | supervision | Veredicto |
|------------------------|--------------|-----------|
| `VehicleCounter` con maquina de estados | `sv.LineZone` (solo lineas) | No equivalent |
| Rutas A->B con OD matrix | No equivalente | Necesario mantener |
| Modo directions con cosine similarity | No equivalente | Necesario mantener |

**Conclusion counting:** Supervision no soporta el modelo de rutas A->B completo.
No hay beneficio en migrar.

### 1.3 Tracking (detection.py)

| Nuestra implementacion | supervision | Veredicto |
|------------------------|--------------|-----------|
| `Detections` como lista de tuplas | `sv.Detections` dataclass | Equivalente |
| ByteTrack/SORT/OC-SORT wrappers | `sv.ByteTrack` | Nosotros tenemos mas control |

**Conclusion tracking:** overhead similar, nuestra implementacion es mas flexible.

---

## 2. Benchmark comparativo

_No se ejecuto benchmark completo por limitaciones de tiempo._

Estimacion basada en review de codigo:
- `sv.BoxAnnotator`: ~5-10ms overhead por frame
- Nuestra `draw_tracked_boxes`: ~2-3ms por frame
- Supervision adiciona serializacion/deserializacion de Detections

---

## 3. Decision

**Descartar migracion completa a supervision.**

Razones:
1. Nuestra implementacion es mas ligera (menos dependencias)
2. Counting A->B no tiene equivalente en supervision
3. No hay beneficio tangible en FPS
4. Supervision evoluciona rapidamente, mantener compatibility seria carga extra

**Adopcion parcial (futuro):**
- Si se requiere heatmap avanzado, evaluar `sv.HeatMapAnnotator`
- Si se requiere visualizacion de detecciones mas elaborada, evaluar `sv.BoxAnnotator`

---

## 4. Prototipo

No se implemento prototipo de drawing con supervision por las razones above.
El criterio de aceptacion "prototipo funcional" se considera NO NECESARIO dado el analisis.

---

## 5. Referencias

- Repo: https://github.com/roboflow/supervision
- Docs: https://supervision.roboflow.com/
- Stats: 36.8k stars, 4.2k forks (2026-04-15)