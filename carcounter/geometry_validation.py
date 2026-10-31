"""Comprobaciones geométricas del perfil que explican qué corregir antes de ejecutar.

Los errores son casos en los que el elemento nunca puede contar (sin detecciones o con
la detección siempre excluida); los avisos son casos parciales o ambiguos.
"""

import cv2
import numpy as np

CANVAS_MAX_SIDE = 960
EXCLUDED_WARNING = 0.5
OVERLAP_ERROR = 0.5
OVERLAP_WARNING = 0.05
LINE_SAMPLES = 25


class _Canvas:
    """Rasteriza polígonos y segmentos a baja resolución; las proporciones bastan para decidir."""

    def __init__(self, groups):
        extent = max((max(max(x, y) for x, y in pts) for g in groups for pts in g.values() if pts), default=1)
        self.scale = min(1.0, CANVAS_MAX_SIDE / max(extent, 1))
        side = int(extent * self.scale) + 2
        self.shape = (side, side)

    def _points(self, pts):
        return np.round(np.asarray(pts, dtype=float) * self.scale).astype(np.int32)

    def polygon(self, pts):
        mask = np.zeros(self.shape, np.uint8)
        cv2.fillPoly(mask, [self._points(pts)], 1)
        return mask.astype(bool)

    def roi(self, roi):
        mask = np.zeros(self.shape, np.uint8)
        x1, y1, x2, y2 = np.round(np.asarray(roi, dtype=float) * self.scale).astype(int)
        mask[y1:y2 + 1, x1:x2 + 1] = 1
        return mask.astype(bool)


def _segment_samples(pts):
    a, b = np.asarray(pts[0], dtype=float), np.asarray(pts[-1], dtype=float)
    return [a + (b - a) * t for t in np.linspace(0, 1, LINE_SAMPLES)]


def _fraction_inside(canvas, kind, pts, mask):
    """Fracción del elemento que cae sobre la máscara (área para zonas, puntos para segmentos)."""
    if kind == "zona":
        own = canvas.polygon(pts)
        area = own.sum()
        return (own & mask).sum() / area if area else 0.0
    hits = 0
    for x, y in _segment_samples(pts):
        col, row = int(round(x * canvas.scale)), int(round(y * canvas.scale))
        hits += 0 <= row < mask.shape[0] and 0 <= col < mask.shape[1] and bool(mask[row, col])
    return hits / LINE_SAMPLES


def _elements(config):
    mode = config.counting_mode
    if mode == "zones":
        return "zona", dict(config.zones)
    if mode == "lines":
        return "línea", {line.name: line.points for line in config.lines}
    if mode == "directions":
        return "dirección", dict(config.directions)
    return "", {}


def _roi_findings(canvas, kind, elements, roi, errors, warnings):
    inside_roi = canvas.roi(roi)
    for name, pts in elements.items():
        share = _fraction_inside(canvas, kind, pts, inside_roi)
        if share == 0:
            errors.append(f"{kind.capitalize()} '{name}' está fuera de la ROI de inferencia {list(roi)}: "
                          "no recibirá detecciones. Muévela dentro de la ROI o amplía la ROI en el Paso 1.")
        elif share < 1:
            warnings.append(f"{kind.capitalize()} '{name}' sale de la ROI de inferencia ({share:.0%} dentro): "
                            "la parte de fuera no detecta. Ajusta la ROI o el elemento.")


def _exclusion_findings(canvas, kind, elements, exclusions, errors, warnings):
    union = np.zeros(canvas.shape, bool)
    for pts in exclusions.values():
        union |= canvas.polygon(pts)
    for name, pts in elements.items():
        share = _fraction_inside(canvas, kind, pts, union)
        if share >= 0.98:
            errors.append(f"{kind.capitalize()} '{name}' queda cubierta por las exclusiones: "
                          "toda detección ahí se descarta. Quita o recorta la exclusión que la tapa.")
        elif share >= EXCLUDED_WARNING:
            warnings.append(f"{kind.capitalize()} '{name}' está excluida en {share:.0%}: "
                            "las detecciones con centro ahí se descartan. Revisa la exclusión.")


def _overlap_findings(canvas, zones, errors, warnings):
    masks = {name: canvas.polygon(pts) for name, pts in zones.items() if len(pts) >= 3}
    names = list(masks)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            smaller = min(masks[first].sum(), masks[second].sum())
            share = (masks[first] & masks[second]).sum() / smaller if smaller else 0.0
            if share >= OVERLAP_ERROR:
                errors.append(f"Las zonas '{first}' y '{second}' se solapan {share:.0%} de la menor: "
                              "un auto cae en ambas y el origen o destino es ambiguo. Sepáralas o fusiónalas.")
            elif share >= OVERLAP_WARNING:
                warnings.append(f"Las zonas '{first}' y '{second}' se solapan {share:.0%} de la menor: "
                                "un auto en el solape cuenta para una sola. Reduce el solape.")


def geometry_findings(config):
    """(errores, avisos) de un AppConfig; cada texto dice qué corregir."""
    errors, warnings = [], []
    kind, elements = _elements(config)
    elements = {name: pts for name, pts in elements.items() if len(pts) >= (3 if kind == "zona" else 2)}
    roi = config.settings.inference_roi
    if roi is not None and (len(roi) != 4 or not roi[0] < roi[2] or not roi[1] < roi[3]):
        roi = None
    if not elements:
        return errors, warnings
    exclusions = {name: pts for name, pts in config.exclusion_zones.items() if len(pts) >= 3}
    drawn = [elements, exclusions]
    canvas = _Canvas(drawn + ([{"roi": [roi[:2], roi[2:]]}] if roi else []))
    if roi:
        _roi_findings(canvas, kind, elements, roi, errors, warnings)
    if exclusions:
        _exclusion_findings(canvas, kind, elements, exclusions, errors, warnings)
    if kind == "zona":
        _overlap_findings(canvas, elements, errors, warnings)
    return errors, warnings
