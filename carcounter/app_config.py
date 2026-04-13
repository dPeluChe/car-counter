"""Typed configuration with dataclasses, validation, and defaults.

Replaces raw dict access in config_io.py with structured types.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class SampleConstraints:
    """Geometric constraints derived from vehicle samples."""
    min_width: int = 0
    max_width: int = 999999
    min_height: int = 0
    max_height: int = 999999
    min_area: int = 0
    max_area: int = 999999
    min_aspect: float = 0.0
    max_aspect: float = 999999.0


@dataclass
class SettingsConfig:
    """Detection and filtering settings."""
    conf_threshold: float = 0.10
    imgsz: int = 1600
    min_area: int = 0
    max_area: int = 999999
    sample_constraints: Optional[SampleConstraints] = None
    sample_count: int = 0
    conf_per_class: Optional[dict[str, float]] = None
    min_origin_frames: int = 3
    min_dest_frames: int = 3
    min_crossing_frames: int = 2

    def validate(self) -> list[str]:
        errors = []
        if not 0.0 < self.conf_threshold <= 1.0:
            errors.append(f"conf_threshold debe estar entre 0 y 1, got {self.conf_threshold}")
        if self.imgsz < 320:
            errors.append(f"imgsz debe ser >= 320, got {self.imgsz}")
        if self.min_area < 0:
            errors.append(f"min_area no puede ser negativo, got {self.min_area}")
        if self.max_area < self.min_area:
            errors.append(f"max_area ({self.max_area}) < min_area ({self.min_area})")
        return errors


@dataclass
class SAHIConfig:
    """SAHI tiling parameters."""
    slice_width: int = 512
    slice_height: int = 512
    overlap_ratio: float = 0.2
    nms_threshold: float = 0.3

    def validate(self) -> list[str]:
        errors = []
        if self.slice_width < 64:
            errors.append(f"slice_width debe ser >= 64, got {self.slice_width}")
        if self.slice_height < 64:
            errors.append(f"slice_height debe ser >= 64, got {self.slice_height}")
        if not 0.0 <= self.overlap_ratio <= 0.9:
            errors.append(f"overlap_ratio debe estar entre 0 y 0.9, got {self.overlap_ratio}")
        return errors


@dataclass
class TrackerConfig:
    """SORT/OC-SORT tracker parameters."""
    max_age: int = 40
    min_hits: int = 3
    iou_threshold: float = 0.2

    def validate(self) -> list[str]:
        errors = []
        if self.max_age < 1:
            errors.append(f"max_age debe ser >= 1, got {self.max_age}")
        if self.min_hits < 1:
            errors.append(f"min_hits debe ser >= 1, got {self.min_hits}")
        if not 0.0 < self.iou_threshold <= 1.0:
            errors.append(f"iou_threshold debe estar entre 0 y 1, got {self.iou_threshold}")
        return errors


@dataclass
class LineConfig:
    """A single counting line."""
    name: str = ""
    points: list = field(default_factory=list)
    tolerance: int = 15


@dataclass
class AppConfig:
    """Root configuration for the car counter application."""
    counting_mode: str = "zones"
    exclusion_zones: dict[str, list] = field(default_factory=dict)
    zones: dict[str, list] = field(default_factory=dict)
    lines: list[LineConfig] = field(default_factory=list)
    directions: dict[str, list] = field(default_factory=dict)
    settings: SettingsConfig = field(default_factory=SettingsConfig)
    sahi: SAHIConfig = field(default_factory=SAHIConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    video_path: str = ""
    model_path: str = ""

    def validate(self) -> list[str]:
        """Validate entire config, returns list of error messages."""
        errors = []

        if self.counting_mode not in ("zones", "lines", "directions"):
            errors.append(f"counting_mode invalido: '{self.counting_mode}'")

        if self.counting_mode == "zones" and len(self.zones) < 2:
            errors.append(f"Modo zones requiere al menos 2 zonas, hay {len(self.zones)}")

        if self.counting_mode == "lines" and len(self.lines) < 1:
            errors.append("Modo lines requiere al menos 1 linea")

        for name, pts in self.zones.items():
            if len(pts) < 3:
                errors.append(f"Zona '{name}' tiene {len(pts)} puntos (min 3)")

        for line in self.lines:
            if len(line.points) < 2:
                errors.append(f"Linea '{line.name}' tiene {len(line.points)} puntos (min 2)")

        errors.extend(self.settings.validate())
        errors.extend(self.sahi.validate())
        errors.extend(self.tracker.validate())

        return errors

    @classmethod
    def from_dict(cls, d: dict) -> AppConfig:
        """Construct from a raw JSON dict with defaults for missing keys."""
        settings_d = d.get("settings", {})
        sc_raw = settings_d.get("sample_constraints")
        sc = SampleConstraints(**sc_raw) if isinstance(sc_raw, dict) else None

        settings = SettingsConfig(
            conf_threshold=settings_d.get("conf_threshold", 0.10),
            imgsz=settings_d.get("imgsz", 1600),
            min_area=settings_d.get("min_area", 0),
            max_area=settings_d.get("max_area", 999999),
            sample_constraints=sc,
            sample_count=settings_d.get("sample_count", 0),
            conf_per_class=settings_d.get("conf_per_class"),
            min_origin_frames=settings_d.get("min_origin_frames", 3),
            min_dest_frames=settings_d.get("min_dest_frames", 3),
            min_crossing_frames=settings_d.get("min_crossing_frames", 2),
        )

        sahi_d = d.get("sahi", {})
        sahi = SAHIConfig(
            slice_width=sahi_d.get("slice_width", 512),
            slice_height=sahi_d.get("slice_height", 512),
            overlap_ratio=sahi_d.get("overlap_ratio", 0.2),
            nms_threshold=sahi_d.get("nms_threshold", 0.3),
        )

        tracker_d = d.get("tracker", {})
        tracker = TrackerConfig(
            max_age=tracker_d.get("max_age", 40),
            min_hits=tracker_d.get("min_hits", 3),
            iou_threshold=tracker_d.get("iou_threshold", 0.2),
        )

        lines_raw = d.get("lines", [])
        lines = [
            LineConfig(
                name=lc.get("name", f"Linea {i+1}"),
                points=lc.get("points", []),
                tolerance=lc.get("tolerance", 15),
            )
            for i, lc in enumerate(lines_raw)
        ]

        return cls(
            counting_mode=d.get("counting_mode", "zones"),
            exclusion_zones=d.get("exclusion_zones", {}),
            zones=d.get("zones", {}),
            lines=lines,
            directions=d.get("directions", {}),
            settings=settings,
            sahi=sahi,
            tracker=tracker,
            video_path=d.get("video_path", ""),
            model_path=d.get("model_path", ""),
        )

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        sc = None
        if self.settings.sample_constraints:
            sc = asdict(self.settings.sample_constraints)

        config = {
            "counting_mode": self.counting_mode,
            "exclusion_zones": dict(self.exclusion_zones),
            "zones": dict(self.zones),
            "lines": [
                {"name": l.name, "points": l.points, "tolerance": l.tolerance}
                for l in self.lines
            ],
            "settings": {
                "min_area": self.settings.min_area,
                "max_area": self.settings.max_area,
                "conf_threshold": round(self.settings.conf_threshold, 2),
                "imgsz": self.settings.imgsz,
                "sample_constraints": sc,
                "sample_count": self.settings.sample_count,
            },
            "sahi": asdict(self.sahi),
            "tracker": asdict(self.tracker),
            "video_path": self.video_path,
            "model_path": self.model_path,
        }

        if self.settings.conf_per_class:
            config["settings"]["conf_per_class"] = {
                k: round(v, 2) for k, v in self.settings.conf_per_class.items()
            }

        if self.directions:
            config["directions"] = self.directions

        return config

    @classmethod
    def load(cls, path: str | Path) -> AppConfig:
        """Load config from JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def save(self, path: str | Path):
        """Save config to JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
