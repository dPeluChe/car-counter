"""Funciones de dibujo OpenCV para el contador."""

import math
import cv2
import numpy as np

from carcounter.constants import ZONE_COLORS_BGR


def draw_zones(frame, zones_np):
    """Dibuja zonas poligonales semi-transparentes."""
    overlay = frame.copy()
    zone_meta = []
    for idx, (name, pts) in enumerate(zones_np.items()):
        color = ZONE_COLORS_BGR[idx % len(ZONE_COLORS_BGR)]
        cv2.fillPoly(overlay, [pts], color)
        zone_meta.append((name, pts, color))
    cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
    for name, pts, color in zone_meta:
        cv2.polylines(frame, [pts], True, color, 2)
        cx = int(np.mean(pts[:, 0]))
        cy = int(np.mean(pts[:, 1]))
        cv2.putText(frame, name, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, color, 2, cv2.LINE_AA)


def draw_lines(frame, counting_lines):
    """Dibuja lineas de cruce con color y nombre."""
    for idx, line in enumerate(counting_lines):
        color = ZONE_COLORS_BGR[idx % len(ZONE_COLORS_BGR)]
        pt1 = tuple(line["pt1"])
        pt2 = tuple(line["pt2"])
        cv2.line(frame, pt1, pt2, color, 3)
        mx = (pt1[0] + pt2[0]) // 2
        my = (pt1[1] + pt2[1]) // 2
        cv2.putText(frame, line["name"], (mx + 5, my - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
        cv2.putText(frame, "up/dn", (mx + 5, my + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def draw_exclusion_zones(frame, exclusion_np):
    """Dibuja zonas de exclusion en rojo semi-transparente."""
    if not exclusion_np:
        return
    overlay = frame.copy()
    for pts in exclusion_np.values():
        cv2.fillPoly(overlay, [pts], (60, 60, 220))
    cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)
    for pts in exclusion_np.values():
        cv2.polylines(frame, [pts], True, (60, 60, 220), 2)


def _draw_panel_bg(frame, x0, y0, panel_w, panel_h, bg_color, alpha, border_color):
    """Dibuja fondo semi-transparente para un panel usando ROI en vez de full frame copy."""
    rx2 = min(frame.shape[1], x0 + panel_w)
    ry2 = min(frame.shape[0], y0 + panel_h)
    roi = frame[y0:ry2, x0:rx2].copy()
    cv2.rectangle(frame, (x0, y0), (x0 + panel_w, y0 + panel_h), bg_color, -1)
    cv2.addWeighted(roi, alpha, frame[y0:ry2, x0:rx2], 1.0 - alpha, 0, frame[y0:ry2, x0:rx2])
    cv2.rectangle(frame, (x0, y0), (x0 + panel_w, y0 + panel_h), border_color, 1)


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

    _draw_panel_bg(frame, x0, y0, panel_w, panel_h, (0, 0, 0), 0.6, (80, 80, 80))

    cv2.putText(frame, "RUTAS DETECTADAS", (x0 + pad, y0 + pad + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Activos: {n_active}", (x0 + pad + 160, y0 + pad + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 100), 1, cv2.LINE_AA)

    y = y0 + pad + line_h + 4
    total = sum(routes.values())
    for route, count in sorted_routes:
        pct = count / total * 100 if total > 0 else 0
        bar_w = int((panel_w - pad * 2 - 90) * count / max(routes.values()))
        cv2.rectangle(frame, (x0 + pad, y + 4), (x0 + pad + bar_w, y + 16),
                      (60, 120, 60), -1)
        cv2.putText(frame, f"{route}:", (x0 + pad, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 255, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{count}  ({pct:.0f}%)",
                    (x0 + panel_w - 80, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 100), 1, cv2.LINE_AA)
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

    _draw_panel_bg(frame, x0, y0, panel_w, panel_h, (8, 8, 8), 0.65, (90, 90, 90))

    cv2.putText(frame, f"TOTAL: {total_ever}",
                (x0 + pad, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.05,
                (60, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"rutas: {total_confirmed}  activos: {n_active}",
                (x0 + pad, y0 + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                (160, 160, 100), 1, cv2.LINE_AA)
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
        cv2.rectangle(frame, (x0 + pad, y + 17), (x0 + pad + bar_w, y + 24), color, -1)
        cv2.putText(frame, route, (x0 + pad, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 1, cv2.LINE_AA)
        cv2.putText(frame, f"{count}  ({pct:.0f}%)", (x0 + panel_w - 94, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (220, 220, 100), 1, cv2.LINE_AA)
        y += row_h


def draw_hud(frame, frame_num, total_f, fps_avg, detections, n_routes_total, vid_w):
    """HUD inferior con info de procesamiento."""
    h = frame.shape[0]
    progress = frame_num / total_f if total_f > 0 else 0
    bar_w = int(vid_w * progress)
    cv2.rectangle(frame, (0, h - 6), (bar_w, h), (80, 200, 80), -1)

    info = f"Frame {frame_num}/{total_f}  FPS:{fps_avg:.1f}  Det:{detections}  Rutas:{n_routes_total}"
    cv2.putText(frame, info, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (200, 200, 200), 1, cv2.LINE_AA)


def draw_tracked_boxes(frame, tracked_boxes, tracks_info, zone_names, trails=None):
    """Dibuja bboxes de vehiculos con color segun estado de tracking."""
    for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        info = tracks_info.get(trk_id, {})
        state = info.get("state", "new")
        origin = info.get("origin", "")

        if state == "done":
            color = (60, 220, 60)
        elif state in ("origin", "transit") and origin in zone_names:
            zone_idx = zone_names.index(origin)
            color = ZONE_COLORS_BGR[zone_idx % len(ZONE_COLORS_BGR)]
            if state == "transit":
                color = tuple(min(255, int(c * 1.3)) for c in color)
        else:
            color = (160, 160, 160)

        # Draw trail
        if trails and trk_id in trails:
            trail = trails[trk_id]
            n = len(trail)
            prev = None
            for i, pt in enumerate(trail):
                if prev is not None:
                    thickness = max(1, int(math.sqrt(float(i) / float(n)) * 2.5))
                    cv2.line(frame, (int(prev[0]), int(prev[1])),
                             (int(pt[0]), int(pt[1])), color, thickness)
                prev = pt

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (cx, cy), 4, color, -1)

        state_icon = {"done": "v", "transit": ">", "origin": "o", "new": "?",
                      "tracking": "~"}.get(state, "")
        label = f"{state_icon}{trk_id}"
        if origin:
            label += f"[{origin}]"
        cv2.putText(frame, label, (x1, max(12, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)


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
