"""Mixin de canvas: zoom, pan, redraw y overlays."""

import numpy as np
from PIL import Image, ImageTk

from carcounter.constants import ZONE_COLORS_HEX as ZONE_COLORS, EXCL_COLORS_HEX as EXCL_COLORS


class CanvasMixin:
    """Zoom, pan, coordinate conversion, redraw y overlays del canvas."""

    # ── Coordenadas ──────────────────────────────
    def _img_to_screen(self, x, y):
        return x * self.zoom + self.pan_x, y * self.zoom + self.pan_y

    def _screen_to_img(self, sx, sy):
        return int((sx - self.pan_x) / self.zoom), int((sy - self.pan_y) / self.zoom)

    # ── Zoom / Pan ───────────────────────────────
    def _clamp_pan(self):
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        img_w = self.img_w * self.zoom
        img_h = self.img_h * self.zoom
        if img_w <= cw:
            self.pan_x = (cw - img_w) / 2
        else:
            self.pan_x = min(0, max(cw - img_w, self.pan_x))
        if img_h <= ch:
            self.pan_y = (ch - img_h) / 2
        else:
            self.pan_y = min(0, max(ch - img_h, self.pan_y))

    def _on_escape(self, _event=None):
        """Cancela cualquier dibujo en progreso."""
        cancelled = False
        # Paso 0: exclusion drawing
        if getattr(self, "excl_drawing", False):
            self.excl_current_pts = []
            self.excl_drawing = False
            cancelled = True
        # Paso 2: zone drawing
        if getattr(self, "zone_drawing", False):
            self.current_zone_pts = []
            self.zone_drawing = False
            cancelled = True
        # Paso 2: line drawing
        if getattr(self, "line_drawing", False):
            self.line_start = None
            self.line_drawing = False
            cancelled = True
        if cancelled:
            self.canvas.config(cursor="crosshair")
            self.status_var.set("Dibujo cancelado (Escape)")
            self._redraw()

    def _enter_pan_mode(self, _event=None):
        self.pan_mode = True
        self.canvas.config(cursor="fleur")

    def _exit_pan_mode(self, _event=None):
        self.pan_mode = False
        self.drag_start = None
        if self.current_step in (0, 1, 2):
            self.canvas.config(cursor="crosshair")
        else:
            self.canvas.config(cursor="arrow")

    def _on_zoom(self, event):
        factor = 1.1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", None) == 4) else 0.9
        anchor_x = getattr(event, "x", self.canvas.winfo_width() / 2)
        anchor_y = getattr(event, "y", self.canvas.winfo_height() / 2)
        img_x = (anchor_x - self.pan_x) / self.zoom
        img_y = (anchor_y - self.pan_y) / self.zoom
        self.zoom = max(0.1, min(8.0, self.zoom * factor))
        self.pan_x = anchor_x - img_x * self.zoom
        self.pan_y = anchor_y - img_y * self.zoom
        self._clamp_pan()
        self._redraw()

    def _on_rpress(self, event):
        self.drag_start = (event.x, event.y)

    def _on_rpan(self, event):
        if self.drag_start:
            self.pan_x += event.x - self.drag_start[0]
            self.pan_y += event.y - self.drag_start[1]
            self.drag_start = (event.x, event.y)
            self._clamp_pan()
            self._redraw()

    def _on_rrelease(self, event):
        self.drag_start = None

    # ── Redraw principal ─────────────────────────
    def _redraw(self):
        if self.frame_rgb is None:
            return
        self.canvas.delete("all")
        cw = self.canvas.winfo_width() or 1000
        ch = self.canvas.winfo_height() or 700

        vx = -self.pan_x / self.zoom
        vy = -self.pan_y / self.zoom
        vw = cw / self.zoom
        vh = ch / self.zoom

        x1 = max(0, int(vx))
        y1 = max(0, int(vy))
        x2 = min(self.img_w, int(vx + vw) + 1)
        y2 = min(self.img_h, int(vy + vh) + 1)
        if x2 <= x1 or y2 <= y1:
            return

        src = self.frame_rgb
        if self.current_step in (2, 3) and self.display_frame_zones is not None:
            src = self.display_frame_zones

        crop = src[y1:y2, x1:x2]
        fw = max(1, int((x2 - x1) * self.zoom))
        fh = max(1, int((y2 - y1) * self.zoom))
        pil = Image.fromarray(crop).resize((fw, fh), Image.Resampling.NEAREST)
        self._tk_img = ImageTk.PhotoImage(pil)

        dx = max(0, self.pan_x) if self.pan_x > 0 else 0
        dy = max(0, self.pan_y) if self.pan_y > 0 else 0
        self.canvas.create_image(dx, dy, image=self._tk_img, anchor="nw")

        if self.current_step == 0:
            self._draw_excl_overlay()
        elif self.current_step == 1:
            self._draw_calib_overlay()
        elif self.current_step == 2:
            if self.counting_mode.get() == "lines":
                self._draw_lines_overlay()
            else:
                self._draw_zones_overlay()
        elif self.current_step == 3:
            self._draw_tile_overlay()

    # ── Overlays ─────────────────────────────────
    def _draw_excl_ref(self):
        """Dibuja zonas de exclusión como referencia visual."""
        for idx, (name, pts) in enumerate(self.exclusion_zones.items()):
            ec = EXCL_COLORS[idx % len(EXCL_COLORS)]
            sp = [self._img_to_screen(p[0], p[1]) for p in pts]
            flat = [c for pt in sp for c in pt]
            if len(flat) >= 4:
                self.canvas.create_polygon(flat, outline=ec, fill=ec, stipple="gray12", width=1)

    def _draw_calib_overlay(self):
        """Dibuja el recuadro de calibración en el canvas."""
        self._draw_excl_ref()

        for i, sample in enumerate(self.vehicle_samples):
            b = sample["bbox"]
            bx1, by1 = self._img_to_screen(b[0], b[1])
            bx2, by2 = self._img_to_screen(b[2], b[3])
            self.canvas.create_rectangle(bx1, by1, bx2, by2,
                                          outline="#A6E3A1", fill="", width=2, dash=(5, 3))
            self.canvas.create_text(
                (bx1 + bx2) / 2, min(by1, by2) - 8,
                text=f"#{i+1} {sample['width']}×{sample['height']}",
                fill="#A6E3A1", font=("Arial", 8, "bold"))

        if self.calib_rect_start and self.calib_rect_end:
            sx1, sy1 = self._img_to_screen(*self.calib_rect_start)
            sx2, sy2 = self._img_to_screen(*self.calib_rect_end)
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                          outline="#FFE66D", width=2, dash=(6, 3))
            w = abs(self.calib_rect_end[0] - self.calib_rect_start[0])
            h = abs(self.calib_rect_end[1] - self.calib_rect_start[1])
            area = w * h
            self.canvas.create_text(
                (sx1 + sx2) / 2, min(sy1, sy2) - 10,
                text=f"Area: {area} px²",
                fill="#FFE66D", font=("Arial", 9, "bold"))

    def _draw_zones_overlay(self):
        """Dibuja zonas guardadas + polígono actual."""
        self._draw_excl_ref()

        selected = self.selected_zone.get() if hasattr(self, "selected_zone") else ""
        for idx, (name, pts) in enumerate(self.zones.items()):
            color = ZONE_COLORS[idx % len(ZONE_COLORS)]
            screen_pts = [self._img_to_screen(p[0], p[1]) for p in pts]
            flat = [coord for pt in screen_pts for coord in pt]
            if len(flat) >= 4:
                is_sel = (name == selected)
                self.canvas.create_polygon(flat, outline=color,
                                            fill=color + ("88" if is_sel else "44"),
                                            width=4 if is_sel else 2)
                cx = sum(p[0] for p in screen_pts) / len(screen_pts)
                cy = sum(p[1] for p in screen_pts) / len(screen_pts)
                self.canvas.create_text(cx, cy, text=name, fill=color,
                                         font=("Arial", 11, "bold"))

        if self.current_zone_pts:
            screen_pts = [self._img_to_screen(p[0], p[1]) for p in self.current_zone_pts]
            for i in range(len(screen_pts) - 1):
                self.canvas.create_line(screen_pts[i][0], screen_pts[i][1],
                                         screen_pts[i+1][0], screen_pts[i+1][1],
                                         fill="#FF6B6B", width=2)
            for pt in screen_pts:
                self.canvas.create_oval(pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5,
                                         fill="#FF6B6B", outline="white", width=1)
            if len(screen_pts) > 2:
                p0 = screen_pts[0]
                self.canvas.create_oval(p0[0]-8, p0[1]-8, p0[0]+8, p0[1]+8,
                                         outline="#FFE66D", width=2)

    def _draw_lines_overlay(self):
        """Dibuja líneas de cruce en el canvas."""
        self._draw_excl_ref()

        for idx, (name, pts) in enumerate(self.counting_lines.items()):
            color = ZONE_COLORS[idx % len(ZONE_COLORS)]
            sp1 = self._img_to_screen(pts[0][0], pts[0][1])
            sp2 = self._img_to_screen(pts[1][0], pts[1][1])
            self.canvas.create_line(sp1[0], sp1[1], sp2[0], sp2[1],
                                     fill=color, width=3)
            mx = (sp1[0] + sp2[0]) / 2
            my = (sp1[1] + sp2[1]) / 2
            self.canvas.create_text(mx, my - 12, text=f"📏 {name}", fill=color,
                                     font=("Arial", 10, "bold"))
            for pt in (sp1, sp2):
                self.canvas.create_oval(pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5,
                                         fill=color, outline="white", width=1)

        if self.line_drawing and self.line_start:
            sp = self._img_to_screen(self.line_start[0], self.line_start[1])
            self.canvas.create_oval(sp[0]-6, sp[1]-6, sp[0]+6, sp[1]+6,
                                     fill="#FFE66D", outline="white", width=2)

    def _draw_tile_overlay(self):
        """Dibuja la cuádrícula SAHI."""
        if not self.img_w:
            return
        if self._tile_grid_visible:
            sw = self.slice_w.get()
            sh = self.slice_h.get()
            ov = self.overlap.get()
            step_x = int(sw * (1 - ov))
            step_y = int(sh * (1 - ov))
            if step_x > 0 and step_y > 0:
                x = 0
                cols = 0
                while x < self.img_w:
                    y = 0
                    rows = 0
                    while y < self.img_h:
                        sx1, sy1 = self._img_to_screen(x, y)
                        sx2, sy2 = self._img_to_screen(min(x + sw, self.img_w), min(y + sh, self.img_h))
                        self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                                      outline="#89B4FA", fill="", width=1, dash=(4, 4))
                        y += step_y
                        rows += 1
                    x += step_x
                    cols += 1
                count = cols * rows if rows > 0 else 0
                self.lbl_tiles.config(text=f"Tiles por frame: {count}  ({cols}×{rows})")
                self.canvas.create_text(8, 8, text=f"Tiles: {count}  ({cols}×{rows})",
                                         anchor="nw", fill="#89B4FA", font=("Arial", 10, "bold"))
        self._draw_zones_overlay()
