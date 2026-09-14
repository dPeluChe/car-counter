"""Grupos de clase acordados con EPS: ligeros, pesados y dos_ruedas."""

import json

import numpy as np
import pytest

from carcounter.constants import CLASS_GROUPS, VEHICLE_CLASSES, class_group
from carcounter.counting import VehicleCounter
from carcounter.export import routes_by_group


@pytest.mark.parametrize("name,group", [
    ("car", "ligeros"), ("van", "ligeros"), ("tricycle", "ligeros"), ("awning-tricycle", "ligeros"),
    ("bus", "pesados"), ("truck", "pesados"),
    ("motor", "dos_ruedas"), ("motorbike", "dos_ruedas"), ("motorcycle", "dos_ruedas"),
    ("bicycle", "dos_ruedas"), (" Car ", "ligeros"), ("pedestrian", None),
])
def test_class_group_mapping(name, group):
    assert class_group(name) == group


def test_every_grouped_class_passes_the_vehicle_filter():
    grouped = set().union(*CLASS_GROUPS.values())
    assert grouped == VEHICLE_CLASSES


def test_counting_events_carry_group_and_export_by_route():
    zones = {
        "A": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32),
        "B": np.array([[300, 0], [400, 0], [400, 100], [300, 100]], dtype=np.int32),
    }
    counter = VehicleCounter(zones, [], min_origin_frames=1, min_dest_frames=1)
    for trk_id, cls_name in ((1, "van"), (2, "bus"), (3, "motor")):
        for frame, x in enumerate((50, 350), start=1):
            counter.set_frame(frame)
            counter.update(trk_id, x, 50, cls_name, "zones")
    assert [event["group"] for event in counter.counting_events] == ["ligeros", "pesados", "dos_ruedas"]
    assert routes_by_group(counter.counting_events) == {"A → B": {"ligeros": 1, "pesados": 1, "dos_ruedas": 1}}


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def test_event_validation_by_group_matches_van_against_human_car(tmp_path):
    from scripts.validate_routes import validate_events
    sha = "a" * 64
    results = _write(tmp_path, "results.json", {
        "frames_processed": 100, "run": {"status": "completed", "video_sha256": sha},
        "counting_events": [{"frame": 10, "route": "A -> B", "class": "van"}]})
    truth = _write(tmp_path, "truth.json", {
        "reviewed": True, "video_sha256": sha, "start_frame": 1, "end_frame": 100,
        "events": [{"frame": 12, "route": "A -> B", "class": "ligeros"}]})
    by_class = validate_events(results, truth)["metrics"]
    by_group = validate_events(results, truth, by_group=True)["metrics"]
    assert (by_class["tp"], by_class["fp"], by_class["fn"]) == (0, 1, 1)
    assert (by_group["tp"], by_group["fp"], by_group["fn"]) == (1, 0, 0)
