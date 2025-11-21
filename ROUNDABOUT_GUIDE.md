# 🎯 Guía de Uso: Modo Glorieta

## Descripción

El modo `roundabout-test` permite **detectar y rastrear vehículos** en videos de glorietas sin contar entradas/salidas. Es ideal para:

- ✅ Verificar que YOLO detecta vehículos desde vistas altas
- ✅ Ver si los autos pequeños son detectados correctamente
- ✅ Observar las trayectorias de los vehículos
- ✅ Identificar zonas problemáticas antes de implementar conteo

## Uso Básico

```bash
# Activar entorno virtual
source env/bin/activate

# Ejecutar en modo glorieta (configuración básica)
python main.py --mode roundabout-test --video assets/glorieta_normal.mp4

# Ejecutar con optimización para objetos pequeños (RECOMENDADO)
python main.py --mode roundabout-test \
  --video assets/glorieta_caballos.mov \
  --conf-threshold 0.25 \
  --max-age 40 \
  --iou-threshold 0.15
```

## Parámetros Disponibles

### Modo Glorieta (Nuevos Parámetros Optimizados)
```bash
--mode roundabout-test              # Modo de detección sin conteo
--video assets/glorieta_normal.mp4  # Video de entrada
--conf-threshold 0.25               # Umbral de confianza (0.15-0.5)
--max-age 40                        # Frames sin detección antes de eliminar track
--iou-threshold 0.15                # Umbral IoU para asociar detecciones
--min-hits 2                        # Mínimo de detecciones para confirmar vehículo
```

**⚠️ IMPORTANTE:** Para vistas aéreas con objetos pequeños, usa los parámetros optimizados.
Ver `OPTIMIZATION_GUIDE.md` para detalles completos.

### Modo Calle (Normal)
```bash
--mode street                   # Modo normal con líneas de conteo
--video assets/test_2.mp4       # Video de entrada
--directions 1                  # 1 o 2 direcciones
--line-y 0.5                    # Posición de línea (0.0-1.0)
--tol 10                        # Tolerancia de píxeles
```

## Diferencias entre Modos

| Característica | `street` | `roundabout-test` |
|---------------|----------|-------------------|
| Líneas de conteo | ✅ Sí | ❌ No |
| Tracking de vehículos | ✅ Sí | ✅ Sí |
| Conteo por dirección | ✅ Sí | ❌ No |
| Gráficos overlay | ✅ Sí | ❌ No |
| Info en pantalla | Contadores | Detectados/Activos |
| Cajas de detección | Moradas | **Verdes** |

## Salida del Modo Glorieta

### Durante la ejecución:
- **Ventana de video** con:
  - Cajas verdes alrededor de vehículos detectados
  - ID de cada vehículo
  - Punto central de tracking (morado)
  - Texto superior: "Detected: X vehicles | Active: Y"

### En consola:
```
🚗 Detected vehicle id=2 class=truck at (568,1046)
🚗 Detected vehicle id=3 class=car at (532,679)
...
```

### Al finalizar:
```
===== SUMMARY =====
Mode: roundabout-test
Video: assets/glorieta_normal.mp4

🚗 Total vehicles detected: 15

Vehicle types detected:
  car: 8
  truck: 5
  motorbike: 2
```

## Archivos Generados

- `result.mp4` - Video procesado con detecciones visualizadas

## Próximos Pasos

Una vez verificado que detecta bien los vehículos:

1. **Analizar trayectorias** - Observar por dónde se mueven los autos
2. **Identificar entradas/salidas** - Marcar las calles de la glorieta
3. **Definir zonas de conteo** - Decidir dónde poner líneas o polígonos
4. **Implementar conteo multi-dirección** - Crear modo `roundabout` completo

## Ajustes Recomendados

### Si los autos pequeños no se detectan:
```bash
# Bajar confianza y aumentar max-age
python main.py --mode roundabout-test \
  --video assets/glorieta_normal.mp4 \
  --conf-threshold 0.2 \
  --max-age 50 \
  --iou-threshold 0.15 \
  --min-hits 1
```

### Si hay muchas detecciones falsas:
```bash
# Aumentar confianza y min-hits
python main.py --mode roundabout-test \
  --video assets/glorieta_normal.mp4 \
  --conf-threshold 0.35 \
  --min-hits 3
```

### Si los IDs cambian constantemente:
```bash
# Aumentar max-age y bajar iou-threshold
python main.py --mode roundabout-test \
  --video assets/glorieta_normal.mp4 \
  --conf-threshold 0.25 \
  --max-age 60 \
  --iou-threshold 0.1
```

## Notas Técnicas

- **Modelo**: YOLOv8l (large) - Buena precisión para objetos pequeños
- **Tracker**: SORT algorithm - Mantiene IDs consistentes
- **Clases detectadas**: car, truck, bus, motorbike
- **Máscara**: Usa `assets/mask.png` si existe (para filtrar zonas)

## Troubleshooting

### Error: "No module named 'ultralytics'"
```bash
source env/bin/activate
pip install -r requirements.txt
```

### Video no se abre
Verificar que el archivo existe:
```bash
ls -lh assets/glorieta_normal.mp4
```

### Detección muy lenta
- Usar un modelo más pequeño: `yolov8m.pt` o `yolov8s.pt`
- Reducir resolución del video
