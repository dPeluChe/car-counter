"""Mixin para carga de video, navegacion de frames y seleccion de modelo del configurador."""

import os
from tkinter import messagebox, filedialog

import cv2
from ultralytics import YOLO


class VideoModelMixin:
    """Video, frames y modelo YOLO usados por todos los pasos."""

    def _load_video_and_model(self):
        self.status_var.set("Cargando modelo YOLO…")
        self.update()
        try:
            self.model = YOLO(self._model_path)
            self.status_var.set(f"✅ Modelo cargado: {self._model_path}")
        except Exception as e:
            self.status_var.set(f"❌ Error cargando modelo: {e}")
            messagebox.showerror("Error", f"No se pudo cargar el modelo YOLO:\n{e}")
        self._load_frame()

    def _load_frame(self):
        self._load_frame_at(0, fit=True)

    def _ensure_nav_cap(self):
        """Abre o reutiliza el VideoCapture para navegacion."""
        if self._nav_cap is None or not self._nav_cap.isOpened():
            self._nav_cap = cv2.VideoCapture(self.video_path)
        return self._nav_cap

    def _release_nav_cap(self):
        if self._nav_cap is not None:
            self._nav_cap.release()
            self._nav_cap = None

    def _load_frame_at(self, frame_idx, fit=False):
        """Carga un frame; solo ajusta el zoom a la ventana al abrir el video, no al navegar."""
        cap = self._ensure_nav_cap()
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            frame_idx = max(0, min(total_frames - 1, frame_idx))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            self._release_nav_cap()
            messagebox.showerror("Error", f"No se pudo leer el video:\n{self.video_path}")
            return
        self.frame_orig = frame.copy()
        self.frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.img_h, self.img_w = frame.shape[:2]
        self.total_frames = max(1, total_frames)
        self.current_frame_idx = frame_idx
        if fit:
            self._fit_to_window()
        self.lbl_video.config(text=f"Video: {os.path.basename(self.video_path)}  ({self.img_w}×{self.img_h})")
        self.lbl_frame_info.config(text=f"Frame {self.current_frame_idx + 1}/{self.total_frames}")
        self.display_frame_zones = self.frame_rgb.copy()
        self._redraw()
        self.status_var.set(f"Video cargado: {self.img_w}x{self.img_h}")

    def _step_frame(self, delta):
        self._load_frame_at(self.current_frame_idx + delta)
        self._reset_calib()
        self.status_var.set(
            f"Frame {self.current_frame_idx + 1}/{self.total_frames} cargado. "
            "Repite la calibración en este frame.")

    def _choose_video(self):
        path = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.MOV"), ("Todos", "*.*")])
        if path:
            self._release_nav_cap()
            self.video_path = path
            self._load_frame()
            self._clear_vehicle_samples()
            self._reset_calib()

    def _show_model_manager(self):
        from carcounter.ui_models import show_model_dialog
        show_model_dialog(self, on_select=self._on_model_selected)

    def _on_model_selected(self, name, path):
        """Callback cuando se selecciona un modelo en el dialogo."""
        if path:
            model = YOLO(path)
            self._model_path = path
            self.model = model
            self.sahi_model = None
            self.calib_test_passed = self.calib_confirmed = False
            if self.frame_orig is not None:
                # Las cajas pintadas eran del modelo anterior
                self._restore_original_frame()
                self._redraw_zones()
            self.status_var.set(f"Modelo cambiado a {name}")
