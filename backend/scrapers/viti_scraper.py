import json
import re

from bs4 import BeautifulSoup

from backend.models import EventData
from backend.scrapers.base import BaseScraper

ARRANGEMENT_URL = "https://www.vitimusea.no/arrangement"
DATA_URL_TEMPLATE = "https://www.vitimusea.no/_next/data/{build_id}/no/arrangement.json"
FLIGHT_SCRIPT = re.compile(r"self\.__next_f\.push\((.*)\);?", re.DOTALL)

# Viti viser også museer utenfor appens dekningsområde på samme side.
MUSEUM_CITIES = {
    "sunnmoere-museum": "Ålesund",
    "jugendstilsenteret-kube": "Ålesund",
    "fiskerimuseet": "Ålesund",
    "storeggen-av-aalesund": "Ålesund",
    "brudavolltunet": "Ørsta",
    "naturmuseet": "Sykkylven",
    "mobelmuseet": "Sykkylven",
}
SUPPORTED_CITIES = {"ålesund", "sula", "giske"}


def _arrangement_items(html: str) -> list | None:
    """Les props for ArrangementPage fra Next.js-dataene i HTML-en."""
    chunks = []
    for script in BeautifulSoup(html, "html.parser").find_all("script"):
        match = FLIGHT_SCRIPT.fullmatch((script.string or "").strip())
        if not match:
            continue
        try:
            chunk = json.loads(match[1])
        except json.JSONDecodeError:
            continue
        if isinstance(chunk, list) and len(chunk) == 2 and chunk[0] == 1 and isinstance(chunk[1], str):
            chunks.append(chunk[1])

    # Én record kan være delt mellom flere script-elementer.
    records = [line.partition(":") for line in "".join(chunks).split("\n")]
    components = {
        f"$L{key}" for key, _, body in records
        if body.startswith("I[") and body.endswith(',"ArrangementPage"]')
    }
    for _, _, body in records:
        if not body.startswith('["$",') or '"items"' not in body:
            continue
        try:
            node = json.loads(body)
        except json.JSONDecodeError:
            continue
        if len(node) < 4 or not isinstance(node[1], str) or node[1] not in components:
            continue
        props = node[3]
        if isinstance(props, dict) and props.get("locale") == "no" and isinstance(props.get("items"), list):
            return props["items"]
    return None


class VitiScraper(BaseScraper):
    source_name = "viti"

    def _activities(self) -> list:
        html = self._get(ARRANGEMENT_URL).text
        activities = _arrangement_items(html)
        if activities is not None:
            return activities

        match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
        if not match:
            raise ValueError("Kunne ikke finne arrangementsdata på Viti-siden")
        data = self._get(DATA_URL_TEMPLATE.format(build_id=match[1])).json()
        activities = (data.get("pageProps") or {}).get("activitiesData")
        if not isinstance(activities, list):
            raise ValueError("Ukjent format på Vitis arrangementsdata")
        return activities

    def scrape(self) -> list[EventData]:
        events = []
        seen_ids = set()
        for activity in self._activities():
            if not isinstance(activity, dict) or activity.get("_lang", "no") != "no":
                continue
            if activity.get("isArchived"):
                continue

            facts = activity.get("exhibitionFacts") or {}
            dates = facts.get("dates") or []
            slug = (activity.get("slug") or {}).get("current")
            title = activity.get("name")
            if not (slug and title and dates):
                continue

            museums = facts.get("selectMuseumArray") or []
            museum_names = [museum["name"] for museum in museums if museum.get("name")]
            museum_cities = {MUSEUM_CITIES.get((museum.get("slug") or {}).get("current")) for museum in museums}
            city = (facts.get("selectCity") or {}).get("cityName")
            if not city and len(museum_cities) == 1:
                city = next(iter(museum_cities))
            if city and city.strip().casefold() not in SUPPORTED_CITIES:
                continue

            image = activity.get("exhibitionImage") or {}
            image_url = (image.get("asset") or {}).get("url")
            tags = []
            for tag in facts.get("museumTag") or []:
                name = tag.get("museumTag") if tag.get("language") == "no" else None
                name = name or ((tag.get("lang") or {}).get("no") or {}).get("museumTag")
                if name:
                    tags.append(name.lower())

            for i, date_entry in enumerate(dates):
                start_at = date_entry.get("startDate")
                source_id = f"viti-{slug}-{i}"
                if not start_at or source_id in seen_ids:
                    continue
                seen_ids.add(source_id)
                events.append(EventData(
                    source="viti",
                    source_id=source_id,
                    title=title,
                    description=facts.get("exhibitionAbstract"),
                    start_at=start_at,
                    end_at=date_entry.get("endDate"),
                    location_name=", ".join(museum_names) or None,
                    city=city,
                    image_url=image_url,
                    url=f"{ARRANGEMENT_URL}/{slug}",
                    tags=tags,
                ))

        self.logger.info("Hentet %d hendelser fra Viti", len(events))
        return events
