"""Car Counter: aplicación principal con interfaz gráfica.

Wizard: 1. Modelo, 2. Video, 3. Perfil y ejecución. El configurador y main.py corren como subprocesos.
Entry point: python -m carcounter
"""

import tkinter as tk
from tkinter import messagebox

from carcounter.app_steps import LaunchStepMixin, ModelStepMixin, RunControlMixin, VideoStepMixin
from carcounter.app_theme import ACCENT, BG, BG_DARK, FG_BRIGHT, FG_DIM, GREEN
from carcounter.process_utils import stop_process


class CarCounterApp(ModelStepMixin, VideoStepMixin, LaunchStepMixin, RunControlMixin, tk.Tk):
    """Wizard principal de Car Counter: compone los mixins de pasos y de subprocesos."""

    def __init__(self):
        super().__init__()
        self.title("Car Counter")
        self.geometry("820x660")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._selected_model = tk.StringVar(value="")
        self._selected_video = tk.StringVar(value="")
        # Sin perfil por defecto: uno viejo de config/ daría zonas que no son las del video elegido
        self._selected_config = tk.StringVar(value="")
        self._selected_tracker = tk.StringVar(value="bytetrack")
        self._custom_model_path = ""
        self._current_step = 0
        self._process = None
        self._process_kind = None
        self._run_dir = None
        self._log_file = None
        self._setup_mtime = None
        self._cancel_btn = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_step(0)

    # ── UI scaffolding ────────────────────────

    def _build_ui(self):
        header = tk.Frame(self, bg=BG_DARK, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Car Counter", bg=BG_DARK, fg=FG_BRIGHT,
                 font=("Arial", 20, "bold")).pack()
        tk.Label(header, text="Conteo y seguimiento de vehículos en video",
                 bg=BG_DARK, fg=FG_DIM, font=("Arial", 10)).pack()

        self._step_bar = tk.Frame(self, bg=BG_DARK, pady=6)
        self._step_bar.pack(fill="x")
        self._step_labels = []
        for name in ("1. Modelo", "2. Video", "3. Perfil y ejecución"):
            lbl = tk.Label(self._step_bar, text=f"  {name}  ", bg=BG_DARK, fg=FG_DIM,
                           font=("Arial", 11), padx=16, pady=4)
            lbl.pack(side="left", padx=2)
            self._step_labels.append(lbl)

        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True, padx=24, pady=16)

        self._status = tk.StringVar(value="Elige un modelo para comenzar")
        tk.Label(self, textvariable=self._status, bg=BG_DARK, fg=GREEN,
                 font=("Courier", 9), anchor="w", padx=12, pady=4
                 ).pack(fill="x", side="bottom")

    def _show_step(self, idx):
        """Activa un step y despacha al builder del mixin correspondiente."""
        self._unbind_wheel()
        self._current_step = idx
        for i, lbl in enumerate(self._step_labels):
            if i < idx:
                lbl.config(bg="#313244", fg=GREEN, font=("Arial", 11, "bold"))
            elif i == idx:
                lbl.config(bg=ACCENT, fg=BG_DARK, font=("Arial", 11, "bold"))
            else:
                lbl.config(bg=BG_DARK, fg=FG_DIM, font=("Arial", 11))

        for w in self._content.winfo_children():
            w.destroy()
        self._cancel_btn = None

        if idx == 0:
            self._build_step_model()
        elif idx == 1:
            self._build_step_video()
        elif idx == 2:
            self._build_step_launch()

    def _on_close(self):
        if self._busy():
            if not messagebox.askyesno("Proceso en curso", "Hay un proceso en curso. ¿Cancelarlo y salir?"):
                return
            stop_process(self._process)
        self.destroy()


def launch():
    app = CarCounterApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
