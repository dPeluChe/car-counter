"""Funciones de dibujo OpenCV para el contador."""

import math
import cv2
import numpy as np

from carcounter.theme import ZONE_COLORS_BGR, Draw, Opacity
from carcounter.draw_utils import TextStyler, ShapeDrawer


def draw_zones(frame, zones_np):
    """Dibuja zonas poligonales semi-transparentes."""
    ShapeDrawer.zone_overlay(frame, zones_np, ZONE_COLORS_BGR, alpha=Opacity.ZONE_FILL)


def draw_lines(frame, counting_lines):
    """Dibuja lineas de cruce con color y nombre."""
    for idx, line in enumerate(counting_lines):
        color = ZONE_COLORS_BGR[idx % len(ZONE_COLORS_BGR)]
        pt1 = tuple(line["pt1"])
        pt2 = tuple(line["pt2"])
        cv2.line(frame, pt1, pt2, color, 3)
        mx = (pt1[0] + pt2[0]) // 2
        my = (pt1[1] + pt2[1]) // 2
        TextStyler.draw(frame, line["name"], (mx + 5, my - 10), color, scale=0.6, thickness=2)
        TextStyler.draw(frame, "up/dn", (mx + 5, my + 20), color, scale=0.5)


def draw_exclusion_zones(frame, exclusion_np):
    """Dibuja zonas de exclusion en rojo semi-transparente."""
    if not exclusion_np:
        return
    overlay = frame.copy()
    for pts in exclusion_np.values():
        cv2.fillPoly(overlay, [pts], Draw.EXCL_OVERLAY)
    cv2.addWeighted(overlay, Opacity.EXCL_FILL, frame, Opacity.EXCL_BG, 0, frame)
    for pts in exclusion_np.values():
        cv2.polylines(frame, [pts], True, Draw.EXCL_OVERLAY, 2)


def _draw_panel_bg(frame, x0, y0, panel_w, panel_h, bg_color, alpha, border_color):
    """Dibuja fondo semi-transparente para un panel usando ROI."""
    ShapeDrawer.panel_bg(frame, x0, y0, panel_w, panel_h, bg_color, alpha, border_color)


def draw_routes_panel(frame, routes, n_active):
    """Panel semitransparente con la matriz de rutas A->B."""
    if not routes:
        return
    pad = 10
    line_h = 22
    sorted_routes = sorted(routes.items(), key=lambda x: -x[1])
    panel_h = pad * 2 + line_h * (len(sorted_routes) + 2)
    panel_w = 280
    x0, y0 = 10, 10

    _draw_panel_bg(frame, x0, y0, panel_w, panel_h, Draw.PANEL_BG, Draw.PANEL_ALPHA, Draw.PANEL_BORDER)

    TextStyler.draw(frame, "RUTAS DETECTADAS", (x0 + pad, y0 + pad + 14), Draw.TEXT_LIGHT, scale=0.5)
    TextStyler.draw(frame, f"Activos: {n_active}", (x0 + pad + 160, y0 + pad + 14), Draw.TEXT_DIM, scale=0.45)

    y = y0 + pad + line_h + 4
    total = sum(routes.values())
    for route, count in sorted_routes:
        pct = count / total * 100 if total > 0 else 0
        bar_w = int((panel_w - pad * 2 - 90) * count / max(routes.values()))
        ShapeDrawer.bar(frame, x0 + pad, y + 4, bar_w, 12, Draw.BAR_GREEN)
        TextStyler.draw(frame, f"{route}:", (x0 + pad, y + 14), Draw.TEXT_ROUTES)
        TextStyler.draw(frame, f"{count}  ({pct:.0f}%)", (x0 + panel_w - 80, y + 14), (255, 255, 100))
        y += line_h


def draw_scoreboard(frame, routes, n_active, total_ever, vid_w, zone_names):
    """Panel scoreboard grande para --demo-mode. Posicion: top-right."""
    total_confirmed = sum(routes.values()) if routes else 0
    sorted_routes = sorted(routes.items(), key=lambda x: -x[1]) if routes else []

    pad = 14
    row_h = 34
    panel_h = pad + 62 + row_h * max(len(sorted_routes), 1) + pad
    panel_w = 390
    x0 = max(0, vid_w - panel_w - 12)
    y0 = 10

    _draw_panel_bg(frame, x0, y0, panel_w, panel_h,
                   Draw.SCOREBOARD_BG, Draw.SCOREBOARD_ALPHA, Draw.SCOREBOARD_BORDER)

    TextStyler.draw(frame, f"TOTAL: {total_ever}", (x0 + pad, y0 + 40),
                    Draw.TEXT_COUNT, scale=1.05, thickness=2)
    TextStyler.draw(frame, f"rutas: {total_confirmed}  activos: {n_active}",
                    (x0 + pad, y0 + 60), Draw.TEXT_DIM, scale=0.48)
    cv2.line(frame, (x0 + pad, y0 + 68), (x0 + panel_w - pad, y0 + 68), (70, 70, 70), 1)

    max_count = max(routes.values(), default=1)
    y = y0 + 76
    for route, count in sorted_routes:
        pct = count / total_confirmed * 100 if total_confirmed > 0 else 0
        origin = route.split("\u2192")[0].strip()
        color = (150, 200, 150)
        for zi, zn in enumerate(zone_names):
            if zn == origin:
                color = ZONE_COLORS_BGR[zi % len(ZONE_COLORS_BGR)]
                break
        bar_w = max(2, int((panel_w - pad * 2 - 100) * count / max_count))
        ShapeDrawer.bar(frame, x0 + pad, y + 17, bar_w, 7, color)
        TextStyler.draw(frame, route, (x0 + pad, y + 14), color, scale=0.62)
        TextStyler.draw(frame, f"{count}  ({pct:.0f}%)", (x0 + panel_w - 94, y + 14),
                        (220, 220, 100), scale=0.60)
        y += row_h


def draw_hud(frame, frame_num, total_f, fps_avg, detections, n_routes_total, vid_w):
    """HUD inferior con info de procesamiento."""
    h = frame.shape[0]
    progress = frame_num / total_f if total_f > 0 else 0
    bar_w = int(vid_w * progress)
    ShapeDrawer.bar(frame, 0, h - 6, bar_w, 6, Draw.HUD_BAR)

    info = f"Frame {frame_num}/{total_f}  FPS:{fps_avg:.1f}  Det:{detections}  Rutas:{n_routes_total}"
    TextStyler.draw(frame, info, (10, h - 12), Draw.TEXT_LIGHT, scale=0.5)


def draw_tracked_boxes(frame, tracked_boxes, tracks_info, zone_names, trails=None):
    """Dibuja bboxes de vehiculos con color segun estado de tracking."""
    for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        info = tracks_info.get(trk_id, {})
        state = info.get("state", "new")
        origin = info.get("origin", "")

        if state == "done":
            color = Draw.STATE_DONE
        elif state in ("origin", "transit") and origin in zone_names:
            zone_idx = zone_names.index(origin)
            color = ZONE_COLORS_BGR[zone_idx % len(ZONE_COLORS_BGR)]
            if state == "transit":
                color = tuple(min(255, int(c * 1.3)) for c in color)
        else:
            color = Draw.STATE_DEFAULT

        # Draw trail
        if trails and trk_id in trails:
            ShapeDrawer.trail(frame, trails[trk_id], color)

        ShapeDrawer.bbox(frame, x1, y1, x2, y2, color)
        ShapeDrawer.centroid(frame, cx, cy, color)

        state_icon = {"done": "v", "transit": ">", "origin": "o", "new": "?",
                      "tracking": "~"}.get(state, "")
        label = f"{state_icon}{trk_id}"
        if origin:
            label += f"[{origin}]"
        TextStyler.label(frame, label, x1, y1, color)


class DensityHeatmap:
    """Acumula centroides y genera un heatmap overlay."""

    def __init__(self, width, height, decay=0.995, blur_ksize=31):
        self._acc = np.zeros((height, width), dtype=np.float32)
        self._decay = decay
        self._blur_ksize = blur_ksize | 1  # ensure odd

    def update(self, centroids):
        """Agrega centroides [(cx,cy), ...] al acumulador con decay temporal."""
        self._acc *= self._decay
        for cx, cy in centroids:
            ix, iy = int(cx), int(cy)
            if 0 <= iy < self._acc.shape[0] and 0 <= ix < self._acc.shape[1]:
                self._acc[iy, ix] += 1.0

    def draw(self, frame, alpha=0.4):
        """Renderiza el heatmap sobre el frame."""
        if self._acc.max() == 0:
            return
        blurred = cv2.GaussianBlur(self._acc, (self._blur_ksize, self._blur_ksize), 0)
        normalized = blurred / max(blurred.max(), 1.0)
        heatmap_u8 = (normalized * 255).astype(np.uint8)
        colored = cv2.applyColorMap(heatmap_u8, cv2.COLORMAP_JET)
        # Solo mezclar donde hay actividad (threshold > 5% del max)
        mask = normalized > 0.05
        mask_3c = np.stack([mask] * 3, axis=-1)
        blended = frame.copy()
        blended[mask_3c] = cv2.addWeighted(
            frame, 1 - alpha, colored, alpha, 0
        )[mask_3c]
        np.copyto(frame, blended)


def format_time(s):
    """Formatea segundos a Xh Xm Xs."""
    h, r = divmod(int(s), 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")
