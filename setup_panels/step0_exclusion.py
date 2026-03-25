"""Mixin para Paso 0: Zonas de Exclusion."""

import math
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np

from carcounter.constants import EXCL_COLORS_HEX as EXCL_COLORS
from carcounter.geometry import in_exclusion_zone


class ExclusionMixin:
    """Métodos de zonas de exclusión (Paso 0)."""

    def _build_panel_excl(self):
        """Construye el panel lateral del Paso 0."""
        self.panel_step0 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step0, "ZONAS DE EXCLUSIÓN", bold=True, color="#FF5555")
        self._lbl(self.panel_step0,
                  "Define polígonos para excluir\n"
                  "vehículos estacionados u otras\n"
                  "áreas sin flujo de tránsito.\n\n"
                  "• Clic izq: agregar punto\n"
                  "• Clic cerca del primero: cerrar\n"
                  "• Paso opcional — puedes continuar\n"
                  "  sin definir zonas", color="#A6ADC8")
        self._lbl(self.panel_step0,
                  "🚫 Detecciones dentro de estas zonas\nno se contarán como tránsito.",
                  color="#F38BA8")
        tk.Frame(self.panel_step0, bg="#313244", height=1).pack(fill="x", pady=8)

        self._lbl(self.panel_step0, "Nombre de la zona:", color="#CDD6F4")
        ttk.Entry(self.panel_step0, textvariable=self.excl_zone_name,
                  font=("Arial", 11)).pack(fill="x", pady=4)

        self.btn_new_excl = tk.Button(self.panel_step0, text="🚫  Nueva zona de exclusión",
                                       command=self._start_excl_draw,
                                       bg="#F38BA8", fg="#11111B", font=("Arial", 10, "bold"),
                                       relief="flat", pady=6)
        self.btn_new_excl.pack(fill="x", pady=4)

        self.btn_del_excl = tk.Button(self.panel_step0, text="🗑  Eliminar zona seleccionada",
                                       command=self._delete_excl_zone,
                                       bg="#313244", fg="#F38BA8", relief="flat", pady=4)
        self.btn_del_excl.pack(fill="x", pady=2)

        tk.Frame(self.panel_step0, bg="#313244", height=1).pack(fill="x", pady=8)
        self._lbl(self.panel_step0, "Zonas de exclusión:", color="#CDD6F4")
        self.excl_listbox = tk.Listbox(self.panel_step0, bg="#11111B", fg="#F38BA8",
                                        selectbackground="#45475A", font=("Arial", 10),
                                        height=8, relief="flat", bd=0)
        self.excl_listbox.pack(fill="both", expand=True)
        self.excl_listbox.bind("<<ListboxSelect>>", self._on_excl_select)

        self.btn_excl_ok = tk.Button(self.panel_step0, text="✅  Continuar →",
                                      command=lambda: self._activate_step(1),
                                      bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_excl_ok.pack(fill="x", pady=8)

    # ── Lógica ───────────────────────────────────
    def _excl_np_cache(self):
        """Retorna dict de zonas de exclusion como numpy arrays, cacheado."""
        if self._excl_np_cached is None:
            self._excl_np_cached = {n: np.array(pts, dtype=np.int32)
                                    for n, pts in self.exclusion_zones.items()}
        return self._excl_np_cached

    def _invalidate_excl_cache(self):
        self._excl_np_cached = None

    def _is_in_exclusion(self, cx, cy):
        return in_exclusion_zone(cx, cy, self._excl_np_cache())

    def _draw_excl_overlay(self):
        """Dibuja zonas de exclusión + polígono en curso."""
        selected = self.excl_selected.get()
        for idx, (name, pts) in enumerate(self.exclusion_zones.items()):
            color = EXCL_COLORS[idx % len(EXCL_COLORS)]
            sp = [self._img_to_screen(p[0], p[1]) for p in pts]
            flat = [c for pt in sp for c in pt]
            if len(flat) >= 4:
                is_sel = (name == selected)
                self.canvas.create_polygon(flat, outline=color,
                                            fill=color + ("88" if is_sel else "44"),
                                            width=4 if is_sel else 2)
                cx = sum(p[0] for p in sp) / len(sp)
                cy = sum(p[1] for p in sp) / len(sp)
                self.canvas.create_text(cx, cy, text=f"🚫 {name}", fill=color,
                                         font=("Arial", 10, "bold"))
        if self.excl_current_pts:
            sp = [self._img_to_screen(p[0], p[1]) for p in self.excl_current_pts]
            for i in range(len(sp) - 1):
                self.canvas.create_line(sp[i][0], sp[i][1], sp[i+1][0], sp[i+1][1],
                                         fill="#FF5555", width=2)
            for pt in sp:
                self.canvas.create_oval(pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5,
                                         fill="#FF5555", outline="white", width=1)
            if len(sp) > 2:
                self.canvas.create_oval(sp[0][0]-8, sp[0][1]-8, sp[0][0]+8, sp[0][1]+8,
                                         outline="#FFE66D", width=2)

    def _start_excl_draw(self):
        name = self.excl_zone_name.get().strip()
        if not name:
            messagebox.showwarning("Exclusión", "Escribe un nombre para la zona.")
            return
        if name in self.exclusion_zones:
            if not messagebox.askyesno("Zona existe", f"La zona '{name}' ya existe. ¿Sobreescribir?"):
                return
            del self.exclusion_zones[name]
            self._invalidate_excl_cache()
            self._refresh_excl_list()
        self.excl_current_pts = []
        self.excl_drawing = True
        self.canvas.config(cursor="crosshair")
        self.status_var.set(f"Dibujando exclusión '{name}' — clic para puntos, clic cerca del primero para cerrar")
        self._redraw()

    def _close_excl_zone(self):
        name = self.excl_zone_name.get().strip()
        if len(self.excl_current_pts) < 3:
            messagebox.showwarning("Exclusión", "Se necesitan al menos 3 puntos.")
            return
        self.exclusion_zones[name] = list(self.excl_current_pts)
        self._invalidate_excl_cache()
        self.excl_current_pts = []
        self.excl_drawing = False
        self.canvas.config(cursor="crosshair")
        self._refresh_excl_list()
        self.status_var.set(f"Zona de exclusión '{name}' guardada ({len(self.exclusion_zones)} en total)")
        n = len(self.exclusion_zones) + 1
        while f"Exclusion {n}" in self.exclusion_zones:
            n += 1
        self.excl_zone_name.set(f"Exclusion {n}")
        self._redraw()

    def _refresh_excl_list(self):
        self.excl_listbox.delete(0, "end")
        for name in self.exclusion_zones:
            self.excl_listbox.insert("end", f"  🚫 {name}  ({len(self.exclusion_zones[name])} pts)")

    def _on_excl_select(self, event):
        sel = self.excl_listbox.curselection()
        if sel:
            name = list(self.exclusion_zones.keys())[sel[0]]
            self.excl_selected.set(name)

    def _delete_excl_zone(self):
        name = self.excl_selected.get()
        if name and name in self.exclusion_zones:
            if messagebox.askyesno("Eliminar", f"¿Eliminar zona de exclusión '{name}'?"):
                del self.exclusion_zones[name]
                self._invalidate_excl_cache()
                self._refresh_excl_list()
                self.excl_selected.set("")
                self._redraw()

    def _on_excl_press(self, event):
        """Maneja clic izquierdo en Paso 0."""
        ix, iy = self._screen_to_img(event.x, event.y)
        if self.excl_drawing:
            if len(self.excl_current_pts) > 2:
                p0 = self.excl_current_pts[0]
                if math.hypot(ix - p0[0], iy - p0[1]) < 20 / self.zoom:
                    self._close_excl_zone()
                    return
            self.excl_current_pts.append((ix, iy))
            self._redraw()
        else:
            clicked = None
            for name, arr in self._excl_np_cache().items():
                if cv2.pointPolygonTest(arr, (float(ix), float(iy)), False) >= 0:
                    clicked = name
                    break
            if clicked:
                self.excl_selected.set(clicked)
                keys = list(self.exclusion_zones.keys())
                self.excl_listbox.selection_clear(0, "end")
                self.excl_listbox.selection_set(keys.index(clicked))
            else:
                self.excl_selected.set("")
                self.excl_listbox.selection_clear(0, "end")
            self._redraw()
