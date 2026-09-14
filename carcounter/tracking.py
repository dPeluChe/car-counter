"""Funciones auxiliares de tracking."""

from carcounter.geometry import bbox_iou


def attach_classes_to_tracks(track_rows, det_rows, det_classes):
    """Asocia clase COCO a cada track SORT por mejor IoU con detecciones."""
    labeled_tracks = []
    for row in track_rows:
        x1, y1, x2, y2, tid = map(int, row)
        best_idx = -1
        best_iou = 0.0
        for idx, det in enumerate(det_rows):
            det_box = tuple(map(int, det[:4]))
            score = bbox_iou((x1, y1, x2, y2), det_box)
            if score > best_iou:
                best_iou = score
                best_idx = idx
        cls_name = det_classes[best_idx] if 0 <= best_idx < len(det_classes) else "car"
        labeled_tracks.append((x1, y1, x2, y2, tid, cls_name))
    return labeled_tracks


class UltralyticsTracker:
    def __init__(self, backend, config, frame_rate=30):
        from types import SimpleNamespace
        import math
        from ultralytics.utils import ROOT, YAML
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.trackers.bot_sort import BOTSORT

        if backend not in {"bytetrack", "botsort"}:
            raise ValueError(f"Tracker desconocido: {backend}")
        options = YAML.load(ROOT / "cfg" / "trackers" / f"{backend}.yaml")
        options.update({key: value for key, value in config.items() if key in options})
        options["tracker_type"] = backend
        for key in ("track_low_thresh", "track_high_thresh", "new_track_thresh", "match_thresh"):
            value = options[key]
            if not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{key} debe estar entre 0 y 1")
        if not options["track_low_thresh"] < options["track_high_thresh"] <= options["new_track_thresh"]:
            raise ValueError("Se requiere track_low_thresh < track_high_thresh <= new_track_thresh")
        if type(options["track_buffer"]) is not int or options["track_buffer"] < 1:
            raise ValueError("track_buffer debe ser un entero positivo")
        if options.get("with_reid"):
            raise ValueError("Este flujo de cajas no proporciona características ReID; usa with_reid=false")
        self.options = options
        self.class_names = []
        tracker_class = BYTETracker if backend == "bytetrack" else BOTSORT
        self.tracker = tracker_class(SimpleNamespace(**options), frame_rate=frame_rate or 30)

    def update_detections(self, frame, detections, classes):
        import numpy as np
        from ultralytics.engine.results import Boxes

        rows = []
        for detection, name in zip(detections, classes):
            if name not in self.class_names:
                self.class_names.append(name)
            rows.append([*detection, self.class_names.index(name)])
        boxes = Boxes(np.asarray(rows, dtype=np.float32).reshape(-1, 6), frame.shape[:2])
        tracks = self.tracker.update(boxes, img=frame)
        return [(*map(int, row[:5]), self.class_names[int(row[6])]) for row in tracks]
