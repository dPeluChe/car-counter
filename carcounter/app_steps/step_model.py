"""Step 1 del wizard: modelo del perfil, archivo propio o catálogo."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from carcounter.app_theme import ACCENT, BG_CARD, BG_DARK, FG, FG_DIM, GREEN, YELLOW, btn
from carcounter.models import MODEL_CATALOG, download_model_with_error, is_downloaded
from carcounter.wizard_actions import CUSTOM_MODEL, PROFILE_MODEL, resolve_model, resolve_path

_WHEEL_EVENTS = ("<MouseWheel>", "<Button-4>", "<Button-5>")
_FAMILIES = [
    ("Aéreo EPS", lambda info: info["source"] == "local",
     "Entrenado en VisDrone para tomas aéreas; es el modelo del aforo EPS"),
    ("YOLO11 (COCO)", lambda info: info["source"] == "ultralytics",
     "Genérico COCO, no entrenado para tomas aéreas"),
    ("RF-DETR (COCO)", lambda info: info["family"] == "rfdetr",
     "Genérico COCO; el configurador no calibra con él"),
]


class ModelStepMixin:
    """Construccion del paso 1 (seleccion de modelo) + acciones."""

    def _build_step_model(self):
        f = self._content
        tk.Label(f, text="Elige el modelo de detección", bg=f["bg"], fg="#FFFFFF",
                 font=("Arial", 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(f, text="AP50 y latencia son referencia COCO del fabricante (T4 FP16), no medidas en el aforo EPS.",
                 bg=f["bg"], fg=FG_DIM, font=("Arial", 9), anchor="w").pack(fill="x", pady=(0, 8))
        self._render_profile_model_card(f)

        list_frame = tk.Frame(f, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, pady=(8, 0))
        canvas = tk.Canvas(list_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_DARK)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._bind_wheel(canvas)

        self._model_btns = {}
        for label, belongs, desc in _FAMILIES:
            self._render_model_family(inner, label, belongs, desc)

    def _render_profile_model_card(self, parent):
        profile_model = resolve_path(self._profile().get("model_path", ""))
        card = tk.Frame(parent, bg=BG_CARD, padx=12, pady=8)
        card.pack(fill="x")
        text = f"Modelo del perfil: {profile_model}" if profile_model else "El perfil actual no indica modelo"
        tk.Label(card, text=text, bg=BG_CARD, fg=GREEN if profile_model else YELLOW,
                 font=("Arial", 10), anchor="w", wraplength=520, justify="left").pack(side="left", fill="x", expand=True)
        btn(card, "Buscar archivo...", font=("Arial", 9), command=self._pick_model_file).pack(side="right", padx=(6, 0))
        btn(card, "Usar el del perfil", bg=GREEN, fg=BG_DARK, font=("Arial", 9, "bold"),
            command=self._select_profile_model).pack(side="right")

    def _bind_wheel(self, canvas):
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
        for event in _WHEEL_EVENTS:
            canvas.bind_all(event, _on_mousewheel)

    def _unbind_wheel(self):
        for event in _WHEEL_EVENTS:
            self.unbind_all(event)

    def _render_model_family(self, parent, family_label, belongs, desc):
        """Renderiza el header de una familia y todos sus modelos."""
        fh = tk.Frame(parent, bg="#313244", pady=5)
        fh.pack(fill="x", pady=(8, 0))
        tk.Label(fh, text=f"  {family_label}", bg="#313244", fg=ACCENT,
                 font=("Arial", 11, "bold"), anchor="w").pack(side="left")
        tk.Label(fh, text=f"  {desc}", bg="#313244", fg=FG_DIM,
                 font=("Arial", 9), anchor="w").pack(side="left", padx=8)
        for name, info in MODEL_CATALOG.items():
            if belongs(info):
                self._render_model_row(parent, name, info)

    def _render_model_row(self, parent, name, info):
        """Renderiza una fila individual de modelo."""
        downloaded = is_downloaded(name)
        row = tk.Frame(parent, bg=BG_CARD, pady=6, padx=12)
        row.pack(fill="x", pady=1)

        left = tk.Frame(row, bg=BG_CARD)
        left.pack(side="left", fill="x", expand=True)
        name_row = tk.Frame(left, bg=BG_CARD)
        name_row.pack(fill="x")
        tk.Label(name_row, text=name, bg=BG_CARD, fg=GREEN if downloaded else FG,
                 font=("Courier", 11, "bold"), anchor="w").pack(side="left")
        if downloaded:
            tk.Label(name_row, text=" disponible", bg=BG_CARD, fg=GREEN,
                     font=("Arial", 8), anchor="w").pack(side="left", padx=4)
        tk.Label(left, text=info.get("note", ""), bg=BG_CARD, fg=FG_DIM,
                 font=("Arial", 8), anchor="w").pack(fill="x")

        if info["coco_ap50"] is not None:
            center = tk.Frame(row, bg=BG_CARD)
            center.pack(side="left", padx=16)
            tk.Label(center, text=f"AP50 COCO {info['coco_ap50']:.1f}", bg=BG_CARD, fg=FG_DIM,
                     font=("Courier", 9), width=15, anchor="w").pack(side="left")
            tk.Label(center, text=f"{info['latency_ms']}ms", bg=BG_CARD, fg=FG_DIM,
                     font=("Courier", 9), width=7, anchor="w").pack(side="left")

        if downloaded:
            b = btn(row, "Seleccionar", bg=GREEN, fg=BG_DARK, font=("Arial", 9, "bold"), width=11,
                    command=lambda n=name: self._select_model(n))
        elif info["source"] == "local":
            b = tk.Label(row, text="No encontrado", bg=BG_CARD, fg=YELLOW, font=("Arial", 9), width=13)
        else:
            b = btn(row, "Descargar", bg=ACCENT, fg=BG_DARK, font=("Arial", 9, "bold"), width=11,
                    command=lambda n=name: self._download_threaded(n))
        b.pack(side="right")
        self._model_btns[name] = b

    def _select_model(self, name):
        choice = resolve_model(name)
        if choice.error:
            messagebox.showwarning("Modelo", choice.error)
            return
        self._selected_model.set(name)
        self._status.set(f"Modelo: {choice.label}")
        self._show_step(1)

    def _select_profile_model(self):
        choice = resolve_model(PROFILE_MODEL, profile=self._profile())
        if choice.error:
            messagebox.showwarning("Modelo del perfil", choice.error)
            return
        self._selected_model.set(PROFILE_MODEL)
        self._status.set(f"Modelo: {choice.label}")
        self._show_step(1)

    def _pick_model_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar pesos del modelo",
            filetypes=[("Pesos", "*.pt *.pth"), ("Todos", "*.*")])
        if not path:
            return
        choice = resolve_model(CUSTOM_MODEL, custom_path=path)
        if choice.error:
            messagebox.showwarning("Modelo", choice.error)
            return
        self._custom_model_path = path
        self._selected_model.set(CUSTOM_MODEL)
        self._status.set(f"Modelo: {choice.label}")
        self._show_step(1)

    def _download_threaded(self, name):
        """Descarga en hilo separado para no bloquear la UI."""
        b = self._model_btns.get(name)
        if b:
            b.config(text="Descargando...", state="disabled", bg=YELLOW, fg=BG_DARK)
        self._status.set(f"Descargando {name}...")

        def _worker():
            ok, error = download_model_with_error(name)
            self.after(0, lambda: self._download_done(name, ok, error))

        threading.Thread(target=_worker, daemon=True).start()

    def _download_done(self, name, ok, error=None):
        # El usuario puede haber avanzado mientras descargaba: solo se redibuja si sigue en este paso
        if ok:
            self._status.set(f"{name} descargado: listo para seleccionar")
        else:
            self._status.set(f"No se pudo descargar {name}")
            messagebox.showerror("Descarga", f"No se pudo descargar {name}:\n{error}")
        if self._current_step == 0:
            self._show_step(0)
