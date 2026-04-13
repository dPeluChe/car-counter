"""Tests para carcounter/engine.py — ProcessingEngine."""

import pytest
import numpy as np
from carcounter.engine import ProcessingEngine, EngineState
from carcounter.counting import VehicleCounter


class TestEngineState:
    def test_initial_state(self):
        zones_np = {
            "A": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32),
            "B": np.array([[300, 0], [400, 0], [400, 100], [300, 100]], dtype=np.int32),
        }
        counter = VehicleCounter(zones_np=zones_np, counting_lines=[])

        engine = ProcessingEngine(
            video_path="nonexistent.mp4",
            detect_fn=lambda f: [],
            counter=counter,
            zones_np=zones_np,
            exclusion_np={},
            counting_lines=[],
            headless=True,
        )
        assert engine.state == EngineState.IDLE
        assert engine.frame_count == 0


class TestEngineCallbacks:
    def test_callback_registration(self):
        zones_np = {
            "A": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32),
        }
        counter = VehicleCounter(zones_np=zones_np, counting_lines=[])

        engine = ProcessingEngine(
            video_path="test.mp4",
            detect_fn=lambda f: [],
            counter=counter,
            zones_np=zones_np,
            exclusion_np={},
            counting_lines=[],
            headless=True,
        )

        events = []
        engine.on("state_changed", lambda **kw: events.append(kw))

        # Simulate state changes
        engine._set_state(EngineState.RUNNING)
        engine._set_state(EngineState.PAUSED)
        engine._set_state(EngineState.STOPPED)

        assert len(events) == 3
        assert events[0]["old_state"] == EngineState.IDLE
        assert events[0]["new_state"] == EngineState.RUNNING
        assert events[1]["new_state"] == EngineState.PAUSED
        assert events[2]["new_state"] == EngineState.STOPPED

    def test_callback_off(self):
        zones_np = {"A": np.array([[0, 0], [100, 0], [100, 100]], dtype=np.int32)}
        counter = VehicleCounter(zones_np=zones_np, counting_lines=[])
        engine = ProcessingEngine(
            video_path="test.mp4", detect_fn=lambda f: [],
            counter=counter, zones_np=zones_np, exclusion_np={},
            counting_lines=[], headless=True,
        )

        events = []
        cb = lambda **kw: events.append(1)
        engine.on("state_changed", cb)
        engine._set_state(EngineState.RUNNING)
        assert len(events) == 1

        engine.off("state_changed", cb)
        engine._set_state(EngineState.PAUSED)
        assert len(events) == 1  # callback removed, not fired


class TestEnginePauseResume:
    def test_pause_resume(self):
        zones_np = {"A": np.array([[0, 0], [100, 0], [100, 100]], dtype=np.int32)}
        counter = VehicleCounter(zones_np=zones_np, counting_lines=[])
        engine = ProcessingEngine(
            video_path="test.mp4", detect_fn=lambda f: [],
            counter=counter, zones_np=zones_np, exclusion_np={},
            counting_lines=[], headless=True,
        )

        engine._set_state(EngineState.RUNNING)
        engine.pause()
        assert engine.state == EngineState.PAUSED

        engine.resume()
        assert engine.state == EngineState.RUNNING

        engine.stop()
        assert engine.state == EngineState.STOPPED

    def test_pause_when_not_running(self):
        zones_np = {"A": np.array([[0, 0], [100, 0], [100, 100]], dtype=np.int32)}
        counter = VehicleCounter(zones_np=zones_np, counting_lines=[])
        engine = ProcessingEngine(
            video_path="test.mp4", detect_fn=lambda f: [],
            counter=counter, zones_np=zones_np, exclusion_np={},
            counting_lines=[], headless=True,
        )
        engine.pause()  # Should be a no-op
        assert engine.state == EngineState.IDLE
