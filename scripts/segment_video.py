"""Divide un video en tramos de camara estable y guarda un frame de referencia por tramo.

Cada tramo estable admite una sola geometria (zonas, lineas, exclusiones) dibujada sobre su
frame de referencia; los tramos de transicion no se cuentan hasta corregir la geometria.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from carcounter.camera_motion import counting_anchors
from carcounter.video_segments import segment_by_stability


def iter_samples(cap, total_frames, step):
    for number in range(1, total_frames + 1, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, number - 1)
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"No se pudo leer el frame {number}")
        yield number, frame


def _clock(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def main():
    parser = argparse.ArgumentParser(description="Divide un video en tramos de cámara estable")
    parser.add_argument("--video", required=True)
    parser.add_argument("--config", help="Perfil opcional: su geometría son los puntos de control y su ROI la máscara")
    parser.add_argument("--every-seconds", type=float, default=5.0)
    parser.add_argument("--max-drift-px", type=float, default=10.0,
                        help="Deriva máxima respecto al inicio del tramo; 10 px coincide con el margen de las zonas")
    parser.add_argument("--min-stable-seconds", type=float, default=30.0)
    parser.add_argument("--frames-dir", help="Guarda el frame de referencia de cada tramo estable")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    if args.every_seconds <= 0 or args.min_stable_seconds < 0:
        parser.error("--every-seconds debe ser positivo y --min-stable-seconds no negativo")

    config = json.loads(Path(args.config).read_text()) if args.config else {}
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        parser.error(f"No se pudo abrir {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(args.every_seconds * fps))
    try:
        segments = segment_by_stability(
            iter_samples(cap, total, step), total, max_drift_px=args.max_drift_px,
            min_stable_frames=round(args.min_stable_seconds * fps),
            anchors=counting_anchors(config) or None,
            inference_roi=config.get("settings", {}).get("inference_roi"))
        if args.frames_dir:
            frames_dir = Path(args.frames_dir)
            frames_dir.mkdir(parents=True, exist_ok=True)
            for segment in segments:
                if segment["reference_frame"] is None:
                    continue
                cap.set(cv2.CAP_PROP_POS_FRAMES, segment["reference_frame"] - 1)
                ok, frame = cap.read()
                if ok:
                    path = frames_dir / f"tramo{segment['index']:02d}_frame{segment['reference_frame']}.jpg"
                    cv2.imwrite(str(path), frame)
                    segment["reference_image"] = str(path)
    finally:
        cap.release()

    for segment in segments:
        segment["start_seconds"] = round((segment["start_frame"] - 1) / fps, 2)
        segment["end_seconds"] = round(segment["end_frame"] / fps, 2)
    report = dict(video=args.video, fps=fps, total_frames=total, sample_every_frames=step,
                  max_drift_px=args.max_drift_px, min_stable_seconds=args.min_stable_seconds,
                  segments=segments,
                  scope="Estabilidad por imagen respecto al inicio de cada tramo; resolución igual al intervalo de muestreo")
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for s in segments:
        print(f"tramo {s['index']:>2}  {s['label']:<10} {_clock(s['start_seconds']):>5} a {_clock(s['end_seconds']):>5}"
              f"  frames {s['start_frame']}-{s['end_frame']}  referencia={s['reference_frame']}"
              f"  deriva_max={s['max_drift_px']:.1f}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
