import pytest
from unittest.mock import MagicMock, patch

from core_agent.skills.parsers.soccershop_api import SoccerShopAPI, normalize_soccershop_odds


class TestSoccerShopOddsNormalization:
    """Test suite for SoccerShop odds normalizer, specially verifying sub-1.0 net profit prices."""

    def test_sp_cases(self):
        assert normalize_soccershop_odds(None) == "SP"
        assert normalize_soccershop_odds(0) == "SP"
        assert normalize_soccershop_odds(-1.5) == "SP"
        assert normalize_soccershop_odds("SP") == "SP"
        assert normalize_soccershop_odds("") == "SP"

    def test_net_profit_odds(self):
        # 0.80 -> 1.80 (4/5)
        assert normalize_soccershop_odds(0.80) == 1.80
        # 0.25 -> 1.25 (1/4)
        assert normalize_soccershop_odds(0.25) == 1.25
        # 0.50 -> 1.50 (1/2)
        assert normalize_soccershop_odds(0.5) == 1.50
        # 0.95 -> 1.95
        assert normalize_soccershop_odds("0.95") == 1.95

    def test_european_decimal_odds(self):
        # Standard decimal odds
        assert normalize_soccershop_odds(1.80) == 1.80
        assert normalize_soccershop_odds(5.0) == 5.0
        assert normalize_soccershop_odds(67.0) == 67.0
        assert normalize_soccershop_odds("15.5") == 15.5


@pytest.mark.asyncio
class TestSoccerShopAPIParsing:
    """Test suite for SoccerShopAPI parser."""

    @pytest.fixture
    def mock_api(self):
        mock_session = MagicMock()
        api = SoccerShopAPI(session=mock_session)
        return api

    def test_fetch_all_events_sync(self, mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"uuid": "ev1", "countryCode": "ZA", "bettingCloseTime": "2026-11-24T15:00:00Z"},
            {"uuid": "ev2", "countryCode": "GB", "bettingCloseTime": "2026-11-24T16:00:00Z"},
        ]
        mock_api._session.get.return_value = mock_response

        events = mock_api.fetch_all_events_sync()
        assert len(events) == 2
        assert events[0]["uuid"] == "ev1"

    def test_fetch_event_batch_sync(self, mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ev1": {
                "track": "Fairview",
                "raceNumber": 1,
                "countryCode": "ZA",
                "bettingCloseTime": "2026-11-24T15:00:00+02:00",
                "horses": [
                    {"id": "1", "name": "FAST RUNNER", "price": 0.80, "placePrice": 0.20, "clothNumber": 1},
                    {"id": "2", "name": "LONG SHOT", "price": 15.0, "placePrice": 3.5, "clothNumber": 2},
                ],
            }
        }
        mock_api._session.post.return_value = mock_response

        batch = mock_api.fetch_event_batch_sync(["ev1"])
        assert "ev1" in batch
        assert batch["ev1"]["track"] == "Fairview"
        assert len(batch["ev1"]["horses"]) == 2

    async def test_get_snapshot_format(self, mock_api):
        mock_events = [
            {"uuid": "ev1", "countryCode": "ZA", "bettingCloseTime": "2026-11-24T15:00:00+02:00"},
            {"uuid": "ev2", "countryCode": "GB", "bettingCloseTime": "2026-11-24T16:00:00+02:00"},
        ]
        mock_batch = {
            "ev1": {
                "uuid": "ev1",
                "track": "Fairview Polytrack",
                "raceNumber": 8,
                "countryCode": "ZA",
                "bettingCloseTime": "2026-11-24T15:00:00+02:00",
                "status": "Dormant",
                "horses": [
                    {"id": "101", "name": "FAVOURITE", "price": 0.80, "placePrice": 0.20, "clothNumber": 1, "jockey": "C Zackey", "trainer": "D G Smith"},
                    {"id": "102", "name": "OUTSIDER", "price": 21.0, "placePrice": 5.0, "clothNumber": 2, "jockey": "R Munger", "trainer": "M Houdalakis"},
                ],
            }
        }

        with patch.object(mock_api, "fetch_all_events_sync", return_value=mock_events), \
             patch.object(mock_api, "fetch_event_batch_sync", return_value=mock_batch):
            snapshot = await mock_api.get_snapshot_format(country_code="ZA")

            assert snapshot["fetch_ok"] is True
            assert snapshot["count"] == 1
            event_id = "soccershop_ev1"
            assert event_id in snapshot["events"]

            ev = snapshot["events"][event_id]
            assert ev["course"] == "Fairview Polytrack"
            assert ev["raceNumber"] == 8
            assert ev["t"] == "15:00"
            assert len(ev["runners"]) == 2

            # Check normalized odds: 0.80 -> 1.80
            r1 = ev["runners"][0]
            assert r1["name"] == "FAVOURITE"
            assert r1["odds"] == 1.80
            assert r1["place_odds"] == 1.20

            # Check standard decimal odds: 21.0
            r2 = ev["runners"][1]
            assert r2["name"] == "OUTSIDER"
            assert r2["odds"] == 21.0
            assert r2["place_odds"] == 5.0

    async def test_get_races_typed_objects(self, mock_api):
        mock_events = [{"uuid": "ev1", "countryCode": "ZA"}]
        mock_batch = {
            "ev1": {
                "uuid": "ev1",
                "track": "Turffontein",
                "raceNumber": 3,
                "countryCode": "ZA",
                "bettingCloseTime": "2026-11-24T13:30:00+02:00",
                "horses": [
                    {"id": "1", "name": "SPEEDY", "price": 2.5, "clothNumber": 4, "status": "Runner"}
                ],
            }
        }
        with patch.object(mock_api, "fetch_all_events_sync", return_value=mock_events), \
             patch.object(mock_api, "fetch_event_batch_sync", return_value=mock_batch):
            races = await mock_api.get_races()
            assert len(races) == 1
            assert races[0].track == "Turffontein"
            assert races[0].race_number == 3
            assert len(races[0].runners) == 1
            assert races[0].runners[0].odds_decimal == 2.5
            assert races[0].runners[0].barrier == 4
