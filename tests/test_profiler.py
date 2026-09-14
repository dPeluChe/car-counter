"""Tests para carcounter/profiler.py."""

import time
import pytest

from carcounter.profiler import Profiler


def test_profiler_has_expected_stages():
    p = Profiler()
    assert p.stages == ["detection", "counting", "visualization", "writing"]
    assert "tracking" not in p.stages


def test_profiler_empty_averages_are_zero():
    p = Profiler()
    avgs = p.get_averages()
    assert all(v == 0 for v in avgs.values())
    assert set(avgs.keys()) == set(p.stages)


def test_profiler_single_stage_timing():
    p = Profiler()
    p.start("detection")
    time.sleep(0.01)
    p.end("detection")
    avgs = p.get_averages()
    assert avgs["detection"] >= 0.01
    assert avgs["counting"] == 0


def test_profiler_accumulates_multiple_samples():
    p = Profiler()
    for _ in range(3):
        p.start("counting")
        time.sleep(0.005)
        p.end("counting")
    assert len(p.stats["counting"]) == 3
    assert p.get_averages()["counting"] >= 0.005


def test_profiler_end_without_start_is_noop():
    p = Profiler()
    p.end("detection")
    assert p.stats["detection"] == []


def test_profiler_multiple_stages_independent():
    p = Profiler()
    p.start("detection")
    p.start("counting")
    time.sleep(0.01)
    p.end("detection")
    p.end("counting")
    avgs = p.get_averages()
    assert avgs["detection"] > 0
    assert avgs["counting"] > 0


def test_profiler_start_clears_previous_start_time():
    """Segundo start() sin end() sobrescribe el start_time, previniendo leak."""
    p = Profiler()
    p.start("detection")
    time.sleep(0.02)
    p.start("detection")
    time.sleep(0.005)
    p.end("detection")
    avgs = p.get_averages()
    # Debe reflejar solo el segundo start, no la suma
    assert avgs["detection"] < 0.015


def test_benchmark_uses_latest_cumulative_average_and_frame_count(tmp_path):
    from carcounter.export import export_benchmark
    export_benchmark(
        str(tmp_path), video_path="test.mp4", config_path="config.json",
        use_sahi=False, total_time=120.0, avg_fps=1.0, routes_matrix={},
        benchmark_data=[
            {"frame": 60, "elapsed": 60, "fps": 1, "detections": 1,
             "tracks": 1, "routes": 0, "stages": {"detection": 0.5}},
            {"frame": 120, "elapsed": 120, "fps": 1, "detections": 1,
             "tracks": 1, "routes": 0, "stages": {"detection": 0.9}},
        ],
    )
    report = (tmp_path / "benchmark_results.txt").read_text()
    detection = next(line for line in report.splitlines() if line.strip().startswith("detection"))
    assert "900.00 ms" in detection
    assert "90.0%" in detection
    assert "tracking" not in report
