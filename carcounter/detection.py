"""Pipeline de deteccion y tracking de vehiculos."""

from carcounter.constants import VEHICLE_CLASSES
from carcounter.geometry import apply_nms, validate_inference_roi
from carcounter.tracking import attach_classes_to_tracks


def detect_and_track(frame, *, model, sahi_model, sahi_predict_fn, sort_tracker,
                     use_sahi, effective_conf, imgsz, conf_for,
                     geo_constraints, exclusion_np,
                     sahi_slice_w, sahi_slice_h, sahi_overlap, sahi_nms_threshold,
                     device="cpu", detector_backend="yolo", rfdetr_model=None,
                     inference_roi=None, raw_detections=None, on_detections=None):
    """Ejecuta deteccion + tracking y retorna lista de (x1,y1,x2,y2,id,cls_name)."""
    if sort_tracker is None:
        raise RuntimeError("No hay tracker disponible; no se pueden asignar IDs persistentes")
    raw = raw_detections if raw_detections is not None else detect_objects(
        frame, model=model, sahi_model=sahi_model, sahi_predict_fn=sahi_predict_fn,
        use_sahi=use_sahi, effective_conf=effective_conf, imgsz=imgsz,
        sahi_slice_w=sahi_slice_w, sahi_slice_h=sahi_slice_h,
        sahi_overlap=sahi_overlap, sahi_nms_threshold=sahi_nms_threshold,
        device=device, detector_backend=detector_backend, rfdetr_model=rfdetr_model,
        inference_roi=inference_roi,
    )
    if on_detections is not None:
        on_detections(raw)
    from carcounter.detector import filter_detections
    detections, classes = filter_detections(raw, conf_for, geo_constraints, exclusion_np)
    if hasattr(sort_tracker, "update_detections"):
        return sort_tracker.update_detections(frame, detections, classes)
    return _track_with_sort(sort_tracker, detections, classes)


def _track_with_sort(sort_tracker, detections, det_classes):
    if sort_tracker is None:
        raise RuntimeError("No hay tracker disponible; no se pueden asignar IDs persistentes")
    sort_out = sort_tracker.update(detections)
    return attach_classes_to_tracks(sort_out, detections, det_classes)


def detect_objects(frame, *, model, effective_conf, imgsz, use_sahi=False,
                   sahi_model=None, sahi_predict_fn=None, sahi_slice_w=512,
                   sahi_slice_h=512, sahi_overlap=0.2, sahi_nms_threshold=0.3,
                   device="cpu", detector_backend="yolo", rfdetr_model=None,
                   inference_roi=None):
    from carcounter.detector import YOLODetector, SAHIDetector, RFDETRDetector

    offset_x = offset_y = 0
    if inference_roi is not None:
        height, width = frame.shape[:2]
        offset_x, offset_y, right, bottom = validate_inference_roi(inference_roi, width, height)
        frame = frame[offset_y:bottom, offset_x:right]
    if use_sahi:
        if sahi_model is None or sahi_predict_fn is None:
            raise RuntimeError("SAHI seleccionado pero no disponible")
        sahi_model.image_size = imgsz
        detector = SAHIDetector(sahi_model, sahi_predict_fn, sahi_slice_w,
                               sahi_slice_h, sahi_overlap, sahi_nms_threshold)
    elif detector_backend == "rfdetr":
        detector = RFDETRDetector(rfdetr_model)
    else:
        detector = YOLODetector(model, imgsz, device)
    raw = detector.infer(frame, effective_conf)
    raw = [d for d in raw if d["cls_name"] in VEHICLE_CLASSES and d["conf"] >= effective_conf]
    if use_sahi and sahi_nms_threshold > 0 and raw:
        rows, classes = apply_nms([list(d["bbox"]) + [d["conf"]] for d in raw],
                                  [d["cls_name"] for d in raw], sahi_nms_threshold)
        raw = [dict(bbox=row[:4], conf=float(row[4]), cls_name=name)
               for row, name in zip(rows, classes)]
    return [dict(d, bbox=(int(d["bbox"][0]) + offset_x, int(d["bbox"][1]) + offset_y,
                         int(d["bbox"][2]) + offset_x, int(d["bbox"][3]) + offset_y))
            for d in raw]
