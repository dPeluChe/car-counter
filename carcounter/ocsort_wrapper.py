"""OC-SORT tracker wrapper compatible con la interfaz SORT del proyecto.

OC-SORT (Observation-Centric SORT) agrega sobre ByteTrack:
- ORU: Re-Update virtual para suavizar re-adquisicion tras oclusiones
- OCM: Direction Consistency en el costo de asociacion (reduce ID switches)

Requiere: pip install trackers supervision
"""

import numpy as np

_OCSORT_AVAILABLE = False
try:
    from trackers import OCSORTTracker
    import supervision as sv
    _OCSORT_AVAILABLE = True
except ImportError:
    pass


def is_ocsort_available():
    return _OCSORT_AVAILABLE


class OCSortWrapper:
    """Wrapper que adapta OCSORTTracker a la interfaz SORT (numpy in/out)."""

    def __init__(self, max_age=40, min_hits=3, iou_threshold=0.2,
                 direction_consistency_weight=0.2, high_conf_threshold=0.1,
                 frame_rate=30.0):
        if not _OCSORT_AVAILABLE:
            raise ImportError(
                "OC-SORT requiere: pip install trackers supervision"
            )
        self._tracker = OCSORTTracker(
            lost_track_buffer=max_age,
            minimum_consecutive_frames=min_hits,
            minimum_iou_threshold=iou_threshold,
            direction_consistency_weight=direction_consistency_weight,
            high_conf_det_threshold=high_conf_threshold,
            frame_rate=frame_rate,
        )

    def update(self, dets=np.empty((0, 5))):
        """Interfaz compatible con Sort.update().

        Args:
            dets: np.array (N,5) con [x1, y1, x2, y2, conf]

        Returns:
            np.array (M,5) con [x1, y1, x2, y2, track_id]
        """
        if len(dets) == 0:
            sv_dets = sv.Detections.empty()
        else:
            sv_dets = sv.Detections(
                xyxy=dets[:, :4].astype(np.float32),
                confidence=dets[:, 4].astype(np.float32),
            )

        tracked = self._tracker.update(sv_dets)

        if tracked.tracker_id is None or len(tracked.tracker_id) == 0:
            return np.empty((0, 5))

        # Filter out unconfirmed tracks (id == -1)
        valid = tracked.tracker_id >= 0
        if not valid.any():
            return np.empty((0, 5))

        xyxy = tracked.xyxy[valid]
        tids = tracked.tracker_id[valid].reshape(-1, 1)
        return np.hstack([xyxy, tids]).astype(np.float64)
