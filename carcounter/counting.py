"""Maquinas de estado para conteo de vehiculos.

Dos modos:
  - zones: rutas A->B por zonas poligonales (glorietas, intersecciones)
  - lines: cruce de linea con deteccion de direccion (aforo simple)
"""

from carcounter.geometry import point_in_zone, point_to_line_side, point_line_distance


class VehicleCounter:
    """Contador de vehiculos con soporte para modos zones y lines."""

    def __init__(self, zones_np, counting_lines, min_origin_frames=3, min_dest_frames=3):
        self.zones_np = zones_np
        self.zone_names = list(zones_np.keys())
        self.counting_lines = counting_lines
        self.min_origin_frames = min_origin_frames
        self.min_dest_frames = min_dest_frames

        self.tracks_info = {}
        self.routes_matrix = {}
        self.total_vehicles_ever = 0
        self._id_prev_cy = {}
        self.frame_count = 0

    def set_frame(self, frame_count):
        """Actualiza el frame actual (llamar antes de procesar detecciones)."""
        self.frame_count = frame_count

    def get_zone_for_point(self, x, y):
        for name, pts in self.zones_np.items():
            if point_in_zone(x, y, pts):
                return name
        return None

    def update(self, trk_id, cx, cy, cls_name, mode):
        """Dispatch al modo correcto."""
        if mode == "lines":
            self._update_line_crossing(trk_id, cx, cy, cls_name)
        else:
            self._update_route(trk_id, cx, cy, cls_name)

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
                info["zone_frames"] = info.get("zone_frames", 0) + 1
            elif current_zone is None:
                if info.get("zone_frames", 0) >= self.min_origin_frames:
                    info["state"] = "transit"
                    info["dest_zone"] = None
                    info["dest_frames"] = 0
                else:
                    info["state"] = "new"
                    info["origin"] = None
            else:
                if info.get("zone_frames", 0) >= self.min_origin_frames:
                    self._register_route(trk_id, origin, current_zone)
            return

        if info["state"] == "transit":
            if current_zone and current_zone != info["origin"]:
                if info.get("dest_zone") == current_zone:
                    info["dest_frames"] = info.get("dest_frames", 0) + 1
                    if info["dest_frames"] >= self.min_dest_frames:
                        self._register_route(trk_id, info["origin"], current_zone)
                else:
                    info["dest_zone"] = current_zone
                    info["dest_frames"] = 1
            else:
                info["dest_zone"] = None
                info["dest_frames"] = 0

    def _register_route(self, trk_id, origin, destination):
        route_key = f"{origin} \u2192 {destination}"
        self.routes_matrix[route_key] = self.routes_matrix.get(route_key, 0) + 1
        self.tracks_info[trk_id]["state"] = "done"
        print(f"  ID={trk_id:>4}  ruta: {route_key}  (total={self.routes_matrix[route_key]})")

    def _update_line_crossing(self, trk_id, cx, cy, cls_name):
        """Conteo por cruce de linea con deteccion de direccion."""
        prev_cy = self._id_prev_cy.get(trk_id)
        self._id_prev_cy[trk_id] = cy

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

        if prev_cy is None:
            return

        for line in self.counting_lines:
            line_name = line["name"]
            x1, y1 = line["pt1"]
            x2, y2 = line["pt2"]
            tol = line["tolerance"]

            dist = point_line_distance(cx, cy, x1, y1, x2, y2)
            if dist > tol:
                continue

            side_prev = point_to_line_side(cx, prev_cy, x1, y1, x2, y2)
            side_now = point_to_line_side(cx, cy, x1, y1, x2, y2)

            if side_prev * side_now < 0:
                direction = "\u2193" if cy > prev_cy else "\u2191"
                crossing_key = f"{line_name} {direction}"

                if crossing_key not in info["lines_crossed"]:
                    info["lines_crossed"].add(crossing_key)
                    info["state"] = "done"
                    self.routes_matrix[crossing_key] = self.routes_matrix.get(crossing_key, 0) + 1
                    print(f"  ID={trk_id:>4}  cruzo: {crossing_key}  cls={cls_name}  (total={self.routes_matrix[crossing_key]})")

    def purge_stale(self, max_missing_frames=200):
        """Purga tracks que no se han visto en max_missing_frames."""
        stale_ids = [
            tid for tid, tinfo in self.tracks_info.items()
            if self.frame_count - tinfo.get("last_seen_frame", 0) > max_missing_frames
        ]
        for tid in stale_ids:
            del self.tracks_info[tid]
            self._id_prev_cy.pop(tid, None)
        if stale_ids:
            print(f"  Purgados {len(stale_ids)} tracks viejos — activos: {len(self.tracks_info)}")
        return len(stale_ids)
