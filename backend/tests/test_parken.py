from pathlib import Path
from unittest.mock import MagicMock, patch, call

from backend.scrapers.parken_scraper import ParkenScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(text=""):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


DETAIL_HTML = """
<html><body>
<h1>Test Event</h1>
<p>22. mar 2026 kl. 19:00 - 21:30</p>
</body></html>
"""


class TestParkenScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "parken_program.html") as f:
            html = f.read()

        scraper = ParkenScraper()
        overview_resp = _mock_response(text=html)
        detail_resp = _mock_response(text=DETAIL_HTML)

        with patch.object(scraper, "_get", side_effect=[overview_resp] + [detail_resp] * 60):
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
        overview_resp = _mock_response(text=html)
        detail_resp = _mock_response(text=DETAIL_HTML)

        with patch.object(scraper, "_get", side_effect=[overview_resp] + [detail_resp] * 60):
            events = scraper.scrape()

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
        detail = '<html><body><p>22. mar 2026 kl. 20:00 - 22:00</p></body></html>'

        scraper = ParkenScraper()
        with patch.object(scraper, "_get", side_effect=[
            _mock_response(text=html),
            _mock_response(text=detail),
        ]):
            events = scraper.scrape()

        assert len(events) == 1
        assert "utsolgt" in events[0].tags
        assert "teater" in events[0].tags

    def test_fetches_time_from_detail_page(self):
        html = '''
        <article class="tease has-image tease-event" data-category="[]">
            <a href="https://www.parkenkulturhus.no/program/99-konsert/"></a>
            <div class="textual-content">
                <p class="dates small">15. mai 2026</p>
                <h3>Konsert</h3>
                <p class="venue small">Hovedscene</p>
            </div>
        </article>
        '''
        detail = '<html><body><p>15. mai 2026 kl. 19:30 - 22:00</p></body></html>'

        scraper = ParkenScraper()
        with patch.object(scraper, "_get", side_effect=[
            _mock_response(text=html),
            _mock_response(text=detail),
        ]):
            events = scraper.scrape()

        assert len(events) == 1
        assert events[0].start_at == "2026-05-15T19:30:00"
        assert events[0].end_at == "2026-05-15T22:00:00"

    def test_falls_back_to_date_only_when_detail_fails(self):
        html = '''
        <article class="tease has-image tease-event" data-category="[]">
            <a href="https://www.parkenkulturhus.no/program/99-konsert/"></a>
            <div class="textual-content">
                <p class="dates small">15. mai 2026</p>
                <h3>Konsert</h3>
            </div>
        </article>
        '''
        scraper = ParkenScraper()

        def side_effect_fn(url, **kwargs):
            if "program/99" in url:
                raise ConnectionError("timeout")
            return _mock_response(text=html)

        with patch.object(scraper, "_get", side_effect=side_effect_fn):
            events = scraper.scrape()

        assert len(events) == 1
        assert events[0].start_at == "2026-05-15T00:00:00"
        assert events[0].end_at is None

    def test_detail_without_time_keeps_date_only(self):
        html = '''
        <article class="tease has-image tease-event" data-category="[]">
            <a href="https://www.parkenkulturhus.no/program/99-konsert/"></a>
            <div class="textual-content">
                <p class="dates small">15. mai 2026</p>
                <h3>Konsert</h3>
            </div>
        </article>
        '''
        detail_no_time = '<html><body><p>Ingen tidspunkt tilgjengelig</p></body></html>'

        scraper = ParkenScraper()
        with patch.object(scraper, "_get", side_effect=[
            _mock_response(text=html),
            _mock_response(text=detail_no_time),
        ]):
            events = scraper.scrape()

        assert len(events) == 1
        assert events[0].start_at == "2026-05-15T00:00:00"
