"""Reporte visual de tracks sin destino y posibles cambios de ID de una corrida de main.py."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from carcounter.track_review import (
    find_id_switch_candidates, find_incomplete, fragmentation, load_tracks, summarize_by_origin,
)

CROP_PX = 120
MAX_CANDIDATES = 50
# Un seek en H.264 decodifica desde el keyframe previo (~180 ms); avanzar con grab() cuesta ~1 ms por frame
SEEK_GAP_FRAMES = 250


def _box(track, moment):
    if track[f"{moment}_bbox"]:
        return track[f"{moment}_bbox"]
    x, y = track[f"{moment}_x"], track[f"{moment}_y"]
    if x is None:
        return None
    half_w, half_h = max(track["avg_width"] or 20, 10) / 2, max(track["avg_height"] or 20, 10) / 2
    return x - half_w, y - half_h, x + half_w, y + half_h


def _request(requests, track, moment, start_frame, images_dir):
    """Registra un recorte (uno por track y momento) y devuelve su ruta relativa al reporte."""
    frame, box = track[f"{moment}_seen_frame"], _box(track, moment)
    if frame is None or box is None:
        return None
    name = f"id{track['track_id']}_{moment}.jpg"
    label = f"ID {track['track_id']} {track['class']} f{start_frame + frame - 1}"
    requests[(track["track_id"], moment)] = (frame, box, label, images_dir / name)
    return f"images/{name}"


def _write_crop(image, box, label, path):
    x1, y1, x2, y2 = box
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    height, width = image.shape[:2]
    left, top = max(0, int(center_x - CROP_PX)), max(0, int(center_y - CROP_PX))
    patch = image[top:min(height, int(center_y + CROP_PX)), left:min(width, int(center_x + CROP_PX))].copy()
    cv2.rectangle(patch, (int(x1) - left, int(y1) - top), (int(x2) - left, int(y2) - top), (0, 0, 255), 2)
    for color, thickness in (((255, 255, 255), 2), ((0, 0, 0), 1)):
        cv2.putText(patch, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, thickness)
    cv2.imwrite(str(path), patch)


def _render_crops(video, start_frame, requests):
    """Decodifica los frames pedidos en orden y devuelve las rutas escritas."""
    by_frame = defaultdict(list)
    for frame, box, label, path in requests.values():
        by_frame[frame].append((box, label, path))
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir {video}")
    written, position = set(), None
    try:
        for frame in sorted(by_frame):
            index = start_frame + frame - 2
            if position is None or not 0 <= index - position <= SEEK_GAP_FRAMES:
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                position = index
            while position < index:
                cap.grab()
                position += 1
            ok, image = cap.read()
            position += 1
            if not ok:
                continue
            for box, label, path in by_frame[frame]:
                _write_crop(image, box, label, path)
                written.add(f"images/{path.name}")
    finally:
        cap.release()
    return written


def _image_lines(item):
    return [f"![{key}]({path})" for key, path in item["images"].items()] + [""]


def _markdown(report):
    frag = report["fragmentation"]
    lines = ["# Revisión de tracks incompletos", "",
             f"Video `{report['video']}` desde el frame {report['start_frame']}, {report['processed_frames']} frames, "
             f"modo `{report['counting_mode']}`. Los frames del texto son relativos a la corrida; las etiquetas de "
             "las imágenes usan el frame del video.", "",
             "## Resumen por acceso de origen", "",
             "| Acceso | Rutas completas | Perdidos | Visibles al final |", "|---|---:|---:|---:|"]
    lines += [f"| {origin} | {row['completos']} | {row['perdidos']} | {row['fin_del_tramo']} |"
              for origin, row in report["summary_by_origin"].items()] or ["| (sin zonas de origen) | 0 | 0 | 0 |"]
    lines += ["", "## Fragmentación de tracks", "",
              f"{frag['short_tracks']} de {frag['tracks']} tracks tienen {frag['short_observations']} observaciones "
              f"o menos (mediana {frag['median_observations']}).", "",
              "## Tracks con origen confirmado y sin destino", ""]
    if not report["incomplete"]:
        lines.append("Ninguno. En modo `lines` o `directions` no hay origen y esta sección queda vacía.")
    for track in report["incomplete"]:
        lines += [f"### ID {track['track_id']} · {track['class']} ({track['group']}) · origen {track['origin']} · "
                  f"{track['cause_hint']}", "",
                  f"Estado `{track['state']}`, frames {track['first_seen_frame']} a {track['last_seen_frame']}, "
                  f"{track['observed_frames']} observaciones, votos de clase `{track['class_votes']}`.", ""]
        lines += _image_lines(track)
    criteria = report["criteria"]
    lines += ["## Posibles cambios de ID", "",
              f"Termina un track y empieza otro del mismo grupo a menos de {criteria['max_distance_factor']} veces el "
              f"tamaño del vehículo y {criteria['max_gap_frames']} frames; cada track aparece en un solo par. "
              f"Total {report['id_switch_candidates_total']}, {report['class_changes']} con cambio de clase; se "
              f"muestran los {len(report['id_switch_candidates'])} más cercanos. Son candidatos, no errores confirmados.", ""]
    if not report["id_switch_candidates"]:
        lines.append("Ninguno.")
    for pair in report["id_switch_candidates"]:
        lines += [f"### ID {pair['ended_track']} → ID {pair['started_track']} · {pair['ended_class']} → "
                  f"{pair['started_class']} · {pair['gap_frames']} frames · {pair['distance_sizes']} tamaños", ""]
        lines += _image_lines(pair)
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reporte de tracks sin destino y posibles cambios de ID")
    parser.add_argument("--results", required=True, help="JSON de main.py")
    parser.add_argument("--tracks-csv", required=True, help="CSV de --output-tracks-csv de la misma corrida")
    parser.add_argument("--output-dir", required=True, help="Directorio nuevo o vacío")
    parser.add_argument("--video", help="Sustituye la ruta del video registrada en el JSON")
    parser.add_argument("--max-gap-frames", type=int, default=10)
    parser.add_argument("--max-distance-factor", type=float, default=1.5,
                        help="Distancia máxima en tamaños del vehículo que termina")
    args = parser.parse_args(argv)
    if args.max_gap_frames < 1 or args.max_distance_factor <= 0:
        parser.error("Los criterios deben ser positivos")

    output = Path(args.output_dir)
    if output.exists() and any(output.iterdir()):
        parser.error(f"{output} no está vacío; usa un directorio nuevo")
    images_dir = output / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    video = args.video or results["video"]
    start_frame = results.get("run", {}).get("start_frame", 1)
    tracks = load_tracks(args.tracks_csv)
    by_id = {track["track_id"]: track for track in tracks}
    incomplete = find_incomplete(tracks, results["frames_processed"])
    candidates = find_id_switch_candidates(tracks, args.max_gap_frames, args.max_distance_factor)
    shown = candidates[:MAX_CANDIDATES]

    requests = {}
    for track in incomplete:
        track["images"] = {moment: _request(requests, track, moment, start_frame, images_dir)
                           for moment in ("first", "last")}
    for pair in shown:
        pair["images"] = dict(
            termina=_request(requests, by_id[pair["ended_track"]], "last", start_frame, images_dir),
            empieza=_request(requests, by_id[pair["started_track"]], "first", start_frame, images_dir))
    written = _render_crops(video, start_frame, requests)
    for item in incomplete + shown:
        item["images"] = {key: path for key, path in item["images"].items() if path in written}

    report = dict(
        video=video, start_frame=start_frame, processed_frames=results["frames_processed"],
        counting_mode=results.get("counting_mode"),
        criteria=dict(max_gap_frames=args.max_gap_frames, max_distance_factor=args.max_distance_factor),
        summary_by_origin=summarize_by_origin(tracks, incomplete), fragmentation=fragmentation(tracks),
        incomplete=incomplete, id_switch_candidates=shown, id_switch_candidates_total=len(candidates),
        class_changes=sum(pair["ended_class"] != pair["started_class"] for pair in candidates))
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(_markdown(report), encoding="utf-8")
    print(output / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
