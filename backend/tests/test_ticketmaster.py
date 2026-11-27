from unittest.mock import MagicMock, patch

import pytest

from backend.generate import normalize_events
from backend.scrapers.ticketmaster_scraper import TicketmasterScraper


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _scrape_events(*items):
    scraper = TicketmasterScraper()
    scraper.api_key = "test-key"
    fixture = {"_embedded": {"events": list(items)}, "page": {"totalPages": 1}}
    with patch.object(scraper, "_get", return_value=_mock_response(fixture)):
        return scraper.scrape()


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
        assert e.start_at == "2026-06-15T19:00:00Z"
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

    @pytest.mark.parametrize(
        ("start", "expected"),
        [
            ({"localDate": "2027-06-18", "localTime": "16:30:00"}, "2027-06-18T16:30:00"),
            ({"localDate": "2027-06-18"}, "2027-06-18"),
            ({"localDate": "2027-06-18", "localTime": "00:00:00"}, "2027-06-18T00:00:00"),
            ({"localDate": "2027-06-18", "localTime": "25:00"}, "2027-06-18"),
            ({"localDate": "2027-02-30"}, None),
            ({"localDate": "2027-06-18", "localTime": "00:00:00", "noSpecificTime": True}, "2027-06-18"),
            ({"dateTime": "2027-06-17T22:00:00Z", "timeTBA": True}, "2027-06-18"),
            ({"dateTime": "2027-06-17T22:00:00Z", "dateTBA": True}, None),
            ({"localDate": "2027-06-18", "dateTBD": True}, None),
            ({}, None),
        ],
    )
    def test_start_date_precision_survives_json_normalization(self, start, expected):
        events = _scrape_events({"id": "event", "name": "Konsert", "dates": {"start": start}})

        assert len(events) == 1
        assert normalize_events([events[0].to_dict()])[0]["start_at"] == expected

    @pytest.mark.parametrize(
        ("end", "expected"),
        [
            ({"dateTime": "2027-06-19T20:00:00Z"}, "2027-06-19T22:00:00"),
            ({"localDate": "2027-06-19", "localTime": {"hourOfDay": 22, "minuteOfHour": 30}}, "2027-06-19T22:30:00"),
            ({"localDate": "2027-06-19", "noSpecificTime": True}, "2027-06-19"),
            ({}, None),
        ],
    )
    def test_end_date_precision_survives_json_normalization(self, end, expected):
        events = _scrape_events({"id": "event", "dates": {"end": end}})

        assert normalize_events([events[0].to_dict()])[0]["end_at"] == expected

    def test_alesund_live_products_become_festival_and_days(self):
        # ID-ene og navnene er fra arrangementsfilen. Datoobjektene er testdata.
        items = [
            {
                "id": "Z698xZb_Z1k7wbt39",
                "name": "Ålesund Live | Festivalpass",
                "url": "https://www.ticketmaster.no/event/132629497",
            },
            {
                "id": "Z698xZb_Z1kuPGvuk",
                "name": "Ålesund Live | Fredagspass",
                "dates": {"start": {"localDate": "2027-06-18", "noSpecificTime": True}},
            },
            {
                "id": "Z698xZb_Z16vb_Z0ZF",
                "name": "Ålesund Live | Lørdagspass",
            },
            {
                "id": "Z698xZb_Z1k39PwFt",
                "name": "Ålesund Live | Oppgradering fra Dagspass til Festivalpass",
                "dates": {"start": {"localDate": "2027-06-18", "localTime": "16:00:00"}},
            },
            {"id": "other", "name": "Festivalpass – Annen festival"},
        ]

        events = _scrape_events(*items)
        output = normalize_events([event.to_dict() for event in events])

        assert [(e["title"], e["start_at"], e["end_at"]) for e in output] == [
            ("Ålesund Live", "2027-06-18", "2027-06-19"),
            ("Ålesund Live – fredag", "2027-06-18T16:30:00", None),
            ("Ålesund Live – lørdag", "2027-06-19T15:00:00", None),
            ("Festivalpass – Annen festival", None, None),
        ]
        assert [e["source_id"] for e in output[:3]] == [
            f"ticketmaster-{item['id']}" for item in items[:3]
        ]
        assert output[0]["url"] == items[0]["url"]

    def test_alesund_live_fallback_respects_changed_discovery_dates(self):
        events = _scrape_events(
            {"id": "Z698xZb_Z1k7wbt39", "dates": {"start": {"localDate": "2027-06-25"}}},
            {"id": "Z698xZb_Z1kuPGvuk", "dates": {"start": {"localDate": "2027-06-25"}}},
            {"id": "Z698xZb_Z16vb_Z0ZF", "dates": {"start": {"dateTBA": True}}},
        )

        assert [(e.start_at, e.end_at) for e in events] == [
            ("2027-06-25", None),
            ("2027-06-25", None),
            (None, None),
        ]
