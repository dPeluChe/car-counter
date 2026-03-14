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
