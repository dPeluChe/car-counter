"""Tests para carcounter/db.py.

Tests del fallback (sin libsql) corren siempre.
Tests del schema/CRUD corren solo cuando libsql_experimental esta instalado.
"""

import json
import importlib.util
import pytest

from carcounter import db


_LIBSQL_INSTALLED = importlib.util.find_spec("libsql_experimental") is not None
needs_libsql = pytest.mark.skipif(
    not _LIBSQL_INSTALLED,
    reason="libsql_experimental no instalado (dependencia opcional)"
)


# ──────────────────────────────────────────────────────────
# Tests que corren siempre (fallback sin libsql)
# ──────────────────────────────────────────────────────────

def test_libsql_available_flag_exists():
    assert hasattr(db, "LIBSQL_AVAILABLE")
    assert isinstance(db.LIBSQL_AVAILABLE, bool)


def test_db_path_is_defined():
    assert db.DB_PATH is not None
    assert str(db.DB_PATH).endswith(".db")


def test_save_run_returns_none_without_libsql(monkeypatch):
    monkeypatch.setattr(db, "LIBSQL_AVAILABLE", False)
    result = db.save_run(
        video_path="/test/video.mp4",
        config_path="/test/config.json",
        frames=100,
        duration=5.0,
        vehicles=10,
        routes_matrix={"A->B": 5},
    )
    assert result is None


def test_list_runs_returns_empty_without_libsql(monkeypatch):
    monkeypatch.setattr(db, "LIBSQL_AVAILABLE", False)
    assert db.list_runs() == []


def test_get_run_returns_none_without_libsql(monkeypatch):
    monkeypatch.setattr(db, "LIBSQL_AVAILABLE", False)
    assert db.get_run(1) is None


def test_init_db_returns_none_without_libsql(monkeypatch):
    monkeypatch.setattr(db, "LIBSQL_AVAILABLE", False)
    assert db.init_db() is None


# ──────────────────────────────────────────────────────────
# Tests que requieren libsql_experimental instalado
# ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    """Redirige DB_PATH a un archivo temporal por test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_file))
    yield str(db_file)


@needs_libsql
def test_init_db_creates_schema(tmp_db):
    conn = db.init_db()
    assert conn is not None
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {row[0] for row in tables}
    assert {"projects", "configs", "runs", "od_entries"}.issubset(names)


@needs_libsql
def test_save_run_returns_id(tmp_db):
    run_id = db.save_run(
        video_path="assets/glorieta_fast.MP4",
        config_path="config/config.json",
        frames=500,
        duration=25.5,
        vehicles=42,
        routes_matrix={"A->B": 20, "A->C": 22},
    )
    assert run_id is not None
    assert isinstance(run_id, int)
    assert run_id >= 1


@needs_libsql
def test_save_run_persists_od_matrix(tmp_db):
    run_id = db.save_run(
        video_path="v.mp4", config_path="c.json",
        frames=100, duration=5.0, vehicles=3,
        routes_matrix={},
        od_matrix={"A": {"B": 2, "C": 1}},
    )
    run = db.get_run(run_id)
    assert run["od_matrix"]["A"]["B"] == 2
    assert run["od_matrix"]["A"]["C"] == 1


@needs_libsql
def test_list_runs_most_recent_first(tmp_db):
    ids = []
    for i in range(3):
        rid = db.save_run(
            video_path=f"v{i}.mp4", config_path="c.json",
            frames=i * 10, duration=float(i), vehicles=i,
            routes_matrix={},
        )
        ids.append(rid)
    runs = db.list_runs()
    assert len(runs) == 3
    # Mas reciente primero (por created_at DESC)
    assert runs[0]["id"] == ids[-1]


@needs_libsql
def test_list_runs_respects_limit(tmp_db):
    for i in range(5):
        db.save_run(
            video_path="v.mp4", config_path="c.json",
            frames=i, duration=0.0, vehicles=0,
            routes_matrix={},
        )
    assert len(db.list_runs(limit=2)) == 2
    assert len(db.list_runs(limit=10)) == 5


@needs_libsql
def test_get_run_missing_returns_none(tmp_db):
    db.init_db()
    assert db.get_run(9999) is None


@needs_libsql
def test_save_run_stores_routes_as_json(tmp_db):
    rm = {"A->B": 5, "B->C": 7}
    rid = db.save_run(
        video_path="v.mp4", config_path="c.json",
        frames=100, duration=5.0, vehicles=12,
        routes_matrix=rm,
    )
    run = db.get_run(rid)
    parsed = json.loads(run["routes_json"])
    assert parsed == rm
