"""Configuracion centralizada de logging para Car Counter."""

import logging
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
LOG_FORMAT_SIMPLE = "[%(levelname)-7s] %(message)s"
DATE_FORMAT = "%H:%M:%S"

_configured = False


def setup_logging(level="INFO", simple=True):
    """Configura logging global para el proyecto.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        simple: True para formato compacto sin timestamp
    """
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt = LOG_FORMAT_SIMPLE if simple else LOG_FORMAT

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=DATE_FORMAT))

    root = logging.getLogger("carcounter")
    root.setLevel(numeric_level)
    root.addHandler(handler)
    root.propagate = False

    _configured = True


def get_logger(name):
    """Retorna un logger bajo el namespace carcounter."""
    return logging.getLogger(f"carcounter.{name}")
