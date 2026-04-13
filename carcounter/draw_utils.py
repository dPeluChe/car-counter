"""Helpers de dibujo para reducir boilerplate de cv2.putText/rectangle.

Provee TextStyler y ShapeDrawer para reutilizar estilos de texto
y figuras en drawing.py y calibration.py.
"""

import cv2
import numpy as np


class TextStyler:
    """Envuelve cv2.putText con estilos predefinidos para reducir repeticion."""

    FONT = cv2.FONT_HERSHEY_SIMPLEX

    @staticmethod
    def draw(frame, text, pos, color, scale=0.45, thickness=1):
        """Dibuja texto con anti-aliasing en la posicion dada."""
        cv2.putText(frame, text, pos, TextStyler.FONT, scale, color, thickness, cv2.LINE_AA)

    @staticmethod
    def label(frame, text, x, y, color, scale=0.42, thickness=1, above=True):
        """Dibuja una etiqueta arriba o abajo de una coordenada."""
        offset_y = max(12, y - 5) if above else y + 15
        cv2.putText(frame, text, (x, offset_y), TextStyler.FONT, scale, color, thickness, cv2.LINE_AA)

    @staticmethod
    def centered(frame, text, cx, cy, color, scale=0.65, thickness=2):
        """Dibuja texto centrado horizontalmente en (cx, cy)."""
        (tw, th), _ = cv2.getTextSize(text, TextStyler.FONT, scale, thickness)
        cv2.putText(frame, text, (cx - tw // 2, cy + th // 2),
                    TextStyler.FONT, scale, color, thickness, cv2.LINE_AA)


class ShapeDrawer:
    """Helpers para figuras comunes: bboxes, panels, overlays."""

    @staticmethod
    def bbox(frame, x1, y1, x2, y2, color, thickness=2):
        """Dibuja un bounding box."""
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    @staticmethod
    def centroid(frame, cx, cy, color, radius=4):
        """Dibuja un punto de centroide."""
        cv2.circle(frame, (cx, cy), radius, color, -1)

    @staticmethod
    def panel_bg(frame, x0, y0, w, h, bg_color=(0, 0, 0), alpha=0.6,
                 border_color=(80, 80, 80)):
        """Dibuja un panel semi-transparente con borde usando ROI."""
        rx2 = min(frame.shape[1], x0 + w)
        ry2 = min(frame.shape[0], y0 + h)
        roi = frame[y0:ry2, x0:rx2].copy()
        cv2.rectangle(frame, (x0, y0), (x0 + w, y0 + h), bg_color, -1)
        cv2.addWeighted(roi, alpha, frame[y0:ry2, x0:rx2], 1.0 - alpha, 0,
                        frame[y0:ry2, x0:rx2])
        cv2.rectangle(frame, (x0, y0), (x0 + w, y0 + h), border_color, 1)

    @staticmethod
    def zone_overlay(frame, zones_np, colors, alpha=0.18):
        """Dibuja zonas poligonales semi-transparentes con labels."""
        overlay = frame.copy()
        meta = []
        for idx, (name, pts) in enumerate(zones_np.items()):
            color = colors[idx % len(colors)]
            cv2.fillPoly(overlay, [pts], color)
            meta.append((name, pts, color))
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)
        for name, pts, color in meta:
            cv2.polylines(frame, [pts], True, color, 2)
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            TextStyler.centered(frame, name, cx, cy, color)

    @staticmethod
    def bar(frame, x, y, width, height, color):
        """Dibuja una barra rectangular rellena."""
        cv2.rectangle(frame, (x, y), (x + width, y + height), color, -1)

    @staticmethod
    def trail(frame, points, color, max_thickness=2.5):
        """Dibuja un trail con grosor gradual."""
        import math
        n = len(points)
        prev = None
        for i, pt in enumerate(points):
            if prev is not None:
                thickness = max(1, int(math.sqrt(float(i) / float(n)) * max_thickness))
                cv2.line(frame, (int(prev[0]), int(prev[1])),
                         (int(pt[0]), int(pt[1])), color, thickness)
            prev = pt
