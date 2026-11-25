from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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

    @pytest.mark.parametrize("title, date_range, first_start, shows", [
        ("Putti Plutti Pott", "27. nov – 6. des", "2026-11-27T18:00:00+01:00", [
            ("27.11", "18:00", "20:00", "2026-11-27"),
            ("28.11", "13:00", "15:00", "2026-11-28"),
            ("28.11", "16:00", "18:00", "2026-11-28"),
            ("29.11", "13:00", "15:00", "2026-11-29"),
            ("29.11", "16:00", "18:00", "2026-11-29"),
            ("03.12", "18:00", "20:00", "2026-12-03"),
            ("04.12", "18:00", "20:00", "2026-12-04"),
            ("05.12", "13:00", "15:00", "2026-12-05"),
            ("05.12", "16:00", "18:00", "2026-12-05"),
            ("06.12", "13:00", "15:00", "2026-12-06"),
            ("06.12", "16:00", "18:00", "2026-12-06"),
        ]),
        ("Nyttårskonserten", "23. jan – 24. jan", "2027-01-23T18:30:00+01:00", [
            ("23.01", "18:30", "20:30", "2027-01-23"),
            ("24.01", "18:30", "20:30", "2027-01-24"),
        ]),
        ("Romjulskonsert", "31. des – 1. jan", "2026-12-31T18:30:00+01:00", [
            ("31.12", "18:30", "20:30", "2026-12-31"),
            ("01.01", "18:30", "20:30", "2027-01-01"),
        ]),
    ])
    def test_extracts_each_performance(self, title, date_range, first_start, shows):
        detail_url = "https://www.parkenkulturhus.no/program/test/"
        overview = f"""
        <article class="tease-event">
            <a href="{detail_url}"></a><h3>{title}</h3><p class="dates">{date_range}</p>
        </article>
        """
        ticket_urls = [
            f"https://billetter.parkenkulturhus.no/nb/buyingflow/tickets/123/{index}/"
            for index, _ in enumerate(shows)
        ]
        # En forestilling kan være oppført uten aktiv billettlenke.
        ticket_urls[-1] = detail_url
        rows = []
        for (day_month, start, end, _), url in zip(shows, ticket_urls):
            ticket = f'<a href="{url}">Kjøp billett</a>' if url != detail_url else ""
            rows.append(f'<p class="event"><span class="date">{day_month} - kl. {start} - {end}'
                        f'</span>{ticket}</p>')
        detail = f"""
        <script type="application/ld+json">
            {{"@type":"Event", "startDate":"{first_start}", "description":""Sitert tekst""}}
        </script>
        <p class="dates ingress">{date_range}</p>
        <div id="shows">{''.join(rows)}</div>
        """

        scraper = ParkenScraper()
        with patch.object(scraper, "_get", side_effect=[
            _mock_response(overview), _mock_response(detail),
        ]):
            events = scraper.scrape()

        assert [e.title for e in events] == [title] * len(shows)
        assert [e.start_at for e in events] == [f"{date}T{start}:00" for _, start, _, date in shows]
        assert [e.end_at for e in events] == [f"{date}T{end}:00" for _, _, end, date in shows]
        assert [e.url for e in events] == ticket_urls
        assert len({e.source_id for e in events}) == len(shows)
