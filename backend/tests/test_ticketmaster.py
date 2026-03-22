from unittest.mock import MagicMock, patch

from backend.scrapers.ticketmaster_scraper import TicketmasterScraper


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestTicketmasterScraper:
    def test_skips_when_no_api_key(self):
        scraper = TicketmasterScraper()
        scraper.api_key = ""
        events = scraper.scrape()
        assert events == []

    def test_parses_events(self):
        fixture = {
            "_embedded": {
                "events": [{
                    "id": "Z698xZ2qZ17",
                    "name": "Stor Konsert",
                    "dates": {"start": {"dateTime": "2026-06-15T19:00:00Z"}},
                    "url": "https://www.ticketmaster.no/event/stor-konsert",
                    "images": [{"url": "https://img.tm.no/test.jpg"}],
                    "priceRanges": [{"min": 450, "max": 850, "currency": "NOK"}],
                    "classifications": [{"genre": {"name": "Rock"}}],
                    "_embedded": {
                        "venues": [{
                            "name": "Parken kulturhus",
                            "address": {"line1": "Keiser Wilhelms gate 22"},
                            "city": {"name": "Ålesund"},
                            "location": {"latitude": "62.47", "longitude": "6.15"},
                        }]
                    },
                }]
            },
            "page": {"totalPages": 1, "number": 0},
        }

        scraper = TicketmasterScraper()
        scraper.api_key = "test-key"
        with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
            events = scraper.scrape()

        assert len(events) == 1
        e = events[0]
        assert e.source == "ticketmaster"
        assert e.source_id == "ticketmaster-Z698xZ2qZ17"
        assert e.title == "Stor Konsert"
        assert e.price_text == "NOK 450–850"
        assert e.is_free is False
        assert e.location_name == "Parken kulturhus"
        assert e.latitude == 62.47
        assert "rock" in e.tags

    def test_handles_empty_response(self):
        fixture = {"page": {"totalPages": 1, "number": 0}}

        scraper = TicketmasterScraper()
        scraper.api_key = "test-key"
        with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
            events = scraper.scrape()

        assert events == []
