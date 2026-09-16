"""Cierre de subprocesos lanzados con start_new_session: se señala al grupo, no solo al líder."""

import os
import signal
import subprocess


def terminate_group(process, sig=signal.SIGTERM):
    """Señal al grupo del proceso; si no tiene grupo propio, cae al proceso solo."""
    if process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), sig)
    except (AttributeError, OSError):
        if sig == signal.SIGKILL:
            process.kill()
        else:
            process.terminate()


def kill_group(process):
    terminate_group(process, signal.SIGKILL)


def stop_process(process, timeout=10):
    """Pide salir y mata el grupo si no sale a tiempo. Bloquea hasta que termina."""
    if process.poll() is not None:
        return
    terminate_group(process)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(process)
        process.wait()
