"""Dialogo compartido para gestionar modelos (usado por setup.py y app.py)."""

import tkinter as tk
from carcounter.models import MODEL_CATALOG, is_downloaded, download_model, get_model_path

BG = "#1E1E2E"
BG_DARK = "#11111B"
BG_CARD = "#181825"
FG = "#CDD6F4"
FG_DIM = "#A6ADC8"
ACCENT = "#89B4FA"
GREEN = "#A6E3A1"
RED = "#F38BA8"


def show_model_dialog(parent, on_select=None):
    """Abre un dialogo modal con el catalogo de modelos.

    Args:
        parent: ventana padre (tk.Tk o tk.Toplevel)
        on_select: callback(name, path) cuando se selecciona un modelo YOLO.
                   path es None para modelos RF-DETR.
    """
    dlg = tk.Toplevel(parent)
    dlg.title("Gestor de Modelos")
    dlg.geometry("750x520")
    dlg.configure(bg=BG)
    dlg.transient(parent)
    dlg.grab_set()

    tk.Label(dlg, text="Gestor de Modelos", bg=BG, fg=FG,
             font=("Arial", 14, "bold")).pack(pady=(12, 4))
    tk.Label(dlg, text="AP50 y latencia: referencia COCO del fabricante (T4 FP16), no medidas en el aforo EPS.",
             bg=BG, fg=FG_DIM, font=("Arial", 9)).pack()

    table_frame = tk.Frame(dlg, bg=BG_DARK)
    table_frame.pack(fill="both", expand=True, padx=12, pady=8)

    canvas = tk.Canvas(table_frame, bg=BG_DARK, highlightthickness=0)
    scrollbar = tk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=BG_DARK)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    status_var = tk.StringVar(value="")
    row_widgets = {}

    def _refresh(name):
        if name in row_widgets:
            downloaded = is_downloaded(name)
            btn, lbl = row_widgets[name]
            lbl.config(text="OK" if downloaded else "--",
                       fg=GREEN if downloaded else RED)
            if downloaded:
                btn.config(text="Usar", bg=GREEN, fg=BG_DARK,
                           command=lambda n=name: _use(n))
            else:
                btn.config(text="Descargar", bg=ACCENT, fg=BG_DARK,
                           command=lambda n=name: _download(n))

    def _download(name):
        status_var.set(f"Descargando {name}...")
        dlg.update()
        ok = download_model(name)
        status_var.set(f"{'OK' if ok else 'Error'}: {name}")
        _refresh(name)
        dlg.update()

    def _use(name):
        info = MODEL_CATALOG[name]
        if info["family"] != "yolo":
            status_var.set(f"{name}: el configurador solo calibra con YOLO")
            return
        path = get_model_path(name)
        if not path:
            status_var.set(f"{name}: pesos no encontrados")
            return
        status_var.set(f"Seleccionado: {name}")
        if on_select:
            on_select(name, path)

    for family_label, family_key, desc in [
        ("YOLO", "yolo", "Incluye VisDrone (aéreo, EPS) y YOLO11 genérico COCO"),
        ("RF-DETR", "rfdetr", "Genérico COCO; solo para ejecutar, no para calibrar"),
    ]:
        fh = tk.Frame(inner, bg="#313244", pady=3)
        fh.pack(fill="x", pady=(6, 0))
        tk.Label(fh, text=f"  {family_label}", bg="#313244", fg=ACCENT,
                 font=("Arial", 10, "bold"), anchor="w").pack(side="left")
        tk.Label(fh, text=f"  {desc}", bg="#313244", fg=FG_DIM,
                 font=("Arial", 9)).pack(side="left", padx=8)

        for name, info in MODEL_CATALOG.items():
            if info["family"] != family_key:
                continue
            downloaded = is_downloaded(name)

            row = tk.Frame(inner, bg=BG_CARD, pady=4, padx=8)
            row.pack(fill="x", pady=1)

            # Name + note
            left = tk.Frame(row, bg=BG_CARD)
            left.pack(side="left", fill="x", expand=True)
            tk.Label(left, text=name, bg=BG_CARD, fg=GREEN if downloaded else FG,
                     font=("Courier", 10, "bold"), anchor="w").pack(fill="x")
            tk.Label(left, text=info.get("note", ""), bg=BG_CARD, fg=FG_DIM,
                     font=("Arial", 8), anchor="w").pack(fill="x")

            if info["coco_ap50"] is not None:
                tk.Label(row, text=f"AP50:{info['coco_ap50']:.1f}", bg=BG_CARD, fg=FG_DIM,
                         font=("Courier", 9, "bold"), width=10).pack(side="left")
                tk.Label(row, text=f"{info['latency_ms']}ms", bg=BG_CARD, fg=FG_DIM,
                         font=("Courier", 9), width=6).pack(side="left")

            # Status + button
            lbl = tk.Label(row, text="OK" if downloaded else "--", bg=BG_CARD,
                           font=("Courier", 9), width=3,
                           fg=GREEN if downloaded else RED)
            lbl.pack(side="left", padx=2)

            if downloaded:
                btn = tk.Button(row, text="Usar", bg=GREEN, fg=BG_DARK,
                                font=("Arial", 9, "bold"), relief="flat", width=10,
                                command=lambda n=name: _use(n))
            elif info["source"] == "local":
                btn = tk.Label(row, text="No encontrado", bg=BG_CARD, fg=RED,
                               font=("Arial", 9), width=12)
            else:
                btn = tk.Button(row, text="Descargar", bg=ACCENT, fg=BG_DARK,
                                font=("Arial", 9, "bold"), relief="flat", width=10,
                                command=lambda n=name: _download(n))
            btn.pack(side="right", padx=4)

            row_widgets[name] = (btn, lbl)

    bottom = tk.Frame(dlg, bg=BG)
    bottom.pack(fill="x", padx=12, pady=8)
    tk.Label(bottom, textvariable=status_var, bg=BG, fg=GREEN,
             font=("Courier", 9), anchor="w").pack(side="left")
    tk.Button(bottom, text="Cerrar", bg="#313244", fg=FG,
              relief="flat", padx=16, command=dlg.destroy).pack(side="right")
