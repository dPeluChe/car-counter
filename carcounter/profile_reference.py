from pathlib import Path
import re

import cv2

from carcounter.detection_cache import file_digest


def reference_errors(reference):
    if reference is None:
        return []
    if not isinstance(reference, dict):
        return ["geometry_reference debe ser un objeto"]
    errors = []
    if not re.fullmatch(r"[0-9a-f]{64}", str(reference.get("video_sha256", ""))):
        errors.append("geometry_reference.video_sha256 inválido")
    for key in ("frame_index", "width", "height"):
        if type(reference.get(key)) is not int or reference[key] < 1:
            errors.append(f"geometry_reference.{key} debe ser un entero positivo")
    return errors


def reference_frame(video_path, frame_index):
    cap = cv2.VideoCapture(str(video_path))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or not 1 <= frame_index <= total:
            raise ValueError("Frame de referencia fuera del video")
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index - 1)
        ok, frame = cap.read()
        if not ok:
            raise ValueError("No se pudo leer el frame de referencia")
        return frame
    finally:
        cap.release()


def make_geometry_reference(video_path, frame_index):
    frame = reference_frame(video_path, frame_index)
    height, width = frame.shape[:2]
    return dict(video_sha256=file_digest(video_path), frame_index=frame_index,
                width=width, height=height)


def validate_profile_video(config, video_path):
    reference = config.get("geometry_reference")
    errors = reference_errors(reference)
    if errors:
        raise ValueError("\n".join(errors))
    if reference is not None:
        if file_digest(video_path) != reference["video_sha256"]:
            raise ValueError("El video no coincide con la geometría calibrada. Crea un perfil para este video.")
        frame = reference_frame(video_path, reference["frame_index"])
        if frame.shape[:2] != (reference["height"], reference["width"]):
            raise ValueError("La resolución no coincide con la referencia geométrica")
        return frame
    original = config.get("video_path")
    if original and Path(original).resolve() != Path(video_path).resolve():
        if not Path(original).is_file() or file_digest(original) != file_digest(video_path):
            raise ValueError("Perfil sin referencia: no se puede reutilizar su geometría en otro video.")
    return None
