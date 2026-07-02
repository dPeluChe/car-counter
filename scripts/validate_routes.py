#!/usr/bin/env python3
"""Valida el conteo end-to-end de rutas (origen -> destino) vs conteo humano.

A diferencia de evaluate_pipeline.py (que mide deteccion por frame), esto mide
el resultado final del pipeline: cuantos autos completaron cada ruta A->B.

Flujo:
  1. make run          -> genera output/results.json (rutas del pipeline)
  2. humano cuenta el mismo clip a mano -> data/validation/route_truth.json
  3. make validate-routes

El ground truth es un JSON plano { "Norte -> Este": 40, "Sur -> Oeste": 12, ... }
Las claves de ruta deben coincidir con las que emite el pipeline en results.json.

Uso:
  python scripts/validate_routes.py \
      --results output/results.json \
      --truth data/validation/route_truth.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from carcounter.validation import counting_accuracy


def _normalize_key(key):
    """Normaliza la clave de ruta. El pipeline usa 'A → B'; aceptamos '->'
    y espacios variables para que el conteo humano sea facil de escribir."""
    return " → ".join(part.strip() for part in key.replace("→", "->").split("->"))


def _normalize_map(d):
    return {_normalize_key(k): int(v) for k, v in d.items()}


def _load_routes(results_path):
    """Extrae el dict de rutas {ruta: conteo} de un results.json del pipeline."""
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    routes = data.get("routes")
    if routes is None:
        print(f"ERROR: {results_path} no tiene campo 'routes' (¿modo zones?)")
        sys.exit(1)
    return routes


def validate(results_path, truth_path):
    pred = _normalize_map(_load_routes(results_path))
    with open(truth_path, encoding="utf-8") as f:
        truth = _normalize_map(json.load(f))

    routes = sorted(set(pred) | set(truth))
    if not routes:
        print("No hay rutas ni en el pipeline ni en el ground truth.")
        return {"per_route": {}, "totals": {}}

    per_route = {}
    total_pred = total_truth = total_abs_err = 0
    acc_sum = 0.0

    print("\n" + "=" * 60)
    print("Validacion de conteo de rutas (pipeline vs humano)")
    print("=" * 60)
    print(f"  {'ruta':<24} {'pred':>6} {'real':>6} {'err':>6} {'acc':>7}")
    for route in routes:
        p = int(pred.get(route, 0))
        t = int(truth.get(route, 0))
        err = abs(p - t)
        acc = counting_accuracy(p, t)
        per_route[route] = {"pred": p, "truth": t, "abs_error": err, "accuracy": acc}
        total_pred += p
        total_truth += t
        total_abs_err += err
        acc_sum += acc
        flag = "" if err == 0 else ("  <-- falta en pipeline" if p == 0
                                    else "  <-- ruta fantasma" if t == 0 else "")
        print(f"  {route:<24} {p:>6} {t:>6} {err:>6} {acc:>7.3f}{flag}")

    mae = total_abs_err / len(routes)
    mean_acc = acc_sum / len(routes)
    overall_acc = counting_accuracy(total_pred, total_truth)

    print("-" * 60)
    print(f"  Total autos (pred/real):   {total_pred} / {total_truth}")
    print(f"  MAE por ruta:              {mae:.2f}")
    print(f"  Accuracy media por ruta:   {mean_acc:.3f}")
    print(f"  Accuracy sobre el total:   {overall_acc:.3f}")
    print("=" * 60)

    return {
        "per_route": per_route,
        "totals": {
            "pred": total_pred, "truth": total_truth,
            "mae": round(mae, 3), "mean_route_accuracy": round(mean_acc, 4),
            "overall_accuracy": round(overall_acc, 4),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Valida conteo de rutas vs humano")
    parser.add_argument("--results", default="output/results.json",
                        help="results.json del pipeline")
    parser.add_argument("--truth", default="data/validation/route_truth.json",
                        help="conteo humano por ruta (JSON plano)")
    parser.add_argument("--output", default=None,
                        help="opcional: guarda el reporte a un JSON")
    args = parser.parse_args()

    if not Path(args.results).exists():
        print(f"ERROR: no existe {args.results}. Corre 'make run' primero.")
        sys.exit(1)
    if not Path(args.truth).exists():
        print(f"ERROR: no existe {args.truth}. Crea el conteo humano "
              f"(ver route_truth.example.json).")
        sys.exit(1)

    report = validate(args.results, args.truth)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Reporte guardado en: {args.output}")


if __name__ == "__main__":
    main()
