import re

from backend.models import EventData
from backend.scrapers.base import BaseScraper

ARRANGEMENT_URL = "https://www.vitimusea.no/arrangement"
DATA_URL_TEMPLATE = "https://www.vitimusea.no/_next/data/{build_id}/no/arrangement.json"


class VitiScraper(BaseScraper):
    source_name = "viti"

    def _get_build_id(self) -> str:
        resp = self._get(ARRANGEMENT_URL)
        match = re.search(r'"buildId"\s*:\s*"([^"]+)"', resp.text)
        if not match:
            raise ValueError("Kunne ikke finne buildId i Viti-siden")
        return match.group(1)

    def scrape(self) -> list[EventData]:
        build_id = self._get_build_id()
        resp = self._get(DATA_URL_TEMPLATE.format(build_id=build_id))
        data = resp.json()

        activities = data.get("pageProps", {}).get("activitiesData", [])
        events = []

        for activity in activities:
            if activity.get("_lang") != "no":
                continue
            if activity.get("isArchived"):
                continue

            facts = activity.get("exhibitionFacts", {})
            dates = facts.get("dates", [])
            if not dates:
                continue

            slug = activity.get("slug", {}).get("current", "")
            title = activity.get("name", "")
            description = facts.get("exhibitionAbstract")

            museums = facts.get("selectMuseumArray", [])
            location_name = ", ".join(m.get("name", "") for m in museums) if museums else None

            image_data = activity.get("exhibitionImage", {})
            image_url = image_data.get("asset", {}).get("url") if image_data else None

            museum_tags = []
            for tag_obj in facts.get("museumTag", []):
                no_tag = tag_obj.get("lang", {}).get("no", {}).get("museumTag")
                if no_tag:
                    museum_tags.append(no_tag.lower())

            city = facts.get("selectCity", {}).get("cityName", "Ålesund")

            for i, date_entry in enumerate(dates):
                events.append(EventData(
                    source="viti",
                    source_id=f"viti-{slug}-{i}",
                    title=title,
                    description=description,
                    start_at=date_entry.get("startDate"),
                    end_at=date_entry.get("endDate"),
                    location_name=location_name,
                    city=city,
                    image_url=image_url,
                    url=f"https://www.vitimusea.no/arrangement/{slug}",
                    tags=museum_tags,
                ))

        self.logger.info(f"Hentet {len(events)} hendelser fra Viti")
        return events
