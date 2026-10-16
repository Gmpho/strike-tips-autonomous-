"""Single-owner Europe scan (Oct-2026).

The in-app scheduler's europe_scan_job fires at 12:30 SAST but never
stamps /app/data/.europe_scan_date, so the odds-monitor heartbeat
(~12:33, which does stamp) always ran a SECOND Europe scan the same day:
twin Groq stampedes, two digests, and the second landing on an exhausted
provider quota (only the first of five meetings analysed).

Per-side SCHEDULER_DISABLE is the mechanism. docker already opts out;
Modal must too so the heartbeat is sole owner.
"""
import pytest

# apscheduler is in requirements.txt (Docker) but absent on some bare hosts.
pytest.importorskip("apscheduler")

from core_agent.core.scheduler import StrikeTipsScheduler  # noqa: E402


def _job_ids(monkeypatch, disable):
    monkeypatch.setenv("SCHEDULER_DISABLE", disable)
    sched = StrikeTipsScheduler(data_dir="/tmp")
    return {j.id for j in sched.scheduler.get_jobs()}


def test_env_silences_only_the_europe_twin(monkeypatch):
    ids = _job_ids(monkeypatch, "europe_scan")
    assert "europe_scan" not in ids
    assert "daily_scan" in ids
    assert "check_results" in ids


def test_europe_scan_registered_when_not_disabled(monkeypatch):
    ids = _job_ids(monkeypatch, "")
    assert "europe_scan" in ids


def test_comma_list_ignores_padding(monkeypatch):
    ids = _job_ids(monkeypatch, " europe_scan , continuous_scan ")
    assert "europe_scan" not in ids
    assert "continuous_scan" not in ids
    assert "daily_scan" in ids
