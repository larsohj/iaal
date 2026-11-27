import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.generate import (
    run_scrapers, merge_with_existing, write_events_json,
    normalize_datetime, filter_past_events, normalize_events,
)
from backend.models import EventData


class TestRunScrapers:
    def test_collects_events_from_all_scrapers(self):
        """Sjekk at run_scrapers samler events fra alle scrapers som dicts."""
        mock_event = EventData(
            source="test", source_id="test-1", title="Test Event"
        )

        mock_scraper = MagicMock()
        mock_scraper.source_name = "test"
        mock_scraper.scrape.return_value = [mock_event]

        with patch("backend.generate.FriskusScraper", return_value=mock_scraper), \
             patch("backend.generate.VitiScraper", return_value=mock_scraper), \
             patch("backend.generate.TikkioScraper", return_value=mock_scraper), \
             patch("backend.generate.ParkenScraper", return_value=mock_scraper), \
             patch("backend.generate.BibliotekScraper", return_value=mock_scraper), \
             patch("backend.generate.BypatriotenScraper", return_value=mock_scraper), \
             patch("backend.generate.OdeonScraper", return_value=mock_scraper), \
             patch("backend.generate.TicketmasterScraper", return_value=mock_scraper), \
             patch("backend.generate.AafkScraper", return_value=mock_scraper):
            events, failed = run_scrapers()

        assert len(events) == 9
        assert failed == []
        assert all(isinstance(e, dict) for e in events)
        assert events[0]["source"] == "test"

    def test_records_failed_scrapers(self):
        ok_scraper = MagicMock()
        ok_scraper.source_name = "ok"
        ok_scraper.scrape.return_value = [
            EventData(source="ok", source_id="ok-1", title="OK")
        ]

        fail_scraper = MagicMock()
        fail_scraper.source_name = "fail"
        fail_scraper.scrape.side_effect = RuntimeError("nettverksfeil")

        with patch("backend.generate.FriskusScraper", return_value=ok_scraper), \
             patch("backend.generate.VitiScraper", return_value=fail_scraper), \
             patch("backend.generate.TikkioScraper", return_value=ok_scraper), \
             patch("backend.generate.ParkenScraper", return_value=ok_scraper), \
             patch("backend.generate.BibliotekScraper", return_value=ok_scraper), \
             patch("backend.generate.BypatriotenScraper", return_value=ok_scraper), \
             patch("backend.generate.OdeonScraper", return_value=ok_scraper), \
             patch("backend.generate.TicketmasterScraper", return_value=ok_scraper), \
             patch("backend.generate.AafkScraper", return_value=ok_scraper):
            events, failed = run_scrapers()

        assert len(events) == 8
        assert "fail" in failed


class TestNormalizeDatetime:
    def test_naive_datetime_unchanged(self):
        assert normalize_datetime("2026-04-01T19:00:00") == "2026-04-01T19:00:00"

    def test_plus_0200_stripped(self):
        assert normalize_datetime("2026-04-01T19:00:00+0200") == "2026-04-01T19:00:00"

    def test_plus_02_colon_00_stripped(self):
        assert normalize_datetime("2026-04-01T19:00:00+02:00") == "2026-04-01T19:00:00"

    def test_utc_converted_to_oslo_summer(self):
        # April = CEST (UTC+2)
        assert normalize_datetime("2026-04-01T17:00:00+0000") == "2026-04-01T19:00:00"

    def test_utc_z_converted_to_oslo_summer(self):
        assert normalize_datetime("2026-04-01T17:00:00.000Z") == "2026-04-01T19:00:00"

    def test_utc_converted_to_oslo_winter(self):
        # Januar = CET (UTC+1)
        assert normalize_datetime("2026-01-15T17:00:00+0000") == "2026-01-15T18:00:00"

    def test_plus_0100_winter(self):
        # CET allerede
        assert normalize_datetime("2026-01-15T18:00:00+0100") == "2026-01-15T18:00:00"

    def test_none_returns_none(self):
        assert normalize_datetime(None) is None

    def test_milliseconds_removed(self):
        assert normalize_datetime("2026-04-01T10:00:00.000Z") == "2026-04-01T12:00:00"


class TestFilterPastEvents:
    def test_removes_past_events(self):
        events = [
            {"source": "a", "start_at": "2020-01-01T10:00:00", "title": "gammel"},
            {"source": "b", "start_at": "2099-01-01T10:00:00", "title": "fremtidig"},
        ]
        result = filter_past_events(events)
        assert len(result) == 1
        assert result[0]["title"] == "fremtidig"

    def test_keeps_events_without_start(self):
        events = [
            {"source": "a", "title": "uten dato"},
            {"source": "b", "start_at": "2099-06-01T10:00:00", "title": "ok"},
        ]
        result = filter_past_events(events)
        assert len(result) == 2

    def test_empty_list(self):
        assert filter_past_events([]) == []


class TestNormalizeEvents:
    def test_normalizes_start_and_end(self):
        events = [
            {
                "source": "tikkio",
                "start_at": "2026-06-06T19:30:00+02:00",
                "end_at": "2026-06-06T23:00:00+02:00",
            },
        ]
        result = normalize_events(events)
        assert result[0]["start_at"] == "2026-06-06T19:30:00"
        assert result[0]["end_at"] == "2026-06-06T23:00:00"

    def test_handles_missing_fields(self):
        events = [{"source": "test"}]
        result = normalize_events(events)
        assert result[0].get("start_at") is None
        assert result[0].get("end_at") is None


class TestMergeWithExisting:
    def test_preserves_events_from_failed_sources(self, tmp_path):
        existing = {
            "events": [
                {"source": "friskus", "source_id": "friskus-1", "title": "Gammel"},
                {"source": "viti", "source_id": "viti-1", "title": "Viti OK"},
            ]
        }
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "events.json").write_text(json.dumps(existing))

        new_events = [{"source": "viti", "source_id": "viti-2", "title": "Ny Viti"}]
        failed = ["friskus"]

        with patch("backend.generate.OUTPUT_DIR", docs_dir):
            merged = merge_with_existing(new_events, failed)

        sources = [e["source"] for e in merged]
        assert "friskus" in sources
        assert "viti" in sources
        assert len(merged) == 2

    def test_no_merge_when_no_failures(self, tmp_path):
        new_events = [{"source": "viti", "source_id": "viti-1", "title": "Test"}]
        merged = merge_with_existing(new_events, [])
        assert merged == new_events

    def test_no_merge_when_no_existing_file(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        new_events = [{"source": "viti", "source_id": "viti-1", "title": "Test"}]
        with patch("backend.generate.OUTPUT_DIR", docs_dir):
            merged = merge_with_existing(new_events, ["friskus"])

        assert merged == new_events


class TestWriteEventsJson:
    def test_writes_valid_json(self, tmp_path):
        docs_dir = tmp_path / "docs"

        events = [
            {"source": "test", "source_id": "test-1", "title": "Testevent"},
            {"source": "test", "source_id": "test-2", "title": "Testevent 2"},
        ]

        with patch("backend.generate.OUTPUT_DIR", docs_dir):
            path = write_events_json(events, [])

        assert path.exists()

        with open(path) as f:
            data = json.load(f)

        assert data["total"] == 2
        assert data["failed_sources"] == []
        assert len(data["events"]) == 2
        assert "generated_at" in data

    def test_writes_utf8_norwegian_characters(self, tmp_path):
        docs_dir = tmp_path / "docs"

        events = [
            {"source": "test", "source_id": "t-1", "title": "Påskeeggjakt i Ålesund"},
        ]

        with patch("backend.generate.OUTPUT_DIR", docs_dir):
            path = write_events_json(events, [])

        content = path.read_text(encoding="utf-8")
        assert "Påskeeggjakt" in content
        assert "Ålesund" in content

    def test_records_failed_sources(self, tmp_path):
        docs_dir = tmp_path / "docs"

        with patch("backend.generate.OUTPUT_DIR", docs_dir):
            path = write_events_json([], ["friskus", "viti"])

        with open(path) as f:
            data = json.load(f)

        assert data["failed_sources"] == ["friskus", "viti"]
        assert data["total"] == 0


def test_normalize_uses_actual_oslo_daylight_saving_transitions():
    assert normalize_datetime("2026-03-25T17:00:00Z") == "2026-03-25T18:00:00"
    assert normalize_datetime("2026-03-29T00:59:00Z") == "2026-03-29T01:59:00"
    assert normalize_datetime("2026-03-29T01:00:00Z") == "2026-03-29T03:00:00"
    assert normalize_datetime("2026-10-25T00:59:00Z") == "2026-10-25T02:59:00"
    assert normalize_datetime("2026-10-25T01:00:00Z") == "2026-10-25T02:00:00"


def test_filter_keeps_ongoing_events_and_uses_oslo_for_naive_times():
    now = datetime(2026, 11, 27, 20, 0, tzinfo=timezone.utc)  # Kl. 21.00 i Oslo
    events = [
        {"title": "lokal start har passert", "start_at": "2026-11-27T20:30:00"},
        {"title": "pågår", "start_at": "2026-10-31T11:00:00Z", "end_at": "2026-12-12T15:00:00Z"},
        {"title": "ingen klokkeslett", "start_at": "2026-11-27"},
        {"title": "passert dato", "start_at": "2026-11-26"},
        {"title": "framtidig med tidssone", "start_at": "2026-11-27T21:15:00+01:00"},
    ]
    assert [event["title"] for event in filter_past_events(events, now=now)] == [
        "pågår", "ingen klokkeslett", "framtidig med tidssone",
    ]


def test_filter_distinguishes_the_two_occurrences_of_a_repeated_local_time():
    now = datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)
    first = {"start_at": "2026-10-25T02:30:00+02:00"}
    second = {"start_at": "2026-10-25T02:30:00+01:00"}
    assert filter_past_events([first, second], now=now) == [second]


def test_main_merges_cross_source_duplicates_and_keeps_separate_showtimes(tmp_path):
    base = {
        "title": "Putti Plutti Pott", "city": "Ålesund",
        "location_name": "Parken kulturhus", "start_at": "2099-11-28T13:00:00",
    }
    friskus = {**base, "source": "friskus", "source_id": "friskus-1",
               "start_at": "2099-11-28T12:00:00Z", "address": "Parkgata 3B", "tags": ["barn"]}
    parken = {**base, "source": "parken", "source_id": "parken-1",
              "location_name": "Parken kulturhus – Hovedscene", "url": "https://tickets.example/13",
              "end_at": "2099-11-28T15:00:00", "tags": ["teater"]}
    late = {**parken, "source_id": "parken-2", "start_at": "2099-11-28T16:00:00"}
    bypatrioten = {**base, "source": "bypatrioten", "source_id": "bypatrioten-1",
                   "title": "Putti Plutti Pott 2099"}

    with patch("backend.generate.run_scrapers", return_value=([friskus, parken, late, bypatrioten], [])), \
            patch("backend.generate.OUTPUT_DIR", tmp_path):
        from backend.generate import main
        path = main()

    events = json.loads(path.read_text())["events"]
    assert [event["source_id"] for event in events] == ["parken-1", "parken-2"]
    assert events[0]["url"] == parken["url"]
    assert events[0]["address"] == friskus["address"]
    assert events[0]["tags"] == ["teater", "barn"]
