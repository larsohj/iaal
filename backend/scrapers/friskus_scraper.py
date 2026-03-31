from backend.models import EventData
from backend.scrapers.base import BaseScraper

MUNICIPALITY_UUIDS = [
    "58057c8b-b578-4082-8c11-97bfe366e5ab",  # Ålesund (inkl. Ørskog)
    "db3b7632-82c3-4895-8c18-d24a559a42ad",  # Sula
    "5900890d-0709-4ea3-bc16-f853e28aaacb",  # Giske
]

BASE_URL = "https://api.friskus.com/api/v1/events"

EVENT_SOURCE_TAGS = {
    "dnt": ["friluftsliv", "tur"],
}


class FriskusScraper(BaseScraper):
    source_name = "friskus"

    def scrape(self) -> list[EventData]:
        events = []
        seen_ids = set()

        for municipality_id in MUNICIPALITY_UUIDS:
            page = 1
            while True:
                resp = self._get(BASE_URL, params={
                    "municipalities[]": municipality_id,
                    "page": page,
                })
                data = resp.json()

                for item in data.get("data", []):
                    event_id = item["id"]
                    if event_id in seen_ids:
                        continue
                    seen_ids.add(event_id)

                    tags = EVENT_SOURCE_TAGS.get(item.get("event_source", ""), [])

                    org_name = item.get("organization", {}).get("name")

                    events.append(EventData(
                        source="friskus",
                        source_id=f"friskus-{event_id}",
                        title=item["name"],
                        start_at=item.get("start_at"),
                        end_at=item.get("end_at"),
                        is_free=item.get("is_free"),
                        is_recurring=item.get("is_recurring", False),
                        organizer=org_name,
                        location_name=org_name,
                        image_url=item.get("thumbnail_url"),
                        url=f"https://alesund.friskus.com/activities/{item.get('slug', '')}",
                        age_groups=item.get("age_group", []),
                        tags=tags,
                    ))

                meta = data.get("meta", {})
                if page >= meta.get("last_page", 1):
                    break
                page += 1

        self.logger.info(f"Hentet {len(events)} hendelser fra Friskus")
        return events
