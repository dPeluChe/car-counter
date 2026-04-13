"""Dataclasses para el estado del configurador y del tracker.

Reemplaza los dicts sueltos (tracks_info, vehicle_samples, etc.)
con tipos estructurados para claridad y type safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─── Tracking state (counting.py) ────────────────────────────

@dataclass
class TrackState:
    """Estado de un track individual en VehicleCounter."""
    state: str = "new"          # new, origin, transit, done, tracking
    origin: Optional[str] = None
    cls_name: str = "car"
    zone_frames: int = 0
    last_seen_frame: int = 0
    dest_zone: Optional[str] = None
    dest_frames: int = 0
    # Lines mode
    lines_crossed: set = field(default_factory=set)
    # Directions mode
    first_pos: Optional[tuple] = None
    last_pos: Optional[tuple] = None
    frame_count: int = 0
    assigned_direction: Optional[str] = None


@dataclass
class ShapeMetrics:
    """Metricas de forma promediadas (EMA) de un vehiculo."""
    avg_width: float = 0.0
    avg_height: float = 0.0
    avg_area: float = 0.0
    avg_aspect: float = 0.0
    avg_elongation: float = 0.0
    samples: int = 0

    def update(self, width: float, height: float, alpha: float = 0.3):
        """Actualiza con exponential moving average."""
        area = width * height
        aspect = width / height if height > 0 else 1.0
        elongation = max(width, height) / min(width, height) if min(width, height) > 0 else 1.0

        if self.samples == 0:
            self.avg_width = width
            self.avg_height = height
            self.avg_area = area
            self.avg_aspect = aspect
            self.avg_elongation = elongation
        else:
            self.avg_width = self.avg_width * (1 - alpha) + width * alpha
            self.avg_height = self.avg_height * (1 - alpha) + height * alpha
            self.avg_area = self.avg_area * (1 - alpha) + area * alpha
            self.avg_aspect = self.avg_aspect * (1 - alpha) + aspect * alpha
            self.avg_elongation = self.avg_elongation * (1 - alpha) + elongation * alpha
        self.samples += 1

    def to_dict(self) -> dict:
        return {
            "avg_width": self.avg_width,
            "avg_height": self.avg_height,
            "avg_area": self.avg_area,
            "avg_aspect": self.avg_aspect,
            "avg_elongation": self.avg_elongation,
            "samples": self.samples,
        }


# ─── Setup state (setup.py) ─────────────────────────────────

@dataclass
class ExclusionState:
    """Estado de las zonas de exclusion en el configurador."""
    zones: dict = field(default_factory=dict)        # {name: [(x,y), ...]}
    current_pts: list = field(default_factory=list)   # puntos en progreso
    drawing: bool = False
    zone_name: str = "Exclusion 1"
    selected: str = ""


@dataclass
class CalibrationState:
    """Estado de la calibracion en el configurador."""
    rect_start: Optional[tuple] = None
    rect_end: Optional[tuple] = None
    drawing: bool = False
    confirmed: bool = False
    test_passed: bool = False
    vehicle_samples: list = field(default_factory=list)
    conf_threshold: float = 0.10
    infer_imgsz: int = 1600
    min_area: int = 0
    max_area: int = 999999


@dataclass
class ZonesState:
    """Estado de las zonas de conteo en el configurador."""
    zones: dict = field(default_factory=dict)         # {name: [(x,y), ...]}
    current_pts: list = field(default_factory=list)    # puntos en progreso
    drawing: bool = False
    zone_name: str = "Norte"
    counting_mode: str = "zones"
    # Lines
    counting_lines: dict = field(default_factory=dict)
    line_drawing: bool = False
    line_start: Optional[tuple] = None
    line_name: str = "Linea 1"


@dataclass
class SAHIState:
    """Estado de los parametros SAHI en el configurador."""
    slice_w: int = 512
    slice_h: int = 512
    overlap: float = 0.2
    nms_threshold: float = 0.3
    tile_grid_visible: bool = True


@dataclass
class TrackerState:
    """Estado de los parametros del tracker en el configurador."""
    max_age: int = 40
    min_hits: int = 3
    iou_threshold: float = 0.2


@dataclass
class VehicleSample:
    """Una muestra de vehiculo para calibracion."""
    bbox: tuple = (0, 0, 0, 0)
    width: int = 0
    height: int = 0
    area: int = 0
    aspect: float = 1.0
