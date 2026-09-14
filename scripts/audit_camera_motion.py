import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from carcounter.camera_motion import CameraMotionMonitor, counting_anchors


def audit(video, config, *, every=30, max_frames=None, max_drift_px=5.0):
    if every < 1 or (max_frames is not None and max_frames < 1):
        raise ValueError("Los intervalos y límites deben ser positivos")
    cap = cv2.VideoCapture(str(video))
    samples = []
    start = time.perf_counter()
    try:
        ok, reference = cap.read()
        if not ok:
            raise ValueError(f"No se pudo leer el video {video}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        limit = min(source_frames, max_frames or source_frames)
        monitor = CameraMotionMonitor(reference, anchors=counting_anchors(config),
                                      inference_roi=config.get("settings", {}).get("inference_roi"),
                                      max_drift_px=max_drift_px)
        for number in range(1, limit + 1, every):
            cap.set(cv2.CAP_PROP_POS_FRAMES, number - 1)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"No se pudo leer el frame {number}")
            samples.append(dict(frame=number, seconds=round((number - 1) / fps, 3) if fps else None,
                                **monitor.check(frame)))
    finally:
        cap.release()
    drifts = [sample["max_drift_px"] for sample in samples if sample["max_drift_px"] is not None]
    status = "unreliable" if not samples or any(s["status"] == "unreliable" for s in samples) else (
        "moved" if any(s["status"] == "moved" for s in samples) else "stable")
    return dict(video=str(video), status=status, samples=samples, sample_interval=every,
                threshold_px=max_drift_px, max_drift_px=max(drifts, default=None),
                processing_seconds=round(time.perf_counter() - start, 3),
                scope="Comprobación de fondo y geometría; no mide precisión del aforo")


def main():
    parser = argparse.ArgumentParser(description="Comprueba movimiento de cámara respecto al primer frame")
    parser.add_argument("--config", required=True)
    parser.add_argument("--video")
    parser.add_argument("--every", type=int, default=30)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--max-drift-px", type=float, default=5.0)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    result = audit(args.video or config["video_path"], config, every=args.every,
                   max_frames=args.max_frames, max_drift_px=args.max_drift_px)
    destination = Path(args.output_json)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}, ensure_ascii=False))
    return 0 if result["status"] == "stable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
