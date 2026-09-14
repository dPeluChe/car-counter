"""libSQL database module for local run history."""

import json
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import libsql_experimental as libsql
    LIBSQL_AVAILABLE = True
except ImportError:
    LIBSQL_AVAILABLE = False

from carcounter.paths import paths
from carcounter.logging_config import get_logger

log = get_logger("db")

DB_PATH = os.path.join(paths.data_dir, "carcounter.db")


def init_db():
    """Initialize the database and create tables if they don't exist."""
    if not LIBSQL_AVAILABLE:
        log.warning("libsql-experimental not installed. Using JSON fallback.")
        return None
    
    os.makedirs(paths.data_dir, exist_ok=True)
    conn = libsql.connect(DB_PATH)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            video_path TEXT,
            model_path TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            json_blob TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER,
            frames INTEGER,
            duration REAL,
            vehicles INTEGER,
            routes_json TEXT,
            events_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (config_id) REFERENCES configs(id)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS od_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            origin TEXT,
            destination TEXT,
            count INTEGER,
            vehicle_class TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )
    """)
    
    conn.commit()
    log.info("Database initialized at %s", DB_PATH)
    return conn


def _add_events_column(conn):
    # DBs creadas antes de counting_events no tienen la columna; el ALTER falla si ya existe
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN events_json TEXT")
        conn.commit()
    except Exception:
        pass


def _get_conn():
    """Get or create database connection."""
    if not LIBSQL_AVAILABLE:
        return None

    if not os.path.exists(DB_PATH):
        return init_db()

    conn = libsql.connect(DB_PATH)
    _add_events_column(conn)
    return conn


def save_run(video_path: str, config_path: str, frames: int, duration: float,
             vehicles: int, routes_matrix: Dict[str, int], 
             od_matrix: Optional[Dict] = None,
             counting_events: Optional[List[Dict]] = None) -> Optional[int]:
    """Save a run to the database.

    Returns the run_id if successful, None otherwise.
    """
    if not LIBSQL_AVAILABLE:
        log.warning("libsql-experimental not installed. Run not saved to DB.")
        return None
    
    conn = _get_conn()
    if conn is None:
        return None
    
    try:
        now = datetime.now().isoformat()
        
        conn.execute(
            "INSERT INTO runs (config_id, frames, duration, vehicles, routes_json, events_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (None, frames, duration, vehicles, json.dumps(routes_matrix),
             json.dumps(counting_events or []), now)
        )
        
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        if od_matrix:
            for origin, dests in od_matrix.items():
                if isinstance(dests, dict):
                    for dest, count in dests.items():
                        conn.execute(
                            "INSERT INTO od_entries (run_id, origin, destination, count, vehicle_class) VALUES (?, ?, ?, ?, ?)",
                            (run_id, origin, dest, count, "")
                        )
        
        conn.commit()
        log.info("Run saved to DB: run_id=%d", run_id)
        return run_id
        
    except Exception as e:
        log.error("Error saving run to DB: %s", e)
        return None


def list_runs(limit: int = 10) -> List[Dict[str, Any]]:
    """List recent runs from the database."""
    if not LIBSQL_AVAILABLE:
        log.warning("libsql-experimental not installed. Cannot list runs.")
        return []
    
    conn = _get_conn()
    if conn is None:
        return []
    
    try:
        rows = conn.execute(
            "SELECT id, frames, duration, vehicles, routes_json, created_at FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        
        runs = []
        for row in rows:
            runs.append({
                "id": row[0],
                "frames": row[1],
                "duration": row[2],
                "vehicles": row[3],
                "routes_json": row[4],
                "created_at": row[5],
            })
        return runs
        
    except Exception as e:
        log.error("Error listing runs: %s", e)
        return []


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific run by ID."""
    if not LIBSQL_AVAILABLE:
        return None
    
    conn = _get_conn()
    if conn is None:
        return None
    
    try:
        row = conn.execute(
            "SELECT id, frames, duration, vehicles, routes_json, created_at, events_json FROM runs WHERE id = ?",
            (run_id,)
        ).fetchone()
        
        if row is None:
            return None
        
        od_rows = conn.execute(
            "SELECT origin, destination, count, vehicle_class FROM od_entries WHERE run_id = ?",
            (run_id,)
        ).fetchall()
        
        od_matrix = {}
        for od_row in od_rows:
            origin, dest, count, cls = od_row
            if origin not in od_matrix:
                od_matrix[origin] = {}
            od_matrix[origin][dest] = count
        
        return {
            "id": row[0],
            "frames": row[1],
            "duration": row[2],
            "vehicles": row[3],
            "routes_json": row[4],
            "created_at": row[5],
            "od_matrix": od_matrix,
            "counting_events": json.loads(row[6] or "[]"),
        }
        
    except Exception as e:
        log.error("Error getting run: %s", e)
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "list"])
    args = parser.parse_args()
    
    if args.command == "init":
        init_db()
    elif args.command == "list":
        runs = list_runs()
        print(f"Recent runs ({len(runs)}):")
        for run in runs:
            print(f"  ID={run['id']} | {run['created_at']} | {run['vehicles']} vehicles | {run['frames']} frames")