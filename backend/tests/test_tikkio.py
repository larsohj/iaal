import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.scrapers.tikkio_scraper import TikkioScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(text="", json_data=None):
    resp = MagicMock()
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestTikkioScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "tikkio_ld_json.json") as f:
            ld_json = json.load(f)

        html = f'<html><head><script type="application/ld+json">{json.dumps(ld_json)}</script></head></html>'

        scraper = TikkioScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) == 3
        first = events[0]
        assert first.source == "tikkio"
        assert first.source_id.startswith("tikkio-")
        assert first.title != ""
        assert first.start_at is not None

    def test_maps_location_and_price(self):
        ld_json = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": {
                "0": {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "Event",
                        "name": "Testkonsert",
                        "startDate": "2026-04-01T20:00:00+02:00",
                        "location": {
                            "@type": "Place",
                            "name": "Terminalen",
                            "geo": {"latitude": "62.47", "longitude": "6.15"},
                        },
                        "offers": {
                            "price": "350.00",
                            "priceCurrency": "NOK",
                            "url": "https://tikkio.com/events/12345-testkonsert",
                        },
                        "organizer": {"name": "Jazzsirkelen"},
                        "image": "https://cdn.tikkio.com/test.jpg",
                    },
                }
            },
        }
        html = f'<html><head><script type="application/ld+json">{json.dumps(ld_json)}</script></head></html>'

        scraper = TikkioScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) == 1
        e = events[0]
        assert e.location_name == "Terminalen"
        assert e.latitude == 62.47
        assert e.longitude == 6.15
        assert e.price_text == "NOK 350.00"
        assert e.is_free is False
        assert e.organizer == "Jazzsirkelen"

    def test_free_event(self):
        ld_json = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": {
                "0": {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "Event",
                        "name": "Gratis event",
                        "startDate": "2026-04-01T20:00:00+02:00",
                        "location": {"name": "Somewhere"},
                        "offers": {"price": "0.00", "priceCurrency": "NOK"},
                    },
                }
            },
        }
        html = f'<html><head><script type="application/ld+json">{json.dumps(ld_json)}</script></head></html>'

        scraper = TikkioScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert events[0].is_free is True
        assert events[0].price_text is None
