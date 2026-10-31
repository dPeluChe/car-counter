def zone_role_errors(zones, roles):
    if not roles:
        return []
    if not isinstance(roles, dict):
        return ["zone_roles debe ser un objeto"]
    errors = []
    if set(roles) != set(zones):
        errors.append("Asigna entrada o salida y acceso a todas las zonas")
    kinds = set()
    for name, spec in roles.items():
        if not isinstance(spec, dict):
            errors.append(f"Rol inválido en {name}")
            continue
        role = spec.get("role")
        if role not in ("entry", "exit"):
            errors.append(f"{name}: role debe ser entry o exit")
        else:
            kinds.add(role)
        access = spec.get("access")
        if not isinstance(access, str) or not access.strip():
            errors.append(f"{name}: indica el nombre del acceso")
    if kinds != {"entry", "exit"}:
        errors.append("Se requiere al menos una entrada y una salida")
    return errors


def update_access_route(counter, track_id, zone, cls_name):
    info = counter.tracks_info.get(track_id)
    if info is None:
        counter.total_vehicles_ever += 1
        info = dict(state="new", origin=None, **{"class": cls_name},
                    zone_frames=0, dest_zone=None, dest_frames=0)
        counter.tracks_info[track_id] = info
    info["last_seen_frame"] = counter.frame_count
    if info["state"] == "done":
        return
    role = counter.zone_roles.get(zone, {}).get("role")
    if info["state"] in ("new", "origin"):
        if info["state"] == "origin" and zone == info["origin"]:
            info["zone_frames"] += 1
            return
        if info["state"] == "origin" and info["zone_frames"] >= counter.min_origin_frames:
            info["state"] = "transit"
        elif role == "entry":
            info.update(state="origin", origin=zone, zone_frames=1)
            return
        else:
            info.update(state="new", origin=None, zone_frames=0)
            return
    if role != "exit":
        info.update(dest_zone=None, dest_frames=0)
        return
    if zone == info["dest_zone"]:
        info["dest_frames"] += 1
    else:
        info.update(dest_zone=zone, dest_frames=1)
    if info["dest_frames"] >= counter.min_dest_frames:
        counter._register_route(track_id, info["origin"], zone, info["class"])
