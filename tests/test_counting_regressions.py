import pytest

from carcounter.counting import VehicleCounter
from tests.test_counting import make_counter, make_line_counter


def follow(counter, points, mode="lines", boxes=None, frames=None):
    for i, (x, y) in enumerate(points):
        counter.set_frame(frames[i] if frames else i + 1)
        counter.update(1, x, y, "car", mode, bbox=boxes[i] if boxes else None)


def test_default_crossing_requires_confirmation_then_counts():
    counter = make_line_counter(min_crossing_frames=2)
    follow(counter, [(100, 80), (100, 90), (100, 110)])
    assert counter.routes_matrix == {}
    counter.set_frame(4)
    counter.update(1, 100, 120, "car", "lines")
    assert counter.routes_matrix == {"Linea 1 ↓": 1}


def test_bbox_can_straddle_line_before_crossing():
    counter = make_line_counter(min_crossing_frames=2)
    ys = [70, 90, 100, 110, 130, 140]
    follow(counter, [(100, y) for y in ys],
           boxes=[(80, y - 15, 120, y + 15) for y in ys])
    assert counter.routes_matrix == {"Linea 1 ↓": 1}


def test_line_extension_does_not_count():
    counter = make_line_counter()
    follow(counter, [(400, 90), (400, 110)])
    assert counter.routes_matrix == {}


def test_going_around_endpoint_does_not_count():
    counter = make_line_counter(min_crossing_frames=2)
    points = [(100, 70), (220, 100), (220, 130), (220, 140)]
    follow(counter, points, boxes=[(x - 15, y - 15, x + 15, y + 15) for x, y in points])
    assert counter.routes_matrix == {}


def test_passing_exactly_on_line_then_crossing_counts():
    counter = make_line_counter(min_crossing_frames=2)
    follow(counter, [(100, y) for y in [80, 100, 110, 120]])
    assert counter.routes_matrix == {"Linea 1 ↓": 1}


@pytest.mark.parametrize("reverse", [False, True])
def test_vertical_line_distinguishes_directions(reverse):
    points = [(100, 0), (100, 200)]
    if reverse:
        points.reverse()
    counter = VehicleCounter({}, [{"name": "V", "pt1": points[0],
                                   "pt2": points[1], "tolerance": 25}],
                             min_crossing_frames=1)
    follow(counter, [(80, 100), (120, 100), (80, 100)])
    assert counter.routes_matrix == {"V →": 1, "V ←": 1}


def test_jitter_does_not_confirm_crossing():
    counter = make_line_counter(min_crossing_frames=2)
    follow(counter, [(100, y) for y in [80, 90, 110, 90, 110, 90]])
    assert counter.routes_matrix == {}


def test_starting_on_line_does_not_invent_origin_side():
    counter = make_line_counter()
    follow(counter, [(100, 100), (100, 110), (100, 120)])
    assert counter.routes_matrix == {}


def test_line_confirmation_does_not_span_missing_frames():
    counter = make_line_counter(min_crossing_frames=2)
    follow(counter, [(100, 80), (100, 110), (100, 120)], frames=[1, 2, 20])
    assert counter.routes_matrix == {}


@pytest.mark.parametrize("transit", [[], [(200, 50)]])
def test_one_destination_frame_is_enough_when_configured(transit):
    counter = make_counter(min_origin=1, min_dest=1)
    follow(counter, [(50, 50), *transit, (350, 50)], mode="zones")
    assert counter.routes_matrix == {"A → B": 1}


def test_unconfirmed_origin_changes_to_new_zone():
    counter = make_counter(min_origin=3, min_dest=1)
    follow(counter, [(50, 50), (350, 50), (350, 50), (350, 50),
                     (200, 50), (50, 50)], mode="zones")
    assert counter.routes_matrix == {"B → A": 1}


def test_destination_confirmation_does_not_span_missing_frames():
    counter = make_counter(min_origin=1, min_dest=2)
    follow(counter, [(50, 50), (200, 50), (350, 50), (350, 50)],
           mode="zones", frames=[1, 2, 3, 30])
    assert counter.routes_matrix == {}


def test_purged_tracks_remain_in_export():
    counter = make_counter(min_origin=1, min_dest=1)
    follow(counter, [(50, 50), (200, 50), (350, 50)], mode="zones")
    before = counter.get_track_data()
    counter.set_frame(300)
    counter.purge_stale()
    assert not counter.tracks_info
    assert counter.get_track_data() == before


def test_export_retains_first_position_after_trail_rollover():
    counter = VehicleCounter({}, [], trail_length=2)
    follow(counter, [(0, 0), (20, 20), (40, 40)], mode="zones")
    row = counter.get_track_data()[0]
    assert row["first_x"] == 0
    assert row["first_y"] == 0
    assert row["observed_frames"] == 3


def test_multiple_lines_keep_independent_confirmation():
    counter = VehicleCounter({}, [
        {"name": name, "pt1": (0, y), "pt2": (200, y), "tolerance": 25}
        for name, y in [("L1", 100), ("L2", 110)]
    ], min_crossing_frames=2)
    follow(counter, [(100, y) for y in [80, 105, 115, 125]])
    assert counter.routes_matrix == {"L1 ↓": 1, "L2 ↓": 1}
    assert [(event["route"], event["frame"]) for event in counter.counting_events] == [("L1 ↓", 3), ("L2 ↓", 4)]


def test_route_event_survives_purge_and_is_not_duplicated():
    counter = make_counter(min_origin=1, min_dest=1)
    follow(counter, [(50, 50), (200, 50), (350, 50), (350, 50)], mode="zones")
    assert len(counter.counting_events) == sum(counter.routes_matrix.values()) == 1
    event = counter.counting_events[0].copy()
    assert event["origin"] == "A"
    assert event["destination"] == "B"
    assert event["class"] == "car"
    assert event["frame"] == 3
    counter.set_frame(300)
    counter.purge_stale()
    assert counter.counting_events == [event]


def test_direction_records_confirmation_frame_once():
    counter = VehicleCounter({}, [], directions={"Este": [[0, 0], [100, 0]]})
    follow(counter, [(x, 0) for x in [0, 4, 8, 12, 16, 20]], mode="directions")
    assert len(counter.counting_events) == 1
    assert counter.counting_events[0]["frame"] == 5
    assert counter.counting_events[0]["direction"] == "Este"
    assert counter.get_track_data()[0]["counted_frame"] == 5


def test_route_class_uses_track_observations_instead_of_first_detection():
    counter = make_counter(min_origin=1, min_dest=1)
    for frame, (x, cls_name) in enumerate([(50, "bus"), (50, "car"), (200, "car"), (350, "car")], 1):
        counter.set_frame(frame)
        counter.update(1, x, 50, cls_name, "zones")
    assert counter.counting_events[0]["class"] == "car"
    assert counter.od_matrix_by_class == {"A": {"B": {"car": 1}}}


def test_single_wrong_class_at_crossing_does_not_change_vehicle_class():
    counter = make_line_counter(min_crossing_frames=1)
    for frame, (y, cls_name) in enumerate([(70, "car"), (80, "car"), (90, "car"), (120, "bus")], 1):
        counter.set_frame(frame)
        counter.update(1, 100, y, cls_name, "lines")
    assert counter.counting_events[0]["class"] == "car"
    for frame in range(5, 10):
        counter.set_frame(frame)
        counter.update(1, 100, 130, "bus", "lines")
    assert counter.get_track_data()[0]["class"] == "car"
    assert len(counter.counting_events) == 1


def test_vehicle_class_votes_are_independent_per_track():
    counter = make_counter(min_origin=1, min_dest=1)
    for frame, x in enumerate([50, 200, 350], 1):
        counter.set_frame(frame)
        counter.update(1, x, 50, "bus", "zones")
        counter.update(2, x, 50, "car", "zones")
    assert [event["class"] for event in counter.counting_events] == ["bus", "car"]
