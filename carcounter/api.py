"""FastAPI REST API for Car Counter.

Provides read-only endpoints to query run data and MJPEG stream.
"""

import io
import threading
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import StreamingResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = HTTPException = StreamingResponse = None

import cv2
import numpy as np
from carcounter.logging_config import get_logger
from carcounter import db

log = get_logger("api")

_current_counter: Optional[Any] = None
_current_run_meta: dict = {}
_current_frame: Optional[np.ndarray] = None
_frame_lock = threading.Lock()
_counter_lock = threading.Lock()

app = None


def _get_app():
    """Lazy-load the FastAPI app."""
    global app
    if app is None and FASTAPI_AVAILABLE:
        from fastapi import FastAPI as _FastAPI
        from fastapi import HTTPException as _HTTPException
        from fastapi.responses import StreamingResponse as _StreamingResponse
        
        app = _FastAPI(title="Car Counter API", version="1.0.0")
        
        @app.get("/api/stats")
        def get_stats():
            with _counter_lock:
                if _current_counter is None:
                    raise _HTTPException(status_code=503, detail="No processing running")
                counter = _current_counter
                meta = dict(_current_run_meta)

            events = list(getattr(counter, "counting_events", []))
            stats = {
                "frame_count": meta.get("frame_count", 0),
                "total_frames": meta.get("total_frames", 0),
                "fps_avg": round(meta.get("fps_avg", 0.0), 2),
                "routes_matrix": dict(counter.routes_matrix),
                "total_vehicles": counter.total_vehicles_ever,
                "events_count": len(events),
                "recent_events": events[-20:],
                "elapsed_time": round(time.time() - meta["start_time"], 1) if "start_time" in meta else 0,
            }
            return stats

        @app.get("/api/runs")
        def list_runs(limit: int = 10):
            runs = db.list_runs(limit=limit)
            return {"runs": runs, "count": len(runs)}

        @app.get("/api/runs/{run_id}")
        def get_run(run_id: int):
            run = db.get_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Run not found")
            return run

        def generate_mjpeg_frame():
            global _current_frame
            while True:
                with _frame_lock:
                    if _current_frame is None:
                        time.sleep(0.1)
                        continue
                    frame = _current_frame.copy()
                
                ret, jpeg = cv2.imencode('.jpg', frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.033)

        @app.get("/api/stream")
        def stream():
            if not FASTAPI_AVAILABLE:
                raise HTTPException(status_code=503, detail="FastAPI not installed")
            return StreamingResponse(
                generate_mjpeg_frame(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )

        @app.get("/api/health")
        def health():
            return {
                "status": "ok",
                "fastapi_available": FASTAPI_AVAILABLE,
                "processing_running": _current_counter is not None,
            }
    
    return app


def set_current_engine(counter, meta: dict = None):
    """Set the current VehicleCounter and run metadata for API access.

    Args:
        counter: VehicleCounter instance
        meta: dict with keys frame_count, total_frames, fps_avg, start_time
    """
    global _current_counter, _current_run_meta
    with _counter_lock:
        _current_counter = counter
        _current_run_meta = meta or {}


def set_current_frame(frame: np.ndarray):
    """Update the current frame for MJPEG streaming."""
    global _current_frame
    with _frame_lock:
        _current_frame = frame.copy()


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    if not FASTAPI_AVAILABLE:
        log.error("FastAPI not installed. Install with: pip install fastapi uvicorn")
        return
    
    _app = _get_app()
    if _app is None:
        return
    
    import uvicorn
    log.info("Starting Car Counter API on http://%s:%d", host, port)
    uvicorn.run(_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()