"""Mixin para Paso 2: validacion y confirmacion de zonas, lineas y direcciones."""

import math
from tkinter import messagebox

import cv2
import numpy as np

from setup_panels.geometry_checks import elements_outside_roi


class ZoneValidationMixin:
    """Valida los elementos del Paso 2 antes de pasar al Paso 3."""

    def _validate_zones(self):
        """Valida zonas/lineas antes de continuar. Retorna (ok, mensaje)."""
        mode = self.counting_mode.get()

        if mode == "zones":
            if not self.zones:
                return False, "No hay zonas definidas. Dibuja al menos 2 zonas."
            if len(self.zones) < 2:
                return False, "Necesitas al menos 2 zonas para detectar rutas A→B."

            # Verificar poligonos con menos de 3 puntos
            for name, pts in self.zones.items():
                if len(pts) < 3:
                    return False, f"La zona '{name}' tiene solo {len(pts)} punto(s). Se necesitan al menos 3."

            # Verificar nombres duplicados (no deberia pasar, pero defensivo)
            names = list(self.zones.keys())
            if len(names) != len(set(names)):
                return False, "Hay nombres de zona duplicados. Cada zona debe tener un nombre unico."

            # Verificar zonas con area minima (poligonos degenerados)
            for name, pts in self.zones.items():
                np_pts = np.array(pts, dtype=np.int32)
                area = cv2.contourArea(np_pts)
                if area < 100:
                    return False, (
                        f"La zona '{name}' tiene un area muy pequena ({int(area)} px²). "
                        "Redibuja con puntos mas separados."
                    )

        elif mode == "lines":
            if not self.counting_lines:
                return False, "No hay lineas definidas. Dibuja al menos una linea de cruce."

            for name, pts in self.counting_lines.items():
                if len(pts) < 2:
                    return False, f"La linea '{name}' no tiene 2 puntos definidos."
                p1, p2 = pts[0], pts[1]
                length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if length < 10:
                    return False, (
                        f"La linea '{name}' es muy corta ({int(length)} px). "
                        "Dibuja una linea mas larga."
                    )

        elif mode == "directions":
            if not self.directions:
                return False, "No hay direcciones definidas. Dibuja al menos un vector de direccion."
            for name, pts in self.directions.items():
                if len(pts) < 2:
                    return False, f"La direccion '{name}' no tiene 2 puntos definidos."

        # Aviso no bloqueante: fuera de la ROI no hay detecciones y ese elemento no contará
        elements = {"zones": (self.zones, None, None), "lines": (None, self.counting_lines, None),
                    "directions": (None, None, self.directions)}[mode]
        outside = elements_outside_roi(self.inference_roi, *elements)
        if outside:
            return True, "Fuera de la ROI de inferencia (no detectará ahí): " + ", ".join(outside)
        return True, ""

    def _confirm_zones(self):
        ok, msg = self._validate_zones()
        if not ok:
            messagebox.showwarning("Validacion", msg)
            return
        if msg:
            messagebox.showwarning("ROI de inferencia", msg)
        mode = self.counting_mode.get()
        if mode == "zones":
            n = len(self.zones)
        elif mode == "lines":
            n = len(self.counting_lines)
        else:
            n = len(self.directions)
        self.status_var.set(f"{n} elemento(s) confirmado(s) — pasando a Paso 3")
        self.after(300, lambda: self._activate_step(3))
