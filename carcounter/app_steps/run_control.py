"""Subprocesos del wizard: configurador (setup.py) y procesamiento (main.py) sin bloquear la UI."""

from pathlib import Path
import shlex
import subprocess
import sys
from tkinter import filedialog, messagebox

from carcounter.paths import paths
from carcounter.wizard_actions import (
    build_run_command, build_setup_command, load_profile, make_run_dir, open_folder_command,
    resolve_model, resolve_path, results_summary, same_file, tail, video_resolution,
)

POLL_MS = 500


def _mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


class RunControlMixin:
    """Lanza setup.py y main.py como subprocesos y consulta su estado con after()."""

    def _profile(self):
        return load_profile(self._selected_config.get())

    def _model_choice(self):
        return resolve_model(self._selected_model.get(), self._custom_model_path, self._profile())

    def _busy(self):
        return self._process is not None and self._process.poll() is None

    def _set_running(self, running):
        if self._cancel_btn is not None and self._cancel_btn.winfo_exists():
            self._cancel_btn.config(state="normal" if running else "disabled")

    def _open_setup(self):
        if self._busy():
            messagebox.showinfo("Proceso en curso", "Espera a que termine o cancela el proceso actual")
            return
        video = self._selected_video.get()
        if not video:
            messagebox.showwarning("Video", "Elige un video primero")
            return
        model = self._model_choice()
        if model["error"]:
            messagebox.showwarning("Modelo", model["error"])
            return
        if model["setup_model"] is None:
            messagebox.showwarning("Modelo", "El configurador calibra con YOLO: se abrirá con su modelo por "
                                             "defecto. RF-DETR solo se usa al ejecutar.")
        config = self._selected_config.get()
        if not config:
            config = filedialog.asksaveasfilename(
                title="Guardar perfil nuevo", initialdir=str(paths.config_dir),
                initialfile=f"{Path(video).stem}.json", defaultextension=".json",
                filetypes=[("JSON", "*.json")])
            if not config:
                return
            self._selected_config.set(config)
        self._setup_mtime = _mtime(config)
        command = build_setup_command(sys.executable, video, config, model["setup_model"])
        self._process = subprocess.Popen(command, cwd=str(paths.root))
        self._process_kind = "setup"
        self._status.set("Configurador abierto: guarda el perfil y ciérralo para volver")
        self._set_running(False)
        self.after(POLL_MS, self._poll_process)

    def _run_processing(self):
        if self._busy():
            messagebox.showinfo("Proceso en curso", "Espera a que termine o cancela el proceso actual")
            return
        video, config = self._selected_video.get(), self._selected_config.get()
        if not video:
            messagebox.showwarning("Video", "Elige un video primero")
            return
        if not config or not Path(config).is_file():
            messagebox.showwarning("Perfil", "Carga un perfil o créalo con Configurar zonas")
            return
        profile = load_profile(config)
        model = resolve_model(self._selected_model.get(), self._custom_model_path, profile)
        if model["error"]:
            messagebox.showwarning("Modelo", model["error"])
            return
        profile_video = resolve_path(profile.get("video_path", ""))
        if not self._confirm_video_matches(video, profile_video):
            return

        run_dir = make_run_dir(video)
        run_dir.mkdir(parents=True, exist_ok=True)
        command = build_run_command(sys.executable, config, video, profile_video,
                                     self._selected_tracker.get(), model["args"], run_dir)
        (run_dir / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
        self._run_dir = run_dir
        self._log_file = open(run_dir / "run.log", "w", encoding="utf-8")
        self._process = subprocess.Popen(command, cwd=str(paths.root), stdout=self._log_file,
                                         stderr=subprocess.STDOUT)
        self._process_kind = "run"
        self._status.set(f"Procesando... salidas en {run_dir}")
        self._set_running(True)
        self.after(POLL_MS, self._poll_process)

    def _confirm_video_matches(self, video, profile_video):
        """Avisa si el video elegido no tiene la resolución del video del perfil (las zonas no coincidirían)."""
        if not profile_video or same_file(video, profile_video) or not Path(profile_video).is_file():
            return True
        chosen, reference = video_resolution(video), video_resolution(profile_video)
        if not chosen or not reference or chosen == reference:
            return True
        return messagebox.askyesno(
            "Resolución distinta",
            f"El video elegido ({chosen[0]}x{chosen[1]}) no tiene la resolución del video del perfil "
            f"({reference[0]}x{reference[1]}). Las zonas no coincidirán. ¿Ejecutar de todos modos?")

    def _poll_process(self):
        if self._process is None:
            return
        code = self._process.poll()
        if code is None:
            self.after(POLL_MS, self._poll_process)
            return
        kind, self._process = self._process_kind, None
        if kind == "setup":
            self._finish_setup(code)
        else:
            self._finish_run(code)

    def _finish_setup(self, code):
        config = self._selected_config.get()
        saved = _mtime(config) is not None and _mtime(config) != self._setup_mtime
        if saved:
            self._status.set(f"Perfil guardado: {Path(config).name}")
        else:
            suffix = f" (código {code})" if code else ""
            self._status.set(f"El configurador se cerró sin guardar el perfil{suffix}")
        if self._current_step == 2:
            self._show_step(2)

    def _cancel_run(self):
        if self._busy():
            self._process.terminate()
            self._status.set("Cancelando...")

    def _finish_run(self, code):
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
        self._set_running(False)
        run_dir = self._run_dir
        log_path = run_dir / "run.log"
        if code == 0:
            self._status.set(f"Terminado: {run_dir}")
            if messagebox.askyesno("Procesamiento terminado",
                                   f"Salidas en:\n{run_dir}\n\n{results_summary(run_dir / 'results.json')}"
                                   "\n\n¿Abrir la carpeta?"):
                self._open_output_folder(run_dir)
        else:
            self._status.set(f"El proceso terminó con código {code}; revisa {log_path}")
            messagebox.showerror("Error al procesar",
                                 f"Código {code}. Últimas líneas de {log_path}:\n\n{tail(log_path)}")
        if self._current_step == 2:
            self._show_step(2)

    def _open_output_folder(self, folder):
        try:
            subprocess.Popen(open_folder_command(folder, sys.platform))
        except OSError as error:
            messagebox.showinfo("Salidas", f"Carpeta de salidas:\n{folder}\n\n({error})")
