"""Catalogo y gestor de modelos de deteccion.

Uso CLI:
    python -m carcounter.models list
    python -m carcounter.models download yolov11m
    python -m carcounter.models download rfdetr-medium
    python -m carcounter.models info rfdetr-base
"""

import os
import sys
from pathlib import Path

from carcounter.paths import paths

# ── Catalogo de modelos ───────────────────────

MODELS_DIR = paths.root / "models"

MODEL_CATALOG = {
    # ── YOLO (ultralytics) ──
    "yolov11n": {
        "family": "yolo",
        "file": "yolo/yolov11n.pt",
        "source": "ultralytics",
        "size_mb": 6,
        "coco_ap50": 55.2,
        "latency_ms": 1.5,
        "params": "2.6M",
        "note": "Nano — mas rapido, menor precision",
    },
    "yolov11s": {
        "family": "yolo",
        "file": "yolo/yolov11s.pt",
        "source": "ultralytics",
        "size_mb": 19,
        "coco_ap50": 59.2,
        "latency_ms": 2.5,
        "params": "9.4M",
        "note": "Small — buen balance velocidad/precision",
    },
    "yolov11m": {
        "family": "yolo",
        "file": "yolo/yolov11m.pt",
        "source": "ultralytics",
        "size_mb": 39,
        "coco_ap50": 64.1,
        "latency_ms": 4.7,
        "params": "20.1M",
        "note": "Medium — recomendado para uso general",
    },
    "yolov11l": {
        "family": "yolo",
        "file": "yolo/yolov11l.pt",
        "source": "ultralytics",
        "size_mb": 49,
        "coco_ap50": 65.4,
        "latency_ms": 6.2,
        "params": "25.3M",
        "note": "Large — mayor precision",
    },
    "yolov11x": {
        "family": "yolo",
        "file": "yolo/yolov11x.pt",
        "source": "ultralytics",
        "size_mb": 110,
        "coco_ap50": 66.1,
        "latency_ms": 11.3,
        "params": "56.9M",
        "note": "XLarge — maxima precision YOLO",
    },
    # ── RF-DETR (Roboflow) ──
    "rfdetr-nano": {
        "family": "rfdetr",
        "file": "rfdetr/rfdetr-nano.pth",
        "source": "rfdetr",
        "variant": "nano",
        "size_mb": 30,
        "coco_ap50": 67.6,
        "latency_ms": 2.3,
        "params": "~3M",
        "note": "Nano — supera YOLO11-M en precision con menor latencia",
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
        "note": "Medium — +9.5 AP50 sobre YOLO11-M, similar latencia",
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
        "note": "Base — modelo original RF-DETR",
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
        "note": "Large — maxima precision RF-DETR",
    },
}


def _model_path(model_info):
    """Retorna el path completo del modelo."""
    return MODELS_DIR / model_info["file"]


def is_downloaded(model_name):
    """True si el modelo ya esta descargado localmente."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        return False
    path = _model_path(info)
    return path.exists() and path.stat().st_size > 1000


def get_model_path(model_name):
    """Retorna el path del modelo si existe, None si no."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        return None
    path = _model_path(info)
    return str(path) if path.exists() else None


def download_model(model_name):
    """Descarga un modelo del catalogo."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        print(f"Modelo '{model_name}' no encontrado en el catalogo.")
        print(f"Modelos disponibles: {', '.join(sorted(MODEL_CATALOG.keys()))}")
        return False

    path = _model_path(info)
    if path.exists() and path.stat().st_size > 1000:
        print(f"  {model_name} ya descargado ({path.stat().st_size / 1e6:.1f} MB)")
        return True

    path.parent.mkdir(parents=True, exist_ok=True)

    if info["source"] == "ultralytics":
        return _download_yolo(model_name, info, path)
    elif info["source"] == "rfdetr":
        return _download_rfdetr(model_name, info, path)
    else:
        print(f"  Fuente desconocida: {info['source']}")
        return False


def _download_yolo(model_name, info, path):
    """Descarga modelo YOLO via ultralytics."""
    try:
        from ultralytics import YOLO
        filename = Path(info["file"]).name
        print(f"  Descargando {model_name} ({info['size_mb']} MB)...")
        # ultralytics descarga al dir actual, luego movemos
        model = YOLO(filename)
        downloaded = Path(filename)
        if downloaded.exists():
            downloaded.rename(path)
            print(f"  OK -> {path}")
            return True
        # ultralytics puede haberlo puesto en otro lugar
        if path.exists():
            print(f"  OK -> {path}")
            return True
        print(f"  Descarga completada pero archivo no encontrado en {path}")
        return False
    except Exception as e:
        print(f"  Error descargando {model_name}: {e}")
        return False


def _download_rfdetr(model_name, info, path):
    """Descarga modelo RF-DETR (se descargan automaticamente al primer predict)."""
    try:
        import rfdetr as _rfdetr
        variant = info.get("variant", "base")
        variant_map = {
            "nano": "RFDETRNano", "small": "RFDETRSmall",
            "medium": "RFDETRMedium", "base": "RFDETRBase",
            "large": "RFDETRLarge",
        }
        cls_name = variant_map.get(variant, "RFDETRBase")
        model_cls = getattr(_rfdetr, cls_name)
        print(f"  Descargando {model_name} ({info['size_mb']} MB)...")
        print(f"  RF-DETR descarga pesos automaticamente al instanciar...")
        _model = model_cls()
        # RF-DETR guarda en cache de HuggingFace, no en nuestro dir
        # Marcamos como disponible creando un archivo marker
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# RF-DETR {variant} - pesos en cache HuggingFace\n")
        print(f"  OK — pesos cacheados por HuggingFace")
        return True
    except ImportError:
        print(f"  Error: pip install rfdetr")
        return False
    except Exception as e:
        print(f"  Error descargando {model_name}: {e}")
        return False


def list_models():
    """Imprime el catalogo de modelos con estado de descarga."""
    print()
    print("=" * 85)
    print("  CATALOGO DE MODELOS — Car Counter")
    print("=" * 85)

    for family in ["yolo", "rfdetr"]:
        family_label = "YOLO (ultralytics)" if family == "yolo" else "RF-DETR (Roboflow DINOv2)"
        print(f"\n  {family_label}")
        print(f"  {'─' * 80}")
        print(f"  {'Modelo':<18} {'AP50':>6} {'Latencia':>9} {'Params':>8} {'Tamaño':>8} {'Estado':>10}")
        print(f"  {'─' * 80}")

        for name, info in MODEL_CATALOG.items():
            if info["family"] != family:
                continue
            downloaded = is_downloaded(name)
            status = "  ✓" if downloaded else "  ✗"
            status_color = status
            print(f"  {name:<18} {info['coco_ap50']:>5.1f}  {info['latency_ms']:>6.1f}ms"
                  f"  {info['params']:>8} {info['size_mb']:>6}MB {status_color:>10}")

    print(f"\n  {'─' * 80}")
    print(f"  Latencias medidas en NVIDIA T4 FP16. AP50 = COCO val2017.")
    print(f"\n  Descargar:  python -m carcounter.models download <nombre>")
    print(f"  Info:       python -m carcounter.models info <nombre>")
    print("=" * 85)
    print()


def model_info(model_name):
    """Imprime informacion detallada de un modelo."""
    info = MODEL_CATALOG.get(model_name)
    if not info:
        print(f"Modelo '{model_name}' no encontrado.")
        return

    downloaded = is_downloaded(model_name)
    path = _model_path(info)

    print(f"\n  Modelo: {model_name}")
    print(f"  {'─' * 50}")
    print(f"  Familia:     {info['family'].upper()}")
    print(f"  COCO AP50:   {info['coco_ap50']}")
    print(f"  Latencia:    {info['latency_ms']}ms (T4 FP16)")
    print(f"  Parametros:  {info['params']}")
    print(f"  Tamaño:      ~{info['size_mb']} MB")
    print(f"  Nota:        {info.get('note', '')}")
    print(f"  Descargado:  {'Si' if downloaded else 'No'}")
    print(f"  Path:        {path}")

    if info["family"] == "yolo":
        print(f"\n  Uso: python main.py --model {path} --video assets/video.mp4")
    else:
        variant = info.get("variant", "base")
        print(f"\n  Uso: python main.py --detector rfdetr --rfdetr-variant {variant} --video assets/video.mp4")
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
