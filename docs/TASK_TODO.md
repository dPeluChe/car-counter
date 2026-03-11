# Tareas Pendientes

Backlog de mejoras para el proyecto Car Counter (glorieta).
Cada tarea tiene criterios de aceptacion claros para validacion.

**Prioridad:** P0 = critico para demo, P1 = mejora importante, P2 = nice-to-have

---

## TODO-016: Visualizacion de muestras de vehiculos en el canvas

**Prioridad:** P2
**Archivo:** `setup_glorieta.py`
**Paso:** 1 (Calibracion)

### Problema

El configurador muestra "Muestras: N" como texto pero no dibuja los bounding boxes de las muestras marcadas sobre el canvas. Si se recarga un config con `--config`, no hay forma visual de saber que muestras se habian marcado previamente.

### Que hacer

- Dibujar los bounding boxes de las muestras de vehiculos sobre el frame en el Paso 1
- Cada muestra con un rectangulo semi-transparente y etiqueta (ancho x alto)
- Las muestras cargadas desde config (via `sample_constraints`) mostrar un resumen visual de los rangos

### Criterios de aceptacion

- [ ] Las muestras marcadas se dibujan como rectangulos sobre el frame
- [ ] Cada muestra muestra sus dimensiones (ancho x alto px)
- [ ] Al agregar/limpiar muestras, el canvas se actualiza inmediatamente
- [ ] Las muestras persisten visualmente al cambiar de frame (si estan en coordenadas absolutas)
- [ ] Si se cargo un config con `sample_constraints`, se muestra un resumen de los rangos en el sidebar

---

## TODO-017: Sliders de confianza por clase en el configurador

**Prioridad:** P2
**Archivo:** `setup_glorieta.py`
**Paso:** 1 (Calibracion) o 3 (SAHI)

### Problema

El campo `conf_per_class` (TODO-005) solo se puede configurar editando el JSON a mano. El configurador tiene un solo slider de confianza global.

### Que hacer

- Agregar seccion expandible o grupo de sliders para las 4 clases vehiculares: car, motorbike, bus, truck
- Si el usuario no toca los sliders individuales, no se genera `conf_per_class` (backward compatible)
- Si ajusta al menos uno, se genera el campo completo en el JSON
- Mostrar los valores actuales si se cargo un config que ya tiene `conf_per_class`

### Criterios de aceptacion

- [ ] Existen sliders individuales para car, motorbike, bus, truck
- [ ] Por defecto usan el valor del slider global (no generan `conf_per_class`)
- [ ] Al mover uno, se activa `conf_per_class` para todas las clases
- [ ] El JSON guardado incluye `conf_per_class` solo si se modifico al menos un slider
- [ ] Al cargar un config con `conf_per_class`, los sliders reflejan los valores
- [ ] Backward compatible: configs sin `conf_per_class` funcionan igual
