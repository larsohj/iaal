import re
from datetime import datetime

from backend.models import EventData
from backend.scrapers.base import BaseScraper

AAFK_URL = "https://aafk.ticketco.events"

# Norske dag- og månedsnavn for parsing
MONTHS_NO = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "mai": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "nov": 11, "des": 12,
    "januar": 1, "februar": 2, "mars": 3, "april": 4,
    "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}

# Titler som ikke er kamper
SKIP_TITLES = {"sesongkort", "tango", "plastkort", "nettbutikk", "abonnement"}


class AafkScraper(BaseScraper):
    source_name = "aafk"

    def scrape(self) -> list[EventData]:
        resp = self._get(AAFK_URL)
        html = resp.text

        events = []
        seen_ids = set()

        # Hero-event (øverst, annet datoformat)
        hero = self._parse_hero(html)
        if hero and hero.source_id not in seen_ids:
            seen_ids.add(hero.source_id)
            events.append(hero)

        # Item-events (med location-felt)
        for event in self._parse_items(html):
            if event.source_id not in seen_ids:
                seen_ids.add(event.source_id)
                events.append(event)

        self.logger.info(f"Hentet {len(events)} kamper fra AaFK")
        return events

    def _parse_hero(self, html: str) -> EventData | None:
        """Parse hero-event: {"id":"...","title":"...","startAt":"07 april 19:00",...}"""
        match = re.search(
            r'"hero":\{"id":"([^"]+)","title":"([^"]*)","startAt":"([^"]*)",'
            r'"description":"[^"]*","minPrice":"([^"]*)",'
            r'"image":"([^"]*)"',
            html,
        )
        if not match:
            return None

        eid, title, start_at_raw, price, image = match.groups()
        title = title.strip()
        if self._should_skip(title):
            return None

        start_at = self._parse_hero_date(start_at_raw)
        image_url = image.replace("\\u002F", "/") if image else None

        return EventData(
            source="aafk",
            source_id=f"aafk-{eid}",
            title=title,
            start_at=start_at,
            location_name="Color Line Stadion",
            city="Ålesund",
            price_text=price if price else None,
            is_free=False,
            image_url=image_url,
            url=f"{AAFK_URL}/no/nb/e/{self._slugify(title)}",
            tags=["fotball"],
        )

    def _parse_items(self, html: str) -> list[EventData]:
        """Parse item-events med location-felt."""
        pattern = (
            r'"id":"([^"]+)","title":"([^"]*)","startAt":"([^"]*)",'
            r'"minPrice":"([^"]*)","location":"([^"]*)",'
            r'"image":"([^"]*)"'
        )
        events = []
        for match in re.finditer(pattern, html):
            eid, title, start_at_raw, price, location, image = match.groups()
            title = title.strip()
            if self._should_skip(title):
                continue

            start_at = self._parse_item_date(start_at_raw)
            image_url = image.replace("\\u002F", "/") if image else None

            events.append(EventData(
                source="aafk",
                source_id=f"aafk-{eid}",
                title=title,
                start_at=start_at,
                location_name=location or "Color Line Stadion",
                city="Ålesund",
                price_text=price if price else None,
                is_free=False,
                image_url=image_url,
                url=f"{AAFK_URL}/no/nb/e/{self._slugify(title)}",
                tags=["fotball"],
            ))
        return events

    @staticmethod
    def _should_skip(title: str) -> bool:
        return any(k in title.lower() for k in SKIP_TITLES)

    @staticmethod
    def _parse_hero_date(raw: str) -> str | None:
        """Parse '07 april 19:00' → ISO 8601. Antar inneværende år."""
        match = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{1,2}):(\d{2})", raw)
        if not match:
            return None
        day = int(match.group(1))
        month = MONTHS_NO.get(match.group(2).lower().rstrip("."))
        if not month:
            return None
        hour, minute = int(match.group(3)), int(match.group(4))
        year = datetime.now().year
        try:
            return datetime(year, month, day, hour, minute).isoformat()
        except ValueError:
            return None

    @staticmethod
    def _parse_item_date(raw: str) -> str | None:
        """Parse 'søndag, 12 apr. 2026, 17:00' → ISO 8601."""
        match = re.search(r"(\d{1,2})\s+(\w+?)\.?\s+(\d{4}),?\s+(\d{1,2}):(\d{2})", raw)
        if not match:
            return None
        day = int(match.group(1))
        month = MONTHS_NO.get(match.group(2).lower().rstrip("."))
        if not month:
            return None
        year = int(match.group(3))
        hour, minute = int(match.group(4)), int(match.group(5))
        try:
            return datetime(year, month, day, hour, minute).isoformat()
        except ValueError:
            return None

    @staticmethod
    def _slugify(title: str) -> str:
        """Enkel slug for URL."""
        slug = title.lower().strip()
        slug = re.sub(r"[^a-zæøå0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "_", slug)
        return slug
