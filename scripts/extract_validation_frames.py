#!/usr/bin/env python3
"""Extrae frames candidatos de un video y deduplica con perceptual hashing.

Uso:
  python scripts/extract_validation_frames.py \
      --video assets/glorieta_fast.MP4 \
      --output-dir data/validation/frames \
      --n-candidates 200 \
      --hash-threshold 5
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from carcounter.paths import paths
from carcounter.validation import phash, dedup_by_phash


def extract_frames(video_path, output_dir, n_candidates=200, hash_threshold=5):
    """Extrae N frames equidistantes del video y deduplica por pHash."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: No se pudo abrir {video_path}")
        sys.exit(1)

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        print(f"ERROR: Video sin frames ({video_path})")
        sys.exit(1)

    step = max(1, total // n_candidates)
    print(f"Video: {total} frames, extrayendo cada {step} frame(s) (~{n_candidates} candidatos)")

    frames = []
    indices = []
    idx = 0
    while idx < total:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
            indices.append(idx)
        idx += step
    cap.release()

    print(f"Candidatos extraidos: {len(frames)}")

    hashes = [phash(f) for f in frames]
    kept = dedup_by_phash(hashes, threshold=hash_threshold)
    print(f"Despues de dedup (threshold={hash_threshold}): {len(kept)} frames unicos")

    for new_idx, orig_i in enumerate(kept):
        out_path = output_dir / f"frame_{new_idx:04d}.jpg"
        cv2.imwrite(str(out_path), frames[orig_i])

    print(f"Guardados en: {output_dir}")
    return len(kept)


def main():
    parser = argparse.ArgumentParser(description="Extrae frames para dataset de validacion")
    parser.add_argument("--video", default=str(paths.default_video))
    parser.add_argument("--output-dir", default=str(paths.data_dir / "validation" / "frames"))
    parser.add_argument("--n-candidates", type=int, default=200,
                        help="Numero aproximado de frames candidatos antes de dedup (default: 200)")
    parser.add_argument("--hash-threshold", type=int, default=5,
                        help="Distancia Hamming maxima para considerar duplicados (default: 5)")
    args = parser.parse_args()

    extract_frames(args.video, args.output_dir, args.n_candidates, args.hash_threshold)


if __name__ == "__main__":
    main()
