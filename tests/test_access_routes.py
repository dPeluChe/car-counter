import numpy as np
import pytest

from carcounter.access_routes import zone_role_errors
from carcounter.app_config import AppConfig
from carcounter.counting import VehicleCounter


def counter():
    zones = {name: np.array([[x, 0], [x + 10, 0], [x + 10, 10], [x, 10]])
             for name, x in (("north_in", 0), ("north_out", 20),
                             ("south_in", 40), ("south_out", 60))}
    roles = {name: dict(role="entry" if name.endswith("_in") else "exit",
                       access="Norte" if name.startswith("north") else "Sur")
             for name in zones}
    return VehicleCounter(zones, [], min_origin_frames=2, min_dest_frames=2, zone_roles=roles)


def observe(instance, positions):
    for frame, x in positions:
        instance.set_frame(frame)
        instance.update(1, x, 5, "car", "zones")


@pytest.mark.parametrize("destination,expected", [(65, "Norte → Sur"), (25, "Norte → Norte")])
def test_entry_exit_and_same_access_return(destination, expected):
    instance = counter()
    observe(instance, list(enumerate([5, 5, 100, destination, destination, destination], 1)))
    assert instance.routes_matrix == {expected: 1}
    event = instance.counting_events[0]
    assert event["origin_zone"] == "north_in"
    assert event["destination_zone"] == ("south_out" if destination == 65 else "north_out")
    assert event["frame"] == 5
    assert instance.get_track_data()[0]["origin"] == "Norte"


@pytest.mark.parametrize("positions", [
    [25, 25, 100, 65, 65],
    [5, 100, 65, 65],
    [5, 5, 100, 45, 45],
    [5, 5, 100],
    [5, 5, 65, 100, 65],
])
def test_exit_first_unconfirmed_entry_other_entry_and_incomplete_not_counted(positions):
    instance = counter()
    observe(instance, list(enumerate(positions, 1)))
    assert not instance.counting_events


def test_intermediate_entry_does_not_replace_confirmed_origin():
    instance = counter()
    observe(instance, list(enumerate([5, 5, 45, 45, 65, 65], 1)))
    assert instance.routes_matrix == {"Norte → Sur": 1}


def test_gap_resets_unconfirmed_exit():
    instance = counter()
    observe(instance, [(1, 5), (2, 5), (3, 65), (8, 65)])
    assert not instance.counting_events
    observe(instance, [(9, 65)])
    assert instance.counting_events[0]["frame"] == 9


def test_roles_roundtrip_and_incomplete_mapping_rejected():
    instance = counter()
    config = dict(zones={name: points.tolist() for name, points in instance.zones_np.items()},
                  zone_roles=instance.zone_roles)
    assert AppConfig.from_dict(config).to_dict()["zone_roles"] == instance.zone_roles
    assert not zone_role_errors(instance.zones_np, instance.zone_roles)
    roles = {"north_in": dict(role="entry", access="")}
    assert len(zone_role_errors(instance.zones_np, roles)) == 3
    with pytest.raises(ValueError):
        VehicleCounter(instance.zones_np, [], zone_roles=roles)
