"""Mixin para Paso 2: Zonas, Lineas y Preview."""

import math
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np

from carcounter.constants import ZONE_COLORS_RGB, EXCL_COLORS_RGB


class ZonesMixin:
    """Métodos de zonas, líneas de cruce y preview (Paso 2)."""

    def _build_panel_zones(self):
        """Construye el panel lateral del Paso 2."""
        self.panel_step2 = tk.Frame(self.sidebar, bg="#181825", padx=12, pady=10)
        self._lbl(self.panel_step2, "MODO DE CONTEO", bold=True, color="#CDD6F4")

        # Selector de modo
        mode_frame = tk.Frame(self.panel_step2, bg="#181825")
        mode_frame.pack(fill="x", pady=4)
        self.btn_mode_zones = tk.Button(mode_frame, text="🗺 Zonas A→B",
                                         command=lambda: self._set_counting_mode("zones"),
                                         bg="#89B4FA", fg="#11111B", font=("Arial", 9, "bold"),
                                         relief="flat", pady=4)
        self.btn_mode_zones.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_mode_lines = tk.Button(mode_frame, text="📏 Cruce de línea",
                                         command=lambda: self._set_counting_mode("lines"),
                                         bg="#313244", fg="#A6ADC8", font=("Arial", 9, "bold"),
                                         relief="flat", pady=4)
        self.btn_mode_lines.pack(side="left", fill="x", expand=True, padx=(2, 0))
        self.btn_mode_directions = tk.Button(mode_frame, text="➡ Direcciones",
                                         command=lambda: self._set_counting_mode("directions"),
                                         bg="#313244", fg="#A6ADC8", font=("Arial", 9, "bold"),
                                         relief="flat", pady=4)
        self.btn_mode_directions.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # ── Subpanel zonas ──
        self.subpanel_zones = tk.Frame(self.panel_step2, bg="#181825")
        self._lbl(self.subpanel_zones,
                  "Dibuja un poligono en cada\n"
                  "zona de entrada/salida.\n\n"
                  "• Clic izq: agregar punto\n"
                  "• Clic cerca del primero: cerrar\n"
                  "• Rueda: zoom", color="#A6ADC8")

        tk.Frame(self.subpanel_zones, bg="#313244", height=1).pack(fill="x", pady=8)
        self._lbl(self.subpanel_zones, "Nombre de la zona:", color="#CDD6F4")
        self.zone_name_entry = ttk.Entry(self.subpanel_zones,
                                         textvariable=self.current_zone_name,
                                         font=("Arial", 11))
        self.zone_name_entry.pack(fill="x", pady=4)

        self.btn_new_zone = tk.Button(self.subpanel_zones, text="✏  Nueva Zona (dibujar)",
                                      command=self._start_zone_draw,
                                      bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_new_zone.pack(fill="x", pady=4)

        self.btn_del_zone = tk.Button(self.subpanel_zones, text="🗑  Eliminar zona seleccionada",
                                      command=self._delete_selected_zone,
                                      bg="#313244", fg="#F38BA8", relief="flat", pady=4)
        self.btn_del_zone.pack(fill="x", pady=2)

        self.btn_undo_point = tk.Button(self.subpanel_zones, text="↩  Deshacer último punto",
                                        command=self._undo_last_point,
                                        bg="#313244", fg="#F9E2AF", relief="flat", pady=4,
                                        state="disabled")
        self.btn_undo_point.pack(fill="x", pady=2)
        self.subpanel_zones.pack(fill="x")

        # ── Subpanel líneas ──
        self.subpanel_lines = tk.Frame(self.panel_step2, bg="#181825")
        self._lbl(self.subpanel_lines,
                  "Dibuja líneas de cruce. Cada\n"
                  "vehículo que cruce la línea se\n"
                  "contará (dirección ↑/↓).\n\n"
                  "• Clic: punto inicio\n"
                  "• Segundo clic: punto final", color="#A6ADC8")

        tk.Frame(self.subpanel_lines, bg="#313244", height=1).pack(fill="x", pady=8)
        self._lbl(self.subpanel_lines, "Nombre de la línea:", color="#CDD6F4")
        self.line_name_entry = ttk.Entry(self.subpanel_lines,
                                          textvariable=self.current_line_name,
                                          font=("Arial", 11))
        self.line_name_entry.pack(fill="x", pady=4)

        self.btn_new_line = tk.Button(self.subpanel_lines, text="📏  Nueva Línea (dibujar)",
                                       command=self._start_line_draw,
                                       bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"),
                                       relief="flat", pady=6)
        self.btn_new_line.pack(fill="x", pady=4)

        self.btn_del_line = tk.Button(self.subpanel_lines, text="🗑  Eliminar línea seleccionada",
                                      command=self._delete_selected_line,
                                      bg="#313244", fg="#F38BA8", relief="flat", pady=4)
        self.btn_del_line.pack(fill="x", pady=2)

        # ── Subpanel direcciones ──
        self.subpanel_directions = tk.Frame(self.panel_step2, bg="#181825")
        self._lbl(self.subpanel_directions,
                  "Dibuja vectores de dirección para\n"
                  "clasificar vehículos por su trayectoria.\n\n"
                  "• Clic: punto inicio\n"
                  "• Segundo clic: punto final", color="#A6ADC8")

        tk.Frame(self.subpanel_directions, bg="#313244", height=1).pack(fill="x", pady=8)
        self._lbl(self.subpanel_directions, "Nombre de la dirección:", color="#CDD6F4")
        self.direction_name_entry = ttk.Entry(self.subpanel_directions,
                                               textvariable=self.current_direction_name,
                                               font=("Arial", 11))
        self.direction_name_entry.pack(fill="x", pady=4)

        self.btn_new_direction = tk.Button(self.subpanel_directions, text="➡  Nueva Dirección (dibujar)",
                                       command=self._start_direction_draw,
                                       bg="#89B4FA", fg="#11111B", font=("Arial", 10, "bold"),
                                       relief="flat", pady=6)
        self.btn_new_direction.pack(fill="x", pady=4)

        self.btn_del_direction = tk.Button(self.subpanel_directions, text="🗑  Eliminar dirección seleccionada",
                                       command=self._delete_selected_direction,
                                       bg="#313244", fg="#F38BA8", relief="flat", pady=4)
        self.btn_del_direction.pack(fill="x", pady=2)

        tk.Frame(self.panel_step2, bg="#313244", height=1).pack(fill="x", pady=8)
        self.btn_preview = tk.Button(self.panel_step2, text="▶  Reproducir",
                                     command=self._toggle_zone_preview,
                                     bg="#F9E2AF", fg="#11111B", font=("Arial", 10, "bold"),
                                     relief="flat", pady=6)
        self.btn_preview.pack(fill="x", pady=4)

        self.btn_det_toggle = tk.Button(self.panel_step2, text="🔍  Detecciones YOLO: OFF",
                                        command=self._toggle_yolo_preview,
                                        bg="#313244", fg="#6C7086", relief="flat", pady=4)
        self.btn_det_toggle.pack(fill="x", pady=2)

        tk.Frame(self.panel_step2, bg="#313244", height=1).pack(fill="x", pady=8)
        self._lbl(self.panel_step2, "Elementos guardados:", color="#CDD6F4")

        self.zones_frame = tk.Frame(self.panel_step2, bg="#181825")
        self.zones_frame.pack(fill="both", expand=True)

        self.selected_zone = tk.StringVar(value="")
        self.zones_listbox = tk.Listbox(self.zones_frame, bg="#11111B", fg="#CDD6F4",
                                         selectbackground="#45475A", font=("Arial", 10),
                                         height=8, relief="flat", bd=0)
        self.zones_listbox.pack(fill="both", expand=True)
        self.zones_listbox.bind("<<ListboxSelect>>", self._on_zone_select)

        self.btn_zones_ok = tk.Button(self.panel_step2, text="✅  Continuar →",
                                      command=self._confirm_zones,
                                      bg="#A6E3A1", fg="#11111B", font=("Arial", 10, "bold"),
                                      relief="flat", pady=6)
        self.btn_zones_ok.pack(fill="x", pady=8)

    # ── Modo de conteo ───────────────────────────
    def _set_counting_mode(self, mode):
        self.counting_mode.set(mode)
        if mode == "zones":
            self.btn_mode_zones.config(bg="#89B4FA", fg="#11111B")
            self.btn_mode_lines.config(bg="#313244", fg="#A6ADC8")
            self.btn_mode_directions.config(bg="#313244", fg="#A6ADC8")
            self.subpanel_lines.pack_forget()
            self.subpanel_directions.pack_forget()
            self.subpanel_zones.pack(fill="x")
        elif mode == "lines":
            self.btn_mode_lines.config(bg="#89B4FA", fg="#11111B")
            self.btn_mode_zones.config(bg="#313244", fg="#A6ADC8")
            self.btn_mode_directions.config(bg="#313244", fg="#A6ADC8")
            self.subpanel_zones.pack_forget()
            self.subpanel_directions.pack_forget()
            self.subpanel_lines.pack(fill="x")
        else:  # directions
            self.btn_mode_directions.config(bg="#89B4FA", fg="#11111B")
            self.btn_mode_zones.config(bg="#313244", fg="#A6ADC8")
            self.btn_mode_lines.config(bg="#313244", fg="#A6ADC8")
            self.subpanel_zones.pack_forget()
            self.subpanel_lines.pack_forget()
            self.subpanel_directions.pack(fill="x")
        self._refresh_zones_list()
        self._redraw()

    # Logica de Lineas y Direcciones extraida a step2_lines.py y step2_directions.py

    # ── Zonas ────────────────────────────────────
    def _start_zone_draw(self):
        self._stop_zone_preview()
        name = self.current_zone_name.get().strip()
        if not name:
            messagebox.showwarning("Zona", "Escribe un nombre para la zona.")
            return
        if name in self.zones:
            if not messagebox.askyesno("Zona existe", f"La zona '{name}' ya existe. ¿Sobreescribir?"):
                return
            del self.zones[name]
            self._refresh_zones_list()
        self.current_zone_pts = []
        self.btn_undo_point.config(state="disabled")
        self.zone_drawing = True
        self.canvas.config(cursor="crosshair")
        self.status_var.set(f"Dibujando zona '{name}' — clic para agregar puntos, clic cerca del primero para cerrar")
        self._redraw()

    def _close_current_zone(self):
        name = self.current_zone_name.get().strip()
        if len(self.current_zone_pts) < 3:
            messagebox.showwarning("Zona", "Se necesitan al menos 3 puntos para una zona.")
            return
        self.zones[name] = list(self.current_zone_pts)
        self.current_zone_pts = []
        self.btn_undo_point.config(state="disabled")
        self.zone_drawing = False
        self.canvas.config(cursor="arrow")
        self._refresh_zones_list()
        self._redraw_zones()
        self.status_var.set(f"Zona '{name}' guardada. ({len(self.zones)} zonas en total)")
        suggestions = ["Norte", "Sur", "Este", "Oeste", "Noreste", "Noroeste", "Sureste", "Suroeste"]
        for s in suggestions:
            if s not in self.zones:
                self.current_zone_name.set(s)
                break

    def _refresh_zones_list(self):
        self.zones_listbox.delete(0, "end")
        mode = self.counting_mode.get()
        if mode == "lines":
            for name in self.counting_lines:
                self.zones_listbox.insert("end", f"  📏 {name}")
        elif mode == "directions":
            for name in self.directions:
                self.zones_listbox.insert("end", f"  ➡ {name}")
        else:
            for name in self.zones:
                self.zones_listbox.insert("end", f"  {name}  ({len(self.zones[name])} pts)")

    def _on_zone_select(self, event):
        sel = self.zones_listbox.curselection()
        if not sel:
            return
        mode = self.counting_mode.get()
        if mode == "lines":
            keys = list(self.counting_lines.keys())
        elif mode == "directions":
            keys = list(self.directions.keys())
        else:
            keys = list(self.zones.keys())
        if sel[0] < len(keys):
            self.selected_zone.set(keys[sel[0]])

    def _delete_selected_zone(self):
        name = self.selected_zone.get()
        if name and name in self.zones:
            if messagebox.askyesno("Eliminar", f"¿Eliminar zona '{name}'?"):
                del self.zones[name]
                self._refresh_zones_list()
                self._redraw_zones()

    def _undo_last_point(self):
        if not self.zone_drawing or not self.current_zone_pts:
            return
        self.current_zone_pts.pop()
        self.btn_undo_point.config(state="normal" if self.current_zone_pts else "disabled")
        n = len(self.current_zone_pts)
        self.status_var.set(
            f"↩ Punto eliminado — {n} punto{'s' if n != 1 else ''} restante{'s' if n != 1 else ''}")
        self._redraw()

    def _redraw_zones(self):
        """Actualiza display_frame_zones con las zonas dibujadas (single-pass overlay)."""
        base = cv2.cvtColor(self.frame_orig, cv2.COLOR_BGR2RGB).copy()
        overlay = base.copy()
        excl_meta = []
        zone_meta = []

        # Fill all exclusion zones on one overlay
        for idx, (name, pts) in enumerate(self.exclusion_zones.items()):
            color = EXCL_COLORS_RGB[idx % len(EXCL_COLORS_RGB)]
            np_pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(overlay, [np_pts], color)
            excl_meta.append((name, np_pts, color))

        # Fill all transit zones on same overlay
        for idx, (name, pts) in enumerate(self.zones.items()):
            color = ZONE_COLORS_RGB[idx % len(ZONE_COLORS_RGB)]
            np_pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(overlay, [np_pts], color)
            zone_meta.append((name, np_pts, color))

        # Single blend pass
        base = cv2.addWeighted(base, 0.75, overlay, 0.25, 0)

        # Draw outlines and labels
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
            cv2.putText(base, name, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        self.display_frame_zones = base
        self._redraw()

    # Preview logic extraida a setup_panels/step2_preview.py (PreviewMixin)

    # Validacion y confirmacion extraidas a setup_panels/step2_validation.py (ZoneValidationMixin)

    # ── Eventos de clic (Paso 2) ─────────────────
    def _on_zones_press(self, event):
        """Maneja clic izquierdo en Paso 2."""
        ix, iy = self._screen_to_img(event.x, event.y)

        if self.line_drawing:
            if self.line_start is None:
                self.line_start = (ix, iy)
                self.status_var.set("Clic en el segundo punto de la línea")
                self._redraw()
            else:
                self._finish_line(ix, iy)
            return

        if self.direction_drawing:
            if self.direction_start is None:
                self.direction_start = (ix, iy)
                self.status_var.set("Clic en el segundo punto de la dirección")
                self._redraw()
            else:
                self._finish_direction(ix, iy)
            return

        if self.zone_drawing:
            if len(self.current_zone_pts) > 2:
                p0 = self.current_zone_pts[0]
                dist = math.hypot(ix - p0[0], iy - p0[1])
                if dist < 20 / self.zoom:
                    self._close_current_zone()
                    return
            self.current_zone_pts.append((ix, iy))
            self.btn_undo_point.config(state="normal")
            self._redraw()
            return

        if not self.pan_mode:
            clicked = None
            for name, pts in self.zones.items():
                arr = np.array(pts, dtype=np.int32)
                if cv2.pointPolygonTest(arr, (float(ix), float(iy)), False) >= 0:
                    clicked = name
                    break
            if clicked:
                self.selected_zone.set(clicked)
                keys = list(self.zones.keys())
                idx = keys.index(clicked)
                self.zones_listbox.selection_clear(0, "end")
                self.zones_listbox.selection_set(idx)
                self.zones_listbox.see(idx)
            else:
                self.selected_zone.set("")
                self.zones_listbox.selection_clear(0, "end")
            self._redraw()
