"""Tests for news → ChromaDB linking in swarm_researcher (B5 gap-fix)."""

from core_agent.skills import swarm_researcher as sr
from core_agent.skills.swarm_researcher import _link_news_to_insights


class _FakeSnapshot:
    """Patch target for get_snapshot."""

    def __init__(self, events):
        self._events = {"events": events}

    def get(self, key, default=None):
        return self._events.get(key, default)


def _setup(monkeypatch, events, saved):
    import core_agent.core.snapshot_cache as sc

    monkeypatch.setattr(sc, "get_snapshot", lambda: _FakeSnapshot(events), raising=False)
    monkeypatch.setattr(sr, "save_racing_insight", lambda horse, insight, metadata: saved.append((horse, metadata)) or True, raising=False)


def test_link_matches_horse_name_in_title(monkeypatch):
    saved = []
    _setup(monkeypatch, {"e1": {
        "course": "Saratoga", "en": "USA: Saratoga",
        "runners": [{"name": "Jon Riggens"}],
    }}, saved)
    items = [{"id": "n1", "title": "Jon Riggens scratched at Saratoga", "summary": "", "published": "", "url": "http://x"}]
    linked = _link_news_to_insights(items)
    assert linked == 1
    horse, meta = saved[0]
    assert horse == "Jon Riggens"
    assert meta["source"] == "news"
    assert meta["region"] == "USA"


def test_link_matches_course_when_no_horse(monkeypatch):
    saved = []
    _setup(monkeypatch, {"e1": {
        "course": "Turffontein", "en": "South Africa: Turffontein",
        "runners": [{"name": "Unrelated Horse"}],
    }}, saved)
    items = [{"id": "n2", "title": "Going change expected at Turffontein today", "summary": "", "published": "", "url": ""}]
    linked = _link_news_to_insights(items)
    assert linked == 1
    horse, meta = saved[0]
    assert horse.startswith("track_")
    assert meta["region"] == "South Africa"


def test_no_link_without_match(monkeypatch):
    saved = []
    _setup(monkeypatch, {"e1": {"course": "York", "en": "UK/IRE: York", "runners": [{"name": "Item"}]}}, saved)
    items = [{"id": "n3", "title": "Completely unrelated football story", "summary": "", "published": "", "url": ""}]
    assert _link_news_to_insights(items) == 0
    assert saved == []


def test_short_names_not_matched(monkeypatch):
    """Horse names under 5 chars are too collision-prone — must not match."""
    saved = []
    _setup(monkeypatch, {"e1": {"course": "York", "en": "UK: York", "runners": [{"name": "Item"}]}}, saved)
    # 'item' is 4 chars — the word "item" appearing alone shouldn't match... but it's exactly 4.
    items = [{"id": "n4", "title": "An item of news about nothing racing related", "summary": "", "published": "", "url": ""}]
    linked = _link_news_to_insights(items)
    # 'item' has len 4 < 5 so skipped; no other match possible
    assert linked == 0


def test_duplicate_ids_linked_once(monkeypatch):
    saved = []
    _setup(monkeypatch, {"e1": {"course": "Curragh", "en": "IRE: Curragh", "runners": [{"name": "Howdyadoit"}]}}, saved)
    items = [{"id": "dup", "title": "Howdyadoit wins at the Curragh", "summary": "", "published": "", "url": ""},
             {"id": "dup", "title": "Howdyadoit wins at the Curragh", "summary": "", "published": "", "url": ""}]
    linked = _link_news_to_insights(items)
    assert linked == 1
    assert len(saved) == 1


def test_empty_items_short_circuit(monkeypatch):
    saved = []
    _setup(monkeypatch, {"e1": {"course": "Curragh", "en": "IRE: Curragh", "runners": [{"name": "Howdyadoit"}]}}, saved)
    assert _link_news_to_insights([]) == 0
    assert saved == []


def test_seen_path_persistence(tmp_path, monkeypatch):
    """With seen_path set, a second call skips already-linked ids (production dedupe)."""
    saved = []
    _setup(monkeypatch, {"e1": {"course": "Curragh", "en": "IRE: Curragh", "runners": [{"name": "Howdyadoit"}]}}, saved)
    seen = str(tmp_path / "seen.json")
    items = [{"id": "x1", "title": "Howdyadoit lands the Curragh handicap", "summary": "", "published": "", "url": ""}]
    assert _link_news_to_insights(items, seen_path=seen) == 1
    # Same items again → skipped via seen file
    assert _link_news_to_insights(items, seen_path=seen) == 0
    assert len(saved) == 1
