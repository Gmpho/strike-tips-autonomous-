import pytest
from unittest.mock import MagicMock, patch

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


@pytest.mark.asyncio
class TestSportyBetAPIParsing:
    @pytest.fixture
    def mock_api(self):
        mock_session = MagicMock()
        return SportyBetAPI(session=mock_session)

    def test_fetch_meetings_sync(self, mock_api):
        mock_api._session.post.return_value.status_code = 200
        mock_api._session.post.return_value.json.return_value = {
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
        meetings = mock_api.fetch_meetings_sync("2026-11-24T00:00:00Z", "2026-11-25T00:00:00Z")
        assert len(meetings) == 1
        assert meetings[0]["name"] == "Fairview"

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
                                    {"bet_type": "WIN", "price": 3.5, "product": {"is_fixed": True}}
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
