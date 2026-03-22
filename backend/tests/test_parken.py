from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.scrapers.parken_scraper import ParkenScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(text=""):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


class TestParkenScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "parken_program.html") as f:
            html = f.read()

        scraper = ParkenScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) > 0
        first = events[0]
        assert first.source == "parken"
        assert first.source_id.startswith("parken-")
        assert first.title != ""
        assert "Parken kulturhus" in first.location_name
        assert first.url.startswith("https://www.parkenkulturhus.no/program/")

    def test_extracts_category_tags(self):
        with open(FIXTURES / "parken_program.html") as f:
            html = f.read()

        scraper = ParkenScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        # Minst ett event bør ha tags
        events_with_tags = [e for e in events if e.tags]
        assert len(events_with_tags) > 0

    def test_parse_date(self):
        assert ParkenScraper._parse_date("22. mar 2026") == "2026-03-22T00:00:00"
        assert ParkenScraper._parse_date("1. jan 2026") == "2026-01-01T00:00:00"
        assert ParkenScraper._parse_date("ugyldig") is None

    def test_extracts_sale_status(self):
        html = '''
        <article class="tease has-image tease-event" data-category='["teater"]'>
            <a href="https://www.parkenkulturhus.no/program/12345-test/"></a>
            <figure class="sale-status-3">
                <div class="sale-status sale-status-3"><p>Utsolgt</p></div>
            </figure>
            <div class="textual-content">
                <p class="dates small">22. mar 2026</p>
                <h3>Test Show</h3>
                <h4>Artist</h4>
                <p class="venue small">Hovedscene</p>
            </div>
        </article>
        '''
        scraper = ParkenScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) == 1
        assert "utsolgt" in events[0].tags
        assert "teater" in events[0].tags
