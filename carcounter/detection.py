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
                     device="cpu", detector_backend="yolo", rfdetr_model=None,
                     vehicle_class_ids=None, class_names=None, inference_roi=None,
                     raw_detections=None, on_detections=None):
    """Ejecuta deteccion + tracking y retorna lista de (x1,y1,x2,y2,id,cls_name)."""

    if sort_tracker is not None or raw_detections is not None or on_detections is not None:
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

    # Agnostico al esquema de clases: usa los ids/nombres del modelo cargado
    # (COCO o VisDrone). Cae a COCO si no se proveen.
    offset_x = offset_y = 0
    if inference_roi is not None:
        if len(inference_roi) != 4 or any(type(v) is not int for v in inference_roi):
            raise ValueError("inference_roi requiere [x1, y1, x2, y2] enteros")
        offset_x, offset_y, right, bottom = inference_roi
        height, width = frame.shape[:2]
        if not (0 <= offset_x < right <= width and 0 <= offset_y < bottom <= height):
            raise ValueError("inference_roi debe estar dentro del video y tener area positiva")
        frame = frame[offset_y:bottom, offset_x:right]
        exclusion_np = {name: pts - np.array([offset_x, offset_y], dtype=np.int32)
                        for name, pts in exclusion_np.items()}

    if vehicle_class_ids is None:
        vehicle_class_ids = VEHICLE_CLASS_IDS
    if class_names is None:
        class_names = COCO_NAMES

    def _name_of(cls_id):
        try:
            return class_names[cls_id]
        except (KeyError, IndexError):
            return ""

    detections = np.empty((0, 5))
    det_classes = []
    tracked_boxes = []

    if use_sahi and sahi_model is not None:
        # -- SAHI path (YOLO o RF-DETR via adapter) --
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

        tracked_boxes = _track_with_sort(sort_tracker, detections, det_classes)

    elif detector_backend == "rfdetr" and rfdetr_model is not None:
        # -- RF-DETR path (siempre usa SORT/OC-SORT para tracking) --
        from carcounter.rfdetr_detector import rfdetr_detect
        raw_dets, raw_classes = rfdetr_detect(rfdetr_model, frame, conf_threshold=effective_conf)

        det_list = []
        filtered_classes = []
        for i in range(len(raw_dets)):
            x1, y1, x2, y2 = map(int, raw_dets[i, :4])
            conf_val = float(raw_dets[i, 4])
            cls_name = raw_classes[i]
            if not _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
                continue
            det_list.append([x1, y1, x2, y2, conf_val])
            filtered_classes.append(cls_name)
        detections = np.array(det_list) if det_list else np.empty((0, 5))
        det_classes = filtered_classes

        tracked_boxes = _track_with_sort(sort_tracker, detections, det_classes)

    elif tracker_backend in ("sort", "ocsort"):
        # -- YOLO + SORT/OC-SORT path --
        results = model(frame, conf=effective_conf, verbose=False,
                        classes=vehicle_class_ids, imgsz=imgsz, device=device)
        det_list = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                cls_name = _name_of(cls_id)
                conf_val = float(box.conf[0])
                if not _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
                    continue
                det_list.append([x1, y1, x2, y2, conf_val])
                det_classes.append(cls_name)
        detections = np.array(det_list) if det_list else np.empty((0, 5))

        tracked_boxes = _track_with_sort(sort_tracker, detections, det_classes)

    else:
        # -- YOLO ByteTrack/BoT-SORT nativo --
        track_results = model.track(
            frame, conf=effective_conf, imgsz=imgsz,
            tracker=tracker_yaml, persist=True, verbose=False,
            classes=vehicle_class_ids, device=device,
        )
        if track_results and track_results[0].boxes is not None:
            for box in track_results[0].boxes:
                if box.id is None:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                tid = int(box.id[0])
                cls_id = int(box.cls[0])
                cls_name = _name_of(cls_id) or "car"
                conf_val = float(box.conf[0])
                if not _filter_box(cls_name, conf_val, x1, y1, x2, y2, conf_for, geo_constraints, exclusion_np):
                    continue
                tracked_boxes.append((x1, y1, x2, y2, tid, cls_name))

    if inference_roi is not None:
        tracked_boxes = [(x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y,
                          tid, cls_name) for x1, y1, x2, y2, tid, cls_name in tracked_boxes]
    return tracked_boxes


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
        if len(inference_roi) != 4 or any(type(v) is not int for v in inference_roi):
            raise ValueError("inference_roi requiere [x1, y1, x2, y2] enteros")
        offset_x, offset_y, right, bottom = inference_roi
        height, width = frame.shape[:2]
        if not (0 <= offset_x < right <= width and 0 <= offset_y < bottom <= height):
            raise ValueError("inference_roi debe estar dentro del video y tener area positiva")
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
