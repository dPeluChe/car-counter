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
