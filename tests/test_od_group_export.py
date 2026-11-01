import csv
import json

import numpy as np

from carcounter.counting import VehicleCounter
from carcounter.export import (
    OD_GROUP_FIELDS, export_json, export_od_by_group_csv, export_od_matrix_csv, routes_by_group,
)
from main import build_parser


def zone(x1, x2):
    return np.array([[x1, 0], [x2, 0], [x2, 100], [x1, 100]], dtype=np.int32)


def counted_events():
    roles = {"A": {"role": "entry", "access": "Norte"}, "B": {"role": "exit", "access": "Sur"},
             "C": {"role": "exit", "access": "Este"}}
    counter = VehicleCounter({"A": zone(0, 100), "B": zone(300, 400), "C": zone(600, 700)}, [],
                             min_origin_frames=1, min_dest_frames=1, zone_roles=roles)
    for trk_id, cls_name, end_x in ((1, "car", 350), (2, "van", 350), (3, "bus", 650), (4, "motor", 350)):
        for frame, x in enumerate((50, end_x), start=1):
            counter.set_frame(frame)
            counter.update(trk_id, x, 50, cls_name, "zones")
    return counter


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_od_by_group_csv_matches_events_and_json(tmp_path):
    counter = counted_events()
    csv_path = tmp_path / "od_by_group.csv"
    export_od_by_group_csv(csv_path, counter.counting_events)
    rows = read_rows(csv_path)
    assert rows[0] == OD_GROUP_FIELDS
    assert rows[1:] == [["Norte", "Este", "pesados", "1"], ["Norte", "Sur", "dos_ruedas", "1"],
                        ["Norte", "Sur", "ligeros", "2"]]

    json_path = tmp_path / "results.json"
    export_json(json_path, video_path="v", config_path="c", use_sahi=False, tracker_backend="t",
                counting_mode="zones", frame_count=2, total_frames=2, duration=1, total_time=1,
                avg_fps=2, total_vehicles=4, routes_matrix=counter.routes_matrix, zone_names=["A"],
                counting_events=counter.counting_events)
    by_group = json.loads(json_path.read_text(encoding="utf-8"))["routes_by_group"]
    from_csv = {}
    for origin, destination, group, count in rows[1:]:
        from_csv.setdefault(f"{origin} → {destination}", {})[group] = int(count)
    assert from_csv == by_group == routes_by_group(counter.counting_events)


def test_od_by_group_csv_totals_match_od_matrix(tmp_path):
    counter = counted_events()
    group_path, matrix_path = tmp_path / "g.csv", tmp_path / "m.csv"
    export_od_by_group_csv(group_path, counter.counting_events)
    export_od_matrix_csv(matrix_path, counter.od_matrix)
    totals = {}
    for origin, destination, _, count in read_rows(group_path)[1:]:
        totals[(origin, destination)] = totals.get((origin, destination), 0) + int(count)
    matrix = read_rows(matrix_path)
    columns = matrix[0][1:]
    from_matrix = {(row[0], column): int(value) for row in matrix[1:]
                   for column, value in zip(columns, row[1:]) if int(value)}
    assert totals == from_matrix


def test_od_by_group_csv_ignores_line_events_and_writes_header(tmp_path):
    path = tmp_path / "empty.csv"
    export_od_by_group_csv(path, [{"mode": "line", "route": "L", "group": "ligeros",
                                   "origin": None, "destination": None}])
    assert read_rows(path) == [OD_GROUP_FIELDS]


def test_cli_exposes_od_group_flag():
    assert build_parser().parse_args(["--output-od-group-csv", "x.csv"]).output_od_group_csv == "x.csv"
