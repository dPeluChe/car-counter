"""Constantes compartidas entre setup y main."""

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

VEHICLE_CLASSES = {"car", "truck", "bus", "motorbike"}
VEHICLE_CLASS_IDS = [2, 3, 5, 7]  # car, motorbike, bus, truck

PREVIEW_VEH_NAMES = {2: "car", 3: "moto", 5: "bus", 7: "truck"}

# Colores hex para Tkinter (setup)
ZONE_COLORS_HEX = [
    "#00FF88", "#FF6B6B", "#4ECDC4", "#FFE66D",
    "#A8E6CF", "#FF8B94", "#B8B8FF", "#FFA07A",
]

EXCL_COLORS_HEX = ["#FF5555", "#FF9500", "#FF6B6B", "#FAB387"]

# Colores RGB para OpenCV en espacio RGB (setup_panels usa RGB, no BGR)
ZONE_COLORS_RGB = [
    (0, 255, 136),    # verde
    (255, 107, 107),  # rojo-coral
    (78, 205, 196),   # cian
    (255, 230, 109),  # amarillo
    (168, 230, 207),  # verde menta
    (255, 139, 148),  # salmon
    (184, 184, 255),  # lavanda
    (255, 160, 122),  # azul claro
]

EXCL_COLORS_RGB = [
    (255, 85, 85),    # rojo
    (255, 149, 0),    # naranja
    (255, 107, 107),  # rojo claro
    (250, 179, 135),  # salmon
]

# Colores BGR para OpenCV (main)
ZONE_COLORS_BGR = [
    (136, 255, 0),    # verde
    (107, 107, 255),  # rojo-coral
    (205, 196, 78),   # cian
    (109, 230, 255),  # amarillo
    (207, 230, 168),  # verde menta
    (148, 139, 255),  # salmon
    (255, 184, 184),  # lavanda
    (122, 160, 255),  # azul claro
]
