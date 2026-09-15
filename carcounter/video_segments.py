"""Division de un video en tramos donde la camara se mantiene estable respecto a un frame de referencia."""

from carcounter.camera_motion import CameraMotionMonitor


def default_anchors(width, height):
    """Esquinas del recuadro central (50 %): donde suele estar la geometria del aforo."""
    return [[width * 0.25, height * 0.25], [width * 0.75, height * 0.25],
            [width * 0.25, height * 0.75], [width * 0.75, height * 0.75]]


def segment_by_stability(samples, total_frames, *, max_drift_px=10.0, min_stable_frames=1,
                         anchors=None, inference_roi=None):
    """Agrupa muestras (numero de frame desde 1, frame BGR) en tramos de camara estable.

    Un tramo termina cuando una muestra supera max_drift_px respecto al primer frame del tramo
    o no se puede estimar; esa muestra abre el siguiente tramo.
    """
    segments, monitor, current = [], None, None
    for number, frame in samples:
        if current is not None:
            result = monitor.check(frame)
            if result["status"] == "stable":
                current["samples"] += 1
                current["max_drift_px"] = max(current["max_drift_px"], result["max_drift_px"])
                continue
            current.update(end_frame=number - 1, split=dict(
                frame=number, status=result["status"], drift_px=result["max_drift_px"],
                reason=result["reason"]))
            segments.append(current)
        height, width = frame.shape[:2]
        monitor = CameraMotionMonitor(frame, anchors=anchors or default_anchors(width, height),
                                      inference_roi=inference_roi, max_drift_px=max_drift_px)
        current = dict(start_frame=number, reference_frame=number, samples=1, max_drift_px=0.0)
    if current is None:
        raise ValueError("No hay muestras para segmentar")
    current.update(end_frame=total_frames, split=None)
    segments.append(current)
    return _label(segments, min_stable_frames)


def _label(segments, min_stable_frames):
    labeled = []
    for segment in segments:
        segment["frames"] = segment["end_frame"] - segment["start_frame"] + 1
        segment["label"] = "stable" if segment["frames"] >= min_stable_frames else "transition"
        previous = labeled[-1] if labeled else None
        if previous and previous["label"] == segment["label"] == "transition":
            previous.update(end_frame=segment["end_frame"], split=segment["split"],
                            frames=segment["end_frame"] - previous["start_frame"] + 1,
                            samples=previous["samples"] + segment["samples"],
                            max_drift_px=max(previous["max_drift_px"], segment["max_drift_px"]))
            continue
        labeled.append(segment)
    for index, segment in enumerate(labeled, 1):
        segment["index"] = index
        if segment["label"] == "transition":
            segment["reference_frame"] = None
    return labeled
