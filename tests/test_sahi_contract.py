from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from carcounter.detection import detect_objects
from carcounter.detection_cache import cache_signature, DetectionCacheReader, DetectionCacheWriter


@pytest.mark.parametrize("use_sahi", [False, True])
def test_detector_color_contract_preserves_source_and_global_boxes(use_sahi):
    frame = np.full((80, 100, 3), [10, 40, 230], dtype=np.uint8)
    original = frame.copy()
    model = Mock()
    model.names = {0: "car"}
    model.return_value = [SimpleNamespace(boxes=[SimpleNamespace(
        xyxy=np.array([[2, 3, 12, 13]]), cls=np.array([0]), conf=np.array([0.8]))])]
    prediction = SimpleNamespace(bbox=SimpleNamespace(minx=2, miny=3, maxx=12, maxy=13),
                                 category=SimpleNamespace(name="car"), score=SimpleNamespace(value=0.8))
    predict = Mock(return_value=SimpleNamespace(object_prediction_list=[prediction]))
    result = detect_objects(frame, model=model, effective_conf=0.1, imgsz=640,
                            use_sahi=use_sahi, sahi_model=SimpleNamespace(),
                            sahi_predict_fn=predict, inference_roi=[20, 10, 90, 70])
    supplied = (predict if use_sahi else model).call_args.args[0]
    assert supplied.shape == (60, 70, 3)
    assert supplied[0, 0].tolist() == ([230, 40, 10] if use_sahi else [10, 40, 230])
    if use_sahi:
        assert supplied.flags.c_contiguous
    np.testing.assert_array_equal(frame, original)
    assert result == [dict(bbox=(22, 13, 32, 23), conf=0.8, cls_name="car")]


@pytest.mark.parametrize("use_sahi", [False, True])
def test_color_contract_invalidates_only_legacy_sahi_caches(tmp_path, use_sahi):
    source = tmp_path / "source"
    source.write_bytes(b"fixture")
    cfg = dict(video_path=str(source), model_path=str(source), imgsz=640,
               settings={}, effective_conf=0.1, sahi_slice_w=256, sahi_slice_h=256,
               sahi_overlap=0.2, sahi_nms=0.3)
    signature = cache_signature(cfg, "yolo", use_sahi)
    legacy = dict(signature)
    legacy.pop("sahi_input_color", None)
    path = tmp_path / "legacy.sqlite"
    writer = DetectionCacheWriter(path, legacy)
    writer.write(1, [])
    writer.close(complete=True)
    if use_sahi:
        assert signature["sahi_input_color"] == "RGB"
        with pytest.raises(ValueError, match="incompatible"):
            DetectionCacheReader(path, signature)
    else:
        assert "sahi_input_color" not in signature
        reader = DetectionCacheReader(path, signature)
        assert reader.read(1) == []
        reader.close()
    corrected = tmp_path / "corrected.sqlite"
    writer = DetectionCacheWriter(corrected, signature)
    writer.write(1, [])
    writer.close(complete=True)
    reader = DetectionCacheReader(corrected, signature)
    assert reader.read(1) == []
    reader.close()
