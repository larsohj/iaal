import os

from backend.models import EventData
from backend.scrapers.base import BaseScraper

API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
AALESUND_LAT = 62.4723
AALESUND_LNG = 6.1549
RADIUS_KM = 50


class TicketmasterScraper(BaseScraper):
    source_name = "ticketmaster"

    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("TICKETMASTER_API_KEY", "")

    def scrape(self) -> list[EventData]:
        if not self.api_key:
            self.logger.warning("TICKETMASTER_API_KEY ikke satt, hopper over")
            return []

        events = []
        page = 0

        while True:
            resp = self._get(API_URL, params={
                "apikey": self.api_key,
                "latlong": f"{AALESUND_LAT},{AALESUND_LNG}",
                "radius": str(RADIUS_KM),
                "unit": "km",
                "locale": "no",
                "page": str(page),
                "size": "50",
            })
            data = resp.json()

            embedded = data.get("_embedded", {})
            tm_events = embedded.get("events", [])

            for item in tm_events:
                venue = {}
                venues = item.get("_embedded", {}).get("venues", [])
                if venues:
                    venue = venues[0]

                # Pris
                price_ranges = item.get("priceRanges", [])
                price_text = None
                is_free = None
                if price_ranges:
                    pr = price_ranges[0]
                    min_p = pr.get("min", 0)
                    max_p = pr.get("max", 0)
                    currency = pr.get("currency", "NOK")
                    if min_p == 0 and max_p == 0:
                        is_free = True
                    else:
                        is_free = False
                        price_text = f"{currency} {min_p}" if min_p == max_p else f"{currency} {min_p}–{max_p}"

                # Tags fra genre
                tags = []
                classifications = item.get("classifications", [])
                if classifications:
                    genre = classifications[0].get("genre", {}).get("name")
                    if genre and genre != "Undefined":
                        tags.append(genre.lower())

                # Koordinater
                location = venue.get("location", {})
                lat = None
                lng = None
                try:
                    lat = float(location.get("latitude", 0))
                    lng = float(location.get("longitude", 0))
                except (ValueError, TypeError):
                    pass

                events.append(EventData(
                    source="ticketmaster",
                    source_id=f"ticketmaster-{item['id']}",
                    title=item.get("name", ""),
                    start_at=item.get("dates", {}).get("start", {}).get("dateTime"),
                    location_name=venue.get("name"),
                    address=venue.get("address", {}).get("line1"),
                    city=venue.get("city", {}).get("name", "Ålesund"),
                    latitude=lat,
                    longitude=lng,
                    is_free=is_free,
                    price_text=price_text,
                    image_url=item.get("images", [{}])[0].get("url") if item.get("images") else None,
                    url=item.get("url"),
                    tags=tags,
                ))

            # Paginering
            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)
            if page + 1 >= total_pages:
                break
            page += 1

        self.logger.info(f"Hentet {len(events)} hendelser fra Ticketmaster")
        return events
