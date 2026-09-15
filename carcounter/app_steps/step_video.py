"""Step 2 del wizard: seleccion de video."""

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from carcounter.app_theme import BG, BG_CARD, BG_DARK, FG, FG_DIM, GREEN, YELLOW, btn
from carcounter.paths import paths
from carcounter.wizard_actions import resolve_path


class VideoStepMixin:
    """Construccion del paso 2 (seleccion de video) + acciones."""

    def _build_step_video(self):
        f = self._content
        summary = tk.Frame(f, bg=BG_CARD, padx=12, pady=8)
        summary.pack(fill="x")
        tk.Label(summary, text=f"Modelo: {self._model_choice()['label'] or 'sin elegir'}", bg=BG_CARD, fg=GREEN,
                 font=("Arial", 11, "bold"), anchor="w").pack(fill="x")

        tk.Label(f, text="Elige el video a procesar", bg=BG, fg="#FFFFFF",
                 font=("Arial", 14, "bold"), anchor="w").pack(fill="x", pady=(12, 0))

        profile_video = resolve_path(self._profile().get("video_path", ""))
        if profile_video:
            card = tk.Frame(f, bg=BG_CARD, padx=12, pady=8)
            card.pack(fill="x", pady=(6, 0))
            exists = Path(profile_video).is_file()
            tk.Label(card, text=f"Video del perfil: {os.path.basename(profile_video)}"
                     + ("" if exists else " (no encontrado)"), bg=BG_CARD, fg=GREEN if exists else YELLOW,
                     font=("Arial", 10, "bold"), anchor="w").pack(side="left")
            if exists:
                btn(card, "Usar el del perfil", bg=GREEN, fg=BG_DARK, font=("Arial", 9, "bold"),
                    command=lambda: self._select_video(profile_video)).pack(side="right")

        videos = self._scan_videos()
        if videos:
            tk.Label(f, text=f"{len(videos)} videos en assets/", bg=BG, fg=FG_DIM,
                     font=("Arial", 9), anchor="w").pack(fill="x", pady=(8, 6))
            self._render_video_list(f, videos)
        else:
            tk.Label(f, text="No hay videos en assets/", bg=BG, fg=YELLOW,
                     font=("Arial", 10)).pack(pady=20)

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x", pady=(12, 0))
        btn(btn_row, "Atrás", fg=FG_DIM, command=lambda: self._show_step(0)).pack(side="left")
        btn(btn_row, "Buscar otro video...", command=self._pick_video_file).pack(side="right")

    def _scan_videos(self):
        """Lista videos en assets/ ordenados por mtime desc."""
        assets = paths.assets_dir
        if not assets.exists():
            return []
        return sorted(
            [fp for fp in assets.iterdir() if fp.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv")],
            key=lambda fp: fp.stat().st_mtime, reverse=True,
        )

    def _render_video_list(self, parent, videos):
        """Renderiza una fila por video con tamaño y botón Usar."""
        list_frame = tk.Frame(parent, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True)
        for vp in videos:
            row = tk.Frame(list_frame, bg=BG_CARD, pady=6, padx=12)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=vp.name, bg=BG_CARD, fg=FG,
                     font=("Courier", 10, "bold"), anchor="w").pack(side="left")
            tk.Label(row, text=f"{vp.stat().st_size / 1e6:.0f} MB", bg=BG_CARD, fg=FG_DIM,
                     font=("Courier", 9)).pack(side="left", padx=12)
            btn(row, "Usar", bg=GREEN, fg="#11111B", font=("Arial", 9, "bold"), width=8,
                command=lambda p=str(vp): self._select_video(p)).pack(side="right")

    def _select_video(self, path):
        self._selected_video.set(path)
        self._status.set(f"Video: {os.path.basename(path)}")
        self._show_step(2)

    def _pick_video_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV *.MP4 *.AVI *.MKV"), ("Todos", "*.*")])
        if path:
            self._select_video(path)
