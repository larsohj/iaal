from unittest.mock import MagicMock, patch

from backend.scrapers.aafk_scraper import AafkScraper


def _mock_response(text=""):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


FIXTURE_HTML = '''
<script>
{"page":{"isEmpty":false,"hasMore":false,"hero":{"id":"hero-1","title":" Eliteserien: Aalesund - Fredrikstad","startAt":"07 april 19:00","description":"","minPrice":"50 kr","image":"https:\\u002F\\u002Fexample.com\\u002Fimg.jpg"},"items":[
{"id":"item-1","title":" Eliteserien: Aalesund - KFUM ","startAt":"søndag, 12 apr. 2026, 17:00","minPrice":"50 kr","location":"Color Line Stadion","image":"https:\\u002F\\u002Fexample.com\\u002Fimg2.jpg"},
{"id":"item-2","title":"Toppserien: AaFK Kvinner - Rosenborg","startAt":"fredag, 24 apr. 2026, 18:00","minPrice":"50 kr","location":"Color Line Stadion","image":"https:\\u002F\\u002Fexample.com\\u002Fimg3.jpg"},
{"id":"item-skip","title":"AaFK Herrer: Sesongkort 2026","startAt":"onsdag, 10 des. 2025, 13:04","minPrice":"100 kr","location":"","image":""}
]}}
</script>
'''


class TestAafkScraper:
    def test_parses_hero_and_items(self):
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=FIXTURE_HTML)):
            events = scraper.scrape()

        # 3 kamper (hero + 2 items, sesongkort filtrert bort)
        assert len(events) == 3

    def test_hero_event_parsed(self):
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=FIXTURE_HTML)):
            events = scraper.scrape()

        hero = events[0]
        assert hero.source == "aafk"
        assert hero.source_id == "aafk-hero-1"
        assert hero.title == "Eliteserien: Aalesund - Fredrikstad"
        assert "19:00:00" in hero.start_at
        assert hero.location_name == "Color Line Stadion"
        assert hero.price_text == "50 kr"
        assert "fotball" in hero.tags

    def test_item_event_parsed(self):
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=FIXTURE_HTML)):
            events = scraper.scrape()

        item = events[1]
        assert item.title == "Eliteserien: Aalesund - KFUM"
        assert item.start_at == "2026-04-12T17:00:00"
        assert item.location_name == "Color Line Stadion"

    def test_skips_sesongkort(self):
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=FIXTURE_HTML)):
            events = scraper.scrape()

        titles = [e.title for e in events]
        assert not any("Sesongkort" in t for t in titles)

    def test_image_url_unescaped(self):
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=FIXTURE_HTML)):
            events = scraper.scrape()

        assert events[0].image_url == "https://example.com/img.jpg"

    def test_deduplicates_hero_and_items(self):
        """Hvis hero-ID også dukker opp i items, ikke dupliser."""
        html = '''
        <script>
        {"page":{"hero":{"id":"same-id","title":"Kamp","startAt":"07 april 19:00","description":"","minPrice":"50 kr","image":""},"items":[
        {"id":"same-id","title":"Kamp","startAt":"søndag, 7 apr. 2026, 19:00","minPrice":"50 kr","location":"Color Line Stadion","image":""}
        ]}}
        </script>
        '''
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text=html)):
            events = scraper.scrape()

        assert len(events) == 1

    def test_handles_empty_page(self):
        scraper = AafkScraper()
        with patch.object(scraper, "_get", return_value=_mock_response(text="<html></html>")):
            events = scraper.scrape()

        assert events == []

    def test_parse_hero_date(self):
        assert AafkScraper._parse_hero_date("07 april 19:00") is not None
        assert "T19:00:00" in AafkScraper._parse_hero_date("07 april 19:00")

    def test_parse_item_date(self):
        assert AafkScraper._parse_item_date("søndag, 12 apr. 2026, 17:00") == "2026-04-12T17:00:00"
        assert AafkScraper._parse_item_date("fredag, 24 apr. 2026, 18:00") == "2026-04-24T18:00:00"
        assert AafkScraper._parse_item_date("ugyldig") is None
