"""Car Counter — Aplicacion principal con interfaz grafica.

Entry point unificado: seleccionar video, configurar, ejecutar, ver resultados.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from carcounter.paths import paths
from carcounter.models import MODEL_CATALOG, is_downloaded, list_models


# ── Colores ───────────────────────────────────

BG = "#1E1E2E"
BG_DARK = "#11111B"
BG_CARD = "#181825"
FG = "#CDD6F4"
FG_DIM = "#A6ADC8"
ACCENT = "#89B4FA"
GREEN = "#A6E3A1"
RED = "#F38BA8"


class HomeScreen(tk.Tk):
    """Pantalla principal de Car Counter."""

    def __init__(self):
        super().__init__()
        self.title("Car Counter")
        self.geometry("700x600")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._selected_video = tk.StringVar(value="")
        self._selected_config = tk.StringVar(value="")
        self._selected_detector = tk.StringVar(value="yolo")
        self._selected_tracker = tk.StringVar(value="bytetrack")
        self._selected_rfdetr_variant = tk.StringVar(value="base")

        self._build_ui()

    def _build_ui(self):
        # ── Header ──
        header = tk.Frame(self, bg=BG_DARK, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="Car Counter", bg=BG_DARK, fg=FG,
                 font=("Arial", 22, "bold")).pack()
        tk.Label(header, text="Conteo y tracking de vehiculos con IA",
                 bg=BG_DARK, fg=FG_DIM, font=("Arial", 10)).pack()

        # ── Content ──
        content = tk.Frame(self, bg=BG, padx=30, pady=20)
        content.pack(fill="both", expand=True)

        # Video selector
        self._card(content, "1. Video", self._build_video_card)

        # Config selector
        self._card(content, "2. Configuracion", self._build_config_card)

        # Detector/Tracker
        self._card(content, "3. Detector y Tracker", self._build_detector_card)

        # ── Action buttons ──
        actions = tk.Frame(content, bg=BG)
        actions.pack(fill="x", pady=(16, 0))

        tk.Button(actions, text="Configurar",
                  command=self._open_setup,
                  bg=ACCENT, fg=BG_DARK, font=("Arial", 12, "bold"),
                  relief="flat", padx=20, pady=8).pack(side="left", padx=(0, 8))

        tk.Button(actions, text="Ejecutar",
                  command=self._run_processing,
                  bg=GREEN, fg=BG_DARK, font=("Arial", 12, "bold"),
                  relief="flat", padx=20, pady=8).pack(side="left", padx=(0, 8))

        tk.Button(actions, text="Modelos",
                  command=self._open_model_manager,
                  bg=BG_CARD, fg=GREEN, font=("Arial", 11),
                  relief="flat", padx=16, pady=8).pack(side="right")

        # ── Status bar ──
        self._status = tk.StringVar(value="Selecciona un video para comenzar")
        tk.Label(self, textvariable=self._status, bg=BG_DARK, fg=GREEN,
                 font=("Courier", 9), anchor="w", padx=12, pady=4).pack(fill="x", side="bottom")

    def _card(self, parent, title, builder_fn):
        """Crea una card visual con titulo y contenido."""
        frame = tk.Frame(parent, bg=BG_CARD, padx=16, pady=10)
        frame.pack(fill="x", pady=(0, 8))
        tk.Label(frame, text=title, bg=BG_CARD, fg=ACCENT,
                 font=("Arial", 11, "bold"), anchor="w").pack(fill="x")
        builder_fn(frame)

    def _build_video_card(self, parent):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=(4, 0))

        self._lbl_video = tk.Label(row, text="Ningun video seleccionado",
                                    bg=BG_CARD, fg=FG_DIM, font=("Arial", 9), anchor="w")
        self._lbl_video.pack(side="left", fill="x", expand=True)

        tk.Button(row, text="Seleccionar", command=self._pick_video,
                  bg="#313244", fg=FG, relief="flat", padx=10).pack(side="right")

        # Check for recent videos in assets/
        assets = paths.assets_dir
        if assets.exists():
            videos = sorted(
                [f for f in assets.iterdir()
                 if f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv")],
                key=lambda f: f.stat().st_mtime, reverse=True
            )
            if videos:
                self._selected_video.set(str(videos[0]))
                self._lbl_video.config(
                    text=f"{videos[0].name}  ({videos[0].stat().st_size / 1e6:.0f} MB)",
                    fg=FG)

    def _build_config_card(self, parent):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=(4, 0))

        self._lbl_config = tk.Label(row, text="Sin config (se creara en el setup)",
                                     bg=BG_CARD, fg=FG_DIM, font=("Arial", 9), anchor="w")
        self._lbl_config.pack(side="left", fill="x", expand=True)

        tk.Button(row, text="Cargar", command=self._pick_config,
                  bg="#313244", fg=FG, relief="flat", padx=10).pack(side="right")

        # Auto-detect existing config
        default_cfg = paths.default_config
        if default_cfg.exists():
            self._selected_config.set(str(default_cfg))
            self._lbl_config.config(text=f"{default_cfg.name}", fg=GREEN)

    def _build_detector_card(self, parent):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=(4, 0))

        # Detector
        tk.Label(row, text="Detector:", bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 9)).pack(side="left")
        for val, label in [("yolo", "YOLO"), ("rfdetr", "RF-DETR")]:
            tk.Radiobutton(row, text=label, variable=self._selected_detector,
                           value=val, bg=BG_CARD, fg=FG, selectcolor=BG_DARK,
                           activebackground=BG_CARD, activeforeground=FG,
                           font=("Arial", 9)).pack(side="left", padx=4)

        tk.Label(row, text="   Tracker:", bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 9)).pack(side="left")
        for val, label in [("bytetrack", "ByteTrack"), ("sort", "SORT"), ("ocsort", "OC-SORT")]:
            tk.Radiobutton(row, text=label, variable=self._selected_tracker,
                           value=val, bg=BG_CARD, fg=FG, selectcolor=BG_DARK,
                           activebackground=BG_CARD, activeforeground=FG,
                           font=("Arial", 9)).pack(side="left", padx=4)

    # ── Actions ───────────────────────────────

    def _pick_video(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV *.MP4"), ("Todos", "*.*")])
        if path:
            self._selected_video.set(path)
            name = os.path.basename(path)
            size = os.path.getsize(path) / 1e6
            self._lbl_video.config(text=f"{name}  ({size:.0f} MB)", fg=FG)
            self._status.set(f"Video: {name}")

    def _pick_config(self):
        path = filedialog.askopenfilename(
            title="Cargar configuracion",
            initialdir=str(paths.config_dir),
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if path:
            self._selected_config.set(path)
            self._lbl_config.config(text=os.path.basename(path), fg=GREEN)
            self._status.set(f"Config: {os.path.basename(path)}")

    def _open_setup(self):
        """Abre el configurador (setup.py) con el video seleccionado."""
        video = self._selected_video.get()
        if not video:
            messagebox.showwarning("Video", "Selecciona un video primero")
            return

        self._status.set("Abriendo configurador...")
        self.update()

        # Build argv for setup
        argv = ["setup.py", "--video", video]
        config = self._selected_config.get()
        if config and os.path.exists(config):
            argv.extend(["--config", config])

        # Import and launch setup in-process
        self.withdraw()
        try:
            import setup
            old_argv = sys.argv
            sys.argv = argv
            app = setup.SetupApp()
            app.mainloop()
            sys.argv = old_argv
            # After setup closes, check if config was created
            if paths.default_config.exists():
                self._selected_config.set(str(paths.default_config))
                self._lbl_config.config(text=paths.default_config.name, fg=GREEN)
                self._status.set("Configuracion guardada")
        except Exception as e:
            messagebox.showerror("Error", f"Error en configurador:\n{e}")
            self._status.set(f"Error: {e}")
        finally:
            self.deiconify()

    def _run_processing(self):
        """Ejecuta el procesamiento del video."""
        video = self._selected_video.get()
        config = self._selected_config.get()
        if not video:
            messagebox.showwarning("Video", "Selecciona un video primero")
            return
        if not config or not os.path.exists(config):
            messagebox.showwarning("Config", "Crea o carga una configuracion primero")
            return

        detector = self._selected_detector.get()
        tracker = self._selected_tracker.get()

        # Build CLI args
        cmd_parts = [
            sys.executable, "main.py",
            "--config", config,
            "--video", video,
            "--detector", detector,
            "--tracker", tracker,
            "--show-fps",
        ]
        if detector == "rfdetr":
            cmd_parts.extend(["--rfdetr-variant", self._selected_rfdetr_variant.get()])

        self._status.set(f"Ejecutando: {detector} + {tracker}...")
        self.update()

        import subprocess
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

    def _open_model_manager(self):
        """Abre el gestor de modelos como dialogo."""
        # Reutiliza el dialogo del setup
        from carcounter.models import download_model, get_model_path

        dlg = tk.Toplevel(self)
        dlg.title("Gestor de Modelos")
        dlg.geometry("750x520")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Gestor de Modelos", bg=BG, fg=FG,
                 font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(dlg, text="Descarga modelos de deteccion", bg=BG, fg=FG_DIM,
                 font=("Arial", 9)).pack()

        table_frame = tk.Frame(dlg, bg=BG_DARK)
        table_frame.pack(fill="both", expand=True, padx=12, pady=8)

        canvas_scroll = tk.Canvas(table_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(table_frame, orient="vertical", command=canvas_scroll.yview)
        inner = tk.Frame(canvas_scroll, bg=BG_DARK)
        inner.bind("<Configure>", lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.create_window((0, 0), window=inner, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas_scroll.pack(side="left", fill="both", expand=True)

        status_var = tk.StringVar(value="")
        row_widgets = {}

        def _refresh(name):
            if name in row_widgets:
                downloaded = is_downloaded(name)
                btn, lbl = row_widgets[name]
                lbl.config(text="OK" if downloaded else "--",
                           fg=GREEN if downloaded else RED)
                btn.config(text="Descargar" if not downloaded else "OK",
                           bg=ACCENT if not downloaded else "#313244",
                           state="normal" if not downloaded else "disabled")

        def _download(name):
            status_var.set(f"Descargando {name}...")
            dlg.update()
            ok = download_model(name)
            status_var.set(f"{'OK' if ok else 'Error'}: {name}")
            _refresh(name)
            dlg.update()

        for family_label, family_key in [("YOLO (ultralytics)", "yolo"),
                                          ("RF-DETR (Roboflow DINOv2)", "rfdetr")]:
            tk.Frame(inner, bg="#45475A", height=1).pack(fill="x", pady=4)
            tk.Label(inner, text=f"  {family_label}", bg=BG_DARK, fg=ACCENT,
                     font=("Arial", 10, "bold"), anchor="w").pack(fill="x")

            hdr = tk.Frame(inner, bg="#313244")
            hdr.pack(fill="x", pady=(2, 0))
            for txt, w in [("Modelo", 14), ("AP50", 6), ("Latencia", 8),
                           ("Params", 8), ("Tamaño", 7), ("", 4), ("", 10)]:
                tk.Label(hdr, text=txt, bg="#313244", fg=FG,
                         font=("Courier", 9, "bold"), width=w, anchor="w").pack(side="left", padx=1)

            for name, info in MODEL_CATALOG.items():
                if info["family"] != family_key:
                    continue
                downloaded = is_downloaded(name)

                row = tk.Frame(inner, bg=BG_CARD)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=name, bg=BG_CARD, fg=FG,
                         font=("Courier", 10), width=14, anchor="w").pack(side="left", padx=1)
                tk.Label(row, text=f"{info['coco_ap50']:.1f}", bg=BG_CARD, fg=GREEN,
                         font=("Courier", 10), width=6, anchor="w").pack(side="left", padx=1)
                tk.Label(row, text=f"{info['latency_ms']}ms", bg=BG_CARD, fg=FG,
                         font=("Courier", 10), width=8, anchor="w").pack(side="left", padx=1)
                tk.Label(row, text=info["params"], bg=BG_CARD, fg=FG_DIM,
                         font=("Courier", 9), width=8, anchor="w").pack(side="left", padx=1)
                tk.Label(row, text=f"{info['size_mb']}MB", bg=BG_CARD, fg=FG_DIM,
                         font=("Courier", 9), width=7, anchor="w").pack(side="left", padx=1)

                lbl = tk.Label(row, text="OK" if downloaded else "--", bg=BG_CARD,
                               font=("Courier", 9), width=4,
                               fg=GREEN if downloaded else RED)
                lbl.pack(side="left", padx=1)

                btn = tk.Button(row, text="Descargar" if not downloaded else "OK",
                                bg=ACCENT if not downloaded else "#313244", fg=BG_DARK,
                                font=("Arial", 9), relief="flat", width=10,
                                state="normal" if not downloaded else "disabled",
                                command=lambda n=name: _download(n))
                btn.pack(side="left", padx=4)

                row_widgets[name] = (btn, lbl)

        bottom = tk.Frame(dlg, bg=BG)
        bottom.pack(fill="x", padx=12, pady=8)
        tk.Label(bottom, textvariable=status_var, bg=BG, fg=GREEN,
                 font=("Courier", 9), anchor="w").pack(side="left")
        tk.Button(bottom, text="Cerrar", bg="#313244", fg=FG,
                  relief="flat", padx=16, command=dlg.destroy).pack(side="right")


def launch():
    """Entry point principal de Car Counter."""
    app = HomeScreen()
    app.mainloop()


if __name__ == "__main__":
    launch()
