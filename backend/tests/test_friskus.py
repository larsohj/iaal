import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.scrapers.friskus_scraper import FriskusScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestFriskusScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "friskus_page1.json") as f:
            fixture = json.load(f)

        # Sett last_page=1 slik at scraperen kun henter én side
        fixture["meta"]["last_page"] = 1

        scraper = FriskusScraper()

        with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
            events = scraper.scrape()

        # 3 events i fixture, men 3 kommuner med same mock → dedupliseres
        assert len(events) == 3

        first = events[0]
        assert first.source == "friskus"
        assert first.source_id.startswith("friskus-")
        assert first.title == "Påskeeggjakt - i Moa bibliotek"
        assert first.organizer == "Moa Bibliotek"
        assert first.start_at is not None
        assert "friskus.com/events/" in first.url

    def test_maps_age_groups(self):
        with open(FIXTURES / "friskus_page1.json") as f:
            fixture = json.load(f)
        fixture["meta"]["last_page"] = 1

        scraper = FriskusScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
            events = scraper.scrape()

        first = events[0]
        assert "children" in first.age_groups
        assert "family" in first.age_groups

    def test_maps_is_free(self):
        with open(FIXTURES / "friskus_page1.json") as f:
            fixture = json.load(f)
        fixture["meta"]["last_page"] = 1

        scraper = FriskusScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
            events = scraper.scrape()

        # Første event: is_free=false, andre: is_free=true
        assert events[0].is_free is False
        assert events[1].is_free is True

    def test_dnt_event_gets_friluftsliv_tag(self):
        fixture = {
            "data": [{
                "id": "test-dnt-1",
                "name": "DNT-tur til Sukkertoppen",
                "start_at": "2026-04-01T10:00:00+0200",
                "end_at": "2026-04-01T15:00:00+0200",
                "is_free": True,
                "is_recurring": False,
                "organization": {"name": "DNT Sunnmøre"},
                "age_group": [],
                "event_source": "dnt",
                "slug": "dnt-tur-sukkertoppen",
            }],
            "meta": {"total": 1, "page": 1, "last_page": 1, "per_page": 15},
        }

        scraper = FriskusScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
            events = scraper.scrape()

        assert len(events) == 1
        assert "friluftsliv" in events[0].tags
        assert "tur" in events[0].tags
