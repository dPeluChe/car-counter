"""Constantes compartidas entre setup y main.

Los colores se importan desde theme.py (single source of truth).
"""

from carcounter.theme import (
    ZONE_COLORS_HEX, ZONE_COLORS_RGB, ZONE_COLORS_BGR,
    EXCL_COLORS_HEX, EXCL_COLORS_RGB,
)

COCO_NAMES = [
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
    "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa", "pottedplant", "bed",
    "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush",
]

# Grupos acordados con EPS (docs/GUIDES/COUNTING_SCOPE.md). Nombres COCO ("motorbike")
# y VisDrone ("motor", "van", "tricycle"); mototaxis (tricycle) cuentan como ligeros.
CLASS_GROUPS = {
    "ligeros": {"car", "van", "tricycle", "awning-tricycle"},
    "pesados": {"bus", "truck"},
    "dos_ruedas": {"motor", "motorbike", "motorcycle", "bicycle"},
}
VEHICLE_CLASSES = set().union(*CLASS_GROUPS.values())


def class_group(name):
    """Grupo EPS de una clase del modelo, o None si no se cuenta."""
    name = str(name).strip().lower()
    return next((group for group, members in CLASS_GROUPS.items() if name in members), None)


VEHICLE_CLASS_IDS = [2, 3, 5, 7]  # car, motorbike, bus, truck (COCO por defecto)

PREVIEW_VEH_NAMES = {2: "car", 3: "moto", 5: "bus", 7: "truck"}


def resolve_vehicle_classes(model):
    names = getattr(model, "names", None)
    if names is None:
        return VEHICLE_CLASS_IDS, COCO_NAMES
    items = names.items() if isinstance(names, dict) else enumerate(names)
    names = {int(i): str(name).strip().lower() for i, name in items}
    ids = [i for i, name in names.items() if name in VEHICLE_CLASSES]
    if not ids:
        raise ValueError("El modelo no contiene clases de vehículos reconocidas")
    return ids, names
