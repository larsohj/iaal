import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.scrapers.viti_scraper import ARRANGEMENT_URL, VitiScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(content=None, json_data=None):
    resp = MagicMock()
    if content:
        resp.text = content
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestVitiScraper:
    def _run_scraper(self, fixture_data):
        scraper = VitiScraper()
        html_resp = _mock_response(content='<script>{"buildId":"test123"}</script>')
        json_resp = _mock_response(json_data=fixture_data)

        with patch.object(scraper, "_get", side_effect=[html_resp, json_resp]):
            return scraper.scrape()

    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "viti_arrangement.json") as f:
            fixture = json.load(f)

        events = self._run_scraper(fixture)
        assert len(events) > 0

        first = events[0]
        assert first.source == "viti"
        assert first.source_id.startswith("viti-")
        assert first.title != ""
        assert first.start_at is not None
        assert "vitimusea.no/arrangement/" in first.url

    def test_creates_one_event_per_date(self):
        fixture = {"pageProps": {"activitiesData": [{
            "_lang": "no",
            "isArchived": False,
            "name": "Multi-dato event",
            "slug": {"current": "multi-dato"},
            "exhibitionFacts": {
                "dates": [
                    {"startDate": "2026-04-01T10:00:00.000Z", "endDate": "2026-04-01T12:00:00.000Z"},
                    {"startDate": "2026-04-02T10:00:00.000Z", "endDate": "2026-04-02T12:00:00.000Z"},
                ],
                "selectMuseumArray": [{"name": "Sunnmøre Museum"}],
                "museumTag": [],
                "selectCity": {"cityName": "Ålesund"},
            },
            "exhibitionImage": None,
        }]}}

        events = self._run_scraper(fixture)
        assert len(events) == 2
        assert events[0].source_id == "viti-multi-dato-0"
        assert events[1].source_id == "viti-multi-dato-1"

    def test_filters_out_english_and_archived(self):
        fixture = {"pageProps": {"activitiesData": [
            {
                "_lang": "en_GB",
                "isArchived": False,
                "name": "English event",
                "slug": {"current": "english"},
                "exhibitionFacts": {
                    "dates": [{"startDate": "2026-04-01T10:00:00.000Z"}],
                    "selectMuseumArray": [],
                    "museumTag": [],
                    "selectCity": {"cityName": "Ålesund"},
                },
                "exhibitionImage": None,
            },
            {
                "_lang": "no",
                "isArchived": True,
                "name": "Arkivert event",
                "slug": {"current": "arkivert"},
                "exhibitionFacts": {
                    "dates": [{"startDate": "2026-04-01T10:00:00.000Z"}],
                    "selectMuseumArray": [],
                    "museumTag": [],
                    "selectCity": {"cityName": "Ålesund"},
                },
                "exhibitionImage": None,
            },
            {
                "_lang": "no",
                "isArchived": False,
                "name": "Gyldig event",
                "slug": {"current": "gyldig"},
                "exhibitionFacts": {
                    "dates": [{"startDate": "2026-04-01T10:00:00.000Z"}],
                    "selectMuseumArray": [{"name": "KUBE"}],
                    "museumTag": [{"lang": {"no": {"museumTag": "Kunst"}}}],
                    "selectCity": {"cityName": "Ålesund"},
                },
                "exhibitionImage": None,
            },
        ]}}

        events = self._run_scraper(fixture)
        assert len(events) == 1
        assert events[0].title == "Gyldig event"
        assert "kunst" in events[0].tags

    def test_maps_museum_location(self):
        fixture = {"pageProps": {"activitiesData": [{
            "_lang": "no",
            "isArchived": False,
            "name": "Test",
            "slug": {"current": "test"},
            "exhibitionFacts": {
                "dates": [{"startDate": "2026-04-01T10:00:00.000Z"}],
                "selectMuseumArray": [
                    {"name": "Jugendstilsenteret og KUBE"},
                    {"name": "Sunnmøre Museum"},
                ],
                "museumTag": [],
                "selectCity": {"cityName": "Ålesund"},
            },
            "exhibitionImage": {"asset": {"url": "https://cdn.sanity.io/images/test.jpg"}},
        }]}}

        events = self._run_scraper(fixture)
        assert events[0].location_name == "Jugendstilsenteret og KUBE, Sunnmøre Museum"
        assert events[0].image_url == "https://cdn.sanity.io/images/test.jpg"


def _app_router_html(items):
    def record(key, data):
        return f"{key}:{json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n"

    # Referanse-ID-en varierer med Next.js-bygg. Oppføringen kan deles mellom to skript.
    page = record("e", ["$", "$L2a", None, {"items": items, "locale": "no"}])
    unrelated = record("f", ["$", "$L99", None, {"items": [], "locale": "no"}])
    chunks = [
        '2a:I[42827,["$2"],"ArrangementPage"]\n' + unrelated + page[:51],
        page[51:],
    ]
    return "".join(f"<script>self.__next_f.push({json.dumps([1, chunk])})</script>" for chunk in chunks)


def test_reads_viti_app_router_activities_and_filters_known_outside_museums():
    dates = [
        {"startDate": "2026-11-29T16:00:00.000Z", "endDate": "2026-11-29T17:00:00.000Z"},
        {"startDate": "2026-12-01T16:00:00.000Z", "endDate": "2026-12-01T17:00:00.000Z"},
    ]
    local = {
        "_type": "activity",
        "name": "Spor etter dei første Sunnmøringane",
        "slug": {"current": "foredrag-spor-etter-dei-foerste-sunnmoeringane"},
        "exhibitionFacts": {
            "dates": dates,
            "selectMuseumArray": [{"name": "Sunnmøre museum", "slug": {"current": "sunnmoere-museum"}}],
            "museumTag": [{"language": "no", "museumTag": "Historie"}],
        },
        "exhibitionImage": {"asset": {"url": "https://cdn.sanity.io/images/test.jpg"}},
    }
    outside = {
        "_type": "activity",
        "name": "Førjulskveld",
        "slug": {"current": "foerjulskveld-26"},
        "exhibitionFacts": {
            "dates": dates,
            "selectMuseumArray": [
                {"name": "Naturmuseet", "slug": {"current": "naturmuseet"}},
                {"name": "Møbelmuseet", "slug": {"current": "mobelmuseet"}},
            ],
        },
    }
    placeholder = {"_type": "activity", "name": None, "slug": None, "exhibitionFacts": None}
    scraper = VitiScraper()
    response = _mock_response(content=_app_router_html([local, local, outside, placeholder]))

    with patch.object(scraper, "_get", return_value=response) as fetch:
        events = scraper.scrape()

    fetch.assert_called_once_with(ARRANGEMENT_URL)
    assert [e.start_at for e in events] == [d["startDate"] for d in dates]
    assert [e.end_at for e in events] == [d["endDate"] for d in dates]
    assert [e.source_id for e in events] == [
        "viti-foredrag-spor-etter-dei-foerste-sunnmoeringane-0",
        "viti-foredrag-spor-etter-dei-foerste-sunnmoeringane-1",
    ]
    assert events[0].city == "Ålesund"
    assert events[0].location_name == "Sunnmøre museum"
    assert events[0].tags == ["historie"]
    assert events[0].image_url == "https://cdn.sanity.io/images/test.jpg"


def test_empty_viti_calendar_is_a_valid_result():
    scraper = VitiScraper()
    with patch.object(scraper, "_get", return_value=_mock_response(content=_app_router_html([]))) as fetch:
        assert scraper.scrape() == []
    fetch.assert_called_once_with(ARRANGEMENT_URL)


def test_unrecognized_viti_html_is_a_source_failure():
    scraper = VitiScraper()
    with patch.object(scraper, "_get", return_value=_mock_response(content="<html>Uventet side</html>")):
        with pytest.raises(ValueError, match="Kunne ikke finne arrangementsdata"):
            scraper.scrape()
