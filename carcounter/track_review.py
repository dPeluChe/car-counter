"""Tracks con origen confirmado y sin destino, y posibles cambios de ID, a partir del CSV de tracks."""

from bisect import bisect_right
from collections import defaultdict
import csv
import math
import statistics

from carcounter.constants import class_group

END_MARGIN_FRAMES = 30
_FLOATS = ("first_x", "first_y", "last_x", "last_y", "avg_width", "avg_height")
_INTS = ("track_id", "first_seen_frame", "last_seen_frame", "observed_frames", "counted_frame")


def _number(value, cast=float):
    return None if value in ("", None) else cast(float(value))


def load_tracks(path):
    """Lee el CSV de export_tracks_csv con números, cajas y grupo EPS tipados."""
    tracks = []
    with open(path, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        missing = {"origin_confirmed", "first_bbox", "last_bbox"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} no tiene {sorted(missing)}: vuelve a correr main.py con --output-tracks-csv")
        for row in reader:
            track = dict(row, group=class_group(row["class"]), origin_confirmed=row["origin_confirmed"] == "True")
            track.update({key: _number(row[key]) for key in _FLOATS})
            track.update({key: _number(row[key], int) for key in _INTS})
            for key in ("first_bbox", "last_bbox"):
                track[key] = tuple(map(float, row[key].split())) if row[key] else None
            tracks.append(track)
    return tracks


def find_incomplete(tracks, processed_frames, end_margin_frames=END_MARGIN_FRAMES):
    """Tracks con origen confirmado y sin destino; separa los que siguen visibles al final del tramo."""
    incomplete = []
    for track in tracks:
        if not track["origin_confirmed"] or track["state"] == "done":
            continue
        at_end = (track["last_seen_frame"] or 0) > processed_frames - end_margin_frames
        incomplete.append(dict(track, cause_hint="fin_del_tramo" if at_end else "perdidos"))
    return incomplete


def find_id_switch_candidates(tracks, max_gap_frames=10, max_distance_factor=1.5):
    """Pares donde un track termina y otro del mismo grupo empieza cerca en pocos frames.

    Distancia en tamaños del vehículo: en tráfico denso los píxeles fijos emparejan autos vecinos.
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
                    ended_class=ended["class"], started_class=new["class"],
                    gap_frames=new["first_seen_frame"] - ended["last_seen_frame"],
                    distance_sizes=round(distance / size, 2)))
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
    """Cuántos tracks son cortos; sirve para comparar variantes de tracker antes y después."""
    observed = [track["observed_frames"] or 0 for track in tracks]
    return dict(tracks=len(tracks), short_observations=short_observations,
                short_tracks=sum(count <= short_observations for count in observed),
                median_observations=statistics.median(observed) if observed else 0)


def summarize_by_origin(tracks, incomplete):
    """Por acceso de origen: rutas completas, perdidos y visibles al final del tramo."""
    summary = defaultdict(lambda: dict(completos=0, perdidos=0, fin_del_tramo=0))
    for track in tracks:
        if track.get("origin") and track["state"] == "done":
            summary[track["origin"]]["completos"] += 1
    for track in incomplete:
        summary[track["origin"]][track["cause_hint"]] += 1
    return dict(sorted(summary.items()))
