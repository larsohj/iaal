import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.generate import run_scrapers, merge_with_existing, write_events_json
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
             patch("backend.generate.BypatriotenScraper", return_value=mock_scraper):
            events, failed = run_scrapers()

        assert len(events) == 6  # 1 event fra hver av 6 scrapers
        assert failed == []
        assert all(isinstance(e, dict) for e in events)
        assert events[0]["source"] == "test"

    def test_records_failed_scrapers(self):
        """Sjekk at feilende scrapers logges uten å krasje."""
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
             patch("backend.generate.BypatriotenScraper", return_value=ok_scraper):
            events, failed = run_scrapers()

        assert len(events) == 5
        assert "fail" in failed


class TestMergeWithExisting:
    def test_preserves_events_from_failed_sources(self, tmp_path):
        """Hvis en scraper feiler, bevar events fra forrige kjøring."""
        # Simuler eksisterende events.json
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
        assert "friskus" in sources  # Bevart fra forrige
        assert "viti" in sources     # Ny
        assert len(merged) == 2

    def test_no_merge_when_no_failures(self, tmp_path):
        new_events = [{"source": "viti", "source_id": "viti-1", "title": "Test"}]
        merged = merge_with_existing(new_events, [])
        assert merged == new_events

    def test_no_merge_when_no_existing_file(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        # Ingen events.json

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
