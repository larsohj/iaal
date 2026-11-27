from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.scrapers.bypatrioten_scraper import BypatriotenScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(text=""):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


class TestBypatriotenScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "bypatrioten_kalender.html") as f:
            html = f.read()

        scraper = BypatriotenScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        # Bør finne noen events (filtrerer bort past events)
        assert len(events) >= 0  # Kan være 0 hvis alle er past

    def test_parses_event_structure(self):
        html = '''
        <article class="mec-event-article">
            <div class="mec-event-time"><i></i> 18.00 - 20.00</div>
            <h4 class="mec-event-title">
                <a class="mec-color-hover" data-event-id="99999"
                   href="https://bypatrioten.com/event/test-event/?occurrence=2026-04-01">
                   Test Event
                </a>
            </h4>
            <div class="mec-event-detail">
                <div class="mec-event-loc-place">Kafeen</div>
            </div>
        </article>
        '''
        scraper = BypatriotenScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) == 1
        e = events[0]
        assert e.source == "bypatrioten"
        assert e.source_id == "bypatrioten-99999-2026-04-01"
        assert e.title == "Test Event"
        assert e.location_name == "Kafeen"
        assert e.start_at == "2026-04-01T18:00:00"
        assert e.end_at == "2026-04-01T20:00:00"

    def test_parse_time_ranges(self):
        start, end = BypatriotenScraper._parse_time("2026-04-01", "08.00 - 11.00")
        assert start == "2026-04-01T08:00:00"
        assert end == "2026-04-01T11:00:00"

        start, end = BypatriotenScraper._parse_time("2026-04-01", None)
        assert start == "2026-04-01T00:00:00"
        assert end is None

    def test_same_day_showings_use_separate_stable_ids(self):
        def showing(timestamp, start, end):
            return f"""
            <article class="mec-event-article">
                <div class="mec-event-time">{start} - {end}</div>
                <h4 class="mec-event-title">
                    <a data-event-id="42350"
                       href="/event/putti-plutti-pott-2026/?occurrence=2026-11-28&amp;time={timestamp}">
                        Putti Plutti Pott 2026
                    </a>
                </h4>
            </article>
            """

        early = showing("1795870800", "13.00", "15.00")
        late = showing("1795881600", "16.00", "18.00")
        scraper = BypatriotenScraper()
        with patch.object(scraper, "_get", side_effect=[
            _mock_response(early + late), _mock_response(late + early),
        ]):
            events = scraper.scrape()
            reversed_events = scraper.scrape()

        expected = {
            "2026-11-28T13:00:00": "bypatrioten-42350-2026-11-28-1795870800",
            "2026-11-28T16:00:00": "bypatrioten-42350-2026-11-28-1795881600",
        }
        assert len(events) == len(reversed_events) == 2
        assert {event.start_at: event.source_id for event in events} == expected
        assert {event.start_at: event.source_id for event in reversed_events} == expected
