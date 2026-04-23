"""Step 1 del wizard: seleccion/descarga de modelo."""

import threading
import tkinter as tk

from carcounter.app_theme import (
    ACCENT, BG_CARD, BG_DARK, BTN_BG, FG, FG_DIM, GREEN, PEACH, RECOMMENDED,
    YELLOW, btn,
)
from carcounter.models import MODEL_CATALOG, download_model, is_downloaded


class ModelStepMixin:
    """Construccion del paso 1 (seleccion de modelo) + acciones."""

    def _build_step_model(self):
        f = self._content

        tk.Label(f, text="Selecciona un modelo de deteccion",
                 bg=f["bg"], fg="#FFFFFF", font=("Arial", 14, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(f, text="AP50 = precision en COCO (mayor es mejor). Latencia medida en NVIDIA T4 FP16.",
                 bg=f["bg"], fg=FG_DIM, font=("Arial", 9),
                 anchor="w").pack(fill="x", pady=(0, 10))

        list_frame = tk.Frame(f, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_DARK)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def _on_mousewheel(event):
            if not canvas.winfo_exists():
                return
            try:
                if event.delta:
                    canvas.yview_scroll(-1 * (event.delta // 120), "units")
                elif event.num == 4:
                    canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    canvas.yview_scroll(3, "units")
            except tk.TclError:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        self._model_btns = {}

        for family_label, family_key, desc in [
            ("YOLO", "yolo", "Rapido y versatil — ideal para tiempo real y hardware limitado"),
            ("RF-DETR", "rfdetr", "Transformer con DINOv2 — mayor precision (+9 AP50 sobre YOLO)"),
        ]:
            self._render_model_family(inner, family_label, family_key, desc)

    def _render_model_family(self, parent, family_label, family_key, desc):
        """Renderiza el header de una familia y todos sus modelos."""
        fh = tk.Frame(parent, bg="#313244", pady=5)
        fh.pack(fill="x", pady=(8, 0))
        tk.Label(fh, text=f"  {family_label}", bg="#313244", fg=ACCENT,
                 font=("Arial", 11, "bold"), anchor="w").pack(side="left")
        tk.Label(fh, text=f"  {desc}", bg="#313244", fg=FG_DIM,
                 font=("Arial", 9), anchor="w").pack(side="left", padx=8)

        for name, info in MODEL_CATALOG.items():
            if info["family"] != family_key:
                continue
            self._render_model_row(parent, name, info)

    def _render_model_row(self, parent, name, info):
        """Renderiza una fila individual de modelo."""
        downloaded = is_downloaded(name)
        is_rec = name in RECOMMENDED

        row = tk.Frame(parent, bg=BG_CARD, pady=6, padx=12)
        row.pack(fill="x", pady=1)

        left = tk.Frame(row, bg=BG_CARD)
        left.pack(side="left", fill="x", expand=True)

        name_row = tk.Frame(left, bg=BG_CARD)
        name_row.pack(fill="x")
        name_fg = GREEN if downloaded else FG
        tk.Label(name_row, text=name, bg=BG_CARD, fg=name_fg,
                 font=("Courier", 11, "bold"), anchor="w").pack(side="left")
        if is_rec:
            tk.Label(name_row, text=" RECOMENDADO", bg=BG_CARD, fg=PEACH,
                     font=("Arial", 8, "bold"), anchor="w").pack(side="left", padx=6)
        if downloaded:
            tk.Label(name_row, text=" descargado", bg=BG_CARD, fg=GREEN,
                     font=("Arial", 8), anchor="w").pack(side="left", padx=4)

        tk.Label(left, text=info.get("note", ""), bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 8), anchor="w").pack(fill="x")

        center = tk.Frame(row, bg=BG_CARD)
        center.pack(side="left", padx=16)

        ap = info["coco_ap50"]
        ap_fg = GREEN if ap >= 70 else (YELLOW if ap >= 60 else FG)
        tk.Label(center, text=f"AP50: {ap:.1f}", bg=BG_CARD, fg=ap_fg,
                 font=("Courier", 10, "bold"), width=11, anchor="w").pack(side="left")
        tk.Label(center, text=f"{info['latency_ms']}ms", bg=BG_CARD, fg=FG_DIM,
                 font=("Courier", 9), width=7, anchor="w").pack(side="left")
        tk.Label(center, text=f"{info['size_mb']}MB", bg=BG_CARD, fg=FG_DIM,
                 font=("Courier", 9), width=6, anchor="w").pack(side="left")

        if downloaded:
            b = btn(row, "Seleccionar", bg=GREEN, fg=BG_DARK,
                    font=("Arial", 9, "bold"), width=11,
                    command=lambda n=name: self._select_model(n))
        else:
            b = btn(row, "Descargar", bg=ACCENT, fg=BG_DARK,
                    font=("Arial", 9, "bold"), width=11,
                    command=lambda n=name: self._download_threaded(n))
        b.pack(side="right")
        self._model_btns[name] = b

    def _select_model(self, name):
        self._selected_model.set(name)
        info = MODEL_CATALOG[name]
        self._status.set(f"Modelo: {name}  (AP50={info['coco_ap50']}, {info['latency_ms']}ms)")
        self._show_step(1)

    def _download_threaded(self, name):
        """Descarga en hilo separado para no bloquear la UI."""
        b = self._model_btns.get(name)
        if b:
            b.config(text="Descargando...", state="disabled", bg=YELLOW, fg=BG_DARK)
        self._status.set(f"Descargando {name}...")
        self.update()

        def _worker():
            ok = download_model(name)
            self.after(0, lambda: self._download_done(name, ok))

        threading.Thread(target=_worker, daemon=True).start()

    def _download_done(self, name, ok):
        if ok:
            self._status.set(f"{name} descargado — listo para usar")
            self._select_model(name)
        else:
            self._status.set(f"Error descargando {name}")
            self._show_step(0)
