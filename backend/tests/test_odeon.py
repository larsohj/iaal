from unittest.mock import MagicMock, patch

from backend.scrapers.odeon_scraper import OdeonScraper


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


MOVIES_FIXTURE = {
    "totalNbrOfItems": 2,
    "items": [
        {
            "ncgId": "NCG100",
            "title": "Testfilmen",
            "slug": "testfilmen",
            "shortDescription": "En test.",
            "posterUrl": "https://catalog.cinema-api.com/test.jpg",
            "genres": [{"name": "Drama"}, {"name": "Komedie"}],
            "versions": [
                {"ncgId": "NCG100V1", "title": "Testfilmen"},
            ],
        },
        {
            "ncgId": "NCG200",
            "title": "Gratis Film",
            "slug": "gratis-film",
            "shortDescription": "Gratis!",
            "posterUrl": "https://catalog.cinema-api.com/gratis.jpg",
            "genres": [],
            "versions": [
                {"ncgId": "NCG200V1", "title": "Gratis Film"},
            ],
        },
    ],
}

SHOWS_FIXTURE = {
    "totalNbrOfItems": 3,
    "items": [
        {
            "reId": "show-1",
            "mId": "NCG100",
            "mvId": "NCG100V1",
            "cId": "NCG47978",
            "ct": "ODEON Ålesund",
            "sId": "NCG47978S3",
            "st": "Sal 5 LUXE",
            "sa": ["LUXE"],
            "utc": "2026-04-01T17:00:00Z",
        },
        {
            "reId": "show-2",
            "mId": "NCG100",
            "mvId": "NCG100V1",
            "cId": "NCG47978",
            "ct": "ODEON Ålesund",
            "sId": "NCG47978S1",
            "st": "Sal 1",
            "sa": [],
            "utc": "2026-04-01T19:30:00Z",
        },
        {
            "reId": "show-3",
            "mId": "NCG200",
            "mvId": "NCG200V1",
            "cId": "NCG47978",
            "ct": "ODEON Ålesund",
            "sId": "NCG47978S2",
            "st": "Sal 2",
            "sa": ["IMAX"],
            "utc": "2026-04-02T14:00:00Z",
        },
    ],
}


class TestOdeonScraper:
    def _run_scraper(self, movies=MOVIES_FIXTURE, shows=SHOWS_FIXTURE):
        scraper = OdeonScraper()
        with patch.object(scraper, "_get", side_effect=[
            _mock_response(movies),
            _mock_response(shows),
        ]):
            return scraper.scrape()

    def test_parses_showings(self):
        events = self._run_scraper()
        assert len(events) == 3

        first = events[0]
        assert first.source == "odeon"
        assert first.source_id == "odeon-show-1"
        assert first.title == "Testfilmen"
        assert first.start_at == "2026-04-01T17:00:00Z"
        assert first.description == "En test."
        # image_url reskrives via _proxy_image_url (catalog → _PROXY_BASE)
        assert "cinema-api.com/test.jpg" in first.image_url
        assert "odeonkino.no/film/testfilmen/" in first.url

    def test_maps_location_and_screen(self):
        events = self._run_scraper()
        assert events[0].location_name == "ODEON Ålesund – Sal 5 LUXE"
        assert events[1].location_name == "ODEON Ålesund – Sal 1"

    def test_maps_tags_from_attributes_and_genres(self):
        events = self._run_scraper()
        assert "luxe" in events[0].tags
        assert "drama" in events[0].tags
        assert "komedie" in events[0].tags

    def test_imax_tag(self):
        events = self._run_scraper()
        assert "imax" in events[2].tags

    def test_skips_unknown_movie_ids(self):
        shows = {
            "totalNbrOfItems": 1,
            "items": [{
                "reId": "show-x",
                "mId": "UNKNOWN",
                "ct": "ODEON Ålesund",
                "st": "Sal 1",
                "sa": [],
                "utc": "2026-04-01T17:00:00Z",
            }],
        }
        events = self._run_scraper(shows=shows)
        assert len(events) == 0

    def test_handles_empty_shows(self):
        events = self._run_scraper(shows={"totalNbrOfItems": 0, "items": []})
        assert events == []

    def test_version_id_lookup(self):
        """Sjekk at mvId (versjon-ID) også matcher filmen."""
        shows = {
            "totalNbrOfItems": 1,
            "items": [{
                "reId": "show-v",
                "mId": "NCG100V1",  # Versjon-ID, ikke hoved-ID
                "ct": "ODEON Ålesund",
                "st": "Sal 3",
                "sa": [],
                "utc": "2026-04-05T20:00:00Z",
            }],
        }
        events = self._run_scraper(shows=shows)
        assert len(events) == 1
        assert events[0].title == "Testfilmen"
