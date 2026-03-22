from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.scrapers.bibliotek_scraper import BibliotekScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(text=""):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


class TestBibliotekScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "bibliotek_forsiden.html") as f:
            html = f.read()

        scraper = BibliotekScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) > 0
        first = events[0]
        assert first.source == "bibliotek"
        assert first.source_id.startswith("bibliotek-")
        assert first.title != ""
        assert first.is_free is True
        assert "CalendarEvent" in first.url

    def test_parses_date_and_time(self):
        html = '''
        <li class="event">
            <div class="event-image"><img src="/test.png"/></div>
            <a href="/Kalender/CalendarEvent.aspx?Id=12345&amp;lang=1&amp;MId1=18377">
                <div class="event-date">
                    <div class="event-date-day">22.</div>
                    <div class="event-date-month">03.</div>
                    <div class="event-date-month">2026</div>
                    <div class="event-time"><span>|</span>kl. 14:30</div>
                </div>
                <div class="event-text">
                    <h3 class="event-title">Bokbad</h3>
                    <div class="event-details">
                        <span class="event-location">Ålesund bibliotek</span>
                    </div>
                </div>
            </a>
        </li>
        '''
        scraper = BibliotekScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) == 1
        e = events[0]
        assert e.source_id == "bibliotek-12345"
        assert e.title == "Bokbad"
        assert e.location_name == "Ålesund bibliotek"
        assert e.start_at == "2026-03-22T14:30:00"
        assert e.image_url.endswith("/test.png")
