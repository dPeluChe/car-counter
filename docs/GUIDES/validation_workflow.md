# Validation Workflow — Medir precision real del pipeline

Esta guia describe el proceso end-to-end para medir que tan bien detecta
nuestro pipeline vs ground truth humano, usando LabelMe + SAM3 como herramienta
de anotacion.

**Objetivo:** pasar de "parece que funciona" a "sabemos que funciona al X%".

---

## Requisitos previos

- Modelo YOLO descargado en `models/yolo/yolov11l.pt` (o el que uses)
- Video de prueba en `assets/` (ej. `glorieta_fast.MP4`)
- [LabelMe v6.1+](https://labelme.io) instalado (herramienta externa, no dep de Python)

---

## Paso 1 — Extraer frames candidatos con dedup

```bash
python scripts/extract_validation_frames.py \
    --video assets/glorieta_fast.MP4 \
    --output-dir data/validation/frames \
    --n-candidates 200 \
    --hash-threshold 5
```

**Que hace:** Saca ~200 frames equidistantes del video. Aplica perceptual
hashing (DCT 64-bit) y descarta frames casi identicos. Resultado: ~50-80
frames realmente diferentes.

**Salida:** `data/validation/frames/frame_XXXX.jpg`

---

## Paso 2 — Pre-etiquetar con YOLO teacher

```bash
python scripts/pre_label_frames.py \
    --frames-dir data/validation/frames \
    --output-dir data/validation/annotations \
    --model models/yolo/yolov11l.pt \
    --conf 0.25
```

**Que hace:** Corre YOLO sobre cada frame y genera anotaciones LabelMe JSON
iniciales. El humano solo tiene que **corregir errores**, no anotar desde cero.

**Salida:** `data/validation/annotations/frame_XXXX.json`

---

## Paso 3 — Corregir anotaciones con LabelMe + SAM3

1. Abrir LabelMe
2. File -> Open Dir -> seleccionar `data/validation/frames/`
3. LabelMe cargara automaticamente los `.json` de `data/validation/annotations/`
   si estan al lado de los frames, o configurar "Change output dir" si los
   tienes separados
4. Para cada frame:
   - Eliminar detecciones falsas (FP del teacher)
   - Agregar vehiculos que el teacher no detecto (FN) usando SAM3 AI-Box mode
     ("arrastra un box, obtiene multiples shapes") para escenas densas
   - Ajustar boxes mal posicionados
5. Guardar (Ctrl+S)

**Tip:** Con SAM3 + AI-Box, anotar 50 frames de una glorieta toma ~30-45 min
en vez de 3-4 horas con bboxes manuales.

---

## Paso 4 — Evaluar el pipeline

```bash
python scripts/evaluate_pipeline.py \
    --frames-dir data/validation/frames \
    --annotations-dir data/validation/annotations \
    --model models/yolo/yolov11l.pt \
    --iou-threshold 0.5
```

**Salida esperada:**

```
Resultados globales (IoU threshold=0.5)
  Precision:          0.9234
  Recall:             0.8712
  F1:                 0.8965
  Counting accuracy:  0.9150
  TP / FP / FN:       234 / 19 / 35
  Predicciones / GT:  253 / 269

Por clase:
  clase               P        R       F1   pred     gt
  car             0.950   0.920   0.935    200    210
  motorcycle      0.700   0.600   0.645     20     25
  truck           0.875   0.750   0.808      8     10
```

---

## Interpretacion

| Counting accuracy | Que hacer |
|-------------------|-----------|
| > 95% | Pipeline excelente, no hay nada que optimizar en detection |
| 85-95% | Aceptable para la mayoria de casos, revisar por-clase si alguna es peor |
| 70-85% | Considerar ajustar `conf_threshold` o usar modelo mas grande (yolov11x) |
| < 70% | Fine-tuning con dataset custom seria rentable |

Si `recall` es bajo pero `precision` alta -> se pierden vehiculos
(bajar `conf_threshold` o usar SAHI con tiles mas pequeños).

Si `precision` es bajo pero `recall` alto -> demasiados FP
(subir `conf_threshold` o agregar zonas de exclusion).

---

## Referencias

- Perceptual hashing: https://github.com/simoncirstoiu/alice
- LabelMe v6.1: https://labelme.io/blog/labelme-v6.1
- SAM3 AI-Box: https://labelme.io/blog/labelme-v6.1
