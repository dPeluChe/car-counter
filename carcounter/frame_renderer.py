"""FrameRenderer: rendering logic separada del widget Tkinter.

Permite testear overlays de zonas, lineas y detecciones sin GUI.
Extraido de setup_panels/canvas.py para mejorar testabilidad.
"""

import cv2
import numpy as np
from carcounter.theme import ZONE_COLORS_RGB, EXCL_COLORS_RGB, Opacity


class FrameRenderer:
    """Renderiza overlays sobre frames sin depender de Tkinter.

    Todos los metodos reciben un frame RGB y retornan el frame modificado.
    """

    @staticmethod
    def draw_exclusion_zones(frame_rgb, exclusion_zones, selected=None):
        """Dibuja zonas de exclusion semi-transparentes sobre un frame RGB.

        Args:
            frame_rgb: numpy array RGB
            exclusion_zones: dict {name: [(x,y), ...]}
            selected: nombre de zona seleccionada (opcional)

        Returns:
            Frame RGB con overlays
        """
        if not exclusion_zones:
            return frame_rgb

        overlay = frame_rgb.copy()
        meta = []
        for idx, (name, pts) in enumerate(exclusion_zones.items()):
            color = EXCL_COLORS_RGB[idx % len(EXCL_COLORS_RGB)]
            np_pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(overlay, [np_pts], color)
            meta.append((name, np_pts, color))

        result = cv2.addWeighted(frame_rgb, Opacity.SETUP_BG, overlay, Opacity.SETUP_FILL, 0)

        for name, np_pts, color in meta:
            cv2.polylines(result, [np_pts], True, color, 2)
            cx = int(np.mean(np_pts[:, 0]))
            cy = int(np.mean(np_pts[:, 1]))
            cv2.putText(result, f"EXCL:{name}", (cx, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return result

    @staticmethod
    def draw_zones(frame_rgb, zones, exclusion_zones=None, selected=None):
        """Dibuja zonas de transito semi-transparentes sobre un frame RGB.

        Args:
            frame_rgb: numpy array RGB
            zones: dict {name: [(x,y), ...]}
            exclusion_zones: dict {name: [(x,y), ...]} (opcional, para referencia)
            selected: nombre de zona seleccionada

        Returns:
            Frame RGB con overlays
        """
        base = frame_rgb.copy()
        overlay = base.copy()
        excl_meta = []
        zone_meta = []

        if exclusion_zones:
            for idx, (name, pts) in enumerate(exclusion_zones.items()):
                color = EXCL_COLORS_RGB[idx % len(EXCL_COLORS_RGB)]
                np_pts = np.array(pts, dtype=np.int32)
                cv2.fillPoly(overlay, [np_pts], color)
                excl_meta.append((name, np_pts, color))

        for idx, (name, pts) in enumerate(zones.items()):
            color = ZONE_COLORS_RGB[idx % len(ZONE_COLORS_RGB)]
            np_pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(overlay, [np_pts], color)
            zone_meta.append((name, np_pts, color))

        base = cv2.addWeighted(base, Opacity.SETUP_BG, overlay, Opacity.SETUP_FILL, 0)

        for name, np_pts, color in excl_meta:
            cv2.polylines(base, [np_pts], True, color, 2)
            cx = int(np.mean(np_pts[:, 0]))
            cy = int(np.mean(np_pts[:, 1]))
            cv2.putText(base, f"EXCL:{name}", (cx, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        for name, np_pts, color in zone_meta:
            cv2.polylines(base, [np_pts], True, color, 2)
            cx = int(np.mean(np_pts[:, 0]))
            cy = int(np.mean(np_pts[:, 1]))
            cv2.putText(base, name, (cx, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return base

    @staticmethod
    def draw_detections(frame_rgb, detections, color=(255, 200, 50)):
        """Dibuja bounding boxes de detecciones sobre un frame RGB.

        Args:
            frame_rgb: numpy array RGB
            detections: list of dicts with 'bbox', 'cls_name', 'conf'
            color: color RGB para las detecciones

        Returns:
            Frame RGB con detecciones
        """
        result = frame_rgb.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            lbl = f"{det.get('cls_name', '?')} {det.get('conf', 0):.2f}"
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
            cv2.putText(result, lbl, (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
        return result

    @staticmethod
    def draw_tile_grid(frame_rgb, img_w, img_h, slice_w, slice_h, overlap):
        """Dibuja la cuadricula SAHI sobre un frame RGB.

        Returns:
            (frame_rgb, tile_count, cols, rows)
        """
        result = frame_rgb.copy()
        step_x = max(1, int(slice_w * (1 - overlap)))
        step_y = max(1, int(slice_h * (1 - overlap)))

        x, cols = 0, 0
        rows = 0
        while x < img_w:
            y = 0
            rows = 0
            while y < img_h:
                sx2 = min(x + slice_w, img_w)
                sy2 = min(y + slice_h, img_h)
                cv2.rectangle(result, (x, y), (sx2, sy2), (137, 180, 250), 1)
                y += step_y
                rows += 1
            x += step_x
            cols += 1

        count = cols * rows if rows > 0 else 0
        return result, count, cols, rows

    @staticmethod
    def draw_vehicle_samples(frame_rgb, samples, color=(166, 227, 161)):
        """Dibuja recuadros de muestras de vehiculos sobre un frame RGB.

        Args:
            frame_rgb: numpy array RGB
            samples: list of dicts with 'bbox', 'width', 'height'

        Returns:
            Frame RGB con muestras
        """
        result = frame_rgb.copy()
        for i, sample in enumerate(samples):
            b = sample["bbox"]
            cv2.rectangle(result, (b[0], b[1]), (b[2], b[3]), color, 2)
            cv2.putText(result, f"#{i+1} {sample['width']}x{sample['height']}",
                        ((b[0] + b[2]) // 2, min(b[1], b[3]) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        return result
