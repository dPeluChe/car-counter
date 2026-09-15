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

from carcounter.constants import CLASS_GROUPS, class_group
from carcounter.validation import canonical_vehicle_label, compute_metrics, counting_accuracy


def _normalize_key(key):
    """Normaliza la clave de ruta. El pipeline usa 'A → B'; aceptamos '->'
    y espacios variables para que el conteo humano sea facil de escribir."""
    return " → ".join(part.strip() for part in key.replace("→", "->").split("->"))


def _normalize_map(d):
    normalized = {}
    for key, value in d.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"Conteo invalido para {key}: se requiere un entero no negativo")
        route = _normalize_key(key)
        if route in normalized:
            raise ValueError(f"Ruta duplicada despues de normalizar: {route}")
        normalized[route] = value
    return normalized


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
    weighted_route_acc = max(0.0, 1.0 - total_abs_err / max(total_truth, 1))

    print("-" * 60)
    print(f"  Total autos (pred/real):   {total_pred} / {total_truth}")
    print(f"  MAE por ruta:              {mae:.2f}")
    print(f"  Accuracy media por ruta:   {mean_acc:.3f}")
    print(f"  Accuracy sobre el total:   {overall_acc:.3f}")
    print(f"  Accuracy ponderada rutas: {weighted_route_acc:.3f}")
    print("=" * 60)

    return {
        "per_route": per_route,
        "totals": {
            "pred": total_pred, "truth": total_truth,
            "mae": round(mae, 3), "mean_route_accuracy": round(mean_acc, 4),
            "overall_accuracy": round(overall_acc, 4),
            "weighted_route_accuracy": round(weighted_route_acc, 4),
            "total_abs_error": total_abs_err,
        },
    }


def _event_label(label, by_group):
    label = canonical_vehicle_label(label)
    if not by_group or label in CLASS_GROUPS:
        return label
    return class_group(label) or label


def _event_rows(rows, start, end, by_group=False):
    if not isinstance(rows, list):
        raise ValueError("events debe ser una lista")
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or type(row.get("frame")) is not int or row["frame"] < 1:
            raise ValueError("Cada evento requiere un frame entero desde 1")
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in ("route", "class")):
            raise ValueError("Cada evento requiere route y class")
        if not start <= row["frame"] <= end:
            raise ValueError("Evento fuera del tramo declarado")
        normalized.append(dict(row, index=index, route=_normalize_key(row["route"]),
                               **{"class": _event_label(row["class"], by_group)}))
    return normalized


def validate_events(results_path, truth_path, tolerance_frames=15, by_group=False):
    if type(tolerance_frames) is not int or tolerance_frames < 0:
        raise ValueError("La tolerancia requiere un entero no negativo")
    results = json.loads(Path(results_path).read_text())
    truth = json.loads(Path(truth_path).read_text())
    if truth.get("reviewed") is not True:
        raise ValueError("La referencia de eventos requiere reviewed=true tras revisión humana")
    digest = results.get("run", {}).get("video_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or digest != truth.get("video_sha256"):
        raise ValueError("La referencia y el resultado requieren el mismo SHA-256 del video")
    start, end = truth.get("start_frame"), truth.get("end_frame")
    processed = results.get("frames_processed")
    if (type(start) is not int or type(end) is not int or type(processed) is not int
            or not 1 <= start <= end <= processed):
        raise ValueError("El tramo revisado debe estar dentro de los frames procesados "
                         "(frames relativos a run.start_frame, del 1 a frames_processed)")
    if results.get("run", {}).get("status") != "completed":
        raise ValueError("La ejecución no está completada")
    all_pred = _event_rows(results.get("counting_events"), 1, processed, by_group)
    pred = [row for row in all_pred if start <= row["frame"] <= end]
    reference = _event_rows(truth.get("events"), start, end, by_group)
    missing_routes = sorted({row["route"] for row in reference} - {row["route"] for row in all_pred})
    groups = sorted({(row["route"], row["class"]) for row in pred + reference})
    matched_pred, matched_truth, matches = set(), set(), []
    for route, cls_name in groups:
        p = sorted((row for row in pred if (row["route"], row["class"]) == (route, cls_name)), key=lambda row: row["frame"])
        t = sorted((row for row in reference if (row["route"], row["class"]) == (route, cls_name)), key=lambda row: row["frame"])
        i = j = 0
        while i < len(p) and j < len(t):
            delta = p[i]["frame"] - t[j]["frame"]
            if abs(delta) <= tolerance_frames:
                matched_pred.add(p[i]["index"])
                matched_truth.add(t[j]["index"])
                matches.append(dict(pred_index=p[i]["index"], truth_index=t[j]["index"],
                                    route=route, **{"class": cls_name}, frame_delta=delta))
                i += 1
                j += 1
            elif delta < 0:
                i += 1
            else:
                j += 1
    unmatched_pred = [row for row in pred if row["index"] not in matched_pred]
    unmatched_truth = [row for row in reference if row["index"] not in matched_truth]
    metrics = compute_metrics(len(matches), len(unmatched_pred), len(unmatched_truth))
    return dict(metrics=metrics, matches=matches, unmatched_predictions=unmatched_pred,
                missed_events=unmatched_truth, start_frame=start, end_frame=end,
                tolerance_frames=tolerance_frames, by_group=by_group,
                routes_missing_in_results=missing_routes,
                scope=f"Emparejamiento temporal por ruta y {'grupo' if by_group else 'clase'}; "
                      "no comprueba identidad física del vehículo")


def main():
    parser = argparse.ArgumentParser(description="Valida conteo de rutas vs humano")
    parser.add_argument("--results", default="output/results.json",
                        help="results.json del pipeline")
    parser.add_argument("--truth", default="data/validation/route_truth.json",
                        help="conteo humano por ruta (JSON plano)")
    parser.add_argument("--output", default=None,
                        help="opcional: guarda el reporte a un JSON")
    parser.add_argument("--min-accuracy", type=float, default=None,
                        help="sale con codigo 1 si la accuracy ponderada por ruta es menor")
    parser.add_argument("--events", action="store_true", help="Compara eventos por ruta, clase y frame")
    parser.add_argument("--tolerance-frames", type=int, default=15)
    parser.add_argument("--by-group", action="store_true",
                        help="Con --events empareja por grupo EPS (ligeros/pesados/dos_ruedas) en vez de clase")
    parser.add_argument("--min-f1", type=float, help="Rechaza la validación de eventos bajo este F1")
    args = parser.parse_args()
    if args.min_accuracy is not None and not 0 <= args.min_accuracy <= 1:
        parser.error("--min-accuracy debe estar entre 0 y 1")
    if args.min_f1 is not None and (not args.events or not 0 <= args.min_f1 <= 1):
        parser.error("--min-f1 requiere --events y un valor entre 0 y 1")
    if args.events and args.min_accuracy is not None:
        parser.error("Con --events usa --min-f1")
    if args.by_group and not args.events:
        parser.error("--by-group requiere --events")

    if not Path(args.results).exists():
        print(f"ERROR: no existe {args.results}. Corre 'make run' primero.")
        sys.exit(1)
    if not Path(args.truth).exists():
        print(f"ERROR: no existe {args.truth}. Crea el conteo humano "
              f"(ver route_truth.example.json).")
        sys.exit(1)

    try:
        report = (validate_events(args.results, args.truth, args.tolerance_frames, args.by_group)
                  if args.events else validate(args.results, args.truth))
    except (ValueError, TypeError, AttributeError) as e:
        parser.error(str(e))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Reporte guardado en: {args.output}")

    if args.events:
        if report["routes_missing_in_results"]:
            print("AVISO: rutas de la referencia sin ningún evento del sistema: "
                  f"{report['routes_missing_in_results']}. Revisa que el nombre coincida con la salida "
                  "(por ejemplo 'Anillo oeste ↓', con sentido).", file=sys.stderr)
        print(json.dumps(report["metrics"], ensure_ascii=False))
        if args.min_f1 is not None:
            metrics = report["metrics"]
            denominator = 2 * metrics["tp"] + metrics["fp"] + metrics["fn"]
            f1 = 2 * metrics["tp"] / denominator if denominator else 0
            if metrics["tp"] + metrics["fn"] == 0 or f1 < args.min_f1:
                raise SystemExit(1)

    if args.min_accuracy is not None:
        totals = report["totals"]
        if not totals or totals["truth"] == 0:
            print("Sin autos de referencia no se puede validar la precision del conteo.")
            raise SystemExit(1)
        accuracy = max(0.0, 1.0 - totals["total_abs_error"] / totals["truth"])
        if accuracy < args.min_accuracy:
            print(f"Conteo rechazado: {accuracy:.3f} < {args.min_accuracy:.3f}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
