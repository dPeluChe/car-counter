import csv
import json

import cv2
import numpy as np
import pytest

from carcounter.export import export_tracks_csv
from carcounter.track_review import (
    find_id_switch_candidates, find_incomplete, load_tracks, summarize_by_origin,
)


def track(track_id, state, origin="", cls="car", first=1, last=10, first_xy=(10, 10), last_xy=(50, 50)):
    return dict(track_id=track_id, state=state, origin=origin, destination="", counted_frame="",
                **{"class": cls}, direction="", first_seen_frame=first, last_seen_frame=last,
                observed_frames=last - first + 1, first_x=first_xy[0], first_y=first_xy[1],
                last_x=last_xy[0], last_y=last_xy[1], trail_length=5, avg_width=20.0, avg_height=12.0,
                avg_area=240.0, avg_aspect=1.67, avg_elongation=1.67)


@pytest.fixture
def tracks_csv(tmp_path):
    rows = [
        track(1, "done", "Norte", first=1, last=40),
        track(2, "transit", "Norte", first=5, last=60, last_xy=(100, 100)),
        track(3, "origin", "Sur", cls="bus", first=80, last=99),
        track(4, "new", first=62, last=90, first_xy=(110, 104)),
        track(5, "new", cls="motor", first=63, last=90, first_xy=(102, 101)),
    ]
    path = tmp_path / "tracks.csv"
    export_tracks_csv(str(path), rows)
    return path


def test_load_tracks_types_numbers_and_group(tracks_csv):
    tracks = load_tracks(tracks_csv)
    assert tracks[0]["track_id"] == 1 and tracks[0]["first_x"] == 10.0
    assert tracks[2]["group"] == "pesados" and tracks[4]["group"] == "dos_ruedas"
    assert tracks[3]["counted_frame"] is None


def test_incomplete_separates_lost_from_visible_at_end(tracks_csv):
    incomplete = find_incomplete(load_tracks(tracks_csv), processed_frames=100, end_margin_frames=10)
    assert [(t["track_id"], t["cause_hint"]) for t in incomplete] == [(2, "perdido"), (3, "fin_del_tramo")]


def test_id_switch_candidates_require_time_space_and_group(tracks_csv):
    candidates = find_id_switch_candidates(load_tracks(tracks_csv), max_gap_frames=5, max_distance_factor=1.5)
    assert [(c["ended_track"], c["started_track"], c["gap_frames"]) for c in candidates] == [(2, 4, 2)]
    assert candidates[0]["distance_sizes"] == pytest.approx(10.8 / 20, abs=0.01)
    assert find_id_switch_candidates(load_tracks(tracks_csv), max_gap_frames=1, max_distance_factor=1.5) == []
    assert find_id_switch_candidates(load_tracks(tracks_csv), max_gap_frames=5, max_distance_factor=0.4) == []


def test_each_track_appears_in_one_pair_only():
    rows = [dict(track(1, "new", first=1, last=10, last_xy=(100, 100)), group="ligeros"),
            dict(track(2, "new", first=11, last=20, first_xy=(104, 100), last_xy=(300, 300)), group="ligeros"),
            dict(track(3, "new", first=11, last=20, first_xy=(115, 100), last_xy=(500, 500)), group="ligeros")]
    candidates = find_id_switch_candidates(rows, max_gap_frames=5, max_distance_factor=1.5)
    assert [(c["ended_track"], c["started_track"]) for c in candidates] == [(1, 2)]


def test_fragmentation_counts_short_tracks(tracks_csv):
    from carcounter.track_review import fragmentation
    assert fragmentation(load_tracks(tracks_csv), short_observations=30) == dict(
        tracks=5, short_observations=30, short_tracks=3, median_observations=29)


def test_summary_by_origin(tracks_csv):
    tracks = load_tracks(tracks_csv)
    summary = summarize_by_origin(tracks, find_incomplete(tracks, 100, 10))
    assert summary == {"Norte": dict(completos=1, perdidos=1, fin_del_tramo=0),
                       "Sur": dict(completos=0, perdidos=0, fin_del_tramo=1)}


def test_script_writes_report_and_crops(tmp_path, tracks_csv):
    from scripts.review_incomplete_tracks import main
    video = tmp_path / "video.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (200, 150))
    for index in range(110):
        frame = np.full((150, 200, 3), index % 255, np.uint8)
        writer.write(frame)
    writer.release()
    results = tmp_path / "results.json"
    results.write_text(json.dumps(dict(video=str(video), frames_processed=100, counting_mode="zones",
                                       run=dict(start_frame=5))))
    output = tmp_path / "review"
    assert main(["--results", str(results), "--tracks-csv", str(tracks_csv), "--output-dir", str(output),
                 "--max-gap-frames", "5", "--max-distance-factor", "1.5", "--end-margin-frames", "10",
                 "--crop-px", "40"]) == 0
    report = json.loads((output / "report.json").read_text())
    assert report["summary_by_origin"]["Norte"]["perdidos"] == 1
    assert report["id_switch_candidates"][0]["images"] == {
        "termina": "images/cambio_id2_last.jpg", "empieza": "images/cambio_id4_first.jpg"}
    assert (output / "images" / "incompleto_id2_first.jpg").exists()
    assert "ID 2 → ID 4" in (output / "report.md").read_text()
    with pytest.raises(SystemExit):
        main(["--results", str(results), "--tracks-csv", str(tracks_csv), "--output-dir", str(output)])
