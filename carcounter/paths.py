"""
carcounter/paths.py
Centralized path resolution for the car counter project.

All paths resolve relative to PROJECT_ROOT (the repo root).
To switch to system paths later (e.g. ~/.carcounter/), only this module changes.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Paths:
    """Resolve all project paths from a single root."""

    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root

    # ── Directories ──────────────────────────────
    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def models_dir(self) -> Path:
        return self.root / "models" / "yolo"

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def benchmarks_dir(self) -> Path:
        return self.root / "output" / "benchmarks"

    # ── Default file paths ───────────────────────
    @property
    def default_config(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def default_model(self) -> Path:
        return self.models_dir / "yolov11l.pt"

    @property
    def default_video(self) -> Path:
        return self.assets_dir / "video.mp4"

    @property
    def default_output_video(self) -> Path:
        return self.output_dir / "result.mp4"

    @property
    def default_output_json(self) -> Path:
        return self.output_dir / "results.json"

    @property
    def default_mask(self) -> Path:
        return self.assets_dir / "mask.png"

    # ── Utilities ────────────────────────────────
    def ensure_dirs(self):
        """Create output and config directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, path_str: str) -> Path:
        """Resolve a possibly-relative path against project root."""
        p = Path(path_str)
        if p.is_absolute():
            return p
        return self.root / p


# Singleton
paths = Paths()
