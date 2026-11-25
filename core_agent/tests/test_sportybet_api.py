import json
from unittest.mock import patch

import pytest

from core_agent.skills.parsers.sportybet_api import SportyBetAPI, normalize_sportybet_odds


class TestSportyBetOddsNormalization:
    def test_odds_normalization(self):
        assert normalize_sportybet_odds(None) == "SP"
        assert normalize_sportybet_odds(0) == "SP"
        assert normalize_sportybet_odds(1.0) == "SP"
        assert normalize_sportybet_odds(-5.0) == "SP"
        assert normalize_sportybet_odds("SP") == "SP"
        assert normalize_sportybet_odds(2.5) == 2.5
        assert normalize_sportybet_odds(14.0) == 14.0
        assert normalize_sportybet_odds("4.40") == 4.40


def _fake_urlopen(body: dict, status: int = 200):
    """Stand-in for urllib.request.urlopen returning ``body`` as JSON."""

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(body).encode("utf-8")

        @property
        def status(self):
            return status

    return lambda request, timeout=None: _Response()


@pytest.fixture
def mock_api():
    return SportyBetAPI()


class TestSportyBetMeetings:
    def test_fetch_meetings_sync(self, mock_api):
        payload = {
            "data": {
                "meetingsBetween": [
                    {
                        "id": "m1",
                        "name": "Fairview",
                        "track": {"name": "Fairview", "country": "South Africa"},
                        "races": [{"id": "r1", "number": 1, "status": "OPEN"}],
                    }
                ]
            }
        }
        with patch(
            "core_agent.skills.parsers.sportybet_api.urllib.request.urlopen",
            _fake_urlopen(payload),
        ):
            meetings = mock_api.fetch_meetings_sync(
                "2026-11-24T00:00:00Z", "2026-11-25T00:00:00Z"
            )

        assert len(meetings) == 1
        assert meetings[0]["name"] == "Fairview"


@pytest.mark.asyncio
class TestSportyBetSnapshot:
    async def test_get_snapshot_format(self, mock_api):
        mock_meetings = [
            {
                "id": "m1",
                "name": "Fairview",
                "track": {"name": "Fairview", "country": "South Africa"},
                "races": [{"id": "r1", "number": 1}],
            }
        ]
        mock_cards = [
            {
                "name": "Fairview",
                "track": {"name": "Fairview", "country": "South Africa"},
                "races": [
                    {
                        "id": "r1",
                        "number": 1,
                        "status": "OPEN",
                        "start_at": "2026-11-24T12:30:00Z",
                        "runners": [
                            {
                                "id": "runner1",
                                "tab_no": 1,
                                "name": "SPEED RUNNER",
                                "barrier": 2,
                                "jockey": "C Zackey",
                                "trainer": "D G Smith",
                                "status": "NORMAL",
                                "prices": [
                                    {
                                        "bet_type": "WIN",
                                        "price": 3.5,
                                        "product": {"is_fixed": True},
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        with patch.object(mock_api, "fetch_meetings_sync", return_value=mock_meetings), \
             patch.object(mock_api, "fetch_race_cards_sync", return_value=mock_cards):
            snapshot = await mock_api.get_snapshot_format(country="South Africa")

            assert snapshot["fetch_ok"] is True
            assert snapshot["count"] == 1
            eid = "sportybet_r1"
            assert eid in snapshot["events"]
            ev = snapshot["events"][eid]
            assert ev["course"] == "Fairview"
            assert ev["raceNumber"] == 1
            assert len(ev["runners"]) == 1
            r = ev["runners"][0]
            assert r["name"] == "SPEED RUNNER"
            assert r["odds"] == 3.5
            assert r["jockeyName"] == "C Zackey"


@pytest.mark.asyncio
async def test_top_tip_is_taken_from_runner_comments(mock_api):
    """The racecard's 'Top Tip' copy lives in runner_comments, not timeform."""
    meetings = [
        {
            "id": "m1",
            "track": {"name": "Kenilworth", "country": "ZA"},
            "races": [{"id": "r1", "number": 1}],
        }
    ]
    cards = [
        {
            "name": "Kenilworth",
            "track": {"name": "Kenilworth", "country": "ZA"},
            "races": [
                {
                    "id": "r1",
                    "number": 1,
                    "runners": [
                        {
                            "id": "runner1",
                            "tab_no": 3,
                            "name": "ONE DAWN",
                            "jockey": "Craig Zackey",
                            "trainer": "Dean Kannemeyer",
                            "status": "STARTER",
                            "prices": [
                                {
                                    "bet_type": "racingFutureWin",
                                    "price": 3.9,
                                    "product": {"is_fixed": True},
                                }
                            ],
                            "runner_comments": [
                                {
                                    "comment": " In the money when 3rd last run at the track. ",
                                    "source": "ILB",
                                    "updated_at": "2026-11-25T11:07:51Z",
                                },
                                {
                                    "comment": "In the money when 3rd last run at the track.",
                                    "source": "ILB",
                                    "updated_at": "2026-11-25T10:00:00Z",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    with patch.object(mock_api, "fetch_meetings_sync", return_value=meetings), \
         patch.object(mock_api, "fetch_race_cards_sync", return_value=cards):
        snap = await mock_api.get_snapshot_format(country="South Africa")

    runner = snap["events"]["sportybet_r1"]["runners"][0]
    assert runner["timeForm"] == "In the money when 3rd last run at the track."
    assert runner["jockeyName"] == "Craig Zackey"
    assert runner["trainerName"] == "Dean Kannemeyer"
