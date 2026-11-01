"""Un trabajo a la vez fuera del hilo de Tk, con cancelación y descarte por cambio de contexto."""

import threading


class BackgroundJob:
    """El resultado solo se entrega si el contexto (video, frame, perfil) sigue siendo el de la partida."""

    def __init__(self):
        self._run = None

    @property
    def active(self):
        return self._run is not None

    def start(self, context, work):
        """work(cancelled) corre en un hilo; debe revisar cancelled.is_set() en los puntos seguros."""
        if self._run is not None:
            raise RuntimeError("Ya hay una prueba en curso")
        cancelled, box = threading.Event(), {"reason": None}

        def target():
            try:
                box["value"] = work(cancelled)
            except Exception as error:
                box["error"] = error
            finally:
                box["done"] = True

        self._run = (context, cancelled, box)
        threading.Thread(target=target, daemon=True).start()

    def cancel(self):
        if self._run is not None:
            self._discard(self._run, "cancelada por el usuario")

    def poll(self, context):
        """None mientras corre; al terminar libera el trabajo y devuelve (estado, valor).

        Estados: 'ok', 'error' y 'descartado' (valor: motivo)."""
        if self._run is None:
            return None
        started, cancelled, box = self._run
        if started != context:
            self._discard(self._run, "cambió el video, el frame o el perfil")
        if not box.get("done"):
            return None
        self._run = None
        if cancelled.is_set():
            return "descartado", box["reason"]
        if "error" in box:
            return "error", box["error"]
        return "ok", box["value"]

    @staticmethod
    def _discard(run, reason):
        _, cancelled, box = run
        box["reason"] = box["reason"] or reason
        cancelled.set()
