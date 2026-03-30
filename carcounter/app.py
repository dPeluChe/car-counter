"""Car Counter — Aplicacion principal con interfaz grafica.

Wizard: Modelo -> Video -> Configurar -> Ejecutar
Entry point: python -m carcounter
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from carcounter.paths import paths
from carcounter.models import MODEL_CATALOG, is_downloaded, download_model

# ── Colores ───────────────────────────────────

BG = "#1E1E2E"
BG_DARK = "#11111B"
BG_CARD = "#181825"
BG_ROW = "#1A1A2E"
FG = "#CDD6F4"
FG_DIM = "#A6ADC8"
FG_BRIGHT = "#FFFFFF"
ACCENT = "#89B4FA"
GREEN = "#A6E3A1"
YELLOW = "#F9E2AF"
RED = "#F38BA8"
PEACH = "#FAB387"


class CarCounterApp(tk.Tk):
    """Wizard principal de Car Counter."""

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

    # ── UI Layout ─────────────────────────────

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG_DARK, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Car Counter", bg=BG_DARK, fg=FG_BRIGHT,
                 font=("Arial", 20, "bold")).pack()
        tk.Label(header, text="Conteo y tracking de vehiculos con IA",
                 bg=BG_DARK, fg=FG_DIM, font=("Arial", 10)).pack()

        # Step indicators
        self._step_bar = tk.Frame(self, bg=BG_DARK, pady=6)
        self._step_bar.pack(fill="x")
        self._step_labels = []
        steps = ["1. Modelo", "2. Video", "3. Lanzar"]
        for i, name in enumerate(steps):
            lbl = tk.Label(self._step_bar, text=f"  {name}  ", bg=BG_DARK, fg=FG_DIM,
                           font=("Arial", 11), padx=16, pady=4)
            lbl.pack(side="left", padx=2)
            self._step_labels.append(lbl)

        # Content container
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True, padx=24, pady=16)

        # Status bar
        self._status = tk.StringVar(value="Selecciona un modelo para comenzar")
        tk.Label(self, textvariable=self._status, bg=BG_DARK, fg=GREEN,
                 font=("Courier", 9), anchor="w", padx=12, pady=4).pack(fill="x", side="bottom")

    def _show_step(self, idx):
        self._current_step = idx
        # Update step bar
        for i, lbl in enumerate(self._step_labels):
            if i < idx:
                lbl.config(bg="#313244", fg=GREEN, font=("Arial", 11, "bold"))
            elif i == idx:
                lbl.config(bg=ACCENT, fg=BG_DARK, font=("Arial", 11, "bold"))
            else:
                lbl.config(bg=BG_DARK, fg=FG_DIM, font=("Arial", 11))

        # Clear content
        for w in self._content.winfo_children():
            w.destroy()

        if idx == 0:
            self._build_step_model()
        elif idx == 1:
            self._build_step_video()
        elif idx == 2:
            self._build_step_launch()

    # ── Step 1: Modelo ────────────────────────

    def _build_step_model(self):
        f = self._content

        tk.Label(f, text="Selecciona un modelo de deteccion",
                 bg=BG, fg=FG_BRIGHT, font=("Arial", 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(f, text="AP50 = precision en COCO (mayor es mejor). Latencia medida en NVIDIA T4 FP16.",
                 bg=BG, fg=FG_DIM, font=("Arial", 9), anchor="w").pack(fill="x", pady=(0, 10))

        # Scrollable model list
        list_frame = tk.Frame(f, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_DARK)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._model_rows = {}

        for family_label, family_key, desc in [
            ("YOLO", "yolo", "Rapido, versatil, ideal para tiempo real"),
            ("RF-DETR", "rfdetr", "Transformer DINOv2, mayor precision (+9 AP50 sobre YOLO)"),
        ]:
            # Family header
            fh = tk.Frame(inner, bg="#313244", pady=4)
            fh.pack(fill="x", pady=(8, 0))
            tk.Label(fh, text=f"  {family_label}", bg="#313244", fg=ACCENT,
                     font=("Arial", 11, "bold"), anchor="w").pack(side="left")
            tk.Label(fh, text=f"  {desc}", bg="#313244", fg=FG_DIM,
                     font=("Arial", 9), anchor="w").pack(side="left", padx=8)

            for name, info in MODEL_CATALOG.items():
                if info["family"] != family_key:
                    continue

                downloaded = is_downloaded(name)
                selected = (self._selected_model.get() == name)

                row_bg = "#2A2A3E" if selected else BG_CARD
                row = tk.Frame(inner, bg=row_bg, pady=6, padx=12)
                row.pack(fill="x", pady=1)

                # Left: model name + note
                left = tk.Frame(row, bg=row_bg)
                left.pack(side="left", fill="x", expand=True)

                name_fg = GREEN if downloaded else FG
                tk.Label(left, text=name, bg=row_bg, fg=name_fg,
                         font=("Courier", 11, "bold"), anchor="w").pack(fill="x")
                tk.Label(left, text=info.get("note", ""), bg=row_bg, fg=FG_DIM,
                         font=("Arial", 8), anchor="w").pack(fill="x")

                # Center: metrics
                center = tk.Frame(row, bg=row_bg)
                center.pack(side="left", padx=16)

                # AP50 with color coding
                ap = info["coco_ap50"]
                ap_fg = GREEN if ap >= 70 else (YELLOW if ap >= 60 else FG)
                tk.Label(center, text=f"AP50: {ap:.1f}", bg=row_bg, fg=ap_fg,
                         font=("Courier", 10, "bold"), width=11, anchor="w").pack(side="left")
                tk.Label(center, text=f"{info['latency_ms']}ms", bg=row_bg, fg=FG_DIM,
                         font=("Courier", 9), width=7, anchor="w").pack(side="left")
                tk.Label(center, text=f"{info['size_mb']}MB", bg=row_bg, fg=FG_DIM,
                         font=("Courier", 9), width=6, anchor="w").pack(side="left")

                # Right: status + action button
                right = tk.Frame(row, bg=row_bg)
                right.pack(side="right")

                if downloaded:
                    btn = tk.Button(right, text="Seleccionar", bg=GREEN, fg=BG_DARK,
                                    font=("Arial", 9, "bold"), relief="flat", width=11,
                                    command=lambda n=name: self._select_model(n))
                else:
                    btn = tk.Button(right, text="Descargar", bg=ACCENT, fg=BG_DARK,
                                    font=("Arial", 9, "bold"), relief="flat", width=11,
                                    command=lambda n=name: self._download_and_refresh(n))
                btn.pack()

                self._model_rows[name] = (row, btn)

    def _select_model(self, name):
        self._selected_model.set(name)
        info = MODEL_CATALOG[name]
        self._status.set(f"Modelo: {name}  (AP50={info['coco_ap50']}, {info['latency_ms']}ms)")
        self._show_step(1)

    def _download_and_refresh(self, name):
        self._status.set(f"Descargando {name}...")
        self.update()
        ok = download_model(name)
        if ok:
            self._status.set(f"{name} descargado")
            self._select_model(name)
        else:
            self._status.set(f"Error descargando {name}")
            self._show_step(0)  # Refresh

    # ── Step 2: Video ─────────────────────────

    def _build_step_video(self):
        f = self._content
        model = self._selected_model.get()
        info = MODEL_CATALOG.get(model, {})

        # Model summary
        summary = tk.Frame(f, bg=BG_CARD, padx=12, pady=8)
        summary.pack(fill="x")
        tk.Label(summary, text=f"Modelo: {model}", bg=BG_CARD, fg=GREEN,
                 font=("Arial", 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(summary, text=f"{info.get('note', '')}  |  AP50: {info.get('coco_ap50', '')}  |  {info.get('latency_ms', '')}ms",
                 bg=BG_CARD, fg=FG_DIM, font=("Arial", 9), anchor="w").pack(fill="x")

        tk.Label(f, text="", bg=BG).pack(pady=4)
        tk.Label(f, text="Selecciona el video a procesar",
                 bg=BG, fg=FG_BRIGHT, font=("Arial", 14, "bold"), anchor="w").pack(fill="x")

        # Video list from assets/
        assets = paths.assets_dir
        videos = []
        if assets.exists():
            videos = sorted(
                [fp for fp in assets.iterdir()
                 if fp.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv")],
                key=lambda fp: fp.stat().st_mtime, reverse=True
            )

        if videos:
            tk.Label(f, text=f"{len(videos)} videos en assets/",
                     bg=BG, fg=FG_DIM, font=("Arial", 9), anchor="w").pack(fill="x", pady=(2, 6))

            list_frame = tk.Frame(f, bg=BG_DARK)
            list_frame.pack(fill="both", expand=True)

            for vp in videos:
                size_mb = vp.stat().st_size / 1e6
                row = tk.Frame(list_frame, bg=BG_CARD, pady=6, padx=12)
                row.pack(fill="x", pady=1)

                tk.Label(row, text=vp.name, bg=BG_CARD, fg=FG,
                         font=("Courier", 10, "bold"), anchor="w").pack(side="left")
                tk.Label(row, text=f"{size_mb:.0f} MB", bg=BG_CARD, fg=FG_DIM,
                         font=("Courier", 9)).pack(side="left", padx=12)

                tk.Button(row, text="Usar", bg=GREEN, fg=BG_DARK,
                          font=("Arial", 9, "bold"), relief="flat", width=8,
                          command=lambda p=str(vp): self._select_video(p)).pack(side="right")
        else:
            tk.Label(f, text="No hay videos en assets/", bg=BG, fg=YELLOW,
                     font=("Arial", 10)).pack(pady=20)

        # Manual picker
        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x", pady=(12, 0))
        tk.Button(btn_row, text="Buscar otro video...", bg="#313244", fg=FG,
                  font=("Arial", 10), relief="flat", padx=16, pady=6,
                  command=self._pick_video_file).pack(side="left")
        tk.Button(btn_row, text="Atras", bg="#313244", fg=FG_DIM,
                  font=("Arial", 10), relief="flat", padx=16, pady=6,
                  command=lambda: self._show_step(0)).pack(side="right")

    def _select_video(self, path):
        self._selected_video.set(path)
        name = os.path.basename(path)
        self._status.set(f"Video: {name}")
        self._show_step(2)

    def _pick_video_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV *.MP4"), ("Todos", "*.*")])
        if path:
            self._select_video(path)

    # ── Step 3: Lanzar ────────────────────────

    def _build_step_launch(self):
        f = self._content
        model_name = self._selected_model.get()
        model_info = MODEL_CATALOG.get(model_name, {})
        video = self._selected_video.get()
        video_name = os.path.basename(video)

        tk.Label(f, text="Todo listo para procesar",
                 bg=BG, fg=FG_BRIGHT, font=("Arial", 14, "bold"), anchor="w").pack(fill="x")

        # Summary card
        card = tk.Frame(f, bg=BG_CARD, padx=16, pady=12)
        card.pack(fill="x", pady=(10, 0))

        for label, value, color in [
            ("Modelo", f"{model_name}  (AP50: {model_info.get('coco_ap50', '?')})", GREEN),
            ("Video", video_name, FG),
        ]:
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:", bg=BG_CARD, fg=FG_DIM,
                     font=("Arial", 10), width=10, anchor="e").pack(side="left")
            tk.Label(row, text=f"  {value}", bg=BG_CARD, fg=color,
                     font=("Arial", 10, "bold"), anchor="w").pack(side="left")

        # Config
        config_card = tk.Frame(f, bg=BG_CARD, padx=16, pady=10)
        config_card.pack(fill="x", pady=(8, 0))

        cfg_row = tk.Frame(config_card, bg=BG_CARD)
        cfg_row.pack(fill="x")
        tk.Label(cfg_row, text="Config:", bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 10), width=10, anchor="e").pack(side="left")

        default_cfg = paths.default_config
        if default_cfg.exists():
            self._selected_config.set(str(default_cfg))
            tk.Label(cfg_row, text=f"  {default_cfg.name}", bg=BG_CARD, fg=GREEN,
                     font=("Arial", 10, "bold"), anchor="w").pack(side="left")
        else:
            tk.Label(cfg_row, text="  Sin config — ejecuta Configurar primero",
                     bg=BG_CARD, fg=YELLOW, font=("Arial", 10), anchor="w").pack(side="left")

        tk.Button(cfg_row, text="Cargar otra", bg="#313244", fg=FG,
                  font=("Arial", 9), relief="flat", padx=8,
                  command=self._pick_config_file).pack(side="right")

        # Tracker selector
        tracker_card = tk.Frame(f, bg=BG_CARD, padx=16, pady=10)
        tracker_card.pack(fill="x", pady=(8, 0))

        tk.Label(tracker_card, text="Tracker:", bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 10)).pack(side="left")

        tracker_info = {
            "bytetrack": ("ByteTrack", "Rapido, buen default"),
            "sort": ("SORT", "Simple, sin dependencias extra"),
            "ocsort": ("OC-SORT", "Mejor con oclusiones"),
        }
        for val, (label, tip) in tracker_info.items():
            rb = tk.Radiobutton(tracker_card, text=f"{label}", variable=self._selected_tracker,
                                value=val, bg=BG_CARD, fg=FG_BRIGHT, selectcolor=ACCENT,
                                activebackground=BG_CARD, activeforeground=FG_BRIGHT,
                                indicatoron=0, padx=12, pady=4, relief="flat",
                                font=("Arial", 9, "bold"), bd=0)
            rb.pack(side="left", padx=4)

        # RF-DETR can't use native ByteTrack
        if model_info.get("family") == "rfdetr":
            self._selected_tracker.set("sort")

        # Action buttons
        actions = tk.Frame(f, bg=BG)
        actions.pack(fill="x", pady=(20, 0))

        tk.Button(actions, text="Configurar zonas",
                  command=self._open_setup,
                  bg=ACCENT, fg=BG_DARK, font=("Arial", 12, "bold"),
                  relief="flat", padx=24, pady=10).pack(side="left", padx=(0, 8))

        tk.Button(actions, text="Ejecutar",
                  command=self._run_processing,
                  bg=GREEN, fg=BG_DARK, font=("Arial", 12, "bold"),
                  relief="flat", padx=24, pady=10).pack(side="left", padx=(0, 8))

        tk.Button(actions, text="Atras", bg="#313244", fg=FG_DIM,
                  font=("Arial", 10), relief="flat", padx=16, pady=10,
                  command=lambda: self._show_step(1)).pack(side="right")

    def _pick_config_file(self):
        path = filedialog.askopenfilename(
            title="Cargar configuracion",
            initialdir=str(paths.config_dir),
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if path:
            self._selected_config.set(path)
            self._status.set(f"Config: {os.path.basename(path)}")
            self._show_step(2)  # Refresh

    # ── Actions ───────────────────────────────

    def _get_model_path(self):
        """Retorna el path del modelo seleccionado para pasarlo al setup/main."""
        name = self._selected_model.get()
        info = MODEL_CATALOG.get(name, {})
        if info.get("family") == "yolo":
            from carcounter.models import get_model_path
            return get_model_path(name) or str(paths.default_model)
        # RF-DETR uses its own loader, return default YOLO for setup compatibility
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
            old_argv = sys.argv
            sys.argv = argv
            setup_app = setup.SetupApp()
            setup_app._model_path = self._get_model_path()
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
            model_path = self._get_model_path()
            cmd_parts.extend(["--model", model_path])

        self._status.set(f"Ejecutando: {model_name} + {tracker}...")
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


def launch():
    """Entry point principal."""
    app = CarCounterApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
