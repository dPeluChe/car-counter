import pytest
import re

from carcounter.app_config import AppConfig
from carcounter.wizard_actions import profile_errors, profile_rows


def percent(text):
    return int(re.search(r"(\d+)%", text).group(1))


def box(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def config(mode="zones", roi=None, exclusions=None, **elements):
    data = {"counting_mode": mode, "exclusion_zones": exclusions or {}, "settings": {}}
    if roi:
        data["settings"]["inference_roi"] = roi
    data.update(elements)
    return AppConfig.from_dict(data)


ZONES = {"A": box(100, 100, 200, 200), "B": box(400, 100, 500, 200)}


def test_clean_profile_has_no_findings():
    assert config(zones=ZONES, roi=[0, 0, 600, 300]).geometry_findings() == ([], [])


def test_zone_fully_outside_roi_is_an_error_that_says_how_to_fix_it():
    errors, warnings = config(zones=ZONES, roi=[0, 0, 300, 300]).geometry_findings()
    assert len(errors) == 1 and "'B'" in errors[0] and "fuera de la ROI" in errors[0]
    assert "amplía la ROI" in errors[0] and warnings == []


def test_zone_partially_outside_roi_is_a_warning():
    errors, warnings = config(zones=ZONES, roi=[0, 0, 450, 300]).geometry_findings()
    assert errors == [] and len(warnings) == 1 and "'B'" in warnings[0] and 48 <= percent(warnings[0]) <= 52


def test_lines_use_the_roi_rule():
    lines = [{"name": "L", "points": [[700, 50], [800, 50]], "tolerance": 15}]
    errors, _ = config("lines", roi=[0, 0, 300, 300], lines=lines).geometry_findings()
    assert "Línea 'L'" in errors[0]


def test_zone_covered_by_exclusion_is_an_error_and_partial_cover_a_warning():
    covered = {"parking": box(90, 90, 210, 210)}
    errors, _ = config(zones=ZONES, exclusions=covered).geometry_findings()
    assert len(errors) == 1 and "'A'" in errors[0] and "Quita o recorta la exclusión" in errors[0]
    half = {"parking": box(0, 0, 150, 300)}
    errors, warnings = config(zones=ZONES, exclusions=half).geometry_findings()
    assert errors == [] and "'A'" in warnings[0] and 48 <= percent(warnings[0]) <= 52


def test_line_inside_exclusion_is_an_error():
    lines = [{"name": "L", "points": [[120, 120], [180, 120]], "tolerance": 15}]
    errors, _ = config("lines", exclusions={"x": box(100, 100, 200, 200)}, lines=lines).geometry_findings()
    assert "Línea 'L'" in errors[0]


def test_overlapping_zones_are_ambiguous():
    twin = {**ZONES, "A2": box(110, 110, 210, 210)}
    errors, _ = config(zones=twin).geometry_findings()
    assert len(errors) == 1 and "'A'" in errors[0] and "'A2'" in errors[0] and "ambiguo" in errors[0]
    edge = {**ZONES, "A2": box(180, 100, 280, 200)}
    errors, warnings = config(zones=edge).geometry_findings()
    assert errors == [] and len(warnings) == 1 and 18 <= percent(warnings[0]) <= 23


def test_touching_zones_do_not_count_as_overlap():
    assert config(zones={"A": box(0, 0, 100, 100), "B": box(101, 0, 200, 100)}).geometry_findings() == ([], [])


def test_validate_blocks_on_errors_but_not_on_warnings():
    assert any("fuera de la ROI" in error for error in config(zones=ZONES, roi=[0, 0, 300, 300]).validate())
    assert config(zones=ZONES, roi=[0, 0, 450, 300]).validate() == []


def test_too_few_points_do_not_crash_the_findings():
    assert config(zones={"A": [[0, 0]], "B": box(0, 0, 10, 10)}).geometry_findings() == ([], [])


@pytest.mark.parametrize("bad", [
    [["bad", 0], [10, 0], [10, 10]],
    [[0, 0], [10, 0], [float("nan"), 10]],
    [[0, 0], [10, 0], [float("inf"), 10]],
    [[0, 0], [10, 0], [10]],
    [[0, 0], [10, 0], None],
    [[0, 0], [10, 0], [True, 10]],
])
def test_invalid_coordinates_are_an_error_naming_the_element(bad):
    errors = config(zones={"A": bad, "B": box(20, 0, 30, 10)}).validate()
    assert any("Zona 'A'" in error and "coordenadas inválidas" in error for error in errors)


def test_invalid_coordinates_in_every_section_are_reported():
    bad = [["x", 1], [2, 3]]
    lines = [{"name": "L", "points": bad, "tolerance": 15}]
    errors, _ = config("lines", lines=lines, directions={"D": bad},
                       exclusions={"E": [[0, 0], [1, 1], ["z", 2]]}).geometry_findings()
    assert [kind for kind in ("Línea 'L'", "Dirección 'D'", "Exclusión 'E'")
            if any(kind in error for error in errors)] == ["Línea 'L'", "Dirección 'D'", "Exclusión 'E'"]


def test_direction_vectors_are_not_spatial_regions():
    east = {"Este": [[500, 500], [600, 500]]}
    assert config("directions", roi=[0, 0, 100, 100], directions=east).geometry_findings() == ([], [])
    assert config("directions", exclusions={"x": box(400, 400, 700, 700)},
                  directions=east).geometry_findings() == ([], [])


def test_translating_a_direction_does_not_change_validity():
    for dx in (0, 300, 5000):
        direction = {"Este": [[10 + dx, 10], [60 + dx, 10]]}
        assert config("directions", roi=[0, 0, 100, 100], directions=direction).validate() == []


def test_a_short_line_crossing_the_roi_between_old_samples_is_valid():
    lines = [{"name": "L", "points": [[0, 0], [100, 0]], "tolerance": 15}]
    errors, warnings = config("lines", roi=[2, 0, 3, 10], lines=lines).geometry_findings()
    assert errors == [] and "Línea 'L'" in warnings[0] and "1% dentro" in warnings[0]


def test_a_zone_touching_the_roi_with_a_thin_overlap_is_valid():
    errors, warnings = config(zones={"A": box(0, 0, 100, 100), "B": box(200, 0, 300, 100)},
                              roi=[99, 0, 400, 100]).geometry_findings()
    assert errors == [] and "Zona 'A'" in warnings[0]


def test_a_small_unexcluded_remainder_is_not_declared_fully_covered():
    lines = [{"name": "L", "points": [[0, 50], [1000, 50]], "tolerance": 15}]
    gap = {"left": box(-1, 0, 499, 100), "right": box(501, 0, 1001, 100)}
    errors, warnings = config("lines", exclusions=gap, lines=lines).geometry_findings()
    assert errors == [] and "Línea 'L'" in warnings[0]
    sliver = {"top": box(100, 100, 200, 149), "bottom": box(100, 151, 200, 200)}
    assert config(zones=ZONES, exclusions=sliver).geometry_findings()[0] == []


def test_a_line_split_across_exclusions_is_fully_covered():
    lines = [{"name": "L", "points": [[0, 50], [1000, 50]], "tolerance": 15}]
    cover = {"left": box(-1, 0, 500, 100), "right": box(500, 0, 1001, 100)}
    errors, _ = config("lines", exclusions=cover, lines=lines).geometry_findings()
    assert "Línea 'L'" in errors[0]


def test_wizard_blocks_a_bad_profile_and_summarises_warnings(tmp_path):
    import json
    bad = {"counting_mode": "zones", "zones": ZONES, "settings": {"inference_roi": [0, 0, 300, 300]}}
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(bad))
    assert any("fuera de la ROI" in error for error in profile_errors(path))
    partial = dict(bad, settings={"inference_roi": [0, 0, 450, 300]})
    assert dict(profile_rows(partial))["Avisos"].startswith("Zona 'B' sale de la ROI")
    assert "Avisos" not in dict(profile_rows(dict(bad, settings={})))
