"""Maquinas de estado para conteo de vehiculos.

Tres modos:
  - zones: rutas A->B por zonas poligonales (glorietas, intersecciones)
  - lines: cruce de linea con deteccion de direccion (aforo simple)
  - directions: asignacion de direccion por cosine similarity del track

lines y directions viven en carcounter/counting_modes.py.
"""

from collections import deque
from carcounter.constants import class_group
from carcounter.logging_config import get_logger
from carcounter.geometry import point_in_zone, point_in_zone_mask, build_zone_masks
from carcounter.counting_modes import LinesDirectionsMixin

log = get_logger("counting")


def _bbox_text(bbox):
    return " ".join(str(int(value)) for value in bbox) if bbox else ""


class VehicleCounter(LinesDirectionsMixin):
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
        self._archived_tracks = []
        self._track_observations = {}
        self.trails = {}
        self.routes_matrix = {}
        self.counting_events = []
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
        info = self.tracks_info.get(trk_id)
        if info and self.frame_count - info["last_seen_frame"] > 1:
            self._crossing_history.pop(trk_id, None)
            info["dest_frames"] = 0
            if info["state"] == "origin" and info["zone_frames"] < self.min_origin_frames:
                info.update(state="new", origin=None, zone_frames=0)
        observation = self._track_observations.setdefault(trk_id, {
            "first_pos": (cx, cy), "first_seen_frame": self.frame_count,
            "observed_frames": 0, "first_bbox": bbox,
        })
        observation["observed_frames"] += 1
        if bbox:
            observation["last_bbox"] = bbox
        if info and info["state"] == "done":
            cls_name = info["class"]
        else:
            votes = observation.setdefault("class_votes", {})
            votes[cls_name] = votes.get(cls_name, 0) + 1
            previous_class = info["class"] if info else cls_name
            best_class = max(votes, key=votes.get)
            cls_name = best_class if votes[best_class] > votes.get(previous_class, 0) else previous_class
            if info:
                info["class"] = cls_name
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
                log.debug("  ID=%4d  entro en [%10s]  cls=%s", trk_id, current_zone, cls_name)
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
                log.debug("  ID=%4d  entro en [%10s]  cls=%s", trk_id, current_zone, info["class"])
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
                    info["state"] = "transit"
                    info["dest_zone"] = current_zone
                    info["dest_frames"] = 1
                    if self.min_dest_frames <= 1:
                        self._register_route(trk_id, origin, current_zone, info["class"])
                else:
                    info["origin"] = current_zone
                    info["zone_frames"] = 1
            return

        if info["state"] == "transit":
            if current_zone and current_zone != info["origin"]:
                if info.get("dest_zone") == current_zone:
                    info["dest_frames"] = info["dest_frames"] + 1
                else:
                    info["dest_zone"] = current_zone
                    info["dest_frames"] = 1
                if info["dest_frames"] >= self.min_dest_frames:
                    self._register_route(trk_id, info["origin"], current_zone, info["class"])
            else:
                info["dest_zone"] = None
                info["dest_frames"] = 0

    def _record_count(self, trk_id, mode, route, cls_name, *, origin=None,
                      destination=None, line=None, direction=None):
        self.routes_matrix[route] = self.routes_matrix.get(route, 0) + 1
        self.tracks_info[trk_id]["counted_frame"] = self.frame_count
        position = self.trails.get(trk_id)
        self.counting_events.append({
            "event_id": len(self.counting_events) + 1, "track_id": int(trk_id),
            "frame": int(self.frame_count), "mode": mode, "route": route,
            "class": cls_name, "group": class_group(cls_name),
            "origin": origin, "destination": destination,
            "line": line, "direction": direction,
            "position": list(map(float, position[-1])) if position else None,
        })

    def _register_route(self, trk_id, origin, destination, cls_name):
        route_key = f"{origin} → {destination}"
        self._record_count(trk_id, "zones", route_key, cls_name, origin=origin, destination=destination)
        self.tracks_info[trk_id]["state"] = "done"
        self.tracks_info[trk_id]["destination"] = destination

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

        log.info("  ID=%4d  ruta: %s  cls=%s  (total=%d)", trk_id, route_key, cls_name, self.routes_matrix[route_key])

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
            self._archived_tracks.append(self._track_data_row(tid, self.tracks_info[tid]))
            del self.tracks_info[tid]
            self._track_observations.pop(tid, None)
            self._id_prev_pos.pop(tid, None)
            self.trails.pop(tid, None)
            self._crossing_history.pop(tid, None)
            self._shape_metrics.pop(tid, None)
        if stale_ids:
            log.debug("  Purgados %d tracks viejos — activos: %d", len(stale_ids), len(self.tracks_info))
        return len(stale_ids)

    # ── Per-track data export ─────────────────

    def get_track_data(self):
        """Retorna datos per-track para CSV export."""
        return self._archived_tracks + [
            self._track_data_row(tid, info) for tid, info in self.tracks_info.items()
        ]

    def _track_data_row(self, tid, info):
        trail = self.trails.get(tid, [])
        observation = self._track_observations.get(tid, {})
        first_pos = observation.get("first_pos")
        last_pos = trail[-1] if trail else None
        shape = self._shape_metrics.get(tid, {})
        return {
            "track_id": tid,
            "class": info.get("class", ""),
            "state": info.get("state", ""),
            "origin": info.get("origin", ""),
            "destination": info.get("destination", ""),
            "counted_frame": info.get("counted_frame", ""),
            "first_seen_frame": observation.get("first_seen_frame", ""),
            "observed_frames": observation.get("observed_frames", 0),
            "origin_confirmed": bool(info.get("origin")) and (
                info.get("state") in ("transit", "done")
                or info.get("zone_frames", 0) >= self.min_origin_frames),
            "class_votes": " ".join(f"{name}:{count}"
                                    for name, count in sorted(observation.get("class_votes", {}).items())),
            "first_bbox": _bbox_text(observation.get("first_bbox")),
            "last_bbox": _bbox_text(observation.get("last_bbox")),
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
        }
