"""Tests para carcounter/api.py.

Los tests basicos de fallback corren siempre.
Los tests que golpean endpoints reales requieren fastapi + httpx.
"""

import importlib.util
import pytest

from carcounter import api
from carcounter import db


_FASTAPI_INSTALLED = (
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None
)
needs_fastapi = pytest.mark.skipif(
    not _FASTAPI_INSTALLED,
    reason="fastapi/httpx no instalados (dependencias opcionales)"
)


# ──────────────────────────────────────────────────────────
# Tests que corren siempre
# ──────────────────────────────────────────────────────────

def test_fastapi_available_flag_exists():
    assert hasattr(api, "FASTAPI_AVAILABLE")
    assert isinstance(api.FASTAPI_AVAILABLE, bool)


def test_run_server_noop_when_fastapi_absent(monkeypatch):
    monkeypatch.setattr(api, "FASTAPI_AVAILABLE", False)
    # Debe retornar sin lanzar, no intenta levantar server
    api.run_server(port=0)


def test_set_current_engine_stores_counter_and_meta():
    class Dummy:
        routes_matrix = {}
        total_vehicles_ever = 0

    d = Dummy()
    meta = {"frame_count": 5, "total_frames": 100, "fps_avg": 12.3, "start_time": 0.0}
    api.set_current_engine(d, meta)
    assert api._current_counter is d
    assert api._current_run_meta == meta
    # Cleanup
    api.set_current_engine(None, {})


def test_set_current_frame_copies_frame():
    import numpy as np
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    api.set_current_frame(frame)
    assert api._current_frame is not frame  # debe ser copia
    assert api._current_frame.shape == frame.shape


# ──────────────────────────────────────────────────────────
# Tests de endpoints reales (requieren fastapi + httpx)
# ──────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """TestClient con app fresca y estado limpio entre tests."""
    from fastapi.testclient import TestClient
    api.app = None
    api._current_counter = None
    api._current_run_meta = {}
    api._current_frame = None
    app_instance = api._get_app()
    assert app_instance is not None
    with TestClient(app_instance) as c:
        yield c
    api.app = None
    api._current_counter = None
    api._current_run_meta = {}
    api._current_frame = None


@needs_fastapi
def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["fastapi_available"] is True
    assert data["processing_running"] is False


@needs_fastapi
def test_stats_returns_503_when_no_processing(client):
    r = client.get("/api/stats")
    assert r.status_code == 503


@needs_fastapi
def test_stats_returns_counter_data_when_processing(client):
    class Dummy:
        routes_matrix = {"A->B": 5, "A->C": 3}
        total_vehicles_ever = 8

    meta = {"frame_count": 42, "total_frames": 1000, "fps_avg": 15.5, "start_time": 0.0}
    api.set_current_engine(Dummy(), meta)

    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["frame_count"] == 42
    assert data["total_frames"] == 1000
    assert data["fps_avg"] == 15.5
    assert data["total_vehicles"] == 8
    assert data["routes_matrix"] == {"A->B": 5, "A->C": 3}


@needs_fastapi
def test_health_shows_processing_running_after_set_engine(client):
    class Dummy:
        routes_matrix = {}
        total_vehicles_ever = 0

    api.set_current_engine(Dummy(), {})
    r = client.get("/api/health")
    assert r.json()["processing_running"] is True


@needs_fastapi
def test_runs_endpoint_returns_list(client, monkeypatch):
    monkeypatch.setattr(db, "list_runs", lambda limit=10: [
        {"id": 1, "frames": 100, "duration": 5.0, "vehicles": 10,
         "routes_json": "{}", "created_at": "2026-04-22T10:00:00"},
    ])
    r = client.get("/api/runs")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["runs"][0]["id"] == 1


@needs_fastapi
def test_runs_endpoint_respects_limit_param(client, monkeypatch):
    seen_limits = []

    def fake_list(limit=10):
        seen_limits.append(limit)
        return []

    monkeypatch.setattr(db, "list_runs", fake_list)
    client.get("/api/runs?limit=3")
    assert seen_limits == [3]


@needs_fastapi
def test_run_detail_returns_404_when_missing(client, monkeypatch):
    monkeypatch.setattr(db, "get_run", lambda run_id: None)
    r = client.get("/api/runs/999")
    assert r.status_code == 404


@needs_fastapi
def test_run_detail_returns_data_when_found(client, monkeypatch):
    monkeypatch.setattr(db, "get_run", lambda run_id: {
        "id": run_id, "frames": 500, "duration": 25.0, "vehicles": 42,
        "routes_json": '{"A->B": 20}', "created_at": "2026-04-22T10:00:00",
        "od_matrix": {"A": {"B": 20}},
    })
    r = client.get("/api/runs/1")
    assert r.status_code == 200
    data = r.json()
    assert data["vehicles"] == 42
    assert data["od_matrix"]["A"]["B"] == 20
