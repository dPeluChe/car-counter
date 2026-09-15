"""Mixin para el modo 'lines' del Paso 2 (cruce de linea).

Metodos: _start_line_draw, _finish_line, _delete_selected_line.

Construccion del subpanel y seleccion de modo viven en step2_zones.py
porque son compartidos entre los 3 modos (zones/lines/directions).
"""

from tkinter import messagebox


class LinesMixin:
    """Logica de dibujo/edicion de lineas de cruce."""

    def _start_line_draw(self):
        name = self.current_line_name.get().strip()
        if not name:
            messagebox.showwarning("Línea", "Escribe un nombre para la línea.")
            return
        if name in self.counting_lines and not messagebox.askyesno(
                "Línea existe", f"La línea '{name}' ya existe. ¿Reemplazarla al terminar la nueva?"):
            return
        self._line_draw_name = name
        self.line_drawing = True
        self.line_start = None
        self.canvas.config(cursor="crosshair")
        self.status_var.set(
            f"Dibujando línea '{name}' — clic para punto inicio, segundo clic para punto final"
        )

    def _finish_line(self, ix, iy):
        name = self._line_draw_name
        self.counting_lines[name] = [list(self.line_start), [ix, iy]]
        self.line_drawing = False
        self.line_start = None
        self._refresh_zones_list()
        self.status_var.set(
            f"Línea '{name}' guardada ({len(self.counting_lines)} en total)"
        )
        # Siguiente nombre sugerido
        n = len(self.counting_lines) + 1
        while f"Línea {n}" in self.counting_lines:
            n += 1
        self.current_line_name.set(f"Línea {n}")
        self._redraw()

    def _delete_selected_line(self):
        sel = self.zones_listbox.curselection()
        if self.counting_mode.get() != "lines" or not sel:
            messagebox.showinfo("Eliminar", "Selecciona una línea de la lista.")
            return
        name = list(self.counting_lines.keys())[sel[0]]
        if messagebox.askyesno("Eliminar", f"¿Eliminar línea '{name}'?"):
            del self.counting_lines[name]
            self._refresh_zones_list()
            self._redraw()
