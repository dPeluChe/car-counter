"""Compara umbrales de supresión entre clases sobre una misma caché de detecciones (sin inferencia)."""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carcounter.track_review import find_id_switch_candidates, fragmentation, load_tracks


def run_variant(python, profile, threshold, args, workdir):
    settings = dict(profile.get("settings", {}), cross_class_nms_iou=threshold)
    path = workdir / f"profile_{threshold}.json"
    path.write_text(json.dumps(dict(profile, settings=settings)), encoding="utf-8")
    out_json, out_tracks = workdir / f"{threshold}.json", workdir / f"{threshold}_tracks.csv"
    command = [python, str(ROOT / "main.py"), "--config", str(path), "--video", args.video, "--no-sahi",
               "--headless", "--no-save", "--max-frames", str(args.max_frames),
               "--replay-detections", args.cache, "--tracker", args.tracker,
               "--output-json", str(out_json), "--output-tracks-csv", str(out_tracks)]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    result = json.loads(out_json.read_text(encoding="utf-8"))
    tracks = load_tracks(out_tracks)
    switches = find_id_switch_candidates(tracks)
    return dict(
        umbral=threshold, eventos=len(result.get("counting_events", [])),
        por_grupo=result.get("routes_by_group", {}), tracks=len(tracks),
        cortos=fragmentation(tracks)["short_tracks"], candidatos_id=len(switches),
        candidatos_con_cambio_de_clase=sum(p["ended_class"] != p["started_class"] for p in switches),
        eventos_detalle=[(e["frame"], e["route"], e["class"]) for e in result.get("counting_events", [])])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--cache", required=True, help="SQLite grabada con --record-detections")
    parser.add_argument("--max-frames", type=int, required=True)
    parser.add_argument("--tracker", default="bytetrack")
    parser.add_argument("--thresholds", type=float, nargs="+", default=[0.0, 0.5, 0.6, 0.7, 0.8])
    parser.add_argument("--output-csv")
    args = parser.parse_args()
    profile = json.loads(Path(args.config).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        rows = [run_variant(sys.executable, profile, t, args, Path(tmp)) for t in args.thresholds]
    header = ("umbral", "eventos", "tracks", "cortos", "candidatos_id", "candidatos_con_cambio_de_clase")
    print("\t".join(header))
    for row in rows:
        print("\t".join(str(row[key]) for key in header))
    base = rows[0]["eventos_detalle"]
    for row in rows[1:]:
        print(f"umbral {row['umbral']}: eventos distintos de la base = "
              f"{sorted(set(row['eventos_detalle']) ^ set(base))}; por grupo = {row['por_grupo']}")
    if args.output_csv:
        with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows([[row[key] for key in header] for row in rows])


if __name__ == "__main__":
    main()
