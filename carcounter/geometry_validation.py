"""Comprobaciones geométricas del perfil que explican qué corregir antes de ejecutar.

Los errores son casos en los que el elemento nunca puede contar (sin detecciones o con
la detección siempre excluida); los avisos son casos parciales o ambiguos. Las decisiones
usan geometría exacta (shapely, dependencia de sahi): nada se bloquea por aproximación.
Las direcciones son vectores de orientación, no regiones: solo se validan sus coordenadas.
"""

import math

from shapely import make_valid
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

EXCLUDED_WARNING = 0.5
OVERLAP_ERROR = 0.5
OVERLAP_WARNING = 0.05
EPSILON = 1e-6


def _finite_point(point):
    return (isinstance(point, (list, tuple)) and len(point) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in point))


def _bad_points(pts):
    return not isinstance(pts, (list, tuple)) or not all(_finite_point(p) for p in pts)


def coordinate_errors(config):
    """Un error por elemento cuyas coordenadas no son pares numéricos finitos."""
    groups = [("Zona", config.zones), ("Exclusión", config.exclusion_zones),
              ("Dirección", config.directions),
              ("Línea", {line.name: line.points for line in config.lines})]
    return [f"{kind} '{name}' tiene coordenadas inválidas: cada punto debe ser [x, y] con números finitos."
            for kind, elements in groups for name, pts in elements.items() if _bad_points(pts)]


def _region(pts):
    shape = Polygon(pts)
    return shape if shape.is_valid else make_valid(shape)


def _spatial_elements(config):
    mode = config.counting_mode
    if mode == "zones":
        return "zona", {n: p for n, p in config.zones.items() if len(p) >= 3 and not _bad_points(p)}
    if mode == "lines":
        return "línea", {line.name: line.points for line in config.lines
                         if len(line.points) >= 2 and not _bad_points(line.points)}
    return "", {}


def _shape(kind, pts):
    return _region(pts) if kind == "zona" else LineString([pts[0], pts[1]])


def _share(kind, shape, mask):
    """Fracción exacta del elemento sobre la máscara (área para zonas, longitud para líneas)."""
    attr = "area" if kind == "zona" else "length"
    size = getattr(shape, attr)
    return getattr(shape.intersection(mask), attr) / size if size else 0.0


def _percent(share):
    return "<1%" if 0 < share < 0.01 else f"{share:.0%}"


def _roi_findings(kind, shapes, roi, errors, warnings):
    inside_roi = box(*roi)
    for name, shape in shapes.items():
        if not shape.intersects(inside_roi):
            errors.append(f"{kind.capitalize()} '{name}' está fuera de la ROI de inferencia {list(roi)}: "
                          "no recibirá detecciones. Muévela dentro de la ROI o amplía la ROI en el Paso 1.")
            continue
        share = _share(kind, shape, inside_roi)
        if share < 1 - EPSILON:
            warnings.append(f"{kind.capitalize()} '{name}' sale de la ROI de inferencia ({_percent(share)} dentro): "
                            "la parte de fuera no detecta. Ajusta la ROI o el elemento.")


def _exclusion_findings(kind, shapes, exclusions, errors, warnings):
    union = unary_union([_region(pts) for pts in exclusions.values()])
    for name, shape in shapes.items():
        share = _share(kind, shape, union)
        if share >= 1 - EPSILON:
            errors.append(f"{kind.capitalize()} '{name}' queda cubierta por las exclusiones: "
                          "toda detección ahí se descarta. Quita o recorta la exclusión que la tapa.")
        elif share >= EXCLUDED_WARNING:
            warnings.append(f"{kind.capitalize()} '{name}' está excluida en {_percent(share)}: "
                            "las detecciones con centro ahí se descartan. Revisa la exclusión.")


def _overlap_findings(shapes, errors, warnings):
    names = list(shapes)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            smaller = min(shapes[first].area, shapes[second].area)
            share = shapes[first].intersection(shapes[second]).area / smaller if smaller else 0.0
            if share >= OVERLAP_ERROR:
                errors.append(f"Las zonas '{first}' y '{second}' se solapan {share:.0%} de la menor: "
                              "un auto cae en ambas y el origen o destino es ambiguo. Sepáralas o fusiónalas.")
            elif share >= OVERLAP_WARNING:
                warnings.append(f"Las zonas '{first}' y '{second}' se solapan {share:.0%} de la menor: "
                                "un auto en el solape cuenta para una sola. Reduce el solape.")


def geometry_findings(config):
    """(errores, avisos) de un AppConfig; cada texto dice qué corregir."""
    errors, warnings = coordinate_errors(config), []
    kind, elements = _spatial_elements(config)
    roi = config.settings.inference_roi
    if roi is not None and (len(roi) != 4 or not roi[0] < roi[2] or not roi[1] < roi[3]):
        roi = None
    if not elements:
        return errors, warnings
    shapes = {name: _shape(kind, pts) for name, pts in elements.items()}
    exclusions = {n: p for n, p in config.exclusion_zones.items() if len(p) >= 3 and not _bad_points(p)}
    if roi:
        _roi_findings(kind, shapes, roi, errors, warnings)
    if exclusions:
        _exclusion_findings(kind, shapes, exclusions, errors, warnings)
    if kind == "zona":
        _overlap_findings(shapes, errors, warnings)
    return errors, warnings
