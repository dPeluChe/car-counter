"""Funciones geom: point-in-polygon, IoU, NMS, filtros, exclusion, line-crossing."""

import math
import cv2
import numpy as np


# ── Zone masks (pre-computed) ─────────────────

def build_zone_masks(zones_np, frame_w, frame_h):
    """Pre-computa masks binarias para cada zona. O(1) lookup vs O(V) pointPolygonTest."""
    masks = {}
    for name, pts in zones_np.items():
        mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 1)
        masks[name] = mask
    return masks


def point_in_zone_mask(x, y, masks):
    """Retorna el nombre de la zona donde cae (x,y) usando masks pre-computadas."""
    ix, iy = int(x), int(y)
    for name, mask in masks.items():
        if 0 <= iy < mask.shape[0] and 0 <= ix < mask.shape[1] and mask[iy, ix]:
            return name
    return None


# ── Point-in-polygon (legacy, para setup) ─────

def point_in_zone(x, y, zone_pts):
    """True si (x,y) esta dentro del poligono zone_pts (np.int32)."""
    return cv2.pointPolygonTest(zone_pts, (float(x), float(y)), False) >= 0


def bbox_intersects_zone(x1, y1, x2, y2, zone_pts):
    """True si cualquier esquina del bbox toca el poligono (mas generoso que solo centro)."""
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    for cx, cy in corners:
        if cv2.pointPolygonTest(zone_pts, (float(cx), float(cy)), False) >= 0:
            return True
    return False


# ── IoU ───────────────────────────────────────

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


# ── NMS ───────────────────────────────────────

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


# ── Geometry filters ──────────────────────────

def passes_geometry_filter(x1, y1, x2, y2, constraints):
    """Valida bbox contra constraints dict (min/max width/height/area/aspect)."""
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    area = width * height
    aspect = width / float(height)
    if area < constraints.get("min_area", 0):
        return False
    if area > constraints.get("max_area", math.inf):
        return False
    if width < constraints.get("min_width", 0):
        return False
    if width > constraints.get("max_width", math.inf):
        return False
    if height < constraints.get("min_height", 0):
        return False
    if height > constraints.get("max_height", math.inf):
        return False
    if aspect < constraints.get("min_aspect", 0.0):
        return False
    if aspect > constraints.get("max_aspect", math.inf):
        return False
    return True


# ── Exclusion zones ──────────────────────────

def in_exclusion_zone(cx, cy, exclusion_np):
    """True si (cx,cy) cae dentro de alguna zona de exclusion."""
    for pts in exclusion_np.values():
        if cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0:
            return True
    return False


# ── Line crossing ────────────────────────────

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


# ── Direction (cosine similarity) ─────────────

def cosine_similarity_2d(vec_a, vec_b):
    """Cosine similarity entre dos vectores 2D. Retorna -1..1."""
    ax, ay = vec_a
    bx, by = vec_b
    dot = ax * bx + ay * by
    norm_a = math.sqrt(ax * ax + ay * ay)
    norm_b = math.sqrt(bx * bx + by * by)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
