"""Integration tests para el pipeline completo: config → detect → count → export.

Testea el flujo end-to-end sin dependencias externas (YOLO, video real).
Usa mocks para el modelo y frames sinteticos.
"""

import json
import os
import tempfile
import numpy as np
import pytest

from carcounter.counting import VehicleCounter
from carcounter.config_io import build_config, save_config, load_config
from carcounter.export import export_json, export_csv, export_tracks_csv, export_od_matrix_csv
from carcounter.drawing import (
    draw_zones, draw_lines, draw_exclusion_zones,
    draw_tracked_boxes, draw_routes_panel, draw_hud,
    DensityHeatmap, format_time,
)
from carcounter.geometry import build_zone_masks
from carcounter.app_config import AppConfig, SettingsConfig, SAHIConfig, TrackerConfig
from carcounter.draw_utils import TextStyler, ShapeDrawer
from carcounter.frame_renderer import FrameRenderer
from carcounter.logging_config import setup_logging


# ── Helpers ──────────────────────────────────

def make_frame(w=640, h=480):
    """Crea un frame sintetico negro."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def make_zones():
    """Crea dos zonas cuadradas para tests."""
    return {
        "A": np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=np.int32),
        "B": np.array([[300, 10], [400, 10], [400, 110], [300, 110]], dtype=np.int32),
    }


def simulate_route(counter, trk_id, cls_name="car", origin_pos=(50, 50),
                    transit_pos=(200, 50), dest_pos=(350, 50),
                    origin_frames=3, transit_frames=2, dest_frames=3):
    """Simula un vehiculo completando una ruta A->B."""
    frame = 0
    # Origin
    for _ in range(origin_frames):
        frame += 1
        counter.set_frame(frame)
        counter.update(trk_id, *origin_pos, cls_name, "zones",
                       bbox=(origin_pos[0]-20, origin_pos[1]-20,
                             origin_pos[0]+20, origin_pos[1]+20))
    # Transit
    for _ in range(transit_frames):
        frame += 1
        counter.set_frame(frame)
        counter.update(trk_id, *transit_pos, cls_name, "zones",
                       bbox=(transit_pos[0]-20, transit_pos[1]-20,
                             transit_pos[0]+20, transit_pos[1]+20))
    # Destination
    for _ in range(dest_frames):
        frame += 1
        counter.set_frame(frame)
        counter.update(trk_id, *dest_pos, cls_name, "zones",
                       bbox=(dest_pos[0]-20, dest_pos[1]-20,
                             dest_pos[0]+20, dest_pos[1]+20))
    return frame


# ── Pipeline Integration Tests ────────────────

class TestPipelineEndToEnd:
    """Tests para el pipeline completo config → count → export."""

    def test_full_pipeline_zones_mode(self, tmp_path):
        """Simula el pipeline completo en modo zones."""
        # 1. Build and save config
        config = build_config(
            counting_mode="zones",
            exclusion_zones={},
            zones={"A": [[10, 10], [110, 10], [110, 110], [10, 110]],
                   "B": [[300, 10], [400, 10], [400, 110], [300, 110]]},
            counting_lines={},
            min_area=100, max_area=50000,
            conf_threshold=0.10, imgsz=640,
            sample_constraints=None, sample_count=0,
            conf_per_class={"car": 0.1, "motorbike": 0.1, "bus": 0.1, "truck": 0.1},
            conf_per_class_modified=False,
            slice_w=512, slice_h=512, overlap=0.2, nms_threshold=0.3,
            max_age=40, min_hits=3, iou_threshold=0.2,
            video_path="test.mp4", model_path="yolo.pt",
        )
        config_path = str(tmp_path / "config.json")
        save_config(config_path, config)

        # 2. Load config back
        loaded = load_config(config_path)
        assert loaded["counting_mode"] == "zones"

        # 3. Setup counter
        zones_np = {name: np.array(pts, dtype=np.int32)
                    for name, pts in loaded["zones"].items()}
        counter = VehicleCounter(
            zones_np=zones_np, counting_lines=[],
            min_origin_frames=3, min_dest_frames=3,
            frame_size=(640, 480),
        )

        # 4. Simulate detections (5 vehicles: A->B)
        for i in range(5):
            simulate_route(counter, trk_id=i+1, cls_name="car")

        # 5. Verify counting
        assert "A → B" in counter.routes_matrix
        assert counter.routes_matrix["A → B"] == 5
        assert counter.total_vehicles_ever == 5
        assert counter.od_matrix == {"A": {"B": 5}}

        # 6. Export JSON
        json_path = str(tmp_path / "results.json")
        export_json(
            json_path, video_path="test.mp4", config_path=config_path,
            use_sahi=False, tracker_backend="sort",
            counting_mode="zones", frame_count=100, total_frames=100,
            duration=10.0, total_time=5.0, avg_fps=20.0,
            total_vehicles=5, routes_matrix=counter.routes_matrix,
            zone_names=list(zones_np.keys()),
        )
        assert os.path.isfile(json_path)
        with open(json_path) as f:
            result = json.load(f)
        assert result["total_routes_completed"] == 5
        assert "A → B" in result["routes"]

        # 7. Export CSV
        csv_path = str(tmp_path / "routes.csv")
        export_csv(csv_path, counter.routes_matrix)
        assert os.path.isfile(csv_path)

        # 8. Export tracks CSV
        tracks_path = str(tmp_path / "tracks.csv")
        export_tracks_csv(tracks_path, counter.get_track_data())
        assert os.path.isfile(tracks_path)

        # 9. Export OD matrix
        od_path = str(tmp_path / "od.csv")
        export_od_matrix_csv(od_path, counter.od_matrix)
        assert os.path.isfile(od_path)

    def test_full_pipeline_lines_mode(self, tmp_path):
        """Simula el pipeline completo en modo lines."""
        lines = [{
            "name": "Linea 1",
            "pt1": (0, 100), "pt2": (400, 100),
            "tolerance": 30,
        }]
        counter = VehicleCounter(
            zones_np={}, counting_lines=lines,
            min_crossing_frames=1,
        )

        # Simulate crossing down
        counter.set_frame(1)
        counter.update(1, 100, 80, "car", "lines")
        counter.set_frame(2)
        counter.update(1, 100, 120, "car", "lines")

        # Simulate crossing up
        counter.set_frame(3)
        counter.update(2, 200, 120, "truck", "lines")
        counter.set_frame(4)
        counter.update(2, 200, 80, "truck", "lines")

        assert "Linea 1 ↓" in counter.routes_matrix
        assert "Linea 1 ↑" in counter.routes_matrix
        assert counter.routes_matrix["Linea 1 ↓"] == 1
        assert counter.routes_matrix["Linea 1 ↑"] == 1

        # Export
        json_path = str(tmp_path / "results.json")
        export_json(
            json_path, video_path="test.mp4", config_path="config.json",
            use_sahi=False, tracker_backend="sort",
            counting_mode="lines", frame_count=4, total_frames=4,
            duration=1.0, total_time=0.5, avg_fps=8.0,
            total_vehicles=2, routes_matrix=counter.routes_matrix,
            zone_names=[],
        )
        with open(json_path) as f:
            result = json.load(f)
        assert result["total_routes_completed"] == 2

    def test_multi_class_od_matrix(self):
        """Verifica que la OD matrix por clase funcione correctamente."""
        zones_np = {
            "Norte": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32),
            "Sur": np.array([[300, 0], [400, 0], [400, 100], [300, 100]], dtype=np.int32),
        }
        counter = VehicleCounter(
            zones_np=zones_np, counting_lines=[],
            min_origin_frames=2, min_dest_frames=2,
            frame_size=(500, 200),
        )

        # Car: Norte->Sur
        simulate_route(counter, 1, "car", (50, 50), (200, 50), (350, 50), 2, 1, 2)
        # Truck: Norte->Sur
        simulate_route(counter, 2, "truck", (50, 50), (200, 50), (350, 50), 2, 1, 2)
        # Bus: Sur->Norte
        simulate_route(counter, 3, "bus", (350, 50), (200, 50), (50, 50), 2, 1, 2)

        assert counter.routes_matrix["Norte → Sur"] == 2
        assert counter.routes_matrix["Sur → Norte"] == 1
        assert counter.od_matrix_by_class["Norte"]["Sur"]["car"] == 1
        assert counter.od_matrix_by_class["Norte"]["Sur"]["truck"] == 1
        assert counter.od_matrix_by_class["Sur"]["Norte"]["bus"] == 1


# ── Drawing Integration Tests ─────────────────

class TestDrawingIntegration:
    """Tests para el pipeline de dibujo completo."""

    def test_full_drawing_pipeline(self):
        """Verifica que todas las funciones de dibujo no crashean."""
        frame = make_frame(640, 480)
        zones_np = make_zones()
        excl_np = {"park": np.array([[500, 400], [600, 400], [600, 450], [500, 450]], dtype=np.int32)}

        draw_exclusion_zones(frame, excl_np)
        draw_zones(frame, zones_np)

        tracked = [(50, 50, 90, 90, 1, "car"), (350, 50, 390, 90, 2, "truck")]
        tracks_info = {
            1: {"state": "origin", "origin": "A"},
            2: {"state": "done", "origin": "B"},
        }
        draw_tracked_boxes(frame, tracked, tracks_info, ["A", "B"],
                           trails={1: [(50, 50), (55, 55), (60, 60)]})

        routes = {"A → B": 3, "B → A": 1}
        draw_routes_panel(frame, routes, 2)
        draw_hud(frame, 50, 100, 15.5, 2, 4, 640)

        # Should not crash — visual correctness is verified manually
        assert frame.shape == (480, 640, 3)

    def test_drawing_lines_mode(self):
        """Verifica dibujo en modo lineas."""
        frame = make_frame(640, 480)
        lines = [
            {"name": "L1", "pt1": (0, 240), "pt2": (640, 240), "tolerance": 20},
        ]
        draw_lines(frame, lines)
        assert frame.shape == (480, 640, 3)

    def test_heatmap_integration(self):
        """Verifica que el heatmap se integra con el pipeline."""
        frame = make_frame(200, 200)
        hm = DensityHeatmap(200, 200, decay=1.0)
        for _ in range(10):
            hm.update([(100, 100), (50, 50)])
        hm.draw(frame)
        assert frame.shape == (200, 200, 3)
        assert frame[100, 100].sum() > 0  # heatmap modifica pixels


# ── Config Integration Tests ──────────────────

class TestConfigIntegration:
    """Tests para el pipeline de configuracion completo."""

    def test_config_round_trip_full(self, tmp_path):
        """Config -> save -> load -> counter funciona correctamente."""
        config = build_config(
            counting_mode="zones",
            exclusion_zones={"park": [[500, 400], [600, 400], [600, 450]]},
            zones={"A": [[10, 10], [110, 10], [110, 110]],
                   "B": [[300, 10], [400, 10], [400, 110]]},
            counting_lines={},
            min_area=100, max_area=50000,
            conf_threshold=0.15, imgsz=1280,
            sample_constraints={"min_width": 20, "max_width": 200,
                                "min_height": 20, "max_height": 200,
                                "min_area": 400, "max_area": 40000,
                                "min_aspect": 0.5, "max_aspect": 3.0},
            sample_count=5,
            conf_per_class={"car": 0.15, "motorbike": 0.2, "bus": 0.15, "truck": 0.1},
            conf_per_class_modified=True,
            slice_w=256, slice_h=256, overlap=0.3, nms_threshold=0.25,
            max_age=30, min_hits=2, iou_threshold=0.3,
            video_path="video.mp4", model_path="yolo.pt",
        )

        path = str(tmp_path / "config.json")
        save_config(path, config)
        loaded = load_config(path)

        # Verify zones load correctly
        zones_np = {n: np.array(pts, dtype=np.int32)
                    for n, pts in loaded["zones"].items()}
        counter = VehicleCounter(
            zones_np=zones_np, counting_lines=[],
            min_origin_frames=3, min_dest_frames=3,
        )
        assert counter.zone_names == ["A", "B"]

    def test_app_config_dataclass_round_trip(self, tmp_path):
        """AppConfig dataclass round-trip."""
        config = AppConfig(
            counting_mode="zones",
            zones={"A": [[0, 0], [100, 0], [100, 100]],
                   "B": [[200, 0], [300, 0], [300, 100]]},
            settings=SettingsConfig(conf_threshold=0.15, imgsz=1280),
            sahi=SAHIConfig(slice_width=256),
            tracker=TrackerConfig(max_age=30),
        )

        path = str(tmp_path / "config.json")
        config.save(path)
        loaded = AppConfig.load(path)

        assert loaded.counting_mode == "zones"
        assert len(loaded.zones) == 2
        assert loaded.settings.conf_threshold == 0.15
        assert loaded.sahi.slice_width == 256
        assert loaded.tracker.max_age == 30

    def test_app_config_validation(self):
        """AppConfig validates correctly."""
        # Valid config
        config = AppConfig(
            counting_mode="zones",
            zones={"A": [[0, 0], [100, 0], [100, 100]],
                   "B": [[200, 0], [300, 0], [300, 100]]},
        )
        assert len(config.validate()) == 0

        # Invalid: not enough zones
        config_bad = AppConfig(counting_mode="zones", zones={"A": [[0, 0]]})
        errors = config_bad.validate()
        assert len(errors) > 0

    def test_app_config_from_legacy_dict(self):
        """AppConfig loads from legacy JSON dict format."""
        legacy = {
            "counting_mode": "zones",
            "zones": {"A": [[0, 0], [100, 0], [100, 100]]},
            "settings": {"conf_threshold": 0.2},
            "sahi": {"slice_width": 256},
            "tracker": {"max_age": 30},
        }
        config = AppConfig.from_dict(legacy)
        assert config.settings.conf_threshold == 0.2
        assert config.sahi.slice_width == 256


# ── FrameRenderer Tests ───────────────────────

class TestFrameRenderer:
    """Tests para FrameRenderer (GUI-free rendering)."""

    def test_draw_zones(self):
        frame = make_frame(640, 480)
        zones = {"A": [(10, 10), (110, 10), (110, 110), (10, 110)]}
        result = FrameRenderer.draw_zones(frame, zones)
        assert result.shape == (480, 640, 3)
        assert not np.array_equal(result, frame)  # something was drawn

    def test_draw_exclusion_zones(self):
        frame = make_frame(640, 480)
        excl = {"park": [(500, 400), (600, 400), (600, 450), (500, 450)]}
        result = FrameRenderer.draw_exclusion_zones(frame, excl)
        assert result.shape == (480, 640, 3)

    def test_draw_detections(self):
        frame = make_frame(640, 480)
        dets = [{"bbox": (10, 10, 50, 50), "cls_name": "car", "conf": 0.85}]
        result = FrameRenderer.draw_detections(frame, dets)
        assert result.shape == (480, 640, 3)

    def test_draw_tile_grid(self):
        frame = make_frame(640, 480)
        result, count, cols, rows = FrameRenderer.draw_tile_grid(
            frame, 640, 480, 256, 256, 0.2)
        assert count > 0
        assert cols > 0
        assert rows > 0


# ── DrawUtils Tests ───────────────────────────

class TestDrawUtils:
    """Tests para TextStyler y ShapeDrawer."""

    def test_text_styler_draw(self):
        frame = make_frame(200, 200)
        TextStyler.draw(frame, "Test", (10, 30), (255, 255, 255))
        assert frame.sum() > 0

    def test_text_styler_centered(self):
        frame = make_frame(200, 200)
        TextStyler.centered(frame, "Center", 100, 100, (255, 255, 255))
        assert frame.sum() > 0

    def test_shape_drawer_bbox(self):
        frame = make_frame(200, 200)
        ShapeDrawer.bbox(frame, 10, 10, 50, 50, (0, 255, 0))
        assert frame[10, 10].sum() > 0

    def test_shape_drawer_panel_bg(self):
        frame = make_frame(200, 200)
        frame[:] = 128  # gray
        ShapeDrawer.panel_bg(frame, 10, 10, 100, 100)
        # Panel area should be darker than 128
        assert frame[50, 50].sum() < 128 * 3

    def test_shape_drawer_trail(self):
        frame = make_frame(200, 200)
        points = [(10, 10), (50, 50), (100, 100)]
        ShapeDrawer.trail(frame, points, (255, 0, 0))
        assert frame.sum() > 0


# ── Logging Integration Tests ─────────────────

class TestLoggingIntegration:
    """Tests para el sistema de logging."""

    def test_setup_logging_idempotent(self):
        """Calling setup_logging twice should not crash."""
        setup_logging("INFO")
        setup_logging("DEBUG")  # second call is a no-op

    def test_format_time(self):
        assert format_time(0) == "0s"
        assert format_time(65) == "1m 5s"
        assert format_time(3665) == "1h 1m 5s"
