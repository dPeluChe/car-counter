# Validación de detección contra cajas humanas

Este procedimiento mide detección por imagen con el perfil real. No mide continuidad de IDs ni rutas: para eso usa [ROUTE_VALIDATION.md](ROUTE_VALIDATION.md). Los requisitos del dataset y su procedencia están en TODO-028 de [TASK_TODO.md](../TASK_TODO.md).

## Preparar una muestra separada

Desde `labs-eps-carcounter`, crea un directorio nuevo. Mantener imágenes y JSON juntos permite que `imagePath` encuentre el archivo por su nombre:

```bash
mkdir -p data/validation
CARCOUNTER_DATASET_DIR=$(mktemp -d "$PWD/data/validation/manual.XXXXXX")
env/bin/python scripts/extract_validation_frames.py \
  --video assets/glorieta_test1min.mp4 \
  --output-dir "$CARCOUNTER_DATASET_DIR" \
  --n-candidates 200 --hash-threshold 5
```

El extractor recorre el video completo y deduplica imágenes. No garantiza obtener 50/80/200 imágenes útiles ni muestrea únicamente los primeros 300 frames. Revisa variedad de escenas; el número de candidatos es aproximado. Repetirlo en la misma carpeta puede sobrescribir JPG: usa una carpeta nueva.

**Límite actual:** `frame_0000.jpg` identifica el orden de exportación, no el frame original. El script no guarda un manifiesto con tiempo/hash/índice de origen. Registra video y comando de extracción; no derives referencias temporales de rutas a partir del nombre. Para evidencia temporal usa el video original y registra explícitamente su frame. La incorporación del manifiesto está pendiente.

## Preetiquetas opcionales

```bash
env/bin/python scripts/pre_label_frames.py \
  --frames-dir "$CARCOUNTER_DATASET_DIR" \
  --output-dir "$CARCOUNTER_DATASET_DIR" \
  --model models/yolo/yolov8l-visdrone.pt --conf 0.10 --imgsz 640
```

El script propone cajas en la imagen completa, no aplica la ROI ni todos los filtros del perfil de producción. Es asistencia para anotar, no un benchmark del perfil. Conserva JSON existentes y genera nuevos archivos con `flags.reviewed=false`.

La confianza baja puede añadir muchas cajas falsas. Corrige también los autos que el modelo omitió; no basta borrar algunas cajas. No se garantiza ahorro de tiempo ni precisión por usar preetiquetas.

## Revisión en el editor

Abre imágenes y JSON en LabelMe o un editor compatible. La interfaz y las funciones opcionales de asistencia deben comprobarse en tu escritorio; no se asume una versión o automatización específica.

- Usa **rectángulos** con clase y dos esquinas. El parser actual solo acepta `shape_type=rectangle`; ignora polígonos y máscaras. No marques una imagen como revisada si sus vehículos quedaron únicamente en esos formatos.
- Corrige posición, clase, omisiones y duplicaciones; registra también imágenes sin vehículos del alcance.
- Mantén `imagePath` apuntando al JPG/PNG correspondiente. No agregues resultados de evaluación ni otros JSON ajenos a la carpeta de anotaciones.
- Usa clases acordadas del modelo; no interpretes IDs de VisDrone como IDs COCO. Los alias `motor`, `motorbike` y `motorcycle` se normalizan a `motorcycle` al evaluar.
- Marca el booleano `flags.reviewed=true` solo tras revisión humana completa de esa imagen. Si el editor no expone ese flag, edita el JSON después de revisar; no uses una conversión masiva de todos los archivos.

Separa imágenes utilizadas para ajustar parámetros de las que se reservarán para aceptar la mejora. La deduplicación por imagen no garantiza por sí sola independencia entre tramos.

## Evaluar el perfil real

```bash
mkdir -p "$CARCOUNTER_DATASET_DIR/evaluation"
env/bin/python scripts/evaluate_pipeline.py \
  --config docs/GUIDES/aerial_counting.example.json \
  --frames-dir "$CARCOUNTER_DATASET_DIR" \
  --annotations-dir "$CARCOUNTER_DATASET_DIR" \
  --iou-threshold 0.5 --device cpu \
  --output-json "$CARCOUNTER_DATASET_DIR/evaluation/report.json"
```

Usa una ruta nueva para cada reporte. Si evalúas otra copia de perfil, cambia `--config` y registra la ruta. El script actual evalúa YOLO y SAHI con su perfil; no tiene un argumento para evaluación RF-DETR. No declares evaluado ese backend mediante este comando.

El evaluador exige referencias revisadas, imágenes presentes y nombres no duplicados. Evalúa vehículos cuyo centro pertenece a la ROI y no cae en exclusiones. No elimina de la referencia los vehículos reales que un filtro geométrico equivocadamente descarta.

## Interpretar resultados

Informa TP/FP/FN y precisión/recall/F1 por clase, además de localización sin clase y error de cantidad por imagen. Una clase incorrecta genera un falso positivo y un falso negativo en la evaluación por clase, aunque la caja localice bien el auto. Los errores de cantidad se suman por imagen para evitar compensaciones entre frames.

No hay un porcentaje humano de referencia aprobado todavía. No se incluyen aquí salidas numéricas ficticias. Acordar umbrales por clase y contexto antes de escoger parámetros; un buen total global puede ocultar omisiones de autos pequeños o errores en una ruta concreta.

Una imagen con `reviewed=true` solo acredita la declaración del revisor, no prueba que haya sido revisada de forma correcta. Conserva responsable, fecha, alcance y anotaciones para poder auditar el resultado.
