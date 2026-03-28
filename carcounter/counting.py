"""Maquinas de estado para conteo de vehiculos.

Tres modos:
  - zones: rutas A->B por zonas poligonales (glorietas, intersecciones)
  - lines: cruce de linea con deteccion de direccion (aforo simple)
  - directions: asignacion de direccion por cosine similarity del track
"""

import math
from collections import deque
from carcounter.geometry import (
    point_in_zone, point_in_zone_mask, build_zone_masks,
    point_to_line_side, point_line_distance,
    cosine_similarity_2d,
)


class VehicleCounter:
    """Contador de vehiculos con soporte para modos zones, lines y directions."""

    def __init__(self, zones_np, counting_lines, min_origin_frames=3, min_dest_frames=3,
                 frame_size=None, directions=None, min_crossing_frames=2,
                 trail_length=64):
        self.zones_np = zones_np
        self.zone_names = list(zones_np.keys())
        self.counting_lines = counting_lines
        self.min_origin_frames = min_origin_frames
        self.min_dest_frames = min_dest_frames
        self.min_crossing_frames = min_crossing_frames

        # Pre-compute zone masks for O(1) lookup
        self._zone_masks = None
        if frame_size and zones_np:
            self._zone_masks = build_zone_masks(zones_np, frame_size[0], frame_size[1])

        # Pre-compute direction vectors (constant, not per-frame)
        self.directions = directions or {}
        self._dir_vectors = {
            name: (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
            for name, pts in self.directions.items()
        }

        self.trail_length = trail_length

        # State
        self.tracks_info = {}
        self.trails = {}
        self.routes_matrix = {}
        self.od_matrix = {}
        self.od_matrix_by_class = {}
        self.total_vehicles_ever = 0
        self._id_prev_pos = {}
        self._crossing_history = {}  # {trk_id: {line_name: deque}}
        self._shape_metrics = {}  # {trk_id: {avg_width, avg_height, ...}}
        self.frame_count = 0

    def set_frame(self, frame_count):
        """Actualiza el frame actual."""
        self.frame_count = frame_count

    def get_zone_for_point(self, x, y):
        """Retorna la zona donde cae (x,y). Usa masks si disponibles."""
        if self._zone_masks:
            return point_in_zone_mask(x, y, self._zone_masks)
        for name, pts in self.zones_np.items():
            if point_in_zone(x, y, pts):
                return name
        return None

    def update(self, trk_id, cx, cy, cls_name, mode, bbox=None):
        """Dispatch al modo correcto. bbox=(x1,y1,x2,y2) opcional para multi-anchor."""
        # Update trail
        if trk_id not in self.trails:
            self.trails[trk_id] = deque(maxlen=self.trail_length)
        self.trails[trk_id].append((cx, cy))

        # Update shape metrics (running average)
        if bbox:
            self._update_shape_metrics(trk_id, bbox)

        if mode == "lines":
            self._update_line_crossing(trk_id, cx, cy, cls_name, bbox)
        elif mode == "directions":
            self._update_direction(trk_id, cx, cy, cls_name)
        else:
            self._update_route(trk_id, cx, cy, cls_name)

    # ── Zones mode ────────────────────────────

    def _update_route(self, trk_id, cx, cy, cls_name):
        """Maquina de estados para tracking de rutas A->B."""
        current_zone = self.get_zone_for_point(cx, cy)

        if trk_id not in self.tracks_info:
            self.total_vehicles_ever += 1
            self.tracks_info[trk_id] = {
                "state": "origin" if current_zone else "new",
                "origin": current_zone,
                "class": cls_name,
                "zone_frames": 1 if current_zone else 0,
                "last_seen_frame": self.frame_count,
                "dest_zone": None,
                "dest_frames": 0,
            }
            if current_zone:
                print(f"  ID={trk_id:>4}  entro en [{current_zone:>10}]  cls={cls_name}")
            return

        info = self.tracks_info[trk_id]
        info["last_seen_frame"] = self.frame_count

        if info["state"] == "done":
            return

        if info["state"] == "new":
            if current_zone:
                info["state"] = "origin"
                info["origin"] = current_zone
                info["zone_frames"] = 1
                print(f"  ID={trk_id:>4}  entro en [{current_zone:>10}]  cls={info['class']}")
            return

        if info["state"] == "origin":
            origin = info["origin"]
            if current_zone == origin:
                info["zone_frames"] = info["zone_frames"] + 1
            elif current_zone is None:
                if info["zone_frames"] >= self.min_origin_frames:
                    info["state"] = "transit"
                    info["dest_zone"] = None
                    info["dest_frames"] = 0
                else:
                    info["state"] = "new"
                    info["origin"] = None
            else:
                if info["zone_frames"] >= self.min_origin_frames:
                    # Transition to transit, then apply dest logic
                    info["state"] = "transit"
                    info["dest_zone"] = current_zone
                    info["dest_frames"] = 1
            return

        if info["state"] == "transit":
            if current_zone and current_zone != info["origin"]:
                if info.get("dest_zone") == current_zone:
                    info["dest_frames"] = info["dest_frames"] + 1
                    if info["dest_frames"] >= self.min_dest_frames:
                        self._register_route(trk_id, info["origin"], current_zone, info["class"])
                else:
                    info["dest_zone"] = current_zone
                    info["dest_frames"] = 1
            else:
                info["dest_zone"] = None
                info["dest_frames"] = 0

    def _register_route(self, trk_id, origin, destination, cls_name):
        route_key = f"{origin} \u2192 {destination}"
        self.routes_matrix[route_key] = self.routes_matrix.get(route_key, 0) + 1
        self.tracks_info[trk_id]["state"] = "done"

        # OD matrix nested
        if origin not in self.od_matrix:
            self.od_matrix[origin] = {}
        self.od_matrix[origin][destination] = self.od_matrix[origin].get(destination, 0) + 1

        # OD matrix per-class
        if origin not in self.od_matrix_by_class:
            self.od_matrix_by_class[origin] = {}
        if destination not in self.od_matrix_by_class[origin]:
            self.od_matrix_by_class[origin][destination] = {}
        cls_counts = self.od_matrix_by_class[origin][destination]
        cls_counts[cls_name] = cls_counts.get(cls_name, 0) + 1

        print(f"  ID={trk_id:>4}  ruta: {route_key}  cls={cls_name}  (total={self.routes_matrix[route_key]})")

    # ── Lines mode (multi-anchor + crossing threshold) ──

    def _update_line_crossing(self, trk_id, cx, cy, cls_name, bbox=None):
        """Conteo por cruce de linea. Soporta multi-anchor y crossing threshold."""
        prev_pos = self._id_prev_pos.get(trk_id)
        self._id_prev_pos[trk_id] = (cx, cy)

        if trk_id not in self.tracks_info:
            self.total_vehicles_ever += 1
            self.tracks_info[trk_id] = {
                "state": "new",
                "class": cls_name,
                "lines_crossed": set(),
                "last_seen_frame": self.frame_count,
            }

        info = self.tracks_info[trk_id]
        info["last_seen_frame"] = self.frame_count

        if prev_pos is None:
            return

        # Compute anchor points (4 corners if bbox available, else just center)
        if bbox:
            x1, y1, x2, y2 = bbox
            anchors_now = [(cx, cy), (x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        else:
            anchors_now = [(cx, cy)]

        for line in self.counting_lines:
            line_name = line["name"]
            lx1, ly1 = line["pt1"]
            lx2, ly2 = line["pt2"]
            tol = line["tolerance"]

            dist = point_line_distance(cx, cy, lx1, ly1, lx2, ly2)
            if dist > tol:
                continue

            # Multi-anchor: check all anchors are on the same side
            sides_now = [point_to_line_side(ax, ay, lx1, ly1, lx2, ly2) for ax, ay in anchors_now]
            has_positive = any(s > 0 for s in sides_now)
            has_negative = any(s < 0 for s in sides_now)
            if has_positive and has_negative:
                # Anchors straddle the line — skip (vehicle is ON the line)
                continue

            side_now = 1 if has_positive else (-1 if has_negative else 0)
            side_prev = 1 if point_to_line_side(prev_pos[0], prev_pos[1], lx1, ly1, lx2, ly2) > 0 else -1

            if side_now == 0:
                continue

            # Crossing threshold: track consecutive frames on same side
            if trk_id not in self._crossing_history:
                self._crossing_history[trk_id] = {}
            trk_hist = self._crossing_history[trk_id]
            if line_name not in trk_hist:
                trk_hist[line_name] = deque(maxlen=self.min_crossing_frames + 1)
            history = trk_hist[line_name]
            history.append(side_now)

            if len(history) < self.min_crossing_frames:
                continue
            if not all(s == side_now for s in history):
                continue

            # Check if actually crossed (previous side was different)
            if side_prev * side_now >= 0:
                continue

            # Determine direction using cross product (works for any line angle)
            direction = "\u2193" if cy > prev_pos[1] else "\u2191"
            crossing_key = f"{line_name} {direction}"

            if crossing_key not in info["lines_crossed"]:
                info["lines_crossed"].add(crossing_key)
                info["state"] = "done"
                self.routes_matrix[crossing_key] = self.routes_matrix.get(crossing_key, 0) + 1
                self._crossing_history.pop(trk_id, None)
                print(f"  ID={trk_id:>4}  cruzo: {crossing_key}  cls={cls_name}  (total={self.routes_matrix[crossing_key]})")

    # ── Directions mode (cosine similarity) ───

    def _update_direction(self, trk_id, cx, cy, cls_name):
        """Asigna track a la direccion mas cercana por cosine similarity."""
        if not self.directions:
            return
        if trk_id not in self.tracks_info:
            self.total_vehicles_ever += 1
            self.tracks_info[trk_id] = {
                "state": "tracking",
                "class": cls_name,
                "first_pos": (cx, cy),
                "last_pos": (cx, cy),
                "frame_count": 1,
                "last_seen_frame": self.frame_count,
                "assigned_direction": None,
            }
            return

        info = self.tracks_info[trk_id]
        info["last_seen_frame"] = self.frame_count
        info["last_pos"] = (cx, cy)
        info["frame_count"] += 1

        if info["state"] == "done":
            return

        min_frames = max(self.min_origin_frames, 5)
        if info["frame_count"] < min_frames:
            return

        first = info["first_pos"]
        track_vec = (cx - first[0], cy - first[1])
        if math.hypot(track_vec[0], track_vec[1]) < 10:
            return

        best_score = -2.0
        best_dir = None
        for dir_name, dir_vec in self._dir_vectors.items():
            score = cosine_similarity_2d(track_vec, dir_vec)
            if score > best_score:
                best_score = score
                best_dir = dir_name

        if best_dir and best_score > 0.5:
            info["state"] = "done"
            info["assigned_direction"] = best_dir
            self.routes_matrix[best_dir] = self.routes_matrix.get(best_dir, 0) + 1
            print(f"  ID={trk_id:>4}  direccion: {best_dir}  sim={best_score:.2f}  cls={cls_name}  (total={self.routes_matrix[best_dir]})")

    # ── Shape metrics ─────────────────────────

    def _update_shape_metrics(self, trk_id, bbox):
        """Actualiza metricas de forma del bbox (running average)."""
        x1, y1, x2, y2 = bbox
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        area = w * h
        aspect = w / h
        elongation = max(w, h) / min(w, h)

        if trk_id not in self._shape_metrics:
            self._shape_metrics[trk_id] = {
                "avg_width": float(w), "avg_height": float(h),
                "avg_area": float(area), "avg_aspect": aspect,
                "avg_elongation": elongation, "samples": 1,
            }
        else:
            m = self._shape_metrics[trk_id]
            n = m["samples"]
            # Exponential moving average (alpha = 0.3)
            a = 0.3
            m["avg_width"] = m["avg_width"] * (1 - a) + w * a
            m["avg_height"] = m["avg_height"] * (1 - a) + h * a
            m["avg_area"] = m["avg_area"] * (1 - a) + area * a
            m["avg_aspect"] = m["avg_aspect"] * (1 - a) + aspect * a
            m["avg_elongation"] = m["avg_elongation"] * (1 - a) + elongation * a
            m["samples"] = n + 1

    def get_shape_metrics(self, trk_id):
        """Retorna metricas de forma promediadas para un track."""
        return self._shape_metrics.get(trk_id)

    # ── Purge stale ───────────────────────────

    def purge_stale(self, max_missing_frames=200):
        """Purga tracks que no se han visto en max_missing_frames."""
        stale_ids = [
            tid for tid, tinfo in self.tracks_info.items()
            if self.frame_count - tinfo.get("last_seen_frame", 0) > max_missing_frames
        ]
        for tid in stale_ids:
            del self.tracks_info[tid]
            self._id_prev_pos.pop(tid, None)
            self.trails.pop(tid, None)
            self._crossing_history.pop(tid, None)
            self._shape_metrics.pop(tid, None)
        if stale_ids:
            print(f"  Purgados {len(stale_ids)} tracks viejos — activos: {len(self.tracks_info)}")
        return len(stale_ids)

    # ── Per-track data export ─────────────────

    def get_track_data(self):
        """Retorna datos per-track para CSV export."""
        rows = []
        for tid, info in self.tracks_info.items():
            trail = list(self.trails.get(tid, []))
            first_pos = trail[0] if trail else None
            last_pos = trail[-1] if trail else None
            shape = self._shape_metrics.get(tid, {})
            rows.append({
                "track_id": tid,
                "class": info.get("class", ""),
                "state": info.get("state", ""),
                "origin": info.get("origin", ""),
                "direction": info.get("assigned_direction", ""),
                "first_x": first_pos[0] if first_pos else "",
                "first_y": first_pos[1] if first_pos else "",
                "last_x": last_pos[0] if last_pos else "",
                "last_y": last_pos[1] if last_pos else "",
                "trail_length": len(trail),
                "last_seen_frame": info.get("last_seen_frame", ""),
                "avg_width": round(shape.get("avg_width", 0), 1),
                "avg_height": round(shape.get("avg_height", 0), 1),
                "avg_area": round(shape.get("avg_area", 0), 1),
                "avg_aspect": round(shape.get("avg_aspect", 0), 2),
                "avg_elongation": round(shape.get("avg_elongation", 0), 2),
            })
        return rows
