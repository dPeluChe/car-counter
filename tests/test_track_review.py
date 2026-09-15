import json

import cv2
import numpy as np
import pytest

from carcounter.counting import VehicleCounter
from carcounter.export import export_tracks_csv
from carcounter.track_review import (
    find_id_switch_candidates, find_incomplete, fragmentation, load_tracks, summarize_by_origin,
)


def track(track_id, state, origin="", confirmed=False, cls="car", first=1, last=10,
          first_xy=(10, 10), last_xy=(50, 50)):
    def box(x, y):
        return f"{x - 10} {y - 6} {x + 10} {y + 6}"
    return dict(track_id=track_id, state=state, origin=origin, origin_confirmed=confirmed, **{"class": cls},
                class_votes=f"{cls}:3", first_seen_frame=first, last_seen_frame=last,
                observed_frames=last - first + 1, first_x=first_xy[0], first_y=first_xy[1],
                last_x=last_xy[0], last_y=last_xy[1], first_bbox=box(*first_xy), last_bbox=box(*last_xy),
                avg_width=20.0, avg_height=12.0)


@pytest.fixture
def tracks_csv(tmp_path):
    rows = [
        track(1, "done", "Norte", True, first=1, last=40),
        track(2, "transit", "Norte", True, first=5, last=60, last_xy=(100, 100)),
        track(3, "origin", "Sur", True, cls="bus", first=80, last=99),
        track(4, "new", cls="van", first=62, last=90, first_xy=(110, 104)),
        track(5, "new", cls="motor", first=63, last=90, first_xy=(102, 101)),
        track(6, "origin", "Este", False, first=30, last=31),
    ]
    path = tmp_path / "tracks.csv"
    export_tracks_csv(str(path), rows)
    return path


def test_counter_exports_boxes_confirmation_and_votes():
    zones = {"A": np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.int32)}
    counter = VehicleCounter(zones, [], min_origin_frames=2)
    for frame, cls_name in ((1, "car"), (2, "van"), (3, "car")):
        counter.set_frame(frame)
        counter.update(7, 50, 50, cls_name, "zones", bbox=(40 + frame, 44, 60, 56))
    row = counter.get_track_data()[0]
    assert row["first_bbox"] == "41 44 60 56" and row["last_bbox"] == "43 44 60 56"
    assert row["origin_confirmed"] is True and row["class_votes"] == "car:2 van:1"


def test_load_tracks_types_numbers_boxes_and_group(tracks_csv):
    tracks = load_tracks(tracks_csv)
    assert tracks[0]["track_id"] == 1 and tracks[0]["first_x"] == 10.0
    assert tracks[1]["last_bbox"] == (90.0, 94.0, 110.0, 106.0)
    assert tracks[2]["group"] == "pesados" and tracks[4]["group"] == "dos_ruedas"
    assert tracks[0]["origin_confirmed"] is True and tracks[5]["origin_confirmed"] is False
    assert tracks[3]["counted_frame"] is None


def test_old_csv_without_new_columns_fails_with_clear_message(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("track_id,class,state\n1,car,done\n")
    with pytest.raises(ValueError, match="vuelve a correr main.py"):
        load_tracks(path)


def test_crop_outside_frame_is_skipped(tmp_path):
    from scripts.review_incomplete_tracks import _write_crop
    image = np.zeros((150, 200, 3), np.uint8)
    assert _write_crop(image, (500, 10, 560, 40), "fuera", tmp_path / "x.jpg") is False
    assert _write_crop(image, (50, 50, 70, 70), "dentro", tmp_path / "y.jpg") is True


def test_incomplete_requires_confirmed_origin_and_separates_end_of_segment(tracks_csv):
    incomplete = find_incomplete(load_tracks(tracks_csv), processed_frames=100)
    assert [(t["track_id"], t["cause_hint"]) for t in incomplete] == [(2, "perdidos"), (3, "fin_del_tramo")]


def test_id_switch_candidates_require_time_space_and_group(tracks_csv):
    candidates = find_id_switch_candidates(load_tracks(tracks_csv), max_gap_frames=5, max_distance_factor=1.5)
    assert [(c["ended_track"], c["started_track"], c["gap_frames"]) for c in candidates] == [(2, 4, 2)]
    assert (candidates[0]["ended_class"], candidates[0]["started_class"]) == ("car", "van")
    assert candidates[0]["distance_sizes"] == pytest.approx(10.8 / 20, abs=0.01)
    assert find_id_switch_candidates(load_tracks(tracks_csv), max_gap_frames=1, max_distance_factor=1.5) == []
    assert find_id_switch_candidates(load_tracks(tracks_csv), max_gap_frames=5, max_distance_factor=0.4) == []


def test_each_track_appears_in_one_pair_only():
    rows = [dict(track(1, "new", first=1, last=10, last_xy=(100, 100)), group="ligeros"),
            dict(track(2, "new", first=11, last=20, first_xy=(104, 100), last_xy=(300, 300)), group="ligeros"),
            dict(track(3, "new", first=11, last=20, first_xy=(115, 100), last_xy=(500, 500)), group="ligeros")]
    candidates = find_id_switch_candidates(rows, max_gap_frames=5, max_distance_factor=1.5)
    assert [(c["ended_track"], c["started_track"]) for c in candidates] == [(1, 2)]


def test_fragmentation_and_summary(tracks_csv):
    tracks = load_tracks(tracks_csv)
    assert fragmentation(tracks, short_observations=30) == dict(
        tracks=6, short_observations=30, short_tracks=4, median_observations=28.5)
    assert summarize_by_origin(tracks, find_incomplete(tracks, 100)) == {
        "Norte": dict(completos=1, perdidos=1, fin_del_tramo=0),
        "Sur": dict(completos=0, perdidos=0, fin_del_tramo=1)}


def test_script_writes_only_used_crops(tmp_path, tracks_csv):
    from scripts.review_incomplete_tracks import main
    video = tmp_path / "video.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (200, 150))
    for index in range(110):
        writer.write(np.full((150, 200, 3), index % 255, np.uint8))
    writer.release()
    results = tmp_path / "results.json"
    results.write_text(json.dumps(dict(video=str(video), frames_processed=100, counting_mode="zones",
                                       run=dict(start_frame=5))))
    output = tmp_path / "review"
    assert main(["--results", str(results), "--tracks-csv", str(tracks_csv), "--output-dir", str(output),
                 "--max-gap-frames", "5"]) == 0
    report = json.loads((output / "report.json").read_text())
    assert report["summary_by_origin"]["Norte"]["perdidos"] == 1
    assert report["class_changes"] == 1
    assert report["id_switch_candidates"][0]["images"] == {
        "termina": "images/id2_last.jpg", "empieza": "images/id4_first.jpg"}
    assert sorted(p.name for p in (output / "images").iterdir()) == [
        "id2_first.jpg", "id2_last.jpg", "id3_first.jpg", "id3_last.jpg", "id4_first.jpg"]
    assert "ID 2 → ID 4 · car → van" in (output / "report.md").read_text()
    with pytest.raises(SystemExit):
        main(["--results", str(results), "--tracks-csv", str(tracks_csv), "--output-dir", str(output)])
