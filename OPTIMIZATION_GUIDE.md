# 🎯 Guía de Optimización para Detección de Vehículos

## Problema Identificado: Objetos Pequeños desde Vistas Aéreas

### Síntomas
- ✅ YOLO detecta los vehículos pero son muy pequeños
- ❌ Los IDs de tracking cambian constantemente (id=2, luego desaparece, luego id=5)
- ❌ Vehículos aparecen y desaparecen entre frames
- ⚠️ Detecciones de objetos no deseados (clocks, trains, etc.)

### Causa Raíz
1. **Objetos pequeños** → Baja confianza de detección
2. **Vista aérea/drone** → Perspectiva diferente al entrenamiento de YOLO
3. **SORT tracker por defecto** → Configurado para objetos grandes y cercanos
4. **Sin filtro de confianza** → Acepta detecciones débiles

---

## 🔧 Nuevos Parámetros Agregados

### `--conf-threshold` (default: 0.3)
**Qué hace:** Filtra detecciones con baja confianza

```bash
# Más estricto (menos falsos positivos, puede perder autos pequeños)
--conf-threshold 0.5

# Más permisivo (detecta más autos pequeños, más ruido)
--conf-threshold 0.2

# Muy permisivo (para objetos muy pequeños)
--conf-threshold 0.15
```

**Recomendación para glorietas aéreas:** `0.2 - 0.25`

---

### `--max-age` (default: 30)
**Qué hace:** Cuántos frames mantener un track sin nuevas detecciones

```bash
# Tracking más estable (objetos pequeños que desaparecen temporalmente)
--max-age 40

# Tracking menos estable (solo objetos claramente visibles)
--max-age 15

# Muy estable (para objetos que se ocultan frecuentemente)
--max-age 60
```

**Por qué es importante:**
- Objetos pequeños pueden no detectarse en cada frame
- Vista aérea puede tener oclusiones (árboles, sombras)
- Mayor `max_age` = IDs más estables

**Recomendación para glorietas aéreas:** `30 - 50`

---

### `--iou-threshold` (default: 0.2)
**Qué hace:** Umbral de IoU para asociar detecciones con tracks existentes

```bash
# Más permisivo (mejor para objetos pequeños/distantes)
--iou-threshold 0.15

# Más estricto (objetos grandes y cercanos)
--iou-threshold 0.3
```

**Por qué bajarlo:**
- Objetos pequeños tienen bounding boxes pequeñas
- Pequeños movimientos = bajo IoU
- Valor bajo = mejor asociación de objetos pequeños

**Recomendación para glorietas aéreas:** `0.15 - 0.2`

---

### `--min-hits` (default: 2)
**Qué hace:** Detecciones consecutivas necesarias para confirmar un track

```bash
# Más sensible (detecta rápido pero más falsos positivos)
--min-hits 1

# Más conservador (menos falsos positivos pero más lento)
--min-hits 3
```

**Recomendación para glorietas aéreas:** `2` (balance)

---

## 📊 Configuraciones Recomendadas por Escenario

### 1. Vista Aérea Alta (Drone > 50m)
**Problema:** Autos muy pequeños (< 30x30 px)

```bash
python main.py --mode roundabout-test \
  --video assets/glorieta_caballos.mov \
  --conf-threshold 0.2 \
  --max-age 50 \
  --iou-threshold 0.15 \
  --min-hits 2
```

**Por qué:**
- `conf 0.2`: Acepta detecciones débiles de objetos pequeños
- `max-age 50`: Mantiene tracks aunque el auto no se detecte en algunos frames
- `iou 0.15`: Asocia mejor objetos pequeños con movimiento

---

### 2. Vista Aérea Media (Drone 20-50m)
**Problema:** Autos medianos, tracking inestable

```bash
python main.py --mode roundabout-test \
  --video assets/patria_acueducto.mp4 \
  --conf-threshold 0.25 \
  --max-age 35 \
  --iou-threshold 0.2 \
  --min-hits 2
```

---

### 3. Vista Frontal/Cámara de Tráfico (Modo Street)
**Problema:** Autos grandes, necesita precisión

```bash
python main.py --mode street \
  --video assets/test_2.mp4 \
  --conf-threshold 0.4 \
  --max-age 25 \
  --iou-threshold 0.3 \
  --min-hits 2
```

---

## 🧪 Proceso de Calibración

### Paso 1: Detectar si YOLO ve los autos
```bash
# Muy permisivo para ver TODO lo que detecta
python main.py --mode roundabout-test \
  --video TU_VIDEO.mp4 \
  --conf-threshold 0.15 \
  --min-hits 1
```

**Observar:**
- ¿Detecta los autos pequeños? → Sí: Subir conf a 0.2-0.25
- ¿Muchos falsos positivos? → Sí: Subir conf a 0.3-0.35
- ¿Detecta objetos raros (clocks, trains)? → Normal, se filtran después

---

### Paso 2: Estabilizar el tracking
```bash
# Una vez que detecta bien, estabilizar IDs
python main.py --mode roundabout-test \
  --video TU_VIDEO.mp4 \
  --conf-threshold 0.25 \
  --max-age 40 \
  --iou-threshold 0.15
```

**Observar en consola:**
```
🚗 Detected vehicle id=2 class=car at (648,657)
🚗 Detected vehicle id=3 class=car at (449,465)
# ... más frames ...
# ¿El id=2 sigue apareciendo o cambia a id=10?
```

**Si los IDs cambian mucho:**
- ↑ Aumentar `max-age` a 50-60
- ↓ Bajar `iou-threshold` a 0.1-0.15

---

### Paso 3: Reducir falsos positivos
```bash
# Ajustar finamente
python main.py --mode roundabout-test \
  --video TU_VIDEO.mp4 \
  --conf-threshold 0.3 \
  --max-age 45 \
  --iou-threshold 0.15 \
  --min-hits 3
```

**Si hay objetos estáticos detectados:**
- ↑ Aumentar `min-hits` a 3-4

---

## 🎬 Comparación de Modelos YOLO

### YOLOv8l vs YOLOv11l vs YOLOv11m

| Modelo | Tamaño | Velocidad | Precisión | Recomendación |
|--------|--------|-----------|-----------|---------------|
| **yolov8l** | ~80MB | ~300ms | Alta | ✅ Buena opción general |
| **yolov11l** | ~85MB | ~280ms | Muy Alta | ✅ **Mejor para objetos pequeños** |
| **yolov11m** | ~50MB | ~200ms | Media-Alta | ⚡ Más rápido, menos preciso |
| yolov8m | ~50MB | ~220ms | Media | ⚡ Alternativa rápida |
| yolov8s | ~22MB | ~150ms | Media-Baja | ❌ No recomendado para objetos pequeños |

**Recomendación:** 
- **YOLOv11l** para máxima precisión en objetos pequeños
- **YOLOv11m** si necesitas velocidad y los objetos no son tan pequeños

---

## 📈 Métricas de Calidad de Tracking

### En el video procesado (`result.mp4`):
1. **IDs estables:** Un auto debe mantener el mismo ID durante todo su recorrido
2. **Sin gaps:** No debe desaparecer y reaparecer con otro ID
3. **Cajas precisas:** Las cajas verdes deben ajustarse bien al vehículo

### En la consola:
```
🚗 Detected vehicle id=2 class=car at (648,657)
🚗 Detected vehicle id=3 class=car at (449,465)
...
# Buscar: ¿Los IDs son secuenciales (2,3,4,5) o saltan mucho (2,15,3,28)?
# IDs secuenciales = tracking estable ✅
# IDs que saltan = tracking inestable ❌
```

---

## 🚨 Problemas Comunes y Soluciones

### Problema: "Detecta clocks, trains, etc."
**Solución:** Ya está filtrado en el código. Solo cuenta: car, truck, bus, motorbike

### Problema: "Los autos pequeños no se detectan"
```bash
# Bajar confianza y ajustar tracker
--conf-threshold 0.15 --max-age 60 --iou-threshold 0.1
```

### Problema: "Demasiados falsos positivos"
```bash
# Subir confianza y min-hits
--conf-threshold 0.35 --min-hits 3
```

### Problema: "IDs cambian constantemente"
```bash
# Aumentar max-age y bajar iou
--max-age 50 --iou-threshold 0.15
```

### Problema: "Muy lento"
```bash
# Usar modelo más pequeño
model = YOLO("models/yolo/yolov11m.pt")
# o
model = YOLO("models/yolo/yolov8m.pt")
```

---

## 🎯 Configuración Óptima Inicial para Glorietas

Basado en tus pruebas, empieza con:

```bash
python main.py --mode roundabout-test \
  --video assets/glorieta_caballos.mov \
  --conf-threshold 0.25 \
  --max-age 40 \
  --iou-threshold 0.15 \
  --min-hits 2
```

Luego ajusta según observes en `result.mp4` y la consola.

---

## 📝 Notas Técnicas

### Filtro de Vehículos
El código ahora solo procesa:
```python
if vehicle_names in ["car", "truck", "bus", "motorbike"] and conf >= args.conf_threshold:
```

Esto elimina:
- ❌ person, bicycle, clock, train, etc.
- ❌ Detecciones con confianza < threshold

### Visualización en Pantalla
En modo `roundabout-test` ahora muestra:
```
Detected: 15 vehicles | Active: 8
conf>=0.25 | max_age=40 | iou<=0.15
```

Esto te permite ver los parámetros en tiempo real.

---

## 🔬 Próximos Pasos

1. **Probar configuración óptima** en tus 3 videos de glorieta
2. **Documentar qué configuración funciona mejor** para cada video
3. **Analizar `result.mp4`** para ver estabilidad de tracking
4. **Decidir si implementar conteo por zonas** una vez que el tracking sea estable

---

## 💡 Tips Finales

- **Siempre revisa `result.mp4`** antes de confiar en los números
- **Los parámetros son interdependientes:** Cambiar uno puede requerir ajustar otros
- **Empieza permisivo, luego restringe:** Es más fácil filtrar que recuperar detecciones perdidas
- **Documenta qué funciona:** Cada escenario puede necesitar configuración diferente
