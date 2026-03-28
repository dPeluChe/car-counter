"""Export de resultados: resumen, JSON, CSV, benchmark."""

import csv
import json
import os
from carcounter.drawing import format_time


def print_summary(*, video_path, config_path, use_sahi, tracker_backend,
                  frame_count, total_frames, total_time, avg_fps,
                  zone_names, total_vehicles, routes_matrix):
    """Imprime resumen final en consola."""
    print("\n" + "=" * 65)
    print("RESUMEN — Car Counter")
    print("=" * 65)
    print(f"Video:   {video_path}")
    print(f"Config:  {config_path}")
    print(f"Modo:    {'SAHI' if use_sahi else 'YOLO estandar'}")
    print(f"Tracker: {tracker_backend}")
    print(f"\nRenderizado:")
    print(f"  Frames procesados: {frame_count}/{total_frames}")
    print(f"  Tiempo total:      {format_time(total_time)}")
    print(f"  FPS promedio:      {avg_fps:.2f}")
    print(f"\nZonas configuradas: {', '.join(zone_names) if zone_names else 'N/A'}")
    print(f"Vehiculos rastreados: {total_vehicles}")
    print(f"Rutas completadas:   {sum(routes_matrix.values())}")

    if routes_matrix:
        print("\nMatriz de Rutas:")
        sorted_routes = sorted(routes_matrix.items(), key=lambda x: -x[1])
        total_routes = sum(routes_matrix.values())
        for route, count in sorted_routes:
            pct = count / total_routes * 100
            bar = "#" * int(pct / 5)
            print(f"  {route:<30} {count:>4}  ({pct:5.1f}%)  {bar}")
    else:
        print("\nNo se completaron rutas. Verifica:")
        print("   1. Las zonas cubren correctamente las bocacalles")
        print("   2. El video tiene suficiente duracion")
        print("   3. El conf_threshold no es demasiado alto")


def export_json(path, *, video_path, config_path, use_sahi, tracker_backend,
                counting_mode, frame_count, total_frames, duration,
                total_time, avg_fps, total_vehicles, routes_matrix, zone_names):
    """Guarda resultados en JSON."""
    data = {
        "video": video_path,
        "config": config_path,
        "mode": "SAHI" if use_sahi else "YOLO",
        "tracker": tracker_backend,
        "counting_mode": counting_mode,
        "frames_processed": frame_count,
        "total_frames": total_frames,
        "duration_seconds": round(duration, 2),
        "processing_time_seconds": round(total_time, 2),
        "fps_avg": round(avg_fps, 2),
        "total_vehicles_tracked": total_vehicles,
        "total_routes_completed": sum(routes_matrix.values()),
        "routes": dict(sorted(routes_matrix.items(), key=lambda x: -x[1])),
        "zones": zone_names,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nResultados JSON: {path}")


def export_csv(path, routes_matrix):
    """Guarda rutas en CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ruta", "conteo", "porcentaje"])
        total = sum(routes_matrix.values())
        for route, count in sorted(routes_matrix.items(), key=lambda x: -x[1]):
            pct = count / total * 100 if total > 0 else 0
            w.writerow([route, count, f"{pct:.1f}"])
    print(f"Resultados CSV: {path}")


def export_tracks_csv(path, track_data):
    """Guarda datos per-track en CSV (trayectorias, clase, estado)."""
    if not track_data:
        return
    fields = ["track_id", "class", "state", "origin", "direction",
              "first_x", "first_y", "last_x", "last_y", "trail_length", "last_seen_frame",
              "avg_width", "avg_height", "avg_area", "avg_aspect", "avg_elongation"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in sorted(track_data, key=lambda r: r["track_id"]):
            w.writerow(row)
    print(f"Tracks CSV: {path}")


def export_od_matrix_csv(path, od_matrix):
    """Guarda OD matrix nested como CSV. Solo aplica en modo zones."""
    if not od_matrix:
        print("OD Matrix: vacia (solo se genera en modo zones)")
        return
    all_zones = set()
    for origin, dests in od_matrix.items():
        all_zones.add(origin)
        all_zones.update(dests.keys())
    zones = sorted(all_zones)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["origen\\destino"] + zones)
        for origin in zones:
            row = [origin]
            for dest in zones:
                row.append(od_matrix.get(origin, {}).get(dest, 0))
            w.writerow(row)
    print(f"OD Matrix CSV: {path}")


def export_benchmark(benchmarks_dir, *, video_path, config_path, use_sahi,
                     total_time, avg_fps, routes_matrix, benchmark_data):
    """Guarda metricas de rendimiento."""
    os.makedirs(benchmarks_dir, exist_ok=True)
    path = os.path.join(benchmarks_dir, "benchmark_results.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Car Counter Benchmark\n" + "=" * 50 + "\n")
        f.write(f"Video: {video_path}\nConfig: {config_path}\nSAHI: {use_sahi}\n")
        f.write(f"Tiempo total: {format_time(total_time)}\nFPS promedio: {avg_fps:.2f}\n")
        f.write(f"Rutas totales: {sum(routes_matrix.values())}\n\nRutas:\n")
        for route, count in sorted(routes_matrix.items(), key=lambda x: -x[1]):
            f.write(f"  {route}: {count}\n")
        f.write(f"\n{'Frame':<10}{'Elapsed':<12}{'FPS':<8}{'Det':<8}{'Tracks':<8}{'Routes':<8}\n")
        f.write("-" * 50 + "\n")
        for d in benchmark_data:
            f.write(f"{d['frame']:<10}{d['elapsed']:<12.2f}{d['fps']:<8.2f}"
                    f"{d['detections']:<8}{d['tracks']:<8}{d['routes']:<8}\n")
    print(f"\nBenchmark: {path}")
