#!/usr/bin/env python3
"""Export model to ONNX format for faster inference on CPU."""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultralytics import YOLO


def export_to_onnx(model_path, imgsz=1600):
    """Convert YOLO .pt model to ONNX format."""
    if not os.path.exists(model_path):
        print(f"Error: Model file not found: {model_path}")
        sys.exit(1)
    
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    
    output_path = model_path.replace(".pt", ".onnx")
    print(f"Exporting to ONNX: {output_path}")
    
    success = model.export(format="onnx", imgsz=imgsz, simplify=True)
    
    print(f"Export complete: {success}")
    print(f"Output: {output_path}")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Export YOLO model to ONNX")
    parser.add_argument("--model", required=True, help="Path to .pt model")
    parser.add_argument("--imgsz", type=int, default=1600,
                        help="Input image size — debe coincidir con el imgsz usado en inferencia (default: 1600)")
    args = parser.parse_args()
    
    export_to_onnx(args.model, args.imgsz)


if __name__ == "__main__":
    main()