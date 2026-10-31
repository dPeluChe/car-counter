from types import SimpleNamespace

import numpy as np

from carcounter.detector import detection_rejection, filter_detections
from carcounter.wizard_actions import profile_rows
from setup_panels.calib_tests import infer_with_params


def test_diagnostics_and_runtime_share_every_rejection_reason():
    raw = [
        dict(bbox=(0, 0, 10, 10), conf=0.9, cls_name="car"),
        dict(bbox=(0, 0, 10, 10), conf=0.9, cls_name="person"),
        dict(bbox=(0, 0, 10, 10), conf=0.1, cls_name="car"),
        dict(bbox=(0, 0, 30, 30), conf=0.9, cls_name="bus"),
        dict(bbox=(50, 50, 60, 60), conf=0.9, cls_name="van"),
    ]
    geometry = {"max_area": 500}
    excluded = {"parking": np.array([[45, 45], [65, 45], [65, 65], [45, 65]])}
    reasons = [detection_rejection(d, lambda _: 0.2, geometry, excluded) for d in raw]
    assert reasons == [None, "clase", "confianza", "tamaño", "exclusión"]
    rows, classes = filter_detections(raw, lambda _: 0.2, geometry, excluded)
    assert rows.tolist() == [[0, 0, 10, 10, 0.9]]
    assert classes == ["car"]


def test_diagnostic_inference_retains_rejected_boxes(monkeypatch):
    from carcounter.runtime import resolve_runtime_config
    raw = [dict(bbox=(1, 2, 3, 4), conf=0.9, cls_name="car")]
    monkeypatch.setattr("setup_panels.calib_tests.detect_objects", lambda *a, **kw: raw)
    cfg = resolve_runtime_config({"settings": {"min_area": 20}},
                                SimpleNamespace(detector="yolo", video=None, model=None, imgsz=None))
    params = dict(cfg=cfg, model=None, sahi_model=None, use_sahi=False, predict_fn=None, exclusion_np={})
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert infer_with_params(frame, params) == []
    diagnostic = infer_with_params(frame, params, diagnostics=True)
    assert diagnostic == [dict(raw[0], rejection="tamaño")]
    assert "rejection" not in raw[0]


def test_summary_distinguishes_disabled_monitor_and_unbound_geometry():
    rows = dict(profile_rows({"settings": {}}))
    assert rows["SAHI"] == "Desactivado"
    assert rows["Cámara"] == "Monitor desactivado"
    assert "Sin referencia" in rows["Referencia"]
    assert "1600" in rows["Detección"]
    rows = dict(profile_rows({"geometry_reference": {"frame_index": 42},
                              "settings": {"camera_max_drift_px": 5, "imgsz": 640},
                              "sahi": {"enabled": True, "slice_width": 256}}))
    assert "42" in rows["Referencia"]
    assert "256" in rows["SAHI"]
    assert "640" in rows["Detección"]
