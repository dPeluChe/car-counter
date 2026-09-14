from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from carcounter.constants import resolve_vehicle_classes
from carcounter.detection import detect_objects, detect_and_track
from carcounter.detector import filter_detections
from carcounter.tracking import UltralyticsTracker
from carcounter.detection_cache import DetectionCacheReader, DetectionCacheWriter
from setup_panels.calib_tests import CalibTestsMixin, best_calibration_match


def model_with_boxes():
    model = Mock()
    model.names = {0: "person", 3: "car", 4: "van", 5: "truck", 8: "bus", 9: "motor"}
    box = SimpleNamespace(xyxy=np.array([[10, 20, 30, 40]]), cls=np.array([4]), conf=np.array([0.8]))
    model.return_value = [SimpleNamespace(boxes=[box])]
    return model


def profile():
    return dict(settings=dict(conf_threshold=0.1, imgsz=640, inference_roi=[100, 50, 250, 150]),
                sahi=dict(enabled=False), model_path="unused")


def test_preview_uses_production_roi_model_and_filters():
    model = model_with_boxes()
    config = profile()
    app = SimpleNamespace(model=model, _build_current_config=lambda: config, exclusion_zones={})
    frame = np.zeros((200, 300, 3), np.uint8)
    preview = CalibTestsMixin._predict_current_profile(app, frame)
    raw = detect_objects(frame, model=model, effective_conf=0.1, imgsz=640,
                         inference_roi=config["settings"]["inference_roi"])
    assert preview == raw == [dict(bbox=(110, 70, 130, 90), conf=0.8, cls_name="van")]
    assert model.call_args.kwargs["classes"] == [3, 4, 5, 8, 9]  # names del mock: sin bicycle/tricycle
    assert model.call_args.args[0].shape == (100, 150, 3)
    app.exclusion_zones = {"excluded": [[105, 65], [135, 65], [135, 95], [105, 95]]}
    assert CalibTestsMixin._predict_current_profile(app, frame) == []


def test_model_class_lists_and_unknown_scheme():
    assert resolve_vehicle_classes(SimpleNamespace(names=["person", "Car", "bus"])) == ([1, 2], {0: "person", 1: "car", 2: "bus"})
    with pytest.raises(ValueError, match="clases"):
        resolve_vehicle_classes(SimpleNamespace(names={2: "dog", 3: "cat"}))


def test_calibration_rejects_large_box_containing_selected_car():
    detections = [dict(bbox=(0, 0, 200, 200), conf=0.99, cls_name="truck")]
    assert best_calibration_match(detections, (50, 50, 70, 70)) is None
    match = dict(bbox=(50, 50, 70, 70), conf=0.6, cls_name="car")
    assert best_calibration_match(detections + [match], (50, 50, 70, 70)) == match


def test_sahi_updates_confidence_and_merges_before_global_tracker():
    model = SimpleNamespace(confidence_threshold=0.9)
    prediction = SimpleNamespace(bbox=SimpleNamespace(minx=10, miny=20, maxx=30, maxy=40),
                                 category=SimpleNamespace(name="car"), score=SimpleNamespace(value=0.6))
    predict = Mock(return_value=SimpleNamespace(object_prediction_list=[prediction, prediction]))
    tracker = SimpleNamespace(update_detections=Mock(return_value=[]))
    recorded = []
    detect_and_track(np.zeros((200, 300, 3), np.uint8), model=None,
        sahi_model=model, sahi_predict_fn=predict, sort_tracker=tracker, use_sahi=True,
        effective_conf=0.1,
        imgsz=640, conf_for=lambda _: 0.1, geo_constraints={}, exclusion_np={},
        sahi_slice_w=128, sahi_slice_h=128, sahi_overlap=0.3, sahi_nms_threshold=0.3,
        inference_roi=[100, 50, 250, 150], on_detections=recorded.extend)
    assert model.confidence_threshold == 0.1
    assert model.image_size == 640
    assert len(recorded) == 1
    assert recorded[0]["bbox"] == (110, 70, 130, 90)
    assert tracker.update_detections.call_count == 1
    np.testing.assert_array_equal(tracker.update_detections.call_args.args[1], [[110, 70, 130, 90, 0.6]])


def test_bytetrack_low_confidence_preserves_id_without_starting_new_track():
    pytest.importorskip("lap")
    tracker = UltralyticsTracker("bytetrack", {"track_low_thresh": 0.1, "track_high_thresh": 0.25,
                                               "new_track_thresh": 0.5, "fuse_score": False}, 30)
    frame = np.zeros((200, 200, 3), np.uint8)
    first = tracker.update_detections(frame, [[20, 20, 40, 40, 0.9]], ["van"])
    assert len(first) == 1
    second = tracker.update_detections(frame, [[21, 20, 41, 40, 0.15], [100, 100, 120, 120, 0.15]], ["van", "car"])
    assert len(second) == 1
    assert second[0][4:] == first[0][4:] == (1, "van")
    assert tracker.update_detections(frame, np.empty((0, 5)), []) == []


@pytest.mark.parametrize("settings", [dict(track_low_thresh=0.5), dict(new_track_thresh=0.1),
                                     dict(track_buffer=0), dict(match_thresh=float("nan"))])
def test_invalid_tracker_thresholds_fail_before_run(settings):
    pytest.importorskip("lap")
    with pytest.raises(ValueError):
        UltralyticsTracker("bytetrack", settings)


def test_cache_replay_reuses_boxes_without_inference_and_can_change_filters(tmp_path):
    path = tmp_path / "detections.sqlite"
    signature = dict(version=1, effective_conf=0.1, video_sha256="video", model_sha256="model")
    raw = [dict(bbox=[0, 0, 20, 20], conf=0.8, cls_name="car"),
           dict(bbox=[30, 0, 50, 20], conf=0.15, cls_name="van")]
    writer = DetectionCacheWriter(path, signature)
    writer.write(1, raw)
    writer.write(2, [])
    writer.close(complete=True)
    reader = DetectionCacheReader(path, {**signature, "effective_conf": 0.25})
    assert reader.frames == 2
    assert reader.read(1) == raw[:1]
    assert reader.read(2) == []
    model = Mock(side_effect=AssertionError("no inference during replay"))
    tracker = SimpleNamespace(update_detections=Mock(return_value=[(0, 0, 20, 20, 1, "car")]))
    output = detect_and_track(np.zeros((100, 100, 3), np.uint8), model=model,
        sahi_model=None, sahi_predict_fn=None, sort_tracker=tracker, use_sahi=False,
        effective_conf=0.25,
        imgsz=640, conf_for=lambda _: 0.25, geo_constraints={}, exclusion_np={},
        sahi_slice_w=128, sahi_slice_h=128, sahi_overlap=0.2, sahi_nms_threshold=0.3,
        raw_detections=reader.read(1))
    assert output == [(0, 0, 20, 20, 1, "car")]
    model.assert_not_called()
    rows, names = filter_detections(reader.read(1), lambda _: 0.25, {"min_area": 500}, {})
    assert len(rows) == 0 and names == []
    reader.close()
    with pytest.raises(FileExistsError):
        DetectionCacheWriter(path, signature)
    for modified in ({**signature, "effective_conf": 0.05}, {**signature, "video_sha256": "other"}):
        with pytest.raises(ValueError, match="incompatible"):
            DetectionCacheReader(path, modified)


def test_cache_rejects_incomplete_or_missing_frames(tmp_path):
    path = tmp_path / "detections.sqlite"
    signature = dict(version=1, effective_conf=0.1)
    writer = DetectionCacheWriter(path, signature)
    with pytest.raises(ValueError, match="consecutivos"):
        writer.write(2, [])
    writer.write(1, [])
    writer.close()
    with pytest.raises(ValueError, match="incompleta"):
        DetectionCacheReader(path, signature)


def test_new_parameters_survive_config_roundtrip():
    from carcounter.app_config import AppConfig
    config = dict(settings=dict(vehicle_samples=[dict(frame=4, bbox=[1, 2, 3, 4])], camera_max_drift_px=5),
                  sahi=dict(enabled=False), tracker=dict(track_high_thresh=0.4,
                  track_low_thresh=0.05, new_track_thresh=0.5, track_buffer=50, gmc_method="orb"))
    saved = AppConfig.from_dict(config).to_dict()
    assert saved["sahi"]["enabled"] is False
    for key, value in config["tracker"].items():
        assert saved["tracker"][key] == value
    assert saved["settings"]["vehicle_samples"] == config["settings"]["vehicle_samples"]
    assert saved["settings"]["camera_max_drift_px"] == 5


@pytest.mark.parametrize("fail", [None, "tracker", "camera"])
def test_cli_replay_counts_without_loading_model_and_rejects_failed_run(tmp_path, monkeypatch, fail):
    import cv2
    import json
    import sys
    import main
    from carcounter.detection_cache import cache_signature
    from carcounter.runtime import resolve_runtime_config

    pytest.importorskip("lap")
    video = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (100, 100))
    if not writer.isOpened():
        pytest.skip("Codec mp4v no disponible")
    for _ in range(7):
        writer.write(np.zeros((100, 100, 3), np.uint8))
    writer.release()
    weights = tmp_path / "model.pt"
    weights.write_bytes(b"cached model; replay must never load these bytes")
    config = dict(counting_mode="lines", lines=[dict(name="Gate", points=[[0, 50], [100, 50]], tolerance=0)],
                  settings=dict(conf_threshold=0.1, min_crossing_frames=1, imgsz=640),
                  sahi=dict(enabled=False), tracker=dict(fuse_score=False),
                  video_path=str(video), model_path=str(weights))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    cfg = resolve_runtime_config(config, SimpleNamespace(detector="yolo", video=None, model=None, imgsz=None))
    cache_path = tmp_path / "cache.sqlite"
    cache = DetectionCacheWriter(cache_path, cache_signature(cfg, "yolo", False))
    for number in range(1, 8):
        cache.write(number, [dict(bbox=[40, number * 10, 60, number * 10 + 20], conf=0.9, cls_name="car")])
    cache.close(complete=True)
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(config_path), "--headless", "--no-save",
                                     "--replay-detections", str(cache_path), "--output-json", str(output)])
    loader = Mock(side_effect=AssertionError("Model loader called during replay"))
    monkeypatch.setattr(main, "load_detector", loader)
    monkeypatch.setattr(main.db, "save_run", Mock())
    if fail == "camera":
        monkeypatch.setattr(sys, "argv", sys.argv + ["--camera-max-drift-px", "5"])
    if fail:
        if fail == "tracker":
            monkeypatch.setattr(main, "process_frame", Mock(side_effect=RuntimeError("broken tracker")))
        with pytest.raises(SystemExit) as error:
            main.main()
        assert error.value.code == 1
        assert not output.exists()
        main.db.save_run.assert_not_called()
    else:
        main.main()
        result = json.loads(output.read_text())
        assert result["frames_processed"] == 7
        assert result["total_routes_completed"] == 1
        assert len(result["counting_events"]) == 1
        assert result["counting_events"][0]["route"] == "Gate ↓"
        assert result["counting_events"][0]["frame"] == 6
        assert len(result["run"]["video_sha256"]) == 64
        assert result["run"]["detection_source"] == "cache"
        assert result["run"]["tracker_parameters"]["fuse_score"] is False
    loader.assert_not_called()


def test_sample_validation_does_not_match_one_detection_to_two_samples():
    from setup_panels.calib_tests import count_sample_matches
    assert count_sample_matches([dict(bbox=(0, 0, 20, 20))],
                                [(0, 0, 20, 20), (1, 1, 21, 21)]) == 1
    assert count_sample_matches([], [(0, 0, 20, 20)]) == 0


def test_classification_errors_and_motorcycle_aliases():
    from carcounter.validation import match_detections
    result = match_detections([(0, 0, 20, 20, "car")], [(0, 0, 20, 20, "bus")], class_aware=True)
    assert (result["tp"], result["fp"], result["fn"]) == (0, 1, 1)
    result = match_detections([(0, 0, 20, 20, "motor")], [(0, 0, 20, 20, "motorbike")], class_aware=True)
    assert result["tp"] == 1


def test_evaluation_requires_review_and_rejects_duplicate_frames(tmp_path):
    import json
    from carcounter.validation import load_labelme_annotations, detections_to_labelme
    data = detections_to_labelme([], "frame.jpg", 100, 100)
    path = tmp_path / "frame.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="revisión humana"):
        load_labelme_annotations(tmp_path, require_reviewed=True)
    data["flags"]["reviewed"] = True
    path.write_text(json.dumps(data))
    (tmp_path / "duplicate.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="duplicadas"):
        load_labelme_annotations(tmp_path, require_reviewed=True)


def test_evaluator_uses_profile_and_penalizes_cancelling_frame_errors(tmp_path, monkeypatch):
    import cv2
    import json
    import ultralytics
    from scripts.evaluate_pipeline import evaluate
    from carcounter.validation import detections_to_labelme
    frames = tmp_path / "frames"
    annotations = tmp_path / "annotations"
    frames.mkdir()
    annotations.mkdir()
    for index in range(2):
        name = f"frame{index}"
        cv2.imwrite(str(frames / f"{name}.png"), np.zeros((100, 100, 3), np.uint8))
        data = detections_to_labelme([(20, 20, 40, 40, "car")], f"{name}.png", 100, 100)
        data["flags"]["reviewed"] = True
        (annotations / f"{name}.json").write_text(json.dumps(data))
    config = dict(model_path="visdrone.pt", settings=dict(imgsz=640, conf_threshold=0.1,
                  inference_roi=[10, 10, 90, 90]), sahi=dict(enabled=False))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    def box(x):
        return SimpleNamespace(xyxy=np.array([[x, 10, x + 20, 30]]), cls=np.array([3]), conf=np.array([0.9]))
    model = Mock()
    model.names = {3: "car", 4: "van", 5: "truck"}
    model.side_effect = [[SimpleNamespace(boxes=[box(10), box(50)])], [SimpleNamespace(boxes=[])]]
    loader = Mock(return_value=model)
    monkeypatch.setattr(ultralytics, "YOLO", loader)
    result = evaluate(frames, annotations, config_path=config_path)
    assert result["frames_evaluated"] == 2
    assert result["overall"]["tp"] == result["overall"]["fp"] == result["overall"]["fn"] == 1
    assert result["counting_accuracy"] == 0
    assert model.call_args.args[0].shape == (80, 80, 3)
    loader.assert_called_once_with("visdrone.pt")
    (frames / "frame1.png").unlink()
    model.side_effect = None
    model.return_value = [SimpleNamespace(boxes=[])]
    with pytest.raises(ValueError, match="Falta el frame"):
        evaluate(frames, annotations, config_path=config_path)


def test_ground_truth_scope_keeps_large_vehicles_to_expose_bad_geometry_filters():
    from scripts.evaluate_pipeline import scoped_ground_truth
    ground_truth = [(0, 0, 90, 90, "bus"), (150, 150, 160, 160, "car"), (10, 10, 20, 20, "person")]
    assert scoped_ground_truth(ground_truth, [0, 0, 100, 100], {}) == ground_truth[:1]


def test_prelabel_preserves_existing_human_annotations(tmp_path, monkeypatch):
    import cv2
    import ultralytics
    from scripts.pre_label_frames import pre_label
    frames = tmp_path / "frames"
    annotations = tmp_path / "annotations"
    frames.mkdir()
    annotations.mkdir()
    cv2.imwrite(str(frames / "frame.png"), np.zeros((100, 100, 3), np.uint8))
    saved = annotations / "frame.json"
    saved.write_text("human annotation, must remain byte-identical")
    model = model_with_boxes()
    monkeypatch.setattr(ultralytics, "YOLO", Mock(return_value=model))
    pre_label(frames, annotations, "unused.pt")
    assert saved.read_text() == "human annotation, must remain byte-identical"
    model.assert_not_called()
