"""Funciones geom: point-in-polygon, IoU, NMS, filtros, exclusion, line-crossing."""

import math
import cv2
import numpy as np


def point_in_zone(x, y, zone_pts):
    """True si (x,y) esta dentro del poligono zone_pts (np.int32)."""
    return cv2.pointPolygonTest(zone_pts, (float(x), float(y)), False) >= 0


def bbox_iou(box_a, box_b):
    """IoU entre dos bboxes (x1,y1,x2,y2)."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    denom = area_a + area_b - inter_area
    return inter_area / denom if denom > 0 else 0.0


def apply_nms(det_list, det_classes, iou_threshold):
    """Greedy NMS post-SAHI. Ordena por conf desc y suprime solapadas."""
    if not det_list:
        return det_list, det_classes
    order = sorted(range(len(det_list)), key=lambda i: -det_list[i][4])
    keep = []
    suppressed = set()
    for pos, i in enumerate(order):
        if i in suppressed:
            continue
        keep.append(i)
        for j in order[pos + 1:]:
            if j not in suppressed and bbox_iou(det_list[i][:4], det_list[j][:4]) > iou_threshold:
                suppressed.add(j)
    return [det_list[k] for k in keep], [det_classes[k] for k in keep]


def passes_geometry_filter(x1, y1, x2, y2, constraints):
    """Valida bbox contra constraints dict (min/max width/height/area/aspect)."""
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    area = width * height
    aspect = width / float(height)
    min_area = constraints.get("min_area", 0)
    max_area = constraints.get("max_area", 999999)
    min_w = constraints.get("min_width", 0)
    max_w = constraints.get("max_width", 999999)
    min_h = constraints.get("min_height", 0)
    max_h = constraints.get("max_height", 999999)
    min_asp = constraints.get("min_aspect", 0.0)
    max_asp = constraints.get("max_aspect", 999999.0)
    if min_area > 0 and area < min_area:
        return False
    if max_area < 999999 and area > max_area:
        return False
    if min_w > 0 and width < min_w:
        return False
    if max_w < 999999 and width > max_w:
        return False
    if min_h > 0 and height < min_h:
        return False
    if max_h < 999999 and height > max_h:
        return False
    if min_asp > 0 and aspect < min_asp:
        return False
    if max_asp < 999999 and aspect > max_asp:
        return False
    return True


def in_exclusion_zone(cx, cy, exclusion_np):
    """True si (cx,cy) cae dentro de alguna zona de exclusion."""
    for pts in exclusion_np.values():
        if cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0:
            return True
    return False


def point_to_line_side(px, py, x1, y1, x2, y2):
    """Cross product: >0 si abajo/derecha, <0 si arriba/izquierda."""
    return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)


def point_line_distance(px, py, x1, y1, x2, y2):
    """Distancia perpendicular del punto a la linea (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return math.hypot(px - x1, py - y1)
    return abs(dx * (y1 - py) - (x1 - px) * dy) / length
