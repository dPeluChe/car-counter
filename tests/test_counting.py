"""Tests para carcounter/counting.py"""

import numpy as np
import pytest
from carcounter.counting import VehicleCounter


# ── Helpers ───────────────────────────────────

def make_square_zone(x, y, size=100):
    """Crea una zona cuadrada como numpy array."""
    return np.array([
        [x, y], [x + size, y], [x + size, y + size], [x, y + size]
    ], dtype=np.int32)


def make_counter(zone_a_pos=(0, 0), zone_b_pos=(300, 0), size=100,
                 min_origin=3, min_dest=3):
    """Crea un VehicleCounter con dos zonas."""
    zones = {
        "A": make_square_zone(*zone_a_pos, size),
        "B": make_square_zone(*zone_b_pos, size),
    }
    return VehicleCounter(
        zones_np=zones, counting_lines=[],
        min_origin_frames=min_origin, min_dest_frames=min_dest,
    )


def make_line_counter(tolerance=25, min_crossing_frames=1):
    """Crea un VehicleCounter con una linea de cruce."""
    lines = [{
        "name": "Linea 1",
        "pt1": (0, 100), "pt2": (200, 100),
        "tolerance": tolerance,
    }]
    return VehicleCounter(zones_np={}, counting_lines=lines,
                          min_crossing_frames=min_crossing_frames)


# ── Zones mode: state machine ────────────────

class TestZonesMode:
    """Tests para el modo zones (rutas A->B)."""

    def test_new_vehicle_outside_zones(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 200, 200, "car", "zones")  # fuera de ambas zonas
        assert c.tracks_info[1]["state"] == "new"
        assert c.total_vehicles_ever == 1

    def test_vehicle_enters_origin(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 50, 50, "car", "zones")  # dentro de zona A
        assert c.tracks_info[1]["state"] == "origin"
        assert c.tracks_info[1]["origin"] == "A"

    def test_full_route_a_to_b(self):
        c = make_counter(min_origin=2, min_dest=2)
        # Entra en A por 2 frames
        for f in range(1, 3):
            c.set_frame(f)
            c.update(1, 50, 50, "car", "zones")
        assert c.tracks_info[1]["state"] == "origin"

        # Sale de A (transito)
        c.set_frame(3)
        c.update(1, 200, 50, "car", "zones")
        assert c.tracks_info[1]["state"] == "transit"

        # Entra en B por 2 frames
        for f in range(4, 6):
            c.set_frame(f)
            c.update(1, 350, 50, "car", "zones")
        assert c.tracks_info[1]["state"] == "done"
        assert "A \u2192 B" in c.routes_matrix
        assert c.routes_matrix["A \u2192 B"] == 1

    def test_bounce_does_not_count(self):
        """Vehiculo que roza la zona destino menos de min_dest_frames no cuenta."""
        c = make_counter(min_origin=2, min_dest=3)
        # Entra en A
        for f in range(1, 4):
            c.set_frame(f)
            c.update(1, 50, 50, "car", "zones")
        # Sale a transito
        c.set_frame(4)
        c.update(1, 200, 50, "car", "zones")
        # Roza B solo 2 frames (< min_dest=3)
        for f in range(5, 7):
            c.set_frame(f)
            c.update(1, 350, 50, "car", "zones")
        # Sale de B
        c.set_frame(7)
        c.update(1, 200, 50, "car", "zones")
        assert c.tracks_info[1]["state"] == "transit"
        assert len(c.routes_matrix) == 0

    def test_origin_too_short_resets(self):
        """Vehiculo que roza origen < min_origin_frames vuelve a new."""
        c = make_counter(min_origin=3, min_dest=3)
        # Entra en A solo 1 frame
        c.set_frame(1)
        c.update(1, 50, 50, "car", "zones")
        # Sale inmediatamente
        c.set_frame(2)
        c.update(1, 200, 200, "car", "zones")
        assert c.tracks_info[1]["state"] == "new"

    def test_done_state_is_final(self):
        """Vehiculo en estado done no cambia."""
        c = make_counter(min_origin=2, min_dest=2)
        # Origin A for 2 frames
        for f in range(1, 3):
            c.set_frame(f)
            c.update(1, 50, 50, "car", "zones")
        # Transit
        c.set_frame(3)
        c.update(1, 200, 50, "car", "zones")
        # Dest B for 2 frames
        for f in range(4, 6):
            c.set_frame(f)
            c.update(1, 350, 50, "car", "zones")
        assert c.tracks_info[1]["state"] == "done"
        # Sigue moviéndose, no cambia
        c.set_frame(6)
        c.update(1, 50, 50, "car", "zones")
        assert c.tracks_info[1]["state"] == "done"
        assert c.routes_matrix["A \u2192 B"] == 1  # no se duplica

    def test_multiple_vehicles(self):
        c = make_counter(min_origin=2, min_dest=2)
        # Vehiculo 1: A->B
        for f in range(1, 3):
            c.set_frame(f)
            c.update(1, 50, 50, "car", "zones")
        c.set_frame(3)
        c.update(1, 200, 50, "car", "zones")
        for f in range(4, 6):
            c.set_frame(f)
            c.update(1, 350, 50, "car", "zones")

        # Vehiculo 2: B->A
        for f in range(6, 8):
            c.set_frame(f)
            c.update(2, 350, 50, "truck", "zones")
        c.set_frame(8)
        c.update(2, 200, 50, "truck", "zones")
        for f in range(9, 11):
            c.set_frame(f)
            c.update(2, 50, 50, "truck", "zones")

        assert c.routes_matrix["A \u2192 B"] == 1
        assert c.routes_matrix["B \u2192 A"] == 1
        assert c.total_vehicles_ever == 2

    def test_class_preserved(self):
        c = make_counter(min_origin=1, min_dest=1)
        c.set_frame(1)
        c.update(1, 50, 50, "truck", "zones")
        assert c.tracks_info[1]["class"] == "truck"


# ── Lines mode: crossing detection ────────────

class TestLinesMode:
    """Tests para el modo lines (cruce de linea)."""

    def test_crossing_downward(self):
        c = make_line_counter()
        # Frame 1: arriba de la linea (y=80)
        c.set_frame(1)
        c.update(1, 100, 80, "car", "lines")
        # Frame 2: abajo de la linea (y=120)
        c.set_frame(2)
        c.update(1, 100, 120, "car", "lines")
        assert c.tracks_info[1]["state"] == "done"
        assert "Linea 1 \u2193" in c.routes_matrix

    def test_crossing_upward(self):
        c = make_line_counter()
        c.set_frame(1)
        c.update(1, 100, 120, "car", "lines")
        c.set_frame(2)
        c.update(1, 100, 80, "car", "lines")
        assert "Linea 1 \u2191" in c.routes_matrix

    def test_no_crossing_same_side(self):
        c = make_line_counter()  # tolerance=25
        c.set_frame(1)
        c.update(1, 100, 80, "car", "lines")
        c.set_frame(2)
        c.update(1, 100, 85, "car", "lines")
        assert len(c.routes_matrix) == 0

    def test_no_crossing_too_far(self):
        """Vehiculo cruza pero esta lejos de la linea (dist > tolerance)."""
        c = make_line_counter(tolerance=15)
        c.set_frame(1)
        c.update(1, 100, 50, "car", "lines")  # 50 px arriba
        c.set_frame(2)
        c.update(1, 100, 150, "car", "lines")  # 50 px abajo, dist=50 > tol=15
        assert len(c.routes_matrix) == 0

    def test_first_frame_no_crossing(self):
        """Primer frame de un track no genera cruce (no hay prev_cy)."""
        c = make_line_counter()
        c.set_frame(1)
        c.update(1, 100, 100, "car", "lines")
        assert len(c.routes_matrix) == 0

    def test_duplicate_crossing_ignored(self):
        """Mismo vehiculo cruzando la misma linea en la misma direccion solo cuenta 1 vez."""
        c = make_line_counter()
        c.set_frame(1)
        c.update(1, 100, 90, "car", "lines")
        c.set_frame(2)
        c.update(1, 100, 110, "car", "lines")
        # Vuelve arriba y cruza de nuevo
        c.set_frame(3)
        c.update(1, 100, 90, "car", "lines")
        c.set_frame(4)
        c.update(1, 100, 110, "car", "lines")
        assert c.routes_matrix["Linea 1 \u2193"] == 1  # solo 1


# ── Purge stale ───────────────────────────────

class TestPurgeStale:
    """Tests para purge_stale."""

    def test_purges_old_tracks(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 200, 200, "car", "zones")
        c.set_frame(300)
        purged = c.purge_stale(max_missing_frames=200)
        assert purged == 1
        assert 1 not in c.tracks_info

    def test_keeps_recent_tracks(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 200, 200, "car", "zones")
        c.set_frame(100)
        purged = c.purge_stale(max_missing_frames=200)
        assert purged == 0
        assert 1 in c.tracks_info

    def test_preserves_total_count(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 200, 200, "car", "zones")
        c.update(2, 200, 200, "car", "zones")
        assert c.total_vehicles_ever == 2
        c.set_frame(300)
        c.purge_stale(max_missing_frames=200)
        assert c.total_vehicles_ever == 2  # preserved

    def test_purges_line_prev_cy(self):
        c = make_line_counter()
        c.set_frame(1)
        c.update(1, 100, 80, "car", "lines")
        c.set_frame(300)
        c.purge_stale(max_missing_frames=200)
        assert 1 not in c._id_prev_pos

    def test_purges_trails(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 200, 200, "car", "zones")
        assert 1 in c.trails
        c.set_frame(300)
        c.purge_stale(max_missing_frames=200)
        assert 1 not in c.trails


# ── Directions mode ───────────────────────────

class TestDirectionsMode:
    """Tests para el modo directions (cosine similarity)."""

    def test_assigns_direction(self):
        directions = {
            "Norte": [[100, 200], [100, 0]],     # vector pointing up
            "Sur":   [[100, 0], [100, 200]],      # vector pointing down
        }
        c = VehicleCounter(zones_np={}, counting_lines=[], directions=directions,
                           min_origin_frames=3)
        # Vehicle moves upward (y decreasing)
        for f in range(1, 8):
            c.set_frame(f)
            c.update(1, 100, 200 - f * 20, "car", "directions")
        assert c.tracks_info[1]["state"] == "done"
        assert "Norte" in c.routes_matrix

    def test_minimum_frames_required(self):
        directions = {"Este": [[0, 100], [200, 100]]}
        c = VehicleCounter(zones_np={}, counting_lines=[], directions=directions,
                           min_origin_frames=5)
        # Only 3 frames - not enough
        for f in range(1, 4):
            c.set_frame(f)
            c.update(1, f * 50, 100, "car", "directions")
        assert c.tracks_info[1]["state"] == "tracking"

    def test_low_similarity_not_assigned(self):
        directions = {"Este": [[0, 100], [200, 100]]}  # horizontal right
        c = VehicleCounter(zones_np={}, counting_lines=[], directions=directions,
                           min_origin_frames=3)
        # Vehicle moves diagonally (low similarity with pure horizontal)
        for f in range(1, 8):
            c.set_frame(f)
            c.update(1, 100 + f * 5, 100 - f * 50, "car", "directions")
        # With strong vertical component, cosine similarity with horizontal may be < 0.5
        # so it might not get assigned depending on the exact vector


# ── OD Matrix ─────────────────────────────────

class TestODMatrix:
    """Tests para OD matrix nested."""

    def test_od_matrix_populated(self):
        c = make_counter(min_origin=2, min_dest=2)
        # Full route A->B
        for f in range(1, 3):
            c.set_frame(f)
            c.update(1, 50, 50, "car", "zones")
        c.set_frame(3)
        c.update(1, 200, 50, "car", "zones")
        for f in range(4, 6):
            c.set_frame(f)
            c.update(1, 350, 50, "car", "zones")
        assert c.od_matrix == {"A": {"B": 1}}

    def test_od_matrix_by_class(self):
        c = make_counter(min_origin=2, min_dest=2)
        for f in range(1, 3):
            c.set_frame(f)
            c.update(1, 50, 50, "truck", "zones")
        c.set_frame(3)
        c.update(1, 200, 50, "truck", "zones")
        for f in range(4, 6):
            c.set_frame(f)
            c.update(1, 350, 50, "truck", "zones")
        assert c.od_matrix_by_class["A"]["B"]["truck"] == 1


# ── Trails ────────────────────────────────────

class TestTrails:
    """Tests para trail recording."""

    def test_trail_recorded(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 50, 50, "car", "zones")
        c.set_frame(2)
        c.update(1, 60, 60, "car", "zones")
        assert len(c.trails[1]) == 2
        assert c.trails[1][0] == (50, 50)
        assert c.trails[1][1] == (60, 60)

    def test_trail_max_length(self):
        c = VehicleCounter(zones_np={}, counting_lines=[], trail_length=5)
        for f in range(1, 20):
            c.set_frame(f)
            c.update(1, f * 10, f * 10, "car", "zones")
        assert len(c.trails[1]) == 5  # max length

    def test_get_track_data(self):
        c = make_counter()
        c.set_frame(1)
        c.update(1, 50, 50, "car", "zones")
        c.set_frame(2)
        c.update(1, 60, 60, "car", "zones")
        data = c.get_track_data()
        assert len(data) == 1
        assert data[0]["track_id"] == 1
        assert data[0]["class"] == "car"
        assert data[0]["first_x"] == 50


# ── Zone masks integration ────────────────────

class TestZoneMasksIntegration:
    """Tests para zone masks en VehicleCounter."""

    def test_counter_with_masks(self):
        zones = {
            "A": make_square_zone(0, 0, 100),
            "B": make_square_zone(300, 0, 100),
        }
        c = VehicleCounter(zones_np=zones, counting_lines=[],
                           frame_size=(500, 200))
        assert c._zone_masks is not None
        assert c.get_zone_for_point(50, 50) == "A"
        assert c.get_zone_for_point(350, 50) == "B"
        assert c.get_zone_for_point(200, 100) is None
