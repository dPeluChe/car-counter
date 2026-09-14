"""Modos de conteo lines (cruce de linea) y directions (cosine similarity) para VehicleCounter."""

import math
from carcounter.logging_config import get_logger
from carcounter.geometry import point_to_line_side, cosine_similarity_2d

log = get_logger("counting")


class LinesDirectionsMixin:
    """Requiere el estado de VehicleCounter: tracks_info, counting_lines, _crossing_history, _dir_vectors."""

    # ── Lines mode (multi-anchor + crossing threshold) ──

    def _update_line_crossing(self, trk_id, cx, cy, cls_name, bbox=None):
        """Conteo por cruce de linea. Soporta multi-anchor y crossing threshold."""
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
            dx, dy = lx2 - lx1, ly2 - ly1
            if dx == 0 and dy == 0:
                continue

            history = self._crossing_history.setdefault(trk_id, {}).setdefault(
                line_name, {"side": 0, "position": None, "pending_frames": 0,
                            "center_side": 0, "intersects": False})

            center_value = point_to_line_side(cx, cy, lx1, ly1, lx2, ly2)
            center_side = 1 if center_value > 0 else (-1 if center_value < 0 else 0)
            if center_side and history["center_side"] * center_side < 0:
                px, py = history["position"]
                before = point_to_line_side(px, py, lx1, ly1, lx2, ly2)
                fraction = before / (before - center_value)
                ix, iy = px + fraction * (cx - px), py + fraction * (cy - py)
                projection = ((ix - lx1) * dx + (iy - ly1) * dy) / (dx * dx + dy * dy)
                history["intersects"] = 0 <= projection <= 1
            if center_side:
                history["center_side"] = center_side
            history["position"] = (cx, cy)

            # Multi-anchor: check all anchors are on the same side
            sides_now = [point_to_line_side(ax, ay, lx1, ly1, lx2, ly2) for ax, ay in anchors_now]
            has_positive = any(s > 0 for s in sides_now)
            has_negative = any(s < 0 for s in sides_now)
            if has_positive and has_negative:
                history["pending_frames"] = 0
                continue

            side_now = 1 if has_positive else (-1 if has_negative else 0)
            if side_now == 0:
                history["pending_frames"] = 0
                continue
            if history["side"] in (0, side_now):
                history.update(side=side_now, position=(cx, cy), pending_frames=0,
                               intersects=False)
                continue

            history["pending_frames"] += 1
            if history["pending_frames"] < self.min_crossing_frames:
                continue
            intersects = history["intersects"]
            history.update(side=side_now, position=(cx, cy), pending_frames=0,
                           intersects=False)
            if not intersects:
                continue
            if abs(dx) >= abs(dy):
                direction = "↓" if side_now * dx > 0 else "↑"
            else:
                direction = "→" if side_now * dy < 0 else "←"
            crossing_key = f"{line_name} {direction}"

            if crossing_key not in info["lines_crossed"]:
                info["lines_crossed"].add(crossing_key)
                info["state"] = "done"
                self._record_count(trk_id, "lines", crossing_key, cls_name, line=line_name, direction=direction)
                log.info("  ID=%4d  cruzo: %s  cls=%s  (total=%d)", trk_id, crossing_key, cls_name, self.routes_matrix[crossing_key])

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
            self._record_count(trk_id, "directions", best_dir, cls_name, direction=best_dir)
            log.info("  ID=%4d  direccion: %s  sim=%.2f  cls=%s  (total=%d)", trk_id, best_dir, best_score, cls_name, self.routes_matrix[best_dir])
