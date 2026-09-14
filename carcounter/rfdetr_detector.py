"""RF-DETR detector wrapper compatible con el pipeline de carcounter.

RF-DETR (Roboflow) usa un backbone transformer DINOv2. Su exactitud en este
material no está medida localmente.

Requiere: pip install rfdetr
"""

import numpy as np
import cv2

from carcounter.constants import VEHICLE_CLASSES

_RFDETR_AVAILABLE = False
try:
    import rfdetr as _rfdetr_module
    from PIL import Image
    _RFDETR_AVAILABLE = True
except ImportError:
    pass

# Mapeo de tamaños a clases RF-DETR
_VARIANT_MAP = {
    "nano": "RFDETRNano",
    "small": "RFDETRSmall",
    "medium": "RFDETRMedium",
    "base": "RFDETRBase",
    "large": "RFDETRLarge",
}


def is_rfdetr_available():
    return _RFDETR_AVAILABLE


def load_rfdetr_model(variant="base", weights=None, device="cpu"):
    """Carga un modelo RF-DETR.

    Args:
        variant: "nano", "small", "medium", "base", "large"
        weights: Path a checkpoint custom, o None para pretrained COCO
        device: "cpu", "cuda", "mps"

    Returns:
        Instancia RF-DETR lista para predict()
    """
    if not _RFDETR_AVAILABLE:
        raise ImportError("RF-DETR requiere: pip install rfdetr")

    cls_name = _VARIANT_MAP.get(variant, "RFDETRBase")
    model_cls = getattr(_rfdetr_module, cls_name, None)
    if model_cls is None:
        raise ValueError(f"RF-DETR variant '{variant}' not found. Options: {list(_VARIANT_MAP.keys())}")

    kwargs = {}
    if weights:
        kwargs["pretrain_weights"] = weights

    model = model_cls(**kwargs)
    return model


def rfdetr_class_names(model):
    """Mapa id -> nombre para los class_id que devuelve model.predict()."""
    # Checkpoint COCO: ids crudos de categoría (base 1, con huecos). Checkpoint propio: índices base 0.
    custom = getattr(getattr(model, "model", None), "class_names", None)
    if custom is not None:
        return {i: str(name).strip().lower() for i, name in enumerate(custom)}
    from rfdetr.util.coco_classes import COCO_CLASSES
    return {int(i): str(name).strip().lower() for i, name in COCO_CLASSES.items()}


def rfdetr_detect(model, frame_bgr, conf_threshold=0.1):
    """Ejecuta deteccion RF-DETR sobre un frame BGR de OpenCV.

    Args:
        model: Instancia RF-DETR
        frame_bgr: numpy array BGR (OpenCV)
        conf_threshold: umbral de confianza

    Returns:
        (detections, det_classes) donde:
        - detections: np.array (N,5) [x1,y1,x2,y2,conf]
        - det_classes: list[str] nombres de clase del checkpoint
    """
    # RF-DETR necesita PIL Image (RGB)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(frame_rgb)

    sv_dets = model.predict(pil_img, threshold=conf_threshold)

    if sv_dets is None or len(sv_dets) == 0:
        return np.empty((0, 5)), []

    # Vectorized vehicle filter
    cls_ids = sv_dets.class_id
    names = rfdetr_class_names(model)
    cls_names = [names.get(int(c), "") for c in cls_ids]
    keep = [i for i, n in enumerate(cls_names) if n in VEHICLE_CLASSES]

    if not keep:
        return np.empty((0, 5)), []

    xyxy = sv_dets.xyxy[keep].astype(np.int32)
    confs = sv_dets.confidence[keep].reshape(-1, 1)
    detections = np.hstack([xyxy, confs]).astype(np.float64)
    det_classes = [cls_names[i] for i in keep]
    return detections, det_classes
