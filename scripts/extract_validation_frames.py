#!/usr/bin/env python3

import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from carcounter.paths import paths
from carcounter.detection_cache import file_digest
from carcounter.validation import phash, hamming_distance


def extract_frames(video_path, output_dir, n_candidates=200, hash_threshold=None):
    if n_candidates < 1:
        raise ValueError("n_candidates debe ser positivo")
    if hash_threshold is not None and not 0 <= hash_threshold <= 64:
        raise ValueError("hash_threshold debe estar entre 0 y 64")
    output_dir = Path(output_dir)
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise FileExistsError("Usa una carpeta nueva o vacía; no se sobrescriben imágenes ni anotaciones")
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            raise ValueError("No se pudo abrir el video")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if total < 1 or not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video sin frames o FPS válido")
        count = min(n_candidates, total)
        indices = [i * (total - 1) // (count - 1) for i in range(count)] if count > 1 else [0]
        manifest = dict(version=1, video_name=Path(video_path).name,
                        video_sha256=file_digest(video_path), fps=fps, total_frames=total,
                        timestamp_basis="frame_index_divided_by_fps", reviewed=False,
                        requested_candidates=n_candidates, sampled_frames=len(indices),
                        hash_threshold=hash_threshold, frames=[])
        output_dir.mkdir(parents=True, exist_ok=True)
        hashes = []
        for idx in indices:
            if not cap.set(cv2.CAP_PROP_POS_FRAMES, idx):
                raise ValueError(f"No se pudo buscar el frame {idx + 1}")
            ret, frame = cap.read()
            if not ret or frame is None:
                raise ValueError(f"No se pudo leer el frame {idx + 1}")
            if hash_threshold is not None:
                fingerprint = phash(frame)
                if any(hamming_distance(fingerprint, old) <= hash_threshold for old in hashes):
                    continue
                hashes.append(fingerprint)
            name = f"frame_{idx + 1:08d}.jpg"
            if not cv2.imwrite(str(output_dir / name), frame):
                raise OSError(f"No se pudo guardar {name}")
            manifest["frames"].append(dict(image=name, frame_index=idx + 1,
                                           timestamp_seconds=idx / fps))
        metadata = output_dir / "metadata"
        metadata.mkdir()
        (metadata / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Guardados {len(manifest['frames'])}/{count} frames en: {output_dir}")
        return len(manifest["frames"])
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description="Extrae frames para dataset de validacion")
    parser.add_argument("--video", default=str(paths.default_video))
    parser.add_argument("--output-dir", default=str(paths.data_dir / "validation" / "frames"))
    parser.add_argument("--n-candidates", type=int, default=200,
                        help="Máximo de frames distribuidos por todo el video (default: 200)")
    parser.add_argument("--hash-threshold", type=int, default=None,
                        help="Deduplicación pHash opcional (0-64); puede descartar vehículos distintos")
    args = parser.parse_args()
    extract_frames(args.video, args.output_dir, args.n_candidates, args.hash_threshold)


if __name__ == "__main__":
    main()
