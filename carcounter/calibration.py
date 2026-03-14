"""Logica de calibracion y deteccion para el configurador."""

import cv2
import numpy as np
from carcounter.constants import COCO_NAMES, VEHICLE_CLASSES, VEHICLE_CLASS_IDS
from carcounter.geometry import bbox_iou, passes_geometry_filter, in_exclusion_zone


# Constantes de calibracion
CALIB_MIN_CONTEXT_PX = 24
CALIB_CONTEXT_RATIO = 0.75
CALIB_TARGET_BOX_SIDE = 160
CALIB_MAX_UPSCALE = 4.0


def get_calibration_roi(selected_box, img_w, img_h):
    """Calcula la ROI con contexto alrededor del recuadro seleccionado."""
    box_w = max(1, selected_box[2] - selected_box[0])
    box_h = max(1, selected_box[3] - selected_box[1])
    pad_x = max(CALIB_MIN_CONTEXT_PX, int(box_w * CALIB_CONTEXT_RATIO))
    pad_y = max(CALIB_MIN_CONTEXT_PX, int(box_h * CALIB_CONTEXT_RATIO))
    return (
        max(0, selected_box[0] - pad_x),
        max(0, selected_box[1] - pad_y),
        min(img_w, selected_box[2] + pad_x),
        min(img_h, selected_box[3] + pad_y),
    )


def get_calibration_scale(selected_box):
    """Calcula factor de escala para reescalar el recorte de calibracion."""
    box_w = max(1, selected_box[2] - selected_box[0])
    box_h = max(1, selected_box[3] - selected_box[1])
    min_side = max(1, min(box_w, box_h))
    scale = CALIB_TARGET_BOX_SIDE / float(min_side)
    return max(1.0, min(CALIB_MAX_UPSCALE, scale))


def compute_sample_constraints(vehicle_samples, loaded_constraints=None):
    """Calcula constraints geometricos a partir de muestras de vehiculos."""
    if not vehicle_samples:
        return loaded_constraints
    widths = [s["width"] for s in vehicle_samples]
    heights = [s["height"] for s in vehicle_samples]
    areas = [s["area"] for s in vehicle_samples]
    aspects = [s["aspect"] for s in vehicle_samples]
    return {
        "min_width": max(1, int(min(widths) * 0.70)),
        "max_width": int(max(widths) * 1.45),
        "min_height": max(1, int(min(heights) * 0.70)),
        "max_height": int(max(heights) * 1.45),
        "min_area": max(1, int(min(areas) * 0.55)),
        "max_area": int(max(areas) * 1.55),
        "min_aspect": max(0.20, min(aspects) * 0.70),
        "max_aspect": min(6.0, max(aspects) * 1.30),
    }


def passes_sample_constraints(bbox, constraints):
    """Valida un bbox contra los constraints de muestras."""
    if constraints is None:
        return True
    return passes_geometry_filter(bbox[0], bbox[1], bbox[2], bbox[3], constraints)


def predict_roi_boxes(roi_frame, conf, scale, model, sahi_model=None,
                      use_sahi=False, force_imgsz=None):
    """Ejecuta deteccion YOLO o SAHI sobre un ROI reescalado."""
    scaled_w = max(1, int(roi_frame.shape[1] * scale))
    scaled_h = max(1, int(roi_frame.shape[0] * scale))
    scaled_frame = cv2.resize(roi_frame, (scaled_w, scaled_h),
                              interpolation=cv2.INTER_CUBIC)
    detections = []

    if use_sahi:
        if sahi_model is None:
            return [], "sahi_unavailable"
        from sahi.predict import get_sliced_prediction
        result = get_sliced_prediction(
            scaled_frame, sahi_model,
            slice_height=min(512, scaled_h),
            slice_width=min(512, scaled_w),
            overlap_height_ratio=0.2,
            overlap_width_ratio=0.2,
            postprocess_type="NMS",
            postprocess_match_threshold=0.5,
            postprocess_match_metric="IOS",
            verbose=0,
        )
        for pred in result.object_prediction_list:
            cls_name = pred.category.name
            if cls_name not in VEHICLE_CLASSES:
                continue
            bbox = pred.bbox
            detections.append({
                "bbox": (
                    int(bbox.minx / scale), int(bbox.miny / scale),
                    int(bbox.maxx / scale), int(bbox.maxy / scale),
                ),
                "cls_name": cls_name,
                "conf": float(pred.score.value),
            })
        return detections, "sahi"

    results = model(
        scaled_frame, conf=conf, verbose=False,
        classes=VEHICLE_CLASS_IDS,
        imgsz=force_imgsz or max(640, max(scaled_w, scaled_h)),
    )
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls_id = int(box.cls[0])
            cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else "?"
            if cls_name not in VEHICLE_CLASSES:
                continue
            detections.append({
                "bbox": (
                    int(x1 / scale), int(y1 / scale),
                    int(x2 / scale), int(y2 / scale),
                ),
                "cls_name": cls_name,
                "conf": float(box.conf[0]),
            })
    return detections, "yolo-upscaled"


def draw_detection_overlay(frame_orig, detections, constraints=None,
                           exclusion_zones=None, frame_origin=(0, 0),
                           frame_base=None, highlight_box=None):
    """Dibuja detecciones sobre un frame con colores segun filtros."""
    display = frame_orig.copy() if frame_base is None else frame_base.copy()
    excl_np = {}
    if exclusion_zones:
        excl_np = {n: np.array(pts, dtype=np.int32)
                   for n, pts in exclusion_zones.items()}

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        x1 += frame_origin[0]
        x2 += frame_origin[0]
        y1 += frame_origin[1]
        y2 += frame_origin[1]
        area = max(0, (x2 - x1) * (y2 - y1))
        color = (90, 130, 255)
        thickness = 2
        if not passes_sample_constraints((x1, y1, x2, y2), constraints):
            color = (70, 70, 180)
            thickness = 1
        if highlight_box:
            overlap_iou = bbox_iou((x1, y1, x2, y2), highlight_box)
            if overlap_iou >= 0.10:
                color = (0, 255, 80)
                thickness = 3
        cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
        cv2.putText(display, f"{det['cls_name']} {det['conf']:.2f} ({area}px²)",
                    (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return display
