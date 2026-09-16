"""Step 3 del wizard: perfil, tracker y lanzamiento."""

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from carcounter.app_theme import ACCENT, BG, BG_CARD, BG_DARK, FG, FG_BRIGHT, FG_DIM, GREEN, RED, YELLOW, btn
from carcounter.paths import paths
from carcounter.wizard_actions import profile_rows


class LaunchStepMixin:
    """Construccion del paso 3 (perfil y ejecución) + selección de perfil."""

    def _build_step_launch(self):
        f = self._content
        tk.Label(f, text="Perfil y ejecución", bg=BG, fg=FG_BRIGHT,
                 font=("Arial", 14, "bold"), anchor="w").pack(fill="x")
        self._render_summary_card(f)
        self._render_config_card(f)
        self._render_tracker_card(f)
        self._render_action_buttons(f)

    def _render_summary_card(self, parent):
        card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=12)
        card.pack(fill="x", pady=(10, 0))
        model = self._model_choice()
        video = self._selected_video.get()
        rows = [
            ("Modelo", model.label or model.error or "sin elegir", GREEN if not model.error else RED),
            ("Video", os.path.basename(video) if video else "sin elegir", FG if video else YELLOW),
        ]
        rows += [(label, value, FG_DIM) for label, value in profile_rows(self._profile())]
        for label, value, color in rows:
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:", bg=BG_CARD, fg=FG_DIM,
                     font=("Arial", 10), width=14, anchor="e").pack(side="left")
            tk.Label(row, text=f"  {value}", bg=BG_CARD, fg=color, font=("Arial", 10, "bold"),
                     anchor="w", wraplength=520, justify="left").pack(side="left")

    def _render_config_card(self, parent):
        config_card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=10)
        config_card.pack(fill="x", pady=(8, 0))
        cfg_row = tk.Frame(config_card, bg=BG_CARD)
        cfg_row.pack(fill="x")
        tk.Label(cfg_row, text="Perfil:", bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 10), width=14, anchor="e").pack(side="left")

        config = self._selected_config.get()
        if config and Path(config).is_file():
            text, color = f"  {Path(config).name}", GREEN
        elif config:
            text, color = f"  {Path(config).name} (se creará al guardar en el configurador)", YELLOW
        else:
            text, color = "  Sin perfil: cárgalo o créalo con Configurar zonas", YELLOW
        tk.Label(cfg_row, text=text, bg=BG_CARD, fg=color,
                 font=("Arial", 10, "bold"), anchor="w").pack(side="left")
        btn(cfg_row, "Cargar otro" if config else "Cargar perfil", font=("Arial", 9),
            command=self._pick_config_file).pack(side="right")

    def _render_tracker_card(self, parent):
        tracker_card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=10)
        tracker_card.pack(fill="x", pady=(8, 0))
        tk.Label(tracker_card, text="Tracker:", bg=BG_CARD, fg=FG_DIM, font=("Arial", 10)).pack(side="left")
        # Todos reciben cajas de cualquier detector (YOLO, SAHI o RF-DETR); no se fuerza SORT
        for val, label in (("bytetrack", "ByteTrack"), ("botsort", "BoT-SORT"), ("sort", "SORT"), ("ocsort", "OC-SORT")):
            tk.Radiobutton(
                tracker_card, text=label, variable=self._selected_tracker, value=val,
                bg=BG_CARD, fg=FG_BRIGHT, selectcolor=ACCENT,
                activebackground=BG_CARD, activeforeground=FG_BRIGHT,
                font=("Arial", 9, "bold"), indicatoron=1, padx=8, pady=2,
            ).pack(side="left", padx=4)

    def _render_action_buttons(self, parent):
        tk.Label(parent, text="Cada ejecución guarda video, results.json, tracks.csv, od_matrix.csv y run.log "
                              "en una carpeta nueva dentro de output/.",
                 bg=BG, fg=FG_DIM, font=("Arial", 9), anchor="w", wraplength=740, justify="left"
                 ).pack(fill="x", pady=(14, 0))
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=(10, 0))
        btn(actions, "Atrás", fg=FG_DIM, command=lambda: self._show_step(1)).pack(side="left")
        if self._run_dir is not None:
            btn(actions, "Abrir última salida", font=("Arial", 9),
                command=lambda: self._open_output_folder(self._run_dir)).pack(side="left", padx=(8, 0))
        self._cancel_btn = btn(actions, "Cancelar", bg=RED, fg=BG_DARK, font=("Arial", 11, "bold"),
                               command=self._cancel_run,
                               state="normal" if self._busy() else "disabled")
        self._cancel_btn.pack(side="right", padx=(8, 0))
        btn(actions, "Ejecutar", bg=GREEN, fg=BG_DARK, font=("Arial", 12, "bold"),
            command=self._run_processing).pack(side="right", padx=(8, 0))
        btn(actions, "Configurar zonas", bg=ACCENT, fg=BG_DARK, font=("Arial", 12, "bold"),
            command=self._open_setup).pack(side="right")

    def _pick_config_file(self):
        path = filedialog.askopenfilename(
            title="Cargar perfil",
            initialdir=str(paths.config_dir),
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if path:
            self._selected_config.set(path)
            self._status.set(f"Perfil: {os.path.basename(path)}")
            self._show_step(2)
