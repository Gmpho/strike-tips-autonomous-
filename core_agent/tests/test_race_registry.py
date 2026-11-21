"""Durable race registry: no flicker on partial fetches, no resurrection.

Carry-forward from the previous snapshot alone let a race vanish after two
missed cycles and reappear when a late GetEvent succeeded. The registry keeps
each race's last-good body for the whole meeting and tombstones races whose
off-time has genuinely passed.
"""

import json
import time

import pytest

from core_agent.core import snapshot_writer as sw


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(sw, "RACE_REGISTRY_PATH", tmp_path / "registry.json")


def _race(expires_in=3600, number=1):
    return {
        "en": "Vaal",
        "raceNumber": number,
        "runners": [{"name": "Comet", "odds": 2.5}],
        "expires_at": time.time() + expires_in,
    }


def test_race_survives_two_consecutive_missing_cycles():
    first = sw.merge_registry_events({"events": {"a": _race()}})
    assert set(first["events"]) == {"a"}

    second = sw.merge_registry_events({"events": {}})
    third = sw.merge_registry_events({"events": {}})

    assert set(second["events"]) == {"a"}
    assert set(third["events"]) == {"a"}, "previous-only carry-forward used to drop it here"
    assert third["events"]["a"]["runners"][0]["odds"] == 2.5


def test_expired_race_is_not_readded_even_when_fetched_again():
    sw.merge_registry_events({"events": {"a": _race(expires_in=1)}})

    path = sw.RACE_REGISTRY_PATH
    registry = json.loads(path.read_text())
    registry["events"]["a"]["expires_at"] = time.time() - 10
    path.write_text(json.dumps(registry))

    after_expiry = sw.merge_registry_events({"events": {"a": _race(expires_in=3600)}})
    assert "a" not in after_expiry["events"], "an off-time-passed race must leave the card"
    registry = json.loads(path.read_text())
    assert "a" in registry["tombstones"]

    late_success = sw.merge_registry_events({"events": {"a": _race(expires_in=3600)}})
    assert "a" not in late_success["events"], "a late GetEvent must not resurrect it"


def test_tombstones_are_pruned_after_a_day():
    sw.merge_registry_events({"events": {}})
    path = sw.RACE_REGISTRY_PATH
    registry = json.loads(path.read_text())
    registry["tombstones"] = {"old": time.time() - 25 * 3600}
    path.write_text(json.dumps(registry))

    sw.merge_registry_events({"events": {}})

    registry = json.loads(path.read_text())
    assert "old" not in registry["tombstones"]


def test_registry_keeps_the_latest_good_body():
    sw.merge_registry_events({"events": {"a": _race(number=1)}})
    sw.merge_registry_events({"events": {"a": _race(number=2)}})

    registry = json.loads(sw.RACE_REGISTRY_PATH.read_text())
    assert registry["events"]["a"]["event"]["raceNumber"] == 2


def test_finished_race_is_never_restored():
    sw.merge_registry_events({"events": {"a": _race()}})
    path = sw.RACE_REGISTRY_PATH
    registry = json.loads(path.read_text())
    registry["events"]["a"]["event"]["isFinished"] = True
    path.write_text(json.dumps(registry))

    out = sw.merge_registry_events({"events": {}})

    assert "a" not in out["events"]
