import hashlib
import json

from bs4 import BeautifulSoup

from backend.models import EventData
from backend.scrapers.base import BaseScraper

LOCATION_URL = "https://tikkio.com/locations/151197-alesund"


class TikkioScraper(BaseScraper):
    source_name = "tikkio"

    def scrape(self) -> list[EventData]:
        resp = self._get(LOCATION_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Siden har flere LD+JSON-tags — finn den med ItemList
        data = None
        for ld_tag in soup.find_all("script", {"type": "application/ld+json"}):
            if not ld_tag.string:
                continue
            parsed = json.loads(ld_tag.string)
            if parsed.get("@type") == "ItemList":
                data = parsed
                break

        if not data:
            self.logger.warning("Fant ikke ItemList JSON-LD på Tikkio-siden")
            return []

        items = data.get("itemListElement", {})

        # itemListElement er en dict med "0", "1", ... som nøkler
        if isinstance(items, dict):
            items = list(items.values())

        events = []
        for list_item in items:
            item = list_item.get("item", {})
            if item.get("@type") != "Event":
                continue

            name = item.get("name", "")
            event_url = item.get("offers", {}).get("url", "")
            if not event_url:
                event_url = item.get("url", "")

            source_id = hashlib.md5(event_url.encode()).hexdigest() if event_url else hashlib.md5(name.encode()).hexdigest()

            location = item.get("location", {})
            geo = location.get("geo", {})

            offers = item.get("offers", {})
            price = offers.get("price", "")
            currency = offers.get("priceCurrency", "NOK")
            try:
                price_float = float(price)
                is_free = price_float == 0
                price_text = None if is_free else f"{currency} {price}"
            except (ValueError, TypeError):
                is_free = None
                price_text = str(price) if price else None

            lat = None
            lng = None
            if geo:
                try:
                    lat = float(geo.get("latitude", 0))
                    lng = float(geo.get("longitude", 0))
                except (ValueError, TypeError):
                    pass

            events.append(EventData(
                source="tikkio",
                source_id=f"tikkio-{source_id}",
                title=name,
                description=item.get("description"),
                start_at=item.get("startDate"),
                end_at=item.get("endDate"),
                is_free=is_free,
                price_text=price_text,
                location_name=location.get("name"),
                latitude=lat,
                longitude=lng,
                organizer=item.get("organizer", {}).get("name"),
                image_url=item.get("image"),
                url=event_url,
            ))

        self.logger.info(f"Hentet {len(events)} hendelser fra Tikkio")
        return events
