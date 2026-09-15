"""Reporte visual de tracks sin destino y posibles cambios de ID de una corrida de main.py.

Usa el JSON de resultados (video, start_frame, frames procesados) y el CSV de --output-tracks-csv.
Genera report.json, report.md y recortes del primer y ultimo frame de cada caso.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from carcounter.track_review import (
    find_id_switch_candidates, find_incomplete, fragmentation, load_tracks, summarize_by_origin,
)


class FrameReader:
    def __init__(self, video, start_frame):
        self.cap = cv2.VideoCapture(str(video))
        if not self.cap.isOpened():
            raise ValueError(f"No se pudo abrir {video}")
        self.start_frame = start_frame

    def crop(self, frame_number, x, y, width, height, label, path, crop_px):
        """Recorta alrededor de la caja aproximada (centro + tamaño promedio) de un frame relativo a la corrida."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame + frame_number - 2)
        ok, frame = self.cap.read()
        if not ok:
            return None
        half_w, half_h = max(width or 30, 10) / 2, max(height or 30, 10) / 2
        cv2.rectangle(frame, (int(x - half_w), int(y - half_h)), (int(x + half_w), int(y + half_h)), (0, 0, 255), 2)
        img_h, img_w = frame.shape[:2]
        x1, y1 = max(0, int(x - crop_px)), max(0, int(y - crop_px))
        x2, y2 = min(img_w, int(x + crop_px)), min(img_h, int(y + crop_px))
        patch = frame[y1:y2, x1:x2].copy()
        cv2.putText(patch, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
        cv2.putText(patch, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        cv2.imwrite(str(path), patch)
        return path.name

    def close(self):
        self.cap.release()


def _snapshots(reader, track, images_dir, crop_px, prefix):
    names = {}
    for moment in ("first", "last"):
        frame = track[f"{moment}_seen_frame"]
        if frame is None or track[f"{moment}_x"] is None:
            continue
        label = f"ID {track['track_id']} {track['class']} f{frame}"
        path = images_dir / f"{prefix}_id{track['track_id']}_{moment}.jpg"
        name = reader.crop(frame, track[f"{moment}_x"], track[f"{moment}_y"],
                           track["avg_width"], track["avg_height"], label, path, crop_px)
        if name:
            names[moment] = f"images/{name}"
    return names


def _markdown(report):
    lines = ["# Revisión de tracks incompletos", "",
             f"Video `{report['video']}`, desde el frame {report['start_frame']}, {report['processed_frames']} frames "
             f"procesados, modo `{report['counting_mode']}`. Los frames son relativos a la corrida.", "",
             "Las cajas son aproximadas: centro registrado y tamaño promedio del track.", "",
             "## Resumen por acceso de origen", "",
             "| Acceso | Rutas completas | Perdidos | Visibles al final |", "|---|---:|---:|---:|"]
    lines += [f"| {origin} | {row['completos']} | {row['perdidos']} | {row['fin_del_tramo']} |"
              for origin, row in report["summary_by_origin"].items()] or ["| (sin zonas de origen) | 0 | 0 | 0 |"]
    frag = report["fragmentation"]
    lines += ["", "## Fragmentación de tracks", "",
              f"{frag['short_tracks']} de {frag['tracks']} tracks tienen {frag['short_observations']} observaciones "
              f"o menos (mediana {frag['median_observations']}). Muchos tracks cortos indican IDs que se cortan "
              "y se vuelven a crear: es la causa principal de rutas perdidas."]
    lines += ["", "## Tracks con origen y sin destino", ""]
    if not report["incomplete"]:
        lines.append("Ninguno. En modo `lines` o `directions` no hay origen y esta sección queda vacía.")
    for track in report["incomplete"]:
        lines += [f"### ID {track['track_id']} · {track['class']} ({track['group']}) · origen {track['origin']} · "
                  f"{track['cause_hint']}", "",
                  f"Estado `{track['state']}`, frames {track['first_seen_frame']} a {track['last_seen_frame']}, "
                  f"{track['observed_frames']} observaciones.", ""]
        lines += [f"![{moment}]({path})" for moment, path in track["images"].items()] + [""]
    lines += ["## Posibles cambios de ID", "",
              f"Termina un track y empieza otro del mismo grupo a menos de {report['criteria']['max_distance_factor']} "
              f"veces el tamaño del vehículo y {report['criteria']['max_gap_frames']} frames. Cada track aparece en "
              f"un solo par. Total: {report['id_switch_candidates_total']}; se muestran los "
              f"{len(report['id_switch_candidates'])} más cercanos. Son candidatos para revisar, no errores confirmados.", ""]
    if not report["id_switch_candidates"]:
        lines.append("Ninguno.")
    for pair in report["id_switch_candidates"]:
        lines += [f"### ID {pair['ended_track']} → ID {pair['started_track']} · {pair['group']} · "
                  f"{pair['gap_frames']} frames · {pair['distance_px']} px", ""]
        lines += [f"![{key}]({path})" for key, path in pair["images"].items()] + [""]
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
    parser.add_argument("--end-margin-frames", type=int, default=30)
    parser.add_argument("--crop-px", type=int, default=120)
    parser.add_argument("--max-candidates", type=int, default=50, help="Candidatos con imagen (los más cercanos)")
    args = parser.parse_args(argv)
    if min(args.max_gap_frames, args.end_margin_frames, args.crop_px, args.max_candidates) < 1 or args.max_distance_factor <= 0:
        parser.error("Los criterios deben ser positivos")

    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    output = Path(args.output_dir)
    if output.exists() and any(output.iterdir()):
        parser.error(f"{output} no está vacío; usa un directorio nuevo")
    images_dir = output / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    tracks = load_tracks(args.tracks_csv)
    by_id = {track["track_id"]: track for track in tracks}
    processed = results["frames_processed"]
    start_frame = results.get("run", {}).get("start_frame", 1)
    incomplete = find_incomplete(tracks, processed, args.end_margin_frames)
    candidates = find_id_switch_candidates(tracks, args.max_gap_frames, args.max_distance_factor)

    reader = FrameReader(args.video or results["video"], start_frame)
    try:
        for track in incomplete:
            track["images"] = _snapshots(reader, track, images_dir, args.crop_px, "incompleto")
        for pair in candidates[:args.max_candidates]:
            ended = _snapshots(reader, by_id[pair["ended_track"]], images_dir, args.crop_px, "cambio")
            started = _snapshots(reader, by_id[pair["started_track"]], images_dir, args.crop_px, "cambio")
            pair["images"] = {k: v for k, v in (("termina", ended.get("last")), ("empieza", started.get("first"))) if v}
    finally:
        reader.close()

    report = dict(
        video=args.video or results["video"], start_frame=start_frame, processed_frames=processed,
        counting_mode=results.get("counting_mode"),
        criteria=dict(max_gap_frames=args.max_gap_frames, max_distance_factor=args.max_distance_factor,
                      end_margin_frames=args.end_margin_frames),
        summary_by_origin=summarize_by_origin(tracks, incomplete),
        fragmentation=fragmentation(tracks),
        incomplete=incomplete, id_switch_candidates=candidates[:args.max_candidates],
        id_switch_candidates_total=len(candidates),
        scope="Candidatos para revisión humana; no confirma pérdidas ni cambios de ID")
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(dict(summary_by_origin=report["summary_by_origin"], fragmentacion=report["fragmentation"],
                          incompletos=len(incomplete),
                          candidatos_cambio_id=len(candidates), reporte=str(output / "report.md")),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
