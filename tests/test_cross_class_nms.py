import numpy as np

from carcounter.app_config import AppConfig
from carcounter.detection import detect_and_track
from carcounter.detector import detection_rejection, filter_detections, mark_cross_class_duplicates
from carcounter.geometry import cross_class_duplicates

CAR = dict(bbox=(100, 100, 200, 180), conf=0.60, cls_name="car")
VAN_SAME_SPOT = dict(bbox=(102, 101, 203, 181), conf=0.40, cls_name="van")
VAN_NEXT_LANE = dict(bbox=(210, 100, 310, 180), conf=0.50, cls_name="van")


def rows(*dets):
    return [[*d["bbox"], d["conf"]] for d in dets], [d["cls_name"] for d in dets]


def test_lower_confidence_box_of_other_class_is_the_duplicate():
    boxes, classes = rows(VAN_SAME_SPOT, CAR)
    assert cross_class_duplicates(boxes, classes, 0.7) == {0}


def test_same_class_and_distinct_vehicles_are_kept():
    twin = dict(CAR, bbox=(102, 101, 203, 181), conf=0.40)
    assert cross_class_duplicates(*rows(CAR, twin), 0.7) == set()
    assert cross_class_duplicates(*rows(CAR, VAN_NEXT_LANE), 0.7) == set()


def test_threshold_decides_partial_overlap():
    shifted = dict(VAN_SAME_SPOT, bbox=(130, 100, 230, 180))
    assert cross_class_duplicates(*rows(CAR, shifted), 0.7) == set()
    assert cross_class_duplicates(*rows(CAR, shifted), 0.3) == {1}


def test_filter_is_off_by_default_and_keeps_both_boxes():
    raw = [CAR, VAN_SAME_SPOT]
    kept, classes = filter_detections(raw, lambda _: 0.1, {}, {})
    assert classes == ["car", "van"] and len(kept) == 2
    kept, classes = filter_detections(raw, lambda _: 0.1, {}, {}, 0.7)
    assert classes == ["car"] and kept.tolist() == [[100, 100, 200, 180, 0.6]]


def test_rejected_box_cannot_suppress_a_valid_one():
    strong_but_excluded = dict(CAR, conf=0.95)
    zone = {"parking": np.array([[0, 0], [400, 0], [400, 400], [0, 400]])}
    kept, _ = filter_detections([strong_but_excluded, VAN_SAME_SPOT], lambda _: 0.1, {}, zone, 0.7)
    assert len(kept) == 0
    kept, classes = filter_detections([dict(CAR, conf=0.95, cls_name="person"), VAN_SAME_SPOT],
                                      lambda _: 0.1, {}, {}, 0.7)
    assert classes == ["van"]


def test_diagnostics_mark_the_same_boxes_the_runtime_drops():
    raw = [CAR, VAN_SAME_SPOT, VAN_NEXT_LANE]
    marked = mark_cross_class_duplicates(
        [dict(d, rejection=detection_rejection(d, lambda _: 0.1, {}, {})) for d in raw], 0.7)
    assert [d["rejection"] for d in marked] == [None, "duplicado", None]
    _, classes = filter_detections(raw, lambda _: 0.1, {}, {}, 0.7)
    assert classes == ["car", "van"]


class RecordingTracker:
    def __init__(self):
        self.seen = []

    def update_detections(self, frame, detections, classes):
        self.seen.append(list(classes))
        return []


def run_tracker(cross_class_iou):
    tracker = RecordingTracker()
    detect_and_track(
        np.zeros((300, 400, 3), np.uint8), model=None, sahi_model=None, sahi_predict_fn=None,
        sort_tracker=tracker, use_sahi=False, effective_conf=0.1, imgsz=640, conf_for=lambda _: 0.1,
        geo_constraints={}, exclusion_np={}, sahi_slice_w=512, sahi_slice_h=512, sahi_overlap=0.2,
        sahi_nms_threshold=0.3, raw_detections=[CAR, VAN_SAME_SPOT], cross_class_iou=cross_class_iou)
    return tracker.seen


def test_tracker_receives_one_box_per_vehicle_only_when_enabled():
    assert run_tracker(0.0) == [["car", "van"]]
    assert run_tracker(0.7) == [["car"]]


def test_profile_round_trip_keeps_default_file_unchanged():
    base = {"counting_mode": "zones", "zones": {}, "settings": {}}
    assert "cross_class_nms_iou" not in AppConfig.from_dict(base).to_dict()["settings"]
    tuned = AppConfig.from_dict({**base, "settings": {"cross_class_nms_iou": 0.7}})
    assert tuned.to_dict()["settings"]["cross_class_nms_iou"] == 0.7
    assert AppConfig.from_dict(tuned.to_dict()).settings.cross_class_nms_iou == 0.7


def test_profile_rejects_threshold_outside_unit_interval():
    config = AppConfig.from_dict({"settings": {"cross_class_nms_iou": 1.5}})
    assert any("cross_class_nms_iou" in error for error in config.validate())
