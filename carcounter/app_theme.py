"""Constantes de tema visual y helpers compartidos por el wizard (app.py + app_steps/).

Separado para evitar imports circulares entre app.py y los step mixins.
"""

import tkinter as tk

# ── Colores ──────────────────────────────────

BG = "#1E1E2E"
BG_DARK = "#11111B"
BG_CARD = "#181825"
FG = "#CDD6F4"
FG_DIM = "#A6ADC8"
FG_BRIGHT = "#FFFFFF"
ACCENT = "#89B4FA"
GREEN = "#A6E3A1"
YELLOW = "#F9E2AF"
RED = "#F38BA8"
PEACH = "#FAB387"
BTN_BG = "#313244"


def btn(parent, text, command, bg=BTN_BG, fg=FG, font=("Arial", 10), **kw):
    """Boton con theme consistente (macOS compatible)."""
    return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                     font=font, relief="flat", padx=14, pady=6,
                     activebackground=bg, activeforeground=fg,
                     highlightbackground=bg, highlightcolor=bg, bd=0, **kw)
