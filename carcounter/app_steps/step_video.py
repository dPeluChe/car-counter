"""Step 2 del wizard: seleccion de video."""

import os
import tkinter as tk
from tkinter import filedialog

from carcounter.app_theme import (
    BG, BG_CARD, BG_DARK, FG, FG_DIM, GREEN, YELLOW, btn,
)
from carcounter.models import MODEL_CATALOG
from carcounter.paths import paths


class VideoStepMixin:
    """Construccion del paso 2 (seleccion de video) + acciones."""

    def _build_step_video(self):
        f = self._content
        model = self._selected_model.get()
        info = MODEL_CATALOG.get(model, {})

        # Resumen del modelo
        summary = tk.Frame(f, bg=BG_CARD, padx=12, pady=8)
        summary.pack(fill="x")
        tk.Label(summary, text=f"Modelo: {model}", bg=BG_CARD, fg=GREEN,
                 font=("Arial", 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(summary,
                 text=f"{info.get('note', '')}  |  AP50: {info.get('coco_ap50', '')}  |  {info.get('latency_ms', '')}ms",
                 bg=BG_CARD, fg=FG_DIM, font=("Arial", 9),
                 anchor="w").pack(fill="x")

        tk.Label(f, text="", bg=BG).pack(pady=4)
        tk.Label(f, text="Selecciona el video a procesar",
                 bg=BG, fg="#FFFFFF", font=("Arial", 14, "bold"),
                 anchor="w").pack(fill="x")

        # Lista de videos de assets/
        videos = self._scan_videos()
        if videos:
            tk.Label(f, text=f"{len(videos)} videos en assets/",
                     bg=BG, fg=FG_DIM, font=("Arial", 9),
                     anchor="w").pack(fill="x", pady=(2, 6))
            self._render_video_list(f, videos)
        else:
            tk.Label(f, text="No hay videos en assets/", bg=BG, fg=YELLOW,
                     font=("Arial", 10)).pack(pady=20)

        # Botones inferiores
        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x", pady=(12, 0))
        btn(btn_row, "Atras", fg=FG_DIM,
            command=lambda: self._show_step(0)).pack(side="left")
        btn(btn_row, "Buscar otro video...",
            command=self._pick_video_file).pack(side="right")

    def _scan_videos(self):
        """Lista videos en assets/ ordenados por mtime desc."""
        assets = paths.assets_dir
        if not assets.exists():
            return []
        return sorted(
            [fp for fp in assets.iterdir()
             if fp.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv")],
            key=lambda fp: fp.stat().st_mtime, reverse=True,
        )

    def _render_video_list(self, parent, videos):
        """Renderiza una fila por video con tamano y boton Usar."""
        list_frame = tk.Frame(parent, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True)
        for vp in videos:
            size_mb = vp.stat().st_size / 1e6
            row = tk.Frame(list_frame, bg=BG_CARD, pady=6, padx=12)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=vp.name, bg=BG_CARD, fg=FG,
                     font=("Courier", 10, "bold"), anchor="w").pack(side="left")
            tk.Label(row, text=f"{size_mb:.0f} MB", bg=BG_CARD, fg=FG_DIM,
                     font=("Courier", 9)).pack(side="left", padx=12)
            btn(row, "Usar", bg=GREEN, fg="#11111B",
                font=("Arial", 9, "bold"), width=8,
                command=lambda p=str(vp): self._select_video(p)).pack(side="right")

    def _select_video(self, path):
        self._selected_video.set(path)
        self._status.set(f"Video: {os.path.basename(path)}")
        self._show_step(2)

    def _pick_video_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV *.MP4"),
                       ("Todos", "*.*")])
        if path:
            self._select_video(path)
