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


def test_lines_and_directions_use_the_same_roi_rule():
    lines = [{"name": "L", "points": [[700, 50], [800, 50]], "tolerance": 15}]
    errors, _ = config("lines", roi=[0, 0, 300, 300], lines=lines).geometry_findings()
    assert "Línea 'L'" in errors[0]
    _, warnings = config("directions", roi=[0, 0, 150, 300],
                         directions={"D": [[100, 50], [300, 50]]}).geometry_findings()
    assert "Dirección 'D'" in warnings[0] and 22 <= percent(warnings[0]) <= 30


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


def test_malformed_geometry_does_not_crash_the_findings():
    assert config(zones={"A": [[0, 0]], "B": box(0, 0, 10, 10)}).geometry_findings() == ([], [])


def test_wizard_blocks_a_bad_profile_and_summarises_warnings(tmp_path):
    import json
    bad = {"counting_mode": "zones", "zones": ZONES, "settings": {"inference_roi": [0, 0, 300, 300]}}
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(bad))
    assert any("fuera de la ROI" in error for error in profile_errors(path))
    partial = dict(bad, settings={"inference_roi": [0, 0, 450, 300]})
    assert dict(profile_rows(partial))["Avisos"].startswith("Zona 'B' sale de la ROI")
    assert "Avisos" not in dict(profile_rows(dict(bad, settings={})))
