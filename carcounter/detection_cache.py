import hashlib
import json
from pathlib import Path
import sqlite3


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_signature(cfg, detector_backend, use_sahi, variant="base", start_frame=1):
    if detector_backend == "rfdetr" and cfg["model_path"].endswith(".pt"):
        raise ValueError("La caché RF-DETR requiere pesos explícitos .pth del detector utilizado")
    signature = {
        "version": 1,
        "video_sha256": file_digest(cfg["video_path"]),
        "model_sha256": file_digest(cfg["model_path"]),
        "detector": detector_backend, "variant": variant,
        "imgsz": cfg["imgsz"], "inference_roi": cfg["settings"].get("inference_roi"),
        "effective_conf": cfg["effective_conf"], "use_sahi": use_sahi,
        "sahi": {key: cfg[key] for key in ("sahi_slice_w", "sahi_slice_h", "sahi_overlap", "sahi_nms")}
                if use_sahi else None,
    }
    # Solo se agrega al empezar después del frame 1 para no invalidar cachés existentes
    if start_frame != 1:
        signature["start_frame"] = start_frame
    return signature


class DetectionCacheWriter:
    def __init__(self, path, signature):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb"):
            pass
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE frames (number INTEGER PRIMARY KEY, detections TEXT NOT NULL)")
        self.connection.execute("INSERT INTO metadata VALUES ('signature', ?)", (json.dumps(signature),))
        self.connection.commit()
        self.frames = 0

    def write(self, number, detections):
        if number != self.frames + 1:
            raise ValueError("La caché requiere frames consecutivos desde 1")
        self.connection.execute("INSERT INTO frames VALUES (?, ?)",
                                (number, json.dumps(detections, allow_nan=False)))
        self.frames = number
        if number % 60 == 0:
            self.connection.commit()

    def close(self, complete=False):
        if complete:
            self.connection.execute("INSERT INTO metadata VALUES ('complete', ?)", (str(self.frames),))
        self.connection.commit()
        self.connection.close()


class DetectionCacheReader:
    def __init__(self, path, signature):
        self.connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            metadata = dict(self.connection.execute("SELECT key, value FROM metadata"))
            if "complete" not in metadata:
                raise ValueError("Caché incompleta: repite la grabación")
            cached = json.loads(metadata["signature"])
            expected = dict(signature)
            minimum = expected.pop("effective_conf")
            cached_minimum = cached.pop("effective_conf")
            if cached != expected or minimum < cached_minimum:
                raise ValueError("Caché incompatible: video, modelo, ROI, resolución, SAHI o confianza distintos")
            self.frames = int(metadata["complete"])
            if self.frames < 1:
                raise ValueError("Caché sin frames")
            count, first, last = self.connection.execute("SELECT count(*), min(number), max(number) FROM frames").fetchone()
            if count != self.frames or (count and (first != 1 or last != count)):
                raise ValueError("Caché con frames faltantes")
            self.minimum = minimum
        except Exception:
            self.connection.close()
            raise

    def read(self, number):
        row = self.connection.execute("SELECT detections FROM frames WHERE number = ?", (number,)).fetchone()
        if row is None:
            raise ValueError(f"Frame {number} ausente de la caché")
        return [det for det in json.loads(row[0]) if det["conf"] >= self.minimum]

    def close(self):
        self.connection.close()
