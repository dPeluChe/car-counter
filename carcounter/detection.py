"""Pipeline de deteccion y tracking de vehiculos."""

import numpy as np
from carcounter.constants import COCO_NAMES, VEHICLE_CLASSES, VEHICLE_CLASS_IDS
from carcounter.geometry import apply_nms, passes_geometry_filter, in_exclusion_zone
from carcounter.tracking import attach_classes_to_tracks


def _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
    """Valida una deteccion contra clase, confianza, geometria y exclusion."""
    if cls_name not in VEHICLE_CLASSES:
        return False
    if conf_val < conf_for(cls_name):
        return False
    if not passes_geometry_filter(x1, y1, x2, y2, geo_constraints):
        return False
    if in_exclusion_zone((x1 + x2) / 2, (y1 + y2) / 2, exclusion_np):
        return False
    return True


def detect_and_track(frame, *, model, sahi_model, sahi_predict_fn, sort_tracker,
                     use_sahi, tracker_backend, tracker_yaml,
                     effective_conf, imgsz, conf_for,
                     geo_constraints, exclusion_np,
                     sahi_slice_w, sahi_slice_h, sahi_overlap, sahi_nms_threshold,
                     device="cpu"):
    """Ejecuta deteccion + tracking y retorna lista de (x1,y1,x2,y2,id,cls_name)."""

    detections = np.empty((0, 5))
    det_classes = []
    tracked_boxes = []

    if use_sahi and sahi_model is not None:
        # -- SAHI path --
        result = sahi_predict_fn(
            frame, sahi_model,
            slice_height=sahi_slice_h, slice_width=sahi_slice_w,
            overlap_height_ratio=sahi_overlap, overlap_width_ratio=sahi_overlap,
            postprocess_type="NMS", postprocess_match_threshold=0.5,
            postprocess_match_metric="IOS", verbose=0,
        )
        det_list = []
        for pred in result.object_prediction_list:
            bbox = pred.bbox
            cls_name = pred.category.name
            conf_val = pred.score.value
            x1, y1, x2, y2 = int(bbox.minx), int(bbox.miny), int(bbox.maxx), int(bbox.maxy)
            if not _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
                continue
            det_list.append([x1, y1, x2, y2, conf_val])
            det_classes.append(cls_name)
        if sahi_nms_threshold > 0 and det_list:
            det_list, det_classes = apply_nms(det_list, det_classes, sahi_nms_threshold)
        detections = np.array(det_list) if det_list else np.empty((0, 5))

        # SAHI usa SORT para tracking
        tracked_boxes = _track_with_sort(sort_tracker, detections, det_classes)

    elif tracker_backend in ("sort", "ocsort"):
        # -- SORT path --
        results = model(frame, conf=effective_conf, verbose=False,
                        classes=VEHICLE_CLASS_IDS, imgsz=imgsz, device=device)
        det_list = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else ""
                conf_val = float(box.conf[0])
                if not _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
                    continue
                det_list.append([x1, y1, x2, y2, conf_val])
                det_classes.append(cls_name)
        detections = np.array(det_list) if det_list else np.empty((0, 5))

        tracked_boxes = _track_with_sort(sort_tracker, detections, det_classes)

    else:
        # -- ByteTrack/BoT-SORT nativo --
        track_results = model.track(
            frame, conf=effective_conf, imgsz=imgsz,
            tracker=tracker_yaml, persist=True, verbose=False,
            classes=VEHICLE_CLASS_IDS, device=device,
        )
        if track_results and track_results[0].boxes is not None:
            for box in track_results[0].boxes:
                if box.id is None:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                tid = int(box.id[0])
                cls_id = int(box.cls[0])
                cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else "car"
                conf_val = float(box.conf[0])
                if not _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
                    continue
                tracked_boxes.append((x1, y1, x2, y2, tid, cls_name))

    return tracked_boxes


def _track_with_sort(sort_tracker, detections, det_classes):
    """Aplica SORT tracker o genera IDs sinteticos como fallback."""
    if sort_tracker is not None:
        sort_out = sort_tracker.update(detections)
        return attach_classes_to_tracks(sort_out, detections, det_classes)
    tracked = []
    for i, det in enumerate(detections):
        x1, y1, x2, y2, _ = map(int, det)
        cls = det_classes[i] if i < len(det_classes) else "car"
        tracked.append((x1, y1, x2, y2, i + 1, cls))
    return tracked
