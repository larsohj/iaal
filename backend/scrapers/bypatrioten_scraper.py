import re
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

from backend.models import EventData
from backend.scrapers.base import BaseScraper

KALENDER_URL = "https://bypatrioten.com/kalender/"


class BypatriotenScraper(BaseScraper):
    source_name = "bypatrioten"

    def scrape(self) -> list[EventData]:
        resp = self._get(KALENDER_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        articles = soup.select("article.mec-event-article")
        events = []

        for article in articles:
            # Hopp over "past events"
            if "mec-past-event" in article.get("class", []):
                continue

            link = article.select_one("h4.mec-event-title a")
            if not link:
                continue

            title = link.get_text(strip=True)
            event_url = link.get("href", "")
            event_id = link.get("data-event-id", "")

            # Hent occurrence-dato fra URL
            parsed = urlparse(event_url)
            params = parse_qs(parsed.query)
            occurrence = params.get("occurrence", [None])[0]

            source_id = f"bypatrioten-{event_id}-{occurrence}" if occurrence else f"bypatrioten-{event_id}"

            # Tidsrom
            time_tag = article.select_one(".mec-event-time")
            time_text = time_tag.get_text(strip=True) if time_tag else None
            start_at, end_at = self._parse_time(occurrence, time_text) if occurrence else (None, None)

            # Sted
            place_tag = article.select_one(".mec-event-loc-place")
            location_name = place_tag.get_text(strip=True) if place_tag else None

            # Bilde
            img = article.select_one(".mec-event-image img")
            image_url = img.get("src") if img else None

            events.append(EventData(
                source="bypatrioten",
                source_id=source_id,
                title=title,
                start_at=start_at,
                end_at=end_at,
                location_name=location_name,
                image_url=image_url,
                url=event_url,
            ))

        self.logger.info(f"Hentet {len(events)} hendelser fra Bypatrioten")
        return events

    @staticmethod
    def _parse_time(date_str: str, time_text: str | None) -> tuple[str | None, str | None]:
        """Parse 'YYYY-MM-DD' + 'HH.MM - HH.MM' til ISO 8601."""
        from datetime import datetime

        if not date_str:
            return None, None

        start_at = None
        end_at = None

        try:
            base_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None, None

        if time_text:
            match = re.match(r"(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})", time_text)
            if match:
                start_at = base_date.replace(
                    hour=int(match.group(1)), minute=int(match.group(2))
                ).isoformat()
                end_at = base_date.replace(
                    hour=int(match.group(3)), minute=int(match.group(4))
                ).isoformat()
                return start_at, end_at

        start_at = base_date.isoformat()
        return start_at, end_at
