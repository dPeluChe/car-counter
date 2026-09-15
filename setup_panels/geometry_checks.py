"""Comprobaciones geométricas del perfil que no dependen de Tk."""


def inference_roi(loaded_config):
    return ((loaded_config or {}).get("settings") or {}).get("inference_roi")


def elements_outside_roi(roi, zones=None, lines=None, directions=None):
    """Nombres de zonas, líneas o direcciones con algún punto fuera de la ROI de inferencia."""
    if not roi:
        return []
    x1, y1, x2, y2 = roi
    outside = []
    for kind, elements in (("zona", zones), ("línea", lines), ("dirección", directions)):
        for name, points in (elements or {}).items():
            if any(not (x1 <= x <= x2 and y1 <= y <= y2) for x, y in points):
                outside.append(f"{kind} {name}")
    return outside
