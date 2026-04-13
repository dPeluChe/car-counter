"""Abstract detector interface for plug-and-play detection backends.

Soporta YOLO, RF-DETR y SAHI como backends intercambiables.
Para agregar un detector nuevo, solo hay que heredar de Detector
e implementar infer().
"""

from abc import ABC, abstractmethod
import numpy as np
from carcounter.constants import COCO_NAMES, VEHICLE_CLASSES, VEHICLE_CLASS_IDS
from carcounter.geometry import apply_nms, passes_geometry_filter, in_exclusion_zone
from carcounter.logging_config import get_logger

log = get_logger("detector")


class Detector(ABC):
    """Interfaz abstracta para backends de deteccion.

    Subclasses deben implementar infer() que retorna detecciones crudas.
    La logica de filtrado (clase, confianza, geometria, exclusion) es comun.
    """

    @abstractmethod
    def infer(self, frame, conf_threshold, **kwargs):
        """Ejecuta inferencia sobre un frame.

        Args:
            frame: numpy array BGR (OpenCV)
            conf_threshold: umbral de confianza minimo

        Returns:
            list[dict]: Lista de detecciones, cada una con:
                - bbox: (x1, y1, x2, y2)
                - cls_name: str (nombre COCO)
                - conf: float
        """
        ...

    def detect(self, frame, conf_threshold, conf_for, geo_constraints,
               exclusion_np, **kwargs):
        """Detecta y filtra vehiculos. Wrapper sobre infer().

        Returns:
            (detections_np, det_classes): numpy array (N,5) y lista de nombres
        """
        raw = self.infer(frame, conf_threshold, **kwargs)
        det_list = []
        det_classes = []
        for det in raw:
            x1, y1, x2, y2 = det["bbox"]
            cls_name = det["cls_name"]
            conf_val = det["conf"]

            if cls_name not in VEHICLE_CLASSES:
                continue
            if conf_val < conf_for(cls_name):
                continue
            if not passes_geometry_filter(x1, y1, x2, y2, geo_constraints):
                continue
            if in_exclusion_zone((x1 + x2) / 2, (y1 + y2) / 2, exclusion_np):
                continue

            det_list.append([x1, y1, x2, y2, conf_val])
            det_classes.append(cls_name)

        detections = np.array(det_list) if det_list else np.empty((0, 5))
        return detections, det_classes


class YOLODetector(Detector):
    """Detector basado en Ultralytics YOLO."""

    def __init__(self, model, imgsz=1600, device="cpu"):
        self.model = model
        self.imgsz = imgsz
        self.device = device

    def infer(self, frame, conf_threshold, **kwargs):
        imgsz = kwargs.get("imgsz", self.imgsz)
        device = kwargs.get("device", self.device)
        results = self.model(
            frame, conf=conf_threshold, verbose=False,
            classes=VEHICLE_CLASS_IDS, imgsz=imgsz, device=device,
        )
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else ""
                conf_val = float(box.conf[0])
                detections.append({
                    "bbox": (x1, y1, x2, y2),
                    "cls_name": cls_name,
                    "conf": conf_val,
                })
        return detections

    def track(self, frame, conf_threshold, tracker_yaml, **kwargs):
        """YOLO native tracking (ByteTrack/BoT-SORT)."""
        imgsz = kwargs.get("imgsz", self.imgsz)
        device = kwargs.get("device", self.device)
        track_results = self.model.track(
            frame, conf=conf_threshold, imgsz=imgsz,
            tracker=tracker_yaml, persist=True, verbose=False,
            classes=VEHICLE_CLASS_IDS, device=device,
        )
        tracked = []
        if track_results and track_results[0].boxes is not None:
            for box in track_results[0].boxes:
                if box.id is None:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                tid = int(box.id[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else "car"
                conf_val = float(box.conf[0])
                tracked.append({
                    "bbox": (x1, y1, x2, y2),
                    "cls_name": cls_name,
                    "conf": conf_val,
                    "track_id": tid,
                })
        return tracked


class RFDETRDetector(Detector):
    """Detector basado en RF-DETR (Roboflow)."""

    def __init__(self, model):
        self.model = model

    def infer(self, frame, conf_threshold, **kwargs):
        from carcounter.rfdetr_detector import rfdetr_detect
        raw_dets, raw_classes = rfdetr_detect(
            self.model, frame, conf_threshold=conf_threshold,
        )
        detections = []
        for i in range(len(raw_dets)):
            x1, y1, x2, y2 = map(int, raw_dets[i, :4])
            conf_val = float(raw_dets[i, 4])
            detections.append({
                "bbox": (x1, y1, x2, y2),
                "cls_name": raw_classes[i],
                "conf": conf_val,
            })
        return detections


class SAHIDetector(Detector):
    """Detector con SAHI tiling sobre cualquier modelo base."""

    def __init__(self, sahi_model, sahi_predict_fn,
                 slice_w=512, slice_h=512, overlap=0.2, nms_threshold=0.3):
        self.sahi_model = sahi_model
        self.sahi_predict_fn = sahi_predict_fn
        self.slice_w = slice_w
        self.slice_h = slice_h
        self.overlap = overlap
        self.nms_threshold = nms_threshold

    def infer(self, frame, conf_threshold, **kwargs):
        result = self.sahi_predict_fn(
            frame, self.sahi_model,
            slice_height=self.slice_h, slice_width=self.slice_w,
            overlap_height_ratio=self.overlap, overlap_width_ratio=self.overlap,
            postprocess_type="NMS", postprocess_match_threshold=0.5,
            postprocess_match_metric="IOS", verbose=0,
        )
        detections = []
        for pred in result.object_prediction_list:
            bbox = pred.bbox
            detections.append({
                "bbox": (int(bbox.minx), int(bbox.miny),
                         int(bbox.maxx), int(bbox.maxy)),
                "cls_name": pred.category.name,
                "conf": pred.score.value,
            })
        return detections

    def detect(self, frame, conf_threshold, conf_for, geo_constraints,
               exclusion_np, **kwargs):
        """Override para aplicar NMS post-SAHI."""
        detections, det_classes = super().detect(
            frame, conf_threshold, conf_for, geo_constraints,
            exclusion_np, **kwargs,
        )
        if self.nms_threshold > 0 and len(detections) > 0:
            det_list = detections.tolist()
            det_list, det_classes = apply_nms(det_list, det_classes, self.nms_threshold)
            detections = np.array(det_list) if det_list else np.empty((0, 5))
        return detections, det_classes
