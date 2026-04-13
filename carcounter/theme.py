"""Centralized theme: colores, fuentes y opacidades para todo el proyecto.

Single source of truth para evitar duplicacion entre constants.py,
drawing.py y setup_panels/.

Paleta base: Catppuccin Mocha.
"""


# ─── Colores de zona (8 colores ciclicos) ────────────────────────

# Formato Tkinter (hex string)
ZONE_COLORS_HEX = [
    "#00FF88", "#FF6B6B", "#4ECDC4", "#FFE66D",
    "#A8E6CF", "#FF8B94", "#B8B8FF", "#FFA07A",
]

# Formato RGB para Pillow / setup_panels (R, G, B)
ZONE_COLORS_RGB = [
    (0, 255, 136),    # verde
    (255, 107, 107),  # rojo-coral
    (78, 205, 196),   # cian
    (255, 230, 109),  # amarillo
    (168, 230, 207),  # verde menta
    (255, 139, 148),  # salmon
    (184, 184, 255),  # lavanda
    (255, 160, 122),  # azul claro
]

# Formato BGR para OpenCV (B, G, R)
ZONE_COLORS_BGR = [
    (136, 255, 0),    # verde
    (107, 107, 255),  # rojo-coral
    (205, 196, 78),   # cian
    (109, 230, 255),  # amarillo
    (207, 230, 168),  # verde menta
    (148, 139, 255),  # salmon
    (255, 184, 184),  # lavanda
    (122, 160, 255),  # azul claro
]


# ─── Colores de exclusion ────────────────────────────────────────

EXCL_COLORS_HEX = ["#FF5555", "#FF9500", "#FF6B6B", "#FAB387"]

EXCL_COLORS_RGB = [
    (255, 85, 85),    # rojo
    (255, 149, 0),    # naranja
    (255, 107, 107),  # rojo claro
    (250, 179, 135),  # salmon
]

EXCL_COLORS_BGR = [
    (85, 85, 255),
    (0, 149, 255),
    (107, 107, 255),
    (135, 179, 250),
]


# ─── Catppuccin Mocha — GUI palette ─────────────────────────────

class UI:
    """Colores y fuentes para la GUI Tkinter (Catppuccin Mocha)."""

    # Backgrounds
    BG_BASE     = "#1E1E2E"
    BG_MANTLE   = "#181825"
    BG_CRUST    = "#11111B"
    BG_SURFACE0 = "#313244"
    BG_SURFACE1 = "#45475A"

    # Foregrounds
    FG_TEXT      = "#CDD6F4"
    FG_SUBTEXT   = "#A6ADC8"
    FG_OVERLAY   = "#6C7086"

    # Accents
    ACCENT_BLUE    = "#89B4FA"
    ACCENT_GREEN   = "#A6E3A1"
    ACCENT_RED     = "#F38BA8"
    ACCENT_YELLOW  = "#F9E2AF"
    ACCENT_MAUVE   = "#CBA6F7"
    ACCENT_TEAL    = "#94E2D5"

    # Fonts
    FONT_TITLE  = ("Arial", 15, "bold")
    FONT_HEADING = ("Arial", 10, "bold")
    FONT_BODY   = ("Arial", 9)
    FONT_BOLD   = ("Arial", 9, "bold")
    FONT_MONO   = ("Courier", 9)
    FONT_MONO_BOLD = ("Courier", 10, "bold")


# ─── Colores de drawing (OpenCV BGR) ────────────────────────────

class Draw:
    """Colores y estilos para OpenCV drawing (main.py)."""

    # Tracked box states
    STATE_DONE     = (60, 220, 60)      # verde
    STATE_DEFAULT  = (160, 160, 160)    # gris

    # Panels
    PANEL_BG       = (0, 0, 0)
    PANEL_BORDER   = (80, 80, 80)
    PANEL_ALPHA    = 0.6

    # Scoreboard
    SCOREBOARD_BG     = (8, 8, 8)
    SCOREBOARD_BORDER = (90, 90, 90)
    SCOREBOARD_ALPHA  = 0.65

    # Text
    TEXT_LIGHT     = (200, 200, 200)
    TEXT_YELLOW    = (100, 220, 255)     # BGR for yellow-ish
    TEXT_COUNT     = (100, 255, 255)     # BGR for route count
    TEXT_ROUTES    = (200, 255, 200)     # route text green
    TEXT_DIM       = (160, 160, 100)

    # HUD
    HUD_BAR        = (80, 200, 80)

    # Exclusion zones overlay
    EXCL_OVERLAY   = (60, 60, 220)

    # Route bar chart
    BAR_GREEN      = (60, 120, 60)



# ─── Opacidades ─────────────────────────────────────────────────

class Opacity:
    """Factores alpha para overlays semi-transparentes."""
    ZONE_FILL      = 0.18
    ZONE_BG        = 0.82
    EXCL_FILL      = 0.22
    EXCL_BG        = 0.78
    SETUP_FILL     = 0.25
    SETUP_BG       = 0.75
    HEATMAP        = 0.4
