"""Step 3 del wizard: configuracion final y lanzamiento del pipeline."""

import os
import tkinter as tk
from tkinter import filedialog

from carcounter.app_theme import (
    ACCENT, BG, BG_CARD, BG_DARK, BTN_BG, FG, FG_BRIGHT, FG_DIM, GREEN, YELLOW, btn,
)
from carcounter.models import MODEL_CATALOG
from carcounter.paths import paths


class LaunchStepMixin:
    """Construccion del paso 3 (lanzamiento) + accion pick_config."""

    def _build_step_launch(self):
        f = self._content
        model_name = self._selected_model.get()
        model_info = MODEL_CATALOG.get(model_name, {})
        video = self._selected_video.get()

        tk.Label(f, text="Todo listo para procesar",
                 bg=BG, fg=FG_BRIGHT, font=("Arial", 14, "bold"),
                 anchor="w").pack(fill="x")

        self._render_summary_card(f, model_name, model_info, video)
        self._render_config_card(f)
        self._render_tracker_card(f, model_info)
        self._render_action_buttons(f)

    def _render_summary_card(self, parent, model_name, model_info, video):
        card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=12)
        card.pack(fill="x", pady=(10, 0))
        rows = [
            ("Modelo", f"{model_name}  (AP50: {model_info.get('coco_ap50', '?')})", GREEN),
            ("Video", os.path.basename(video), FG),
        ]
        for label, value, color in rows:
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:", bg=BG_CARD, fg=FG_DIM,
                     font=("Arial", 10), width=10, anchor="e").pack(side="left")
            tk.Label(row, text=f"  {value}", bg=BG_CARD, fg=color,
                     font=("Arial", 10, "bold"), anchor="w").pack(side="left")

    def _render_config_card(self, parent):
        config_card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=10)
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
                     bg=BG_CARD, fg=YELLOW, font=("Arial", 10),
                     anchor="w").pack(side="left")

        btn(cfg_row, "Cargar otra", font=("Arial", 9),
            command=self._pick_config_file).pack(side="right")

    def _render_tracker_card(self, parent, model_info):
        tracker_card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=10)
        tracker_card.pack(fill="x", pady=(8, 0))
        tk.Label(tracker_card, text="Tracker:", bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 10)).pack(side="left")

        tracker_opts = [
            ("bytetrack", "ByteTrack"),
            ("sort", "SORT"),
            ("ocsort", "OC-SORT"),
        ]
        # RF-DETR no soporta ByteTrack nativo → default SORT
        if model_info.get("family") == "rfdetr":
            self._selected_tracker.set("sort")

        for val, label in tracker_opts:
            tk.Radiobutton(
                tracker_card, text=label, variable=self._selected_tracker, value=val,
                bg=BG_CARD, fg=FG_BRIGHT, selectcolor=ACCENT,
                activebackground=BG_CARD, activeforeground=FG_BRIGHT,
                font=("Arial", 9, "bold"), indicatoron=1, padx=8, pady=2,
            ).pack(side="left", padx=4)

        tk.Label(tracker_card,
                 text="(ByteTrack: rapido | OC-SORT: mejor con oclusiones)",
                 bg=BG_CARD, fg=FG_DIM, font=("Arial", 8)).pack(side="right")

    def _render_action_buttons(self, parent):
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=(20, 0))

        btn(actions, "Atras", fg=FG_DIM,
            command=lambda: self._show_step(1)).pack(side="left")
        btn(actions, "Ejecutar", bg=GREEN, fg=BG_DARK,
            font=("Arial", 12, "bold"),
            command=self._run_processing).pack(side="right", padx=(8, 0))
        btn(actions, "Configurar zonas", bg=ACCENT, fg=BG_DARK,
            font=("Arial", 12, "bold"),
            command=self._open_setup).pack(side="right")

    def _pick_config_file(self):
        path = filedialog.askopenfilename(
            title="Cargar configuracion",
            initialdir=str(paths.config_dir),
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if path:
            self._selected_config.set(path)
            self._status.set(f"Config: {os.path.basename(path)}")
            self._show_step(2)
