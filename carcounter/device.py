"""Auto-deteccion de device para inferencia (CPU/CUDA/MPS)."""

import torch


def detect_device(requested="auto"):
    """Detecta el mejor device disponible.

    Args:
        requested: "auto", "cpu", "cuda", o "mps"

    Returns:
        Tuple (device_str, description) para usar en YOLO y SAHI.
    """
    if requested != "auto":
        return requested, requested

    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return "cuda", f"cuda ({name})"

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps", "mps (Apple Silicon)"

    return "cpu", "cpu"
