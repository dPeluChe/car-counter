"""Catalogo y gestor de modelos de deteccion.

Uso CLI:
    python -m carcounter.models list
    python -m carcounter.models download yolov11m
    python -m carcounter.models download rfdetr-medium
    python -m carcounter.models info rfdetr-base
"""

import sys
from pathlib import Path

from carcounter.paths import paths

# ── Catalogo de modelos ───────────────────────

MODELS_DIR = paths.root / "models"
# Un .pt/.pth real pesa varios MB; archivos menores son marcadores o descargas cortadas
MIN_WEIGHTS_BYTES = 1_000_000

MODEL_CATALOG = {
    # ── Aéreo (local, no descargable) ──
    "yolov8l-visdrone": {
        "family": "yolo",
        "file": "yolo/yolov8l-visdrone.pt",
        "source": "local",
        "size_mb": None,
        "coco_ap50": None,
        "latency_ms": None,
        "params": "?",
        "note": "Entrenado en VisDrone (tomas aéreas); modelo del aforo EPS",
    },
    # ── YOLO11 (ultralytics, COCO) ──
    "yolov11n": {
        "family": "yolo",
        "file": "yolo/yolov11n.pt",
        "asset": "yolo11n.pt",
        "source": "ultralytics",
        "size_mb": 6,
        "coco_ap50": 55.2,
        "latency_ms": 1.5,
        "params": "2.6M",
        "note": "Nano",
    },
    "yolov11s": {
        "family": "yolo",
        "file": "yolo/yolov11s.pt",
        "asset": "yolo11s.pt",
        "source": "ultralytics",
        "size_mb": 19,
        "coco_ap50": 59.2,
        "latency_ms": 2.5,
        "params": "9.4M",
        "note": "Small",
    },
    "yolov11m": {
        "family": "yolo",
        "file": "yolo/yolov11m.pt",
        "asset": "yolo11m.pt",
        "source": "ultralytics",
        "size_mb": 39,
        "coco_ap50": 64.1,
        "latency_ms": 4.7,
        "params": "20.1M",
        "note": "Medium",
    },
    "yolov11l": {
        "family": "yolo",
        "file": "yolo/yolov11l.pt",
        "asset": "yolo11l.pt",
        "source": "ultralytics",
        "size_mb": 49,
        "coco_ap50": 65.4,
        "latency_ms": 6.2,
        "params": "25.3M",
        "note": "Large",
    },
    "yolov11x": {
        "family": "yolo",
        "file": "yolo/yolov11x.pt",
        "asset": "yolo11x.pt",
        "source": "ultralytics",
        "size_mb": 110,
        "coco_ap50": 66.1,
        "latency_ms": 11.3,
        "params": "56.9M",
        "note": "XLarge",
    },
    # ── RF-DETR (Roboflow, COCO) ──
    "rfdetr-nano": {
        "family": "rfdetr",
        "file": "rfdetr/rfdetr-nano.pth",
        "source": "rfdetr",
        "variant": "nano",
        "size_mb": 30,
        "coco_ap50": 67.6,
        "latency_ms": 2.3,
        "params": "~3M",
        "note": "Nano",
    },
    "rfdetr-small": {
        "family": "rfdetr",
        "file": "rfdetr/rfdetr-small.pth",
        "source": "rfdetr",
        "variant": "small",
        "size_mb": 60,
        "coco_ap50": 70.8,
        "latency_ms": 3.2,
        "params": "~10M",
        "note": "Small",
    },
    "rfdetr-medium": {
        "family": "rfdetr",
        "file": "rfdetr/rfdetr-medium.pth",
        "source": "rfdetr",
        "variant": "medium",
        "size_mb": 100,
        "coco_ap50": 73.6,
        "latency_ms": 4.4,
        "params": "~20M",
        "note": "Medium",
    },
    "rfdetr-base": {
        "family": "rfdetr",
        "file": "rfdetr/rfdetr-base.pth",
        "source": "rfdetr",
        "variant": "base",
        "size_mb": 120,
        "coco_ap50": 74.2,
        "latency_ms": 5.5,
        "params": "29M",
        "note": "Base",
    },
    "rfdetr-large": {
        "family": "rfdetr",
        "file": "rfdetr/rfdetr-large.pth",
        "source": "rfdetr",
        "variant": "large",
        "size_mb": 280,
        "coco_ap50": 75.1,
        "latency_ms": 6.8,
        "params": "~50M",
        "note": "Large",
    },
}


def _model_path(model_info):
    """Retorna el path completo del modelo."""
    return MODELS_DIR / model_info["file"]


def is_valid_weights(path):
    """True si el archivo existe y tiene tamaño de pesos reales (no un marcador)."""
    try:
        return bool(path) and Path(path).is_file() and Path(path).stat().st_size >= MIN_WEIGHTS_BYTES
    except OSError:
        return False


def is_downloaded(model_name):
    """True si el modelo ya esta disponible localmente o en cache."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        return False
    path = _model_path(info)
    if is_valid_weights(path):
        return True
    if info["source"] == "rfdetr":
        return path.with_suffix(".cached").exists() or _rfdetr_in_cache(info)
    return False


def _rfdetr_in_cache(info):
    """Check if RF-DETR weights exist in HuggingFace cache."""
    try:
        cache_dir = Path.home() / ".cache" / "rf-detr"
        if not cache_dir.exists():
            return False
        pth_name = f"rf-detr-{info.get('variant', 'base')}.pth"
        return any(f.name == pth_name for f in cache_dir.rglob("*.pth"))
    except Exception:
        return False


def get_model_path(model_name):
    """Retorna el path del modelo si hay pesos reales, None si no."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        return None
    path = _model_path(info)
    return str(path) if is_valid_weights(path) else None


def download_model_with_error(model_name):
    """Descarga un modelo del catalogo. Retorna (ok, mensaje_de_error)."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        return False, f"Modelo '{model_name}' no encontrado en el catálogo"
    path = _model_path(info)
    if is_valid_weights(path):
        return True, None
    if info["source"] == "local":
        return False, f"{model_name} no se descarga: copia el archivo en {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if info["source"] == "ultralytics":
            _download_yolo(model_name, info, path)
        elif info["source"] == "rfdetr":
            _download_rfdetr(model_name, info, path)
        else:
            return False, f"Fuente desconocida: {info['source']}"
    except Exception as error:
        return False, f"{type(error).__name__}: {error}"
    return True, None


def download_model(model_name):
    """Descarga un modelo del catalogo (compatibilidad CLI)."""
    ok, error = download_model_with_error(model_name)
    if error:
        print(f"  Error con {model_name}: {error}")
    return ok


def _download_yolo(model_name, info, path):
    """Descarga el asset de Ultralytics (yolo11*.pt) directo a su ruta final."""
    from ultralytics.utils.downloads import attempt_download_asset
    print(f"  Descargando {model_name} ({info['size_mb']} MB)...")
    downloaded = Path(attempt_download_asset(str(path.parent / info["asset"])))
    if downloaded.resolve() != path.resolve() and downloaded.exists():
        downloaded.replace(path)
    if not is_valid_weights(path):
        raise RuntimeError(f"la descarga no dejó pesos válidos en {path}")
    print(f"  OK -> {path}")


def _download_rfdetr(model_name, info, path):
    """RF-DETR baja sus pesos a la cache al instanciar; se deja un marcador .cached, no un .pth falso."""
    import rfdetr as _rfdetr
    variant_map = {"nano": "RFDETRNano", "small": "RFDETRSmall", "medium": "RFDETRMedium",
                   "base": "RFDETRBase", "large": "RFDETRLarge"}
    model_cls = getattr(_rfdetr, variant_map.get(info.get("variant", "base"), "RFDETRBase"))
    print(f"  Descargando {model_name} ({info['size_mb']} MB) a la cache de RF-DETR...")
    model_cls()
    path.with_suffix(".cached").write_text(f"RF-DETR {info.get('variant', 'base')}: pesos en cache\n")
    print("  OK: pesos en cache")


def _metric(value, fmt):
    return format(value, fmt) if value is not None else "-"


def list_models():
    """Imprime el catalogo de modelos con estado de descarga."""
    print()
    print("=" * 85)
    print("  CATALOGO DE MODELOS: Car Counter")
    print("=" * 85)

    for family in ["yolo", "rfdetr"]:
        family_label = "YOLO (ultralytics y locales)" if family == "yolo" else "RF-DETR (Roboflow DINOv2)"
        print(f"\n  {family_label}")
        print(f"  {'─' * 80}")
        print(f"  {'Modelo':<18} {'AP50':>6} {'Latencia':>9} {'Params':>8} {'Tamaño':>8} {'Estado':>10}")
        print(f"  {'─' * 80}")

        for name, info in MODEL_CATALOG.items():
            if info["family"] != family:
                continue
            status = "  ✓" if is_downloaded(name) else "  ✗"
            print(f"  {name:<18} {_metric(info['coco_ap50'], '>5.1f'):>6}  {_metric(info['latency_ms'], '>6.1f'):>6}ms"
                  f"  {info['params']:>8} {_metric(info['size_mb'], '>6'):>6}MB {status:>10}")

    print(f"\n  {'─' * 80}")
    print("  AP50 y latencia: referencia COCO del fabricante (T4 FP16), no medidas en el aforo EPS.")
    print("\n  Descargar:  python -m carcounter.models download <nombre>")
    print("  Info:       python -m carcounter.models info <nombre>")
    print("=" * 85)
    print()


def model_info(model_name):
    """Imprime informacion detallada de un modelo."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        print(f"Modelo '{model_name}' no encontrado.")
        return

    path = _model_path(info)
    print(f"\n  Modelo: {model_name}")
    print(f"  {'─' * 50}")
    print(f"  Familia:     {info['family'].upper()} ({info['source']})")
    print(f"  COCO AP50:   {_metric(info['coco_ap50'], '.1f')} (referencia del fabricante)")
    print(f"  Latencia:    {_metric(info['latency_ms'], '.1f')}ms (T4 FP16)")
    print(f"  Parametros:  {info['params']}")
    print(f"  Tamaño:      ~{_metric(info['size_mb'], '')} MB")
    print(f"  Nota:        {info.get('note', '')}")
    print(f"  Descargado:  {'Si' if is_downloaded(model_name) else 'No'}")
    print(f"  Path:        {path}")

    if info["family"] == "yolo":
        print(f"\n  Uso: python main.py --model {path} --video assets/video.mp4")
    else:
        print(f"\n  Uso: python main.py --detector rfdetr --rfdetr-variant {info.get('variant', 'base')} --video assets/video.mp4")
    print()


# ── CLI ───────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        list_models()
        return

    cmd = sys.argv[1]

    if cmd == "list":
        list_models()
    elif cmd == "download":
        if len(sys.argv) < 3:
            print("Uso: python -m carcounter.models download <nombre>")
            print(f"Modelos: {', '.join(sorted(MODEL_CATALOG.keys()))}")
            return
        name = sys.argv[2]
        if name == "all":
            for n in MODEL_CATALOG:
                download_model(n)
        else:
            download_model(name)
    elif cmd == "info":
        if len(sys.argv) < 3:
            print("Uso: python -m carcounter.models info <nombre>")
            return
        model_info(sys.argv[2])
    else:
        print(f"Comando desconocido: {cmd}")
        print("Comandos: list, download, info")


if __name__ == "__main__":
    main()
