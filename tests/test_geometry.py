"""Tests para carcounter/geometry.py"""

import math
import numpy as np
import pytest
from carcounter.geometry import (
    point_in_zone,
    build_zone_masks,
    point_in_zone_mask,
    bbox_intersects_zone,
    bbox_iou,
    apply_nms,
    passes_geometry_filter,
    in_exclusion_zone,
    point_to_line_side,
    cosine_similarity_2d,
    point_line_distance,
)


# ── point_in_zone ─────────────────────────────

class TestPointInZone:
    """Tests para point_in_zone (cv2.pointPolygonTest wrapper)."""

    @pytest.fixture
    def square(self):
        return np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)

    def test_inside(self, square):
        assert point_in_zone(50, 50, square) is True

    def test_outside(self, square):
        assert point_in_zone(150, 50, square) is False

    def test_on_edge(self, square):
        # cv2.pointPolygonTest returns 0 for edge, >= 0 means inside
        assert point_in_zone(0, 50, square) is True

    def test_on_vertex(self, square):
        assert point_in_zone(0, 0, square) is True

    def test_outside_negative(self, square):
        assert point_in_zone(-10, -10, square) is False

    def test_triangle(self):
        tri = np.array([[0, 0], [200, 0], [100, 200]], dtype=np.int32)
        assert point_in_zone(100, 50, tri) is True
        assert point_in_zone(5, 190, tri) is False


# ── bbox_iou ──────────────────────────────────

class TestBboxIou:
    """Tests para bbox_iou."""

    def test_identical(self):
        box = (10, 10, 50, 50)
        assert bbox_iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        assert bbox_iou((0, 0, 10, 10), (20, 20, 30, 30)) == pytest.approx(0.0)

    def test_partial_overlap(self):
        iou = bbox_iou((0, 0, 10, 10), (5, 5, 15, 15))
        # intersection = 5*5=25, union = 100+100-25=175
        assert iou == pytest.approx(25 / 175)

    def test_contained(self):
        iou = bbox_iou((0, 0, 100, 100), (25, 25, 75, 75))
        # intersection = 50*50=2500, union = 10000+2500-2500=10000
        assert iou == pytest.approx(2500 / 10000)

    def test_zero_area_box(self):
        assert bbox_iou((5, 5, 5, 5), (0, 0, 10, 10)) == pytest.approx(0.0)

    def test_touching_edges(self):
        # Boxes share an edge but no interior overlap
        assert bbox_iou((0, 0, 10, 10), (10, 0, 20, 10)) == pytest.approx(0.0)


# ── apply_nms ─────────────────────────────────

class TestApplyNms:
    """Tests para apply_nms (greedy NMS post-SAHI)."""

    def test_empty(self):
        det, cls = apply_nms([], [], 0.3)
        assert det == []
        assert cls == []

    def test_no_overlap(self):
        dets = [[0, 0, 10, 10, 0.9], [50, 50, 60, 60, 0.8]]
        classes = ["car", "truck"]
        kept_dets, kept_cls = apply_nms(dets, classes, 0.3)
        assert len(kept_dets) == 2

    def test_suppresses_overlap(self):
        dets = [
            [0, 0, 10, 10, 0.9],   # higher conf, kept
            [1, 1, 11, 11, 0.5],   # overlaps heavily, suppressed
        ]
        classes = ["car", "car"]
        kept_dets, kept_cls = apply_nms(dets, classes, 0.3)
        assert len(kept_dets) == 1
        assert kept_dets[0][4] == 0.9

    def test_keeps_low_overlap(self):
        dets = [
            [0, 0, 10, 10, 0.9],
            [8, 8, 18, 18, 0.8],  # small overlap
        ]
        classes = ["car", "car"]
        kept_dets, kept_cls = apply_nms(dets, classes, 0.5)
        assert len(kept_dets) == 2

    def test_preserves_classes(self):
        dets = [
            [0, 0, 10, 10, 0.9],
            [1, 1, 11, 11, 0.5],  # suppressed
            [50, 50, 60, 60, 0.7],
        ]
        classes = ["car", "truck", "bus"]
        kept_dets, kept_cls = apply_nms(dets, classes, 0.3)
        assert kept_cls == ["car", "bus"]


# ── passes_geometry_filter ────────────────────

class TestPassesGeometryFilter:
    """Tests para passes_geometry_filter."""

    def test_passes_defaults(self):
        constraints = {
            "min_area": 0, "max_area": 999999,
            "min_width": 0, "max_width": 999999,
            "min_height": 0, "max_height": 999999,
            "min_aspect": 0.0, "max_aspect": 999999.0,
        }
        assert passes_geometry_filter(0, 0, 50, 50, constraints) is True

    def test_fails_min_area(self):
        constraints = {"min_area": 1000, "max_area": 999999,
                       "min_width": 0, "max_width": 999999,
                       "min_height": 0, "max_height": 999999,
                       "min_aspect": 0.0, "max_aspect": 999999.0}
        # area = 10*10 = 100 < 1000
        assert passes_geometry_filter(0, 0, 10, 10, constraints) is False

    def test_fails_max_area(self):
        constraints = {"min_area": 0, "max_area": 50,
                       "min_width": 0, "max_width": 999999,
                       "min_height": 0, "max_height": 999999,
                       "min_aspect": 0.0, "max_aspect": 999999.0}
        # area = 10*10 = 100 > 50
        assert passes_geometry_filter(0, 0, 10, 10, constraints) is False

    def test_fails_min_width(self):
        constraints = {"min_area": 0, "max_area": 999999,
                       "min_width": 20, "max_width": 999999,
                       "min_height": 0, "max_height": 999999,
                       "min_aspect": 0.0, "max_aspect": 999999.0}
        assert passes_geometry_filter(0, 0, 10, 50, constraints) is False

    def test_fails_aspect_ratio(self):
        constraints = {"min_area": 0, "max_area": 999999,
                       "min_width": 0, "max_width": 999999,
                       "min_height": 0, "max_height": 999999,
                       "min_aspect": 0.5, "max_aspect": 2.0}
        # width=100, height=10, aspect=10.0 > 2.0
        assert passes_geometry_filter(0, 0, 100, 10, constraints) is False

    def test_zero_size_box(self):
        constraints = {"min_area": 0, "max_area": 999999,
                       "min_width": 0, "max_width": 999999,
                       "min_height": 0, "max_height": 999999,
                       "min_aspect": 0.0, "max_aspect": 999999.0}
        # width/height clamped to 1
        assert passes_geometry_filter(5, 5, 5, 5, constraints) is True


# ── in_exclusion_zone ─────────────────────────

class TestInExclusionZone:
    """Tests para in_exclusion_zone."""

    def test_empty_exclusion(self):
        assert in_exclusion_zone(50, 50, {}) is False

    def test_inside_zone(self):
        zones = {"park": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)}
        assert in_exclusion_zone(50, 50, zones) is True

    def test_outside_zone(self):
        zones = {"park": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)}
        assert in_exclusion_zone(150, 150, zones) is False

    def test_multiple_zones(self):
        zones = {
            "park1": np.array([[0, 0], [50, 0], [50, 50], [0, 50]], dtype=np.int32),
            "park2": np.array([[200, 200], [300, 200], [300, 300], [200, 300]], dtype=np.int32),
        }
        assert in_exclusion_zone(25, 25, zones) is True
        assert in_exclusion_zone(250, 250, zones) is True
        assert in_exclusion_zone(100, 100, zones) is False


# ── point_to_line_side ────────────────────────

class TestPointToLineSide:
    """Tests para point_to_line_side (cross product)."""

    def test_horizontal_line_above(self):
        # Line from (0,50) to (100,50), point at (50,0) is above
        side = point_to_line_side(50, 0, 0, 50, 100, 50)
        assert side < 0  # above/left

    def test_horizontal_line_below(self):
        side = point_to_line_side(50, 100, 0, 50, 100, 50)
        assert side > 0  # below/right

    def test_on_line(self):
        side = point_to_line_side(50, 50, 0, 50, 100, 50)
        assert side == 0

    def test_opposite_sides(self):
        s1 = point_to_line_side(50, 0, 0, 50, 100, 50)
        s2 = point_to_line_side(50, 100, 0, 50, 100, 50)
        assert s1 * s2 < 0  # opposite signs


# ── point_line_distance ───────────────────────

class TestPointLineDistance:
    """Tests para point_line_distance."""

    def test_perpendicular_distance(self):
        # Point at (50, 0), horizontal line at y=50
        dist = point_line_distance(50, 0, 0, 50, 100, 50)
        assert dist == pytest.approx(50.0)

    def test_on_line(self):
        dist = point_line_distance(50, 50, 0, 50, 100, 50)
        assert dist == pytest.approx(0.0)

    def test_zero_length_line(self):
        # Degenerate: line is a point at (10,10)
        dist = point_line_distance(13, 14, 10, 10, 10, 10)
        assert dist == pytest.approx(5.0)

    def test_diagonal_line(self):
        # Line from (0,0) to (10,10), point at (10,0)
        dist = point_line_distance(10, 0, 0, 0, 10, 10)
        expected = 10 / math.sqrt(2)
        assert dist == pytest.approx(expected)


# ── Zone masks ────────────────────────────────

class TestZoneMasks:
    """Tests para build_zone_masks y point_in_zone_mask."""

    def test_mask_inside(self):
        zones = {"A": np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.int32)}
        masks = build_zone_masks(zones, 100, 100)
        assert point_in_zone_mask(50, 50, masks) == "A"

    def test_mask_outside(self):
        zones = {"A": np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.int32)}
        masks = build_zone_masks(zones, 100, 100)
        assert point_in_zone_mask(5, 5, masks) is None

    def test_mask_multiple_zones(self):
        zones = {
            "A": np.array([[0, 0], [50, 0], [50, 50], [0, 50]], dtype=np.int32),
            "B": np.array([[60, 60], [100, 60], [100, 100], [60, 100]], dtype=np.int32),
        }
        masks = build_zone_masks(zones, 110, 110)
        assert point_in_zone_mask(25, 25, masks) == "A"
        assert point_in_zone_mask(80, 80, masks) == "B"
        assert point_in_zone_mask(55, 55, masks) is None

    def test_out_of_bounds(self):
        zones = {"A": np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.int32)}
        masks = build_zone_masks(zones, 100, 100)
        assert point_in_zone_mask(200, 200, masks) is None
        assert point_in_zone_mask(-5, -5, masks) is None


# ── bbox_intersects_zone ──────────────────────

class TestBboxIntersectsZone:
    """Tests para bbox_intersects_zone (4-corner test)."""

    def test_center_inside(self):
        zone = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)
        assert bbox_intersects_zone(25, 25, 75, 75, zone) is True

    def test_center_outside_corner_inside(self):
        zone = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)
        # Center at (120,50) is outside, but left corners at (90,10) and (90,90) are inside
        assert bbox_intersects_zone(90, 10, 150, 90, zone) is True

    def test_fully_outside(self):
        zone = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)
        assert bbox_intersects_zone(200, 200, 300, 300, zone) is False


# ── cosine_similarity_2d ──────────────────────

class TestCosineSimilarity:
    """Tests para cosine_similarity_2d."""

    def test_identical_vectors(self):
        assert cosine_similarity_2d((1, 0), (1, 0)) == pytest.approx(1.0)

    def test_opposite_vectors(self):
        assert cosine_similarity_2d((1, 0), (-1, 0)) == pytest.approx(-1.0)

    def test_perpendicular(self):
        assert cosine_similarity_2d((1, 0), (0, 1)) == pytest.approx(0.0)

    def test_diagonal(self):
        sim = cosine_similarity_2d((1, 1), (1, 0))
        assert sim == pytest.approx(1 / math.sqrt(2))

    def test_zero_vector(self):
        assert cosine_similarity_2d((0, 0), (1, 0)) == pytest.approx(0.0)
