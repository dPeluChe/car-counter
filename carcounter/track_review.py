"""Revision de tracks que no completaron ruta y de posibles cambios de ID, a partir del CSV de tracks."""

from bisect import bisect_right
import csv
import math
import statistics

from carcounter.constants import class_group

INCOMPLETE_STATES = {"origin", "transit"}


def _number(value, cast=float):
    return None if value in ("", None) else cast(float(value))


def load_tracks(path):
    """Lee el CSV de export_tracks_csv con numeros tipados y grupo EPS."""
    with open(path, newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    tracks = []
    for row in rows:
        track = dict(row, group=class_group(row.get("class", "")))
        for key in ("first_x", "first_y", "last_x", "last_y", "avg_width", "avg_height"):
            track[key] = _number(row.get(key))
        for key in ("track_id", "first_seen_frame", "last_seen_frame", "observed_frames", "counted_frame"):
            track[key] = _number(row.get(key), int)
        tracks.append(track)
    return tracks


def find_incomplete(tracks, processed_frames, end_margin_frames=30):
    """Tracks con origen y sin destino; los que siguen visibles al final del tramo se marcan aparte."""
    incomplete = []
    for track in tracks:
        if track["state"] not in INCOMPLETE_STATES or not track.get("origin"):
            continue
        at_end = (track["last_seen_frame"] or 0) > processed_frames - end_margin_frames
        incomplete.append(dict(track, cause_hint="fin_del_tramo" if at_end else "perdido"))
    return incomplete


def find_id_switch_candidates(tracks, max_gap_frames=10, max_distance_factor=1.5):
    """Pares donde un track termina y otro del mismo grupo empieza cerca en pocos frames.

    La distancia se mide en tamaños del vehículo que termina (en tráfico denso los píxeles fijos
    emparejan autos vecinos) y cada track queda en un solo par: el de menor hueco y distancia.
    """
    started = sorted((t for t in tracks if t["first_seen_frame"] is not None and t["first_x"] is not None),
                     key=lambda t: t["first_seen_frame"])
    starts = [t["first_seen_frame"] for t in started]
    pairs = []
    for ended in tracks:
        if ended["last_seen_frame"] is None or ended["last_x"] is None:
            continue
        size = max(ended["avg_width"] or 0, ended["avg_height"] or 0, 10)
        lo = bisect_right(starts, ended["last_seen_frame"])
        hi = bisect_right(starts, ended["last_seen_frame"] + max_gap_frames)
        for new in started[lo:hi]:
            if new["track_id"] == ended["track_id"] or new["group"] != ended["group"]:
                continue
            distance = math.hypot(new["first_x"] - ended["last_x"], new["first_y"] - ended["last_y"])
            if distance <= max_distance_factor * size:
                pairs.append(dict(
                    ended_track=ended["track_id"], started_track=new["track_id"], group=ended["group"],
                    gap_frames=new["first_seen_frame"] - ended["last_seen_frame"],
                    distance_px=round(distance, 1), distance_sizes=round(distance / size, 2),
                    ended_state=ended["state"], started_state=new["state"]))
    pairs.sort(key=lambda pair: (pair["gap_frames"], pair["distance_sizes"]))
    used_ended, used_started, candidates = set(), set(), []
    for pair in pairs:
        if pair["ended_track"] in used_ended or pair["started_track"] in used_started:
            continue
        used_ended.add(pair["ended_track"])
        used_started.add(pair["started_track"])
        candidates.append(pair)
    return candidates


def fragmentation(tracks, short_observations=10):
    """Cuántos tracks son cortos: muchos indican IDs que se cortan y se vuelven a crear."""
    observed = [track["observed_frames"] or 0 for track in tracks]
    return dict(tracks=len(tracks), short_observations=short_observations,
                short_tracks=sum(count <= short_observations for count in observed),
                median_observations=statistics.median(observed) if observed else 0)


def summarize_by_origin(tracks, incomplete):
    """Por acceso de origen: rutas completas, tracks perdidos y visibles al final del tramo."""
    summary = {}

    def row(origin):
        return summary.setdefault(origin, dict(completos=0, perdidos=0, fin_del_tramo=0))

    for track in tracks:
        if track.get("origin") and track["state"] == "done":
            row(track["origin"])["completos"] += 1
    for track in incomplete:
        row(track["origin"])["perdidos" if track["cause_hint"] == "perdido" else "fin_del_tramo"] += 1
    return dict(sorted(summary.items()))
