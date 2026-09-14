import json
import sys

import pytest

from scripts.validate_routes import _normalize_map, main, validate, validate_events


def write_counts(tmp_path, pred, truth):
    results = tmp_path / "results.json"
    reference = tmp_path / "truth.json"
    results.write_text(json.dumps({"routes": pred}))
    reference.write_text(json.dumps(truth))
    return results, reference


def test_swapped_routes_do_not_pass_on_equal_totals(tmp_path):
    paths = write_counts(tmp_path, {"A -> B": 10}, {"B -> A": 10})
    totals = validate(*paths)["totals"]
    assert totals["overall_accuracy"] == 1
    assert totals["weighted_route_accuracy"] == 0
    assert totals["total_abs_error"] == 20


def test_weighted_accuracy_detects_missing_vehicles(tmp_path):
    paths = write_counts(tmp_path, {"A → B": 8}, {" A -> B ": 10})
    assert validate(*paths)["totals"]["weighted_route_accuracy"] == 0.8


@pytest.mark.parametrize("value", [-1, 1.5, True, "3"])
def test_invalid_count_rejected(value):
    with pytest.raises(ValueError):
        _normalize_map({"A -> B": value})


def test_duplicate_route_aliases_are_rejected():
    with pytest.raises(ValueError, match="duplicada"):
        _normalize_map({"A -> B": 10, "A → B": 5})


@pytest.mark.parametrize("pred,truth,exit_code", [
    ({"A -> B": 10}, {"A -> B": 10}, None),
    ({"A -> B": 8}, {"A -> B": 10}, 1),
    ({"A -> B": 10}, {"B -> A": 10}, 1),
    ({}, {}, 1),
    ({"A -> B": 0}, {"A -> B": 0}, 1),
])
def test_cli_acceptance_gate(tmp_path, monkeypatch, pred, truth, exit_code):
    results, reference = write_counts(tmp_path, pred, truth)
    monkeypatch.setattr(sys, "argv", ["validate_routes", "--results", str(results),
                                     "--truth", str(reference), "--min-accuracy", "0.95"])
    if exit_code is None:
        main()
    else:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == exit_code


def write_events(tmp_path, predictions, events, **truth_overrides):
    results, truth = tmp_path / "events-result.json", tmp_path / "events-truth.json"
    results.write_text(json.dumps(dict(frames_processed=300, counting_events=predictions,
                                      run=dict(video_sha256="a" * 64, status="completed"))))
    reference = dict(reviewed=True, video_sha256="a" * 64, start_frame=1, end_frame=300, events=events)
    reference.update(truth_overrides)
    truth.write_text(json.dumps(reference))
    return results, truth


def event(frame, route="A -> B", cls="car"):
    return {"frame": frame, "route": route, "class": cls}


def test_same_route_totals_do_not_hide_duplicate_and_missed_event(tmp_path):
    paths = write_events(tmp_path, [event(30), event(31)], [event(30), event(200)])
    report = validate_events(*paths, tolerance_frames=5)
    assert report["metrics"] == dict(tp=1, fp=1, fn=1, precision=0.5, recall=0.5, f1=0.5)
    assert report["unmatched_predictions"][0]["frame"] == 31
    assert report["missed_events"][0]["frame"] == 200


def test_events_match_one_to_one_by_direction_class_and_time(tmp_path):
    paths = write_events(tmp_path, [event(30, "B -> A"), event(40, cls="bus"), event(70)],
                         [event(30), event(40), event(80)])
    report = validate_events(*paths, tolerance_frames=10)
    assert report["metrics"]["tp"] == 1
    assert report["metrics"]["fp"] == 2
    assert report["metrics"]["fn"] == 2
    assert report["matches"][0]["frame_delta"] == -10


def test_chronological_matching_does_not_lose_valid_pair_to_nearest_event(tmp_path):
    paths = write_events(tmp_path, [event(5), event(9)], [event(8), event(12)])
    assert validate_events(*paths, tolerance_frames=4)["metrics"]["tp"] == 2


def test_only_human_reviewed_segment_is_evaluated(tmp_path):
    paths = write_events(tmp_path, [event(5), event(50)], [event(50)], start_frame=40, end_frame=60)
    assert validate_events(*paths)["metrics"] == dict(tp=1, fp=0, fn=0, precision=1, recall=1, f1=1)


@pytest.mark.parametrize("override", [dict(reviewed=False), dict(reviewed="true"),
                                      dict(video_sha256="b" * 64), dict(end_frame=301),
                                      dict(start_frame=0), dict(events=[event(301)])])
def test_event_reference_must_be_reviewed_and_match_video_segment(tmp_path, override):
    options = dict(events=[event(50)])
    options.update(override)
    paths = write_events(tmp_path, [event(50)], **options)
    with pytest.raises(ValueError):
        validate_events(*paths)


def test_empty_reference_cannot_pass_event_acceptance_gate(tmp_path, monkeypatch):
    results, truth = write_events(tmp_path, [], [])
    monkeypatch.setattr(sys, "argv", ["validate_routes", "--results", str(results),
                                     "--truth", str(truth), "--events", "--min-f1", "0"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
