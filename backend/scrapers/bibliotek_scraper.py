import re
from urllib.parse import urljoin, parse_qs, urlparse

from bs4 import BeautifulSoup

from backend.models import EventData
from backend.scrapers.base import BaseScraper

BASE_URL = "https://alesundsbiblioteka.no/"


class BibliotekScraper(BaseScraper):
    source_name = "bibliotek"

    def scrape(self) -> list[EventData]:
        resp = self._get(BASE_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        event_items = soup.select("li.event")
        events = []

        for item in event_items:
            link = item.find("a", href=True)
            if not link:
                continue

            href = link["href"]
            detail_url = urljoin(BASE_URL, href)

            # Hent event-ID fra URL
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            event_id = params.get("Id", [None])[0]
            if not event_id:
                continue

            title_tag = item.select_one(".event-title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            location_tag = item.select_one(".event-location")
            location_name = location_tag.get_text(strip=True) if location_tag else None

            # Parse dato og tid
            day_tag = item.select_one(".event-date-day")
            month_tag = item.select_one(".event-date-month")
            time_tag = item.select_one(".event-time")

            start_at = self._parse_datetime(item)

            # Bilde
            img = item.find("img")
            image_url = None
            if img and img.get("src"):
                image_url = urljoin(BASE_URL, img["src"])

            events.append(EventData(
                source="bibliotek",
                source_id=f"bibliotek-{event_id}",
                title=title,
                start_at=start_at,
                location_name=location_name,
                image_url=image_url,
                url=detail_url,
                is_free=True,
            ))

        self.logger.info(f"Hentet {len(events)} hendelser fra biblioteket")
        return events

    @staticmethod
    def _parse_datetime(item) -> str | None:
        """Parse dato fra bibliotek-HTML: day='22.', month='03.', year='2026', time='kl. 10:00'"""
        from datetime import datetime

        date_parts = item.select(".event-date-day, .event-date-month")
        time_tag = item.select_one(".event-time")

        if len(date_parts) < 3:
            return None

        try:
            day = int(date_parts[0].get_text(strip=True).rstrip("."))
            month = int(date_parts[1].get_text(strip=True).rstrip("."))
            year = int(date_parts[2].get_text(strip=True).rstrip("."))
        except (ValueError, IndexError):
            return None

        hour, minute = 0, 0
        if time_tag:
            time_text = time_tag.get_text(strip=True)
            time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))

        try:
            dt = datetime(year, month, day, hour, minute)
            return dt.isoformat()
        except ValueError:
            return None
