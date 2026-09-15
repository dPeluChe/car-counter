"""Mixin para el modo 'directions' del Paso 2 (vectores de direccion).

Metodos: _start_direction_draw, _finish_direction, _delete_selected_direction.

Construccion del subpanel y seleccion de modo viven en step2_zones.py
porque son compartidos entre los 3 modos (zones/lines/directions).
"""

from tkinter import messagebox


class DirectionsMixin:
    """Logica de dibujo/edicion de vectores de direccion."""

    def _start_direction_draw(self):
        name = self.current_direction_name.get().strip()
        if not name:
            messagebox.showwarning("Dirección", "Escribe un nombre para la dirección.")
            return
        if name in self.directions and not messagebox.askyesno(
                "Dirección existe", f"La dirección '{name}' ya existe. ¿Reemplazarla al terminar la nueva?"):
            return
        self._direction_draw_name = name
        self.direction_drawing = True
        self.direction_start = None
        self.canvas.config(cursor="crosshair")
        self.status_var.set(
            f"Dibujando dirección '{name}' — clic para punto inicio, segundo clic para punto final"
        )

    def _finish_direction(self, ix, iy):
        name = self._direction_draw_name
        self.directions[name] = [list(self.direction_start), [ix, iy]]
        self.direction_drawing = False
        self.direction_start = None
        self._refresh_zones_list()
        self.status_var.set(
            f"Dirección '{name}' guardada ({len(self.directions)} en total)"
        )
        self._redraw()

    def _delete_selected_direction(self):
        sel = self.zones_listbox.curselection()
        if self.counting_mode.get() != "directions" or not sel:
            messagebox.showinfo("Eliminar", "Selecciona una dirección de la lista.")
            return
        name = list(self.directions.keys())[sel[0]]
        if messagebox.askyesno("Eliminar", f"¿Eliminar dirección '{name}'?"):
            del self.directions[name]
            self._refresh_zones_list()
            self._redraw()
