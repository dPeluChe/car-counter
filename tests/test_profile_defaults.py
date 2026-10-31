from pathlib import Path
import shlex
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from carcounter.app_config import AppConfig, SAHIConfig
from carcounter.runtime import load_sahi, resolve_runtime_config


@pytest.mark.parametrize("target", ["run", "run-full"])
@pytest.mark.parametrize("video", [None, "clips/other video.mp4"])
def test_make_run_preserves_profile_video_unless_explicit(target, video):
    command = ["make", "--no-print-directory", "-n", target]
    if video is not None:
        command.append(f"VIDEO={video}")
    import os
    environment = dict(os.environ)
    for key in ("VIDEO", "MAKEFLAGS", "MFLAGS", "MAKELEVEL"):
        environment.pop(key, None)
    output = subprocess.check_output(command, text=True, env=environment,
                                     cwd=Path(__file__).resolve().parents[1])
    args = shlex.split(output.replace("\\\n", " "))
    if video is None:
        assert "--video" not in args
    else:
        assert args[args.index("--video") + 1] == video


@pytest.mark.parametrize("settings", [None, {}, {"enabled": False}, {"enabled": True}])
@pytest.mark.parametrize("no_sahi", [False, True])
def test_sahi_activation_matches_typed_profile_and_runtime(monkeypatch, settings, no_sahi):
    import sahi

    config = {} if settings is None else {"sahi": settings}
    enabled = bool(settings and settings.get("enabled"))
    typed = AppConfig.from_dict(config)
    assert typed.sahi.enabled is enabled
    assert AppConfig.from_dict(typed.to_dict()).sahi.enabled is enabled
    assert SAHIConfig().enabled is False
    args = SimpleNamespace(detector="yolo", video=None, model=None, imgsz=None,
                           no_sahi=no_sahi)
    cfg = resolve_runtime_config(config, args)
    loader = Mock(return_value=object())
    monkeypatch.setattr(sahi.AutoDetectionModel, "from_pretrained", loader)
    model, predict, active = load_sahi(args, cfg, "yolo", "cpu")
    assert active is (enabled and not no_sahi)
    assert loader.called is active
    assert (model is not None) is active
    assert (predict is not None) is active


def test_explicit_video_override_and_profile_video():
    config = {"video_path": "calibrated.mp4"}
    args = SimpleNamespace(detector="yolo", video=None, model=None, imgsz=None)
    assert resolve_runtime_config(config, args)["video_path"] == "calibrated.mp4"
    args.video = "override.mp4"
    assert resolve_runtime_config(config, args)["video_path"] == "override.mp4"
