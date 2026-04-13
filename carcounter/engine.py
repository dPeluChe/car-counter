"""ProcessingEngine: arquitectura event-driven para el pipeline de video.

Reemplaza el loop monolitico de main.py con un engine que soporta:
- pause/resume
- callbacks para eventos (frame_processed, route_detected, etc.)
- estado observable para futuras UIs (web, desktop)

Uso basico:
    engine = ProcessingEngine(config)
    engine.on("route_detected", my_callback)
    engine.run()  # blocking
    # o:
    engine.start()  # non-blocking (thread)
"""

from __future__ import annotations

import time
import threading
from collections import deque
from enum import Enum, auto
from typing import Callable, Any

import cv2
import numpy as np

from carcounter.counting import VehicleCounter
from carcounter.drawing import (
    draw_zones, draw_lines, draw_exclusion_zones, draw_tracked_boxes,
    draw_routes_panel, draw_hud, format_time, DensityHeatmap,
)
from carcounter.logging_config import get_logger

log = get_logger("engine")


class EngineState(Enum):
    """Estados del ProcessingEngine."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()


class ProcessingEngine:
    """Pipeline de procesamiento event-driven para video."""

    def __init__(self, *, video_path, detect_fn, counter, zones_np,
                 exclusion_np, counting_lines, counting_mode="zones",
                 zone_names=None, output_path=None, headless=False,
                 show_fps=False, heatmap=False, demo_mode=False,
                 max_frames=None):
        """
        Args:
            video_path: Ruta al video
            detect_fn: Callable(frame) -> list[(x1,y1,x2,y2,id,cls)]
            counter: VehicleCounter instance
            zones_np: dict de zonas como numpy arrays
            exclusion_np: dict de zonas de exclusion como numpy arrays
            counting_lines: list de lineas de conteo
            counting_mode: "zones", "lines", "directions"
            zone_names: lista de nombres de zona
            output_path: ruta para guardar video (None = no guardar)
            headless: True para no mostrar ventana
            show_fps: True para mostrar HUD
            heatmap: True para activar heatmap
            demo_mode: True para scoreboard grande
            max_frames: maximo de frames a procesar
        """
        self.video_path = video_path
        self.detect_fn = detect_fn
        self.counter = counter
        self.zones_np = zones_np
        self.exclusion_np = exclusion_np
        self.counting_lines = counting_lines
        self.counting_mode = counting_mode
        self.zone_names = zone_names or list(zones_np.keys())
        self.output_path = output_path
        self.headless = headless
        self.show_fps = show_fps
        self.heatmap = heatmap
        self.demo_mode = demo_mode
        self.max_frames = max_frames

        # State
        self._state = EngineState.IDLE
        self._callbacks: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        self._thread = None

        # Metrics
        self.frame_count = 0
        self.total_frames = 0
        self.fps_avg = 0.0
        self.start_time = 0.0

    @property
    def state(self) -> EngineState:
        return self._state

    # ── Event system ────────────────────────────

    def on(self, event: str, callback: Callable):
        """Registra un callback para un evento.

        Eventos disponibles:
        - frame_processed(frame_count, fps, tracked_boxes)
        - route_detected(route_key, count, cls_name)
        - progress(pct, frame_count, total, fps, eta)
        - state_changed(old_state, new_state)
        - error(exception, frame_count)
        - completed(stats_dict)
        """
        self._callbacks.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable):
        """Desregistra un callback."""
        if event in self._callbacks:
            self._callbacks[event] = [
                cb for cb in self._callbacks[event] if cb != callback
            ]

    def _emit(self, event: str, **kwargs):
        """Emite un evento a todos los callbacks registrados."""
        for cb in self._callbacks.get(event, []):
            try:
                cb(**kwargs)
            except Exception as e:
                log.warning("Error en callback %s.%s: %s", event, cb.__name__, e)

    def _set_state(self, new_state: EngineState):
        old = self._state
        self._state = new_state
        self._emit("state_changed", old_state=old, new_state=new_state)

    # ── Control ─────────────────────────────────

    def pause(self):
        """Pausa el procesamiento."""
        changed = False
        with self._lock:
            if self._state == EngineState.RUNNING:
                self._state = EngineState.PAUSED
                changed = True
        if changed:
            self._emit("state_changed", old_state=EngineState.RUNNING,
                        new_state=EngineState.PAUSED)
            log.info("Engine pausado en frame %d", self.frame_count)

    def resume(self):
        """Reanuda el procesamiento."""
        changed = False
        with self._lock:
            if self._state == EngineState.PAUSED:
                self._state = EngineState.RUNNING
                changed = True
        if changed:
            self._emit("state_changed", old_state=EngineState.PAUSED,
                        new_state=EngineState.RUNNING)
            log.info("Engine reanudado en frame %d", self.frame_count)

    def stop(self):
        """Detiene el procesamiento."""
        old = None
        with self._lock:
            if self._state in (EngineState.RUNNING, EngineState.PAUSED):
                old = self._state
                self._state = EngineState.STOPPED
        if old is not None:
            self._emit("state_changed", old_state=old, new_state=EngineState.STOPPED)
            log.info("Engine detenido en frame %d", self.frame_count)

    def start(self):
        """Inicia procesamiento en un thread separado."""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def wait(self, timeout=None):
        """Espera a que termine el procesamiento."""
        if self._thread:
            self._thread.join(timeout=timeout)

    # ── Main loop ────────────────────────────────

    def run(self):
        """Ejecuta el loop principal de procesamiento (blocking)."""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            log.error("No se pudo abrir: %s", self.video_path)
            self._set_state(EngineState.ERROR)
            return

        vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vid_fps = cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        writer = None
        if self.output_path:
            writer = cv2.VideoWriter(
                self.output_path, cv2.VideoWriter_fourcc(*"mp4v"),
                vid_fps, (vid_w, vid_h),
            )

        _heatmap = DensityHeatmap(vid_w, vid_h) if self.heatmap else None
        fps_samples = deque(maxlen=30)
        self.frame_count = 0
        self.start_time = time.time()
        self._set_state(EngineState.RUNNING)
        consecutive_errors = 0

        try:
            while self._state != EngineState.STOPPED:
                # Handle pause
                while self._state == EngineState.PAUSED:
                    time.sleep(0.1)
                if self._state == EngineState.STOPPED:
                    break

                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                self.frame_count += 1
                self.counter.set_frame(self.frame_count)
                t0 = time.time()

                # Detection
                try:
                    tracked_boxes = self.detect_fn(frame)
                    consecutive_errors = 0
                except Exception as e:
                    consecutive_errors += 1
                    self._emit("error", exception=e, frame_count=self.frame_count)
                    log.error("Error deteccion frame %d: %s", self.frame_count, e)
                    if consecutive_errors >= 10:
                        log.critical("Demasiados errores consecutivos. Abortando.")
                        self._set_state(EngineState.ERROR)
                        break
                    tracked_boxes = []

                # Counting — snapshot routes once before the loop
                prev_routes = dict(self.counter.routes_matrix)
                for (x1, y1, x2, y2, trk_id, cls_name) in tracked_boxes:
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    self.counter.update(trk_id, cx, cy, cls_name, self.counting_mode,
                                        bbox=(x1, y1, x2, y2))
                # Emit new routes detected this frame
                for key, count in self.counter.routes_matrix.items():
                    if key not in prev_routes or count > prev_routes[key]:
                        self._emit("route_detected", route_key=key,
                                   count=count, cls_name="")

                if self.frame_count % 120 == 0:
                    self.counter.purge_stale()

                # Visualization
                if _heatmap:
                    centroids = [((x1+x2)//2, (y1+y2)//2)
                                 for x1, y1, x2, y2, _, _ in tracked_boxes]
                    _heatmap.update(centroids)
                    _heatmap.draw(frame)

                draw_exclusion_zones(frame, self.exclusion_np)
                if self.counting_mode == "lines":
                    draw_lines(frame, self.counting_lines)
                else:
                    draw_zones(frame, self.zones_np)

                draw_tracked_boxes(frame, tracked_boxes, self.counter.tracks_info,
                                   self.zone_names, trails=self.counter.trails)

                draw_routes_panel(frame, self.counter.routes_matrix, len(tracked_boxes))

                elapsed = time.time() - t0
                fps_samples.append(1.0 / elapsed if elapsed > 0 else 0)
                self.fps_avg = float(np.mean(fps_samples))

                if self.show_fps:
                    draw_hud(frame, self.frame_count, self.total_frames,
                             self.fps_avg, len(tracked_boxes),
                             sum(self.counter.routes_matrix.values()), vid_w)

                # Emit progress
                self._emit("frame_processed",
                           frame_count=self.frame_count,
                           fps=self.fps_avg,
                           tracked_boxes=tracked_boxes)

                if self.frame_count % 60 == 0:
                    et = time.time() - self.start_time
                    pct = self.frame_count / self.total_frames * 100 if self.total_frames > 0 else 0
                    eta = (et / self.frame_count) * (self.total_frames - self.frame_count)
                    self._emit("progress",
                               pct=pct,
                               frame_count=self.frame_count,
                               total=self.total_frames,
                               fps=self.fps_avg,
                               eta=eta)

                if not self.headless:
                    cv2.imshow("Car Counter", frame)
                if writer:
                    writer.write(frame)
                if self.max_frames and self.frame_count >= self.max_frames:
                    break
                if not self.headless and cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        except KeyboardInterrupt:
            log.info("Interrumpido por el usuario")
        finally:
            total_time = time.time() - self.start_time
            stats = {
                "frame_count": self.frame_count,
                "total_frames": self.total_frames,
                "total_time": total_time,
                "avg_fps": self.frame_count / total_time if total_time > 0 else 0,
                "routes_matrix": dict(self.counter.routes_matrix),
                "total_vehicles": self.counter.total_vehicles_ever,
            }
            self._emit("completed", stats=stats)

            if writer:
                writer.release()
            cap.release()
            if not self.headless:
                cv2.destroyAllWindows()

            if self._state != EngineState.ERROR:
                self._set_state(EngineState.IDLE)

            log.info("Engine finalizado: %d frames, %.1f fps avg",
                     self.frame_count,
                     stats["avg_fps"])
