import math

import cv2
import numpy as np

from carcounter.geometry import validate_inference_roi


class CameraMotionMonitor:
    def __init__(self, reference, *, anchors=None, inference_roi=None, max_drift_px=5.0,
                 min_inliers=30, min_inlier_ratio=0.5, image_width=960):
        if not math.isfinite(max_drift_px) or max_drift_px <= 0:
            raise ValueError("max_drift_px debe ser positivo y finito")
        if min_inliers < 3 or not 0 < min_inlier_ratio <= 1 or image_width < 64:
            raise ValueError("Parámetros de correspondencia inválidos")
        self.shape = reference.shape[:2]
        height, width = self.shape
        self.size = (min(width, image_width), max(1, round(height * min(width, image_width) / width)))
        self.scale = np.diag([self.size[0] / width, self.size[1] / height, 1.0])
        self.anchors = np.asarray(anchors if anchors is not None and len(anchors) else
                                  [[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]], dtype=np.float64)
        if self.anchors.ndim != 2 or self.anchors.shape[1] != 2 or not np.isfinite(self.anchors).all():
            raise ValueError("Los puntos de control requieren coordenadas finitas Nx2")
        self.max_drift_px = max_drift_px
        self.min_inliers = min_inliers
        self.min_inlier_ratio = min_inlier_ratio
        self.mask = np.full(self.size[::-1], 255, np.uint8)
        if inference_roi is not None:
            x1, y1, x2, y2 = validate_inference_roi(inference_roi, width, height)
            sx, sy = self.scale[0, 0], self.scale[1, 1]
            self.mask[int(y1 * sy):math.ceil(y2 * sy), int(x1 * sx):math.ceil(x2 * sx)] = 0
        self.orb = cv2.ORB_create(nfeatures=2000)
        self.reference_points, self.reference_descriptors = self._features(reference)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    def _features(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, self.size, interpolation=cv2.INTER_AREA)
        points, descriptors = self.orb.detectAndCompute(gray, self.mask)
        return points, descriptors

    def check(self, frame):
        if frame.shape[:2] != self.shape:
            return self._result("unreliable", reason="Cambió la resolución del video")
        points, descriptors = self._features(frame)
        if self.reference_descriptors is None or descriptors is None or len(descriptors) < 2:
            return self._result("unreliable", reason="No hay textura suficiente para comprobar la cámara")
        pairs = self.matcher.knnMatch(self.reference_descriptors, descriptors, k=2)
        matches = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance]
        unique = {}
        for match in sorted(matches, key=lambda item: item.distance):
            unique.setdefault(match.trainIdx, match)
        matches = list(unique.values())
        if len(matches) < self.min_inliers:
            return self._result("unreliable", matches=len(matches), reason="Pocas correspondencias de fondo")
        source = np.float32([self.reference_points[m.queryIdx].pt for m in matches])
        target = np.float32([points[m.trainIdx].pt for m in matches])
        matrix, mask = cv2.estimateAffinePartial2D(source, target, method=cv2.RANSAC,
                                                ransacReprojThreshold=2.0, maxIters=2000,
                                                confidence=0.99, refineIters=10)
        if matrix is None or mask is None or not np.isfinite(matrix).all():
            return self._result("unreliable", matches=len(matches), reason="No se pudo estimar el movimiento")
        inliers = mask.ravel().astype(bool)
        count = int(inliers.sum())
        ratio = count / len(matches)
        if count < self.min_inliers or ratio < self.min_inlier_ratio:
            return self._result("unreliable", matches=len(matches), inliers=count,
                                reason="Correspondencias inconsistentes")
        span = np.ptp(source[inliers], axis=0) / np.asarray(self.size)
        if min(span) < 0.25:
            return self._result("unreliable", matches=len(matches), inliers=count,
                                reason="Puntos concentrados en una región pequeña")
        full_matrix = np.linalg.inv(self.scale) @ np.vstack([matrix, [0, 0, 1]]) @ self.scale
        projected = np.column_stack([self.anchors, np.ones(len(self.anchors))]) @ full_matrix[:2].T
        drift = float(np.linalg.norm(projected - self.anchors, axis=1).max())
        result = self._result("moved" if drift > self.max_drift_px else "stable", matches=len(matches), inliers=count)
        result.update(max_drift_px=round(drift, 4), transform=full_matrix[:2].tolist())
        return result

    @staticmethod
    def _result(status, matches=0, inliers=0, reason=None):
        return dict(status=status, matches=matches, inliers=inliers,
                    inlier_ratio=round(inliers / matches, 4) if matches else 0,
                    max_drift_px=None, transform=None, reason=reason)


def counting_anchors(config):
    points = [point for line in config.get("lines", []) for point in line.get("points", [])]
    points.extend(point for polygon in config.get("zones", {}).values() for point in polygon)
    points.extend(point for direction in config.get("directions", {}).values() for point in direction)
    return points
