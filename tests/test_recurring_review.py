import fcntl
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import recurring_review as review


@pytest.mark.parametrize("used,ready", [(0, True), (50, True), (95, False), (100, False), (105, False)])
def test_quota_respects_reserve(used, ready):
    assert review.quota_decision({"rateLimits": {"primary": {"usedPercent": used}}})["ready"] is ready


@pytest.mark.parametrize("snapshot", [None, {}, {"primary": {"usedPercent": "0"}},
                                     {"primary": {"usedPercent": float("nan")}},
                                     {"primary": {"usedPercent": True}}])
def test_unknown_quota_never_starts_work(snapshot):
    assert not review.quota_decision({"rateLimits": snapshot})["ready"]


def test_weekly_limit_and_account_limit_block_even_when_short_window_has_room():
    snapshot = {"primary": {"usedPercent": 10}, "secondary": {"usedPercent": 100}}
    assert not review.quota_decision({"rateLimits": snapshot})["ready"]
    snapshot["secondary"]["usedPercent"] = 10
    snapshot["spendControlReached"] = True
    assert not review.quota_decision({"rateLimits": snapshot})["ready"]


def test_codex_bucket_overrides_legacy_bucket():
    payload = {"rateLimits": {"primary": {"usedPercent": 0}},
               "rateLimitsByLimitId": {"codex": {"primary": {"usedPercent": 100}}}}
    assert not review.quota_decision(payload)["ready"]


def test_five_hour_slots_cross_midnight_without_daily_reset():
    start = 22 * 3600
    assert review.next_slot(start, start - 1) == start
    assert review.next_slot(start, start) == 27 * 3600
    assert review.next_slot(start, 28 * 3600) == 32 * 3600
    assert review.next_slot(start, 48 * 3600) == 52 * 3600


def test_skipped_attempt_is_not_retried_every_minute(tmp_path, monkeypatch):
    probe = Mock(return_value={"ready": False, "reason": "Cuota agotada"})
    monkeypatch.setattr(review, "preflight", probe)
    monkeypatch.setattr(review.subprocess, "Popen", Mock(side_effect=AssertionError("No agent")))
    settings = {"start": 100, "codex": "unused"}
    assert review.run_due(settings, tmp_path, now=100)["status"] == "skipped"
    assert review.run_due(settings, tmp_path, now=160)["status"] == "waiting"
    assert review.run_due(settings, tmp_path, now=100 + review.INTERVAL)["status"] == "skipped"
    assert probe.call_count == 2


def test_pause_and_lock_prevent_quota_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "preflight", Mock(side_effect=AssertionError("No probe")))
    settings = {"start": 0}
    with (tmp_path / "lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert review.run_due(settings, tmp_path, now=100)["status"] == "busy"
    (tmp_path / "PAUSED").touch()
    assert review.run_due(settings, tmp_path, now=100)["status"] == "paused"


def test_low_disk_and_unavailable_quota_skip(tmp_path, monkeypatch):
    monkeypatch.setattr(review.shutil, "disk_usage", lambda _: SimpleNamespace(free=100))
    probe = Mock(side_effect=TimeoutError("Sin conexión"))
    monkeypatch.setattr(review, "read_quota", probe)
    assert not review.preflight({"codex": "unused"})["ready"]
    probe.assert_not_called()
    monkeypatch.setattr(review.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024 ** 3))
    assert review.preflight({"codex": "unused"})["reason"] == "Sin conexión"


def test_crontab_preserves_other_tasks_and_install_is_idempotent():
    existing = 'MAILTO=""\n15 2 * * * /usr/bin/true\n'
    installed = review.managed_crontab(existing, "* * * * * new-task")
    assert installed.startswith(existing)
    assert review.managed_crontab(installed, "* * * * * new-task") == installed
    assert review.managed_crontab(installed, None) == existing
    with pytest.raises(ValueError):
        review.managed_crontab(existing + review.BEGIN, "new-task")


def test_denied_crontab_read_never_replaces_existing_jobs(monkeypatch):
    command = Mock(return_value=SimpleNamespace(returncode=1, stdout="", stderr="Operation not permitted"))
    monkeypatch.setattr(review.subprocess, "run", command)
    with pytest.raises(RuntimeError):
        review.install({"codex": "unused"})
    command.assert_called_once()


def test_ready_job_uses_sandbox_prompt_and_saves_report(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "preflight", lambda _: {"ready": True})
    process = Mock(returncode=0)
    process.poll.return_value = 0
    launcher = Mock(return_value=process)
    monkeypatch.setattr(review.subprocess, "Popen", launcher)
    state = review.run_due({"start": 0, "codex": "/codex"}, tmp_path, now=100)
    assert state["status"] == "finished"
    command = launcher.call_args.args[0]
    assert command[:6] == ["/codex", "-a", "never", "-s", "workspace-write", "exec"]
    process.communicate.assert_called_once_with(review.PROMPT.read_bytes(), timeout=45 * 60)
    assert json.loads((tmp_path / "state.json").read_text())["next_run"] == review.INTERVAL
