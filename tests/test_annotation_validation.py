import json

import pytest

from carcounter.validation import labelme_to_detections, load_labelme_annotations


@pytest.mark.parametrize("kind", ["polygon", "mask", "circle", "line", None])
def test_unsupported_shapes_never_become_empty_truth(kind):
    shape = dict(shape_type=kind, label="car", points=[[0, 0], [10, 10]])
    with pytest.raises(ValueError, match="Forma 1.*rectangle"):
        labelme_to_detections({"shapes": [shape]})


@pytest.mark.parametrize("points", [
    [], [[0, 0]], [[0, 0], [10, 10], [20, 20]],
    [[0], [10, 10]], [[0, 0], [10, 10, 20]], None,
    [[0, 0], [float("nan"), 10]], [[0, 0], [float("inf"), 10]],
    [[False, 0], [10, 10]], [["0", 0], [10, 10]],
    [[0, 0], [0, 10]], [[0, 0], [10, 0]], [[0.1, 0.1], [0.9, 0.9]],
])
def test_malformed_boxes_fail_instead_of_disappearing(points):
    with pytest.raises(ValueError, match="Forma 1"):
        labelme_to_detections({"shapes": [dict(shape_type="rectangle", label="car", points=points)]})


@pytest.mark.parametrize("label", [None, "", " ", 2])
def test_missing_class_is_not_silently_excluded(label):
    with pytest.raises(ValueError, match="Forma 1.*label"):
        labelme_to_detections({"shapes": [dict(shape_type="rectangle", label=label,
                                             points=[[0, 0], [10, 10]])]})


@pytest.mark.parametrize("data", [None, [], {}, {"shapes": None}, {"shapes": {}}, {"shapes": [None]}])
def test_invalid_document_is_not_empty_reference(data):
    with pytest.raises(ValueError):
        labelme_to_detections(data)


def test_reviewed_file_reports_filename_and_invalid_shape_without_modifying_it(tmp_path):
    path = tmp_path / "bad-frame.json"
    data = dict(imagePath="bad-frame.jpg", flags=dict(reviewed=True), shapes=[
        dict(shape_type="rectangle", label="car", points=[[0, 0], [10, 10]]),
        dict(shape_type="polygon", label="car", points=[[0, 0], [10, 10], [10, 0]])])
    original = json.dumps(data)
    path.write_text(original)
    with pytest.raises(ValueError, match="bad-frame.json.*Forma 2"):
        load_labelme_annotations(tmp_path, require_reviewed=True)
    assert path.read_text() == original


def test_explicit_empty_reviewed_frame_remains_valid(tmp_path):
    data = dict(imagePath="empty.jpg", flags=dict(reviewed=True), shapes=[])
    (tmp_path / "empty.json").write_text(json.dumps(data))
    assert load_labelme_annotations(tmp_path, require_reviewed=True) == {"empty": []}
