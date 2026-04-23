"""Car Counter — Aplicacion principal con interfaz grafica.

Wizard: Modelo -> Video -> Configurar -> Ejecutar
Entry point: python -m carcounter

La construccion de cada paso vive en carcounter/app_steps/ (un mixin por paso).
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

from carcounter.app_steps import LaunchStepMixin, ModelStepMixin, VideoStepMixin
from carcounter.app_theme import ACCENT, BG, BG_DARK, FG_BRIGHT, FG_DIM, GREEN
from carcounter.models import MODEL_CATALOG
from carcounter.paths import paths


class CarCounterApp(ModelStepMixin, VideoStepMixin, LaunchStepMixin, tk.Tk):
    """Wizard principal de Car Counter — compone los 3 step mixins."""

    def __init__(self):
        super().__init__()
        self.title("Car Counter")
        self.geometry("780x640")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._selected_model = tk.StringVar(value="")
        self._selected_video = tk.StringVar(value="")
        self._selected_config = tk.StringVar(value="")
        self._selected_tracker = tk.StringVar(value="bytetrack")
        self._current_step = 0

        self._build_ui()
        self._show_step(0)

    # ── UI scaffolding ────────────────────────

    def _build_ui(self):
        header = tk.Frame(self, bg=BG_DARK, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Car Counter", bg=BG_DARK, fg=FG_BRIGHT,
                 font=("Arial", 20, "bold")).pack()
        tk.Label(header, text="Conteo y tracking de vehiculos con IA",
                 bg=BG_DARK, fg=FG_DIM, font=("Arial", 10)).pack()

        self._step_bar = tk.Frame(self, bg=BG_DARK, pady=6)
        self._step_bar.pack(fill="x")
        self._step_labels = []
        for name in ("1. Modelo", "2. Video", "3. Lanzar"):
            lbl = tk.Label(self._step_bar, text=f"  {name}  ", bg=BG_DARK, fg=FG_DIM,
                           font=("Arial", 11), padx=16, pady=4)
            lbl.pack(side="left", padx=2)
            self._step_labels.append(lbl)

        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True, padx=24, pady=16)

        self._status = tk.StringVar(value="Selecciona un modelo para comenzar")
        tk.Label(self, textvariable=self._status, bg=BG_DARK, fg=GREEN,
                 font=("Courier", 9), anchor="w", padx=12, pady=4
                 ).pack(fill="x", side="bottom")

    def _show_step(self, idx):
        """Activa un step y despacha al builder del mixin correspondiente."""
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

        if idx == 0:
            self._build_step_model()
        elif idx == 1:
            self._build_step_video()
        elif idx == 2:
            self._build_step_launch()

    # ── Actions (compartidas entre steps) ─────

    def _get_model_path(self):
        name = self._selected_model.get()
        info = MODEL_CATALOG.get(name, {})
        if info.get("family") == "yolo":
            from carcounter.models import get_model_path
            return get_model_path(name) or str(paths.default_model)
        return str(paths.default_model)

    def _open_setup(self):
        video = self._selected_video.get()
        if not video:
            messagebox.showwarning("Video", "Selecciona un video primero")
            return

        self._status.set("Abriendo configurador...")
        self.update()

        argv = ["setup.py", "--video", video]
        config = self._selected_config.get()
        if config and os.path.exists(config):
            argv.extend(["--config", config])

        self.withdraw()
        try:
            import setup
            setup.DEFAULT_VIDEO = video
            setup.MODEL_PATH = self._get_model_path()
            old_argv = sys.argv
            sys.argv = argv
            setup_app = setup.SetupApp()
            setup_app.mainloop()
            sys.argv = old_argv
            if paths.default_config.exists():
                self._selected_config.set(str(paths.default_config))
                self._status.set("Configuracion guardada")
        except Exception as e:
            messagebox.showerror("Error", f"Error en configurador:\n{e}")
            self._status.set(f"Error: {e}")
        finally:
            self.deiconify()
            self._show_step(2)

    def _run_processing(self):
        video = self._selected_video.get()
        config = self._selected_config.get()
        if not video:
            messagebox.showwarning("Video", "Selecciona un video primero")
            return
        if not config or not os.path.exists(config):
            messagebox.showwarning("Config", "Configura las zonas primero (boton Configurar)")
            return

        model_name = self._selected_model.get()
        model_info = MODEL_CATALOG.get(model_name, {})
        tracker = self._selected_tracker.get()

        cmd_parts = [
            sys.executable, "main.py",
            "--config", config,
            "--video", video,
            "--tracker", tracker,
            "--show-fps",
        ]

        if model_info.get("family") == "rfdetr":
            cmd_parts.extend(["--detector", "rfdetr",
                              "--rfdetr-variant", model_info.get("variant", "base")])
        else:
            cmd_parts.extend(["--model", self._get_model_path()])

        self._status.set(f"Ejecutando: {model_name} + {tracker}...")
        self.update()

        self.withdraw()
        try:
            result = subprocess.run(cmd_parts, cwd=str(paths.root))
            if result.returncode == 0:
                self._status.set("Procesamiento completado")
            else:
                self._status.set(f"Proceso termino con codigo {result.returncode}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._status.set(f"Error: {e}")
        finally:
            self.deiconify()


def launch():
    app = CarCounterApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
