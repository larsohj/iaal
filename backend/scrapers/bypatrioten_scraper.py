import json
import re
from collections import defaultdict
from datetime import date
from html import unescape
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
        schedules = defaultdict(set)
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.get_text())
            except ValueError:
                continue
            if not isinstance(data, dict) or data.get("@type") != "Event":
                continue
            try:
                first = date.fromisoformat(data["startDate"]).isoformat()
                last = date.fromisoformat(data.get("endDate") or first).isoformat()
            except (KeyError, TypeError, ValueError):
                continue
            if last >= first and isinstance(data.get("name"), str) and isinstance(data.get("url"), str):
                schedules[(unescape(data["url"]), unescape(data["name"]).strip())].add((first, last))

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

            # Dato og kilde-ID kan være felles for flere forestillinger.
            parsed = urlparse(event_url)
            params = parse_qs(parsed.query)
            occurrence = params.get("occurrence", [None])[0]

            occurrence_time = params.get("time", [""])[0]
            id_parts = ["bypatrioten", event_id]
            if occurrence:
                id_parts.append(occurrence)
            if re.fullmatch(r"[0-9]+", occurrence_time):
                id_parts.append(occurrence_time)
            source_id = "-".join(id_parts)

            # Tidsrom
            time_tag = article.select_one(".mec-event-time")
            time_text = time_tag.get_text(strip=True) if time_tag else None
            start_at, end_at = self._parse_time(occurrence, time_text) if occurrence else (None, None)

            if not occurrence:
                dates = schedules.get((event_url, title), set())
                if len(dates) == 1:
                    first, last = next(iter(dates))
                    start_at, end_at = self._parse_time(first, time_text)
                    if end_at:
                        end_at = last + end_at[10:]
                    elif last != first:
                        end_at = last

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
        """Behold datoen alene når kalenderen ikke oppgir klokkeslett."""
        try:
            day = date.fromisoformat(date_str).isoformat()
        except (TypeError, ValueError):
            return None, None

        clock = r"([01]?\d|2[0-3])[.:]([0-5]\d)"
        match = re.fullmatch(rf"{clock}(?:\s*[-–]\s*{clock})?", (time_text or "").strip())
        if not match:
            return day, None

        hour, minute, end_hour, end_minute = match.groups()
        start = f"{day}T{hour.zfill(2)}:{minute}:00"
        end = f"{day}T{end_hour.zfill(2)}:{end_minute}:00" if end_hour else None
        return start, end
