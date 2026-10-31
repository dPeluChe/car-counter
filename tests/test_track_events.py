import csv

from carcounter.counting import VehicleCounter
from carcounter.track_events import TrackObservationLog


def test_observation_events_distinguish_missing_from_identity_change(tmp_path):
    path = tmp_path / "events.csv"
    log = TrackObservationLog(path, start_frame=101)
    log.update(1, [(0, 0, 10, 10, 7, "car")])
    log.update(2, [])
    log.update(3, [])
    log.update(4, [(1, 0, 11, 10, 7, "van"), (20, 20, 30, 30, 8, "car")])
    log.close()
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert [row["event"] for row in rows] == [
        "first_observation", "observation_lost", "observed_again", "class_changed", "first_observation"]
    assert [row["source_frame"] for row in rows] == ["101", "102", "104", "104", "104"]
    assert rows[2]["missing_frames"] == "2"
    assert rows[3]["previous_class"] == "car"
    assert rows[3]["class"] == "van"


def test_absolute_frames_survive_track_archival():
    counter = VehicleCounter({}, [])
    counter.frame_offset = 100
    counter.set_frame(1)
    counter.update(7, 5, 5, "car", "zones", bbox=(0, 0, 10, 10))
    counter.set_frame(4)
    counter.update(7, 6, 5, "car", "zones", bbox=(1, 0, 11, 10))
    counter._record_count(7, "zones", "A → B", "car", origin="A", destination="B")
    assert counter.counting_events[0]["source_frame"] == 104
    assert counter.counting_events[0]["frame"] == 4
    counter.set_frame(300)
    counter.purge_stale()
    row = counter.get_track_data()[0]
    assert row["first_seen_source_frame"] == 101
    assert row["last_seen_source_frame"] == row["counted_source_frame"] == 104


def test_empty_log_still_has_schema(tmp_path):
    path = tmp_path / "events.csv"
    log = TrackObservationLog(path)
    log.update(1, [])
    log.close()
    with path.open() as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == list(TrackObservationLog.fields)
        assert list(reader) == []
