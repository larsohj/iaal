import json
import re
from dataclasses import replace
from datetime import datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from backend.models import EventData
from backend.scrapers.base import BaseScraper

PROGRAM_URL = "https://www.parkenkulturhus.no/program/"
OSLO = ZoneInfo("Europe/Oslo")
CLOCK_TIMES = r"kl\.\s*(\d{1,2}):(\d{2})(?:\s*[-–]\s*(\d{1,2}):(\d{2}))?"
SHOW_TIME = re.compile(r"(\d{1,2})\.(\d{1,2})\.?\s*[-–]\s*" + CLOCK_TIMES)
SINGLE_TIME = re.compile(r"(\d{1,2}\.\s*\w+\s+\d{4})\s+" + CLOCK_TIMES)


class ParkenScraper(BaseScraper):
    source_name = "parken"

    def scrape(self) -> list[EventData]:
        resp = self._get(PROGRAM_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        articles = soup.select("article.tease-event")
        events = []

        for article in articles:
            link = article.find("a", href=True)
            if not link:
                continue

            detail_url = urljoin(PROGRAM_URL, link["href"])

            # Hent slug fra URL for source_id
            slug_match = re.search(r"/program/(.+?)/?$", detail_url)
            slug = slug_match.group(1) if slug_match else detail_url

            title_tag = article.select_one("h3")
            title = title_tag.get_text(strip=True) if title_tag else ""

            subtitle_tag = article.select_one("h4")
            organizer = subtitle_tag.get_text(strip=True) if subtitle_tag else None

            date_tag = article.select_one("p.dates")
            date_text = date_tag.get_text(strip=True) if date_tag else None

            venue_tag = article.select_one("p.venue")
            venue = venue_tag.get_text(strip=True) if venue_tag else None
            location_name = f"Parken kulturhus – {venue}" if venue else "Parken kulturhus"

            # Bilde
            figure = article.find("figure")
            image_url = figure.get("data-source") if figure else None

            # Status og kategori-tags
            tags = []
            data_category = article.get("data-category", "[]")
            try:
                categories = json.loads(data_category)
                tags.extend(categories)
            except (json.JSONDecodeError, TypeError):
                pass

            sale_status = article.select_one(".sale-status p")
            if sale_status:
                tags.append(sale_status.get_text(strip=True).lower())

            event = EventData(
                source="parken",
                source_id=f"parken-{slug}",
                title=title,
                organizer=organizer,
                start_at=self._parse_date(date_text) if date_text else None,
                location_name=location_name,
                image_url=image_url,
                url=detail_url,
                tags=tags,
            )
            events.extend(self._fetch_performances(event))

        self.logger.info(f"Hentet {len(events)} hendelser fra Parken")
        return events

    def _fetch_performances(self, event: EventData) -> list[EventData]:
        try:
            resp = self._get(event.url)
        except Exception:
            return [event]

        soup = BeautifulSoup(resp.text, "html.parser")
        start, end = self._structured_times(soup)
        shows = soup.select("#shows p.event")
        if shows:
            anchor = start or (datetime.fromisoformat(event.start_at) if event.start_at else None)
            if anchor:
                performances = self._parse_shows(shows, event, anchor)
                if performances:
                    return performances

        date_tag = soup.select_one("p.dates.ingress")
        if date_tag is None:
            date_tag = soup.find("p", string=SINGLE_TIME)
        match = SINGLE_TIME.search(date_tag.get_text(" ", strip=True)) if date_tag else None
        if match and (date := self._parse_date(match[1])):
            try:
                start, end = self._with_times(datetime.fromisoformat(date), match.groups()[1:])
            except ValueError:
                pass

        if start:
            return [replace(event, start_at=start.isoformat(), end_at=end.isoformat() if end else None)]
        return [event]

    def _parse_shows(self, shows, event: EventData, anchor: datetime) -> list[EventData]:
        year = anchor.year
        previous_date = None
        performances = {}
        for show in shows:
            date_tag = show.select_one(".date")
            match = SHOW_TIME.fullmatch(date_tag.get_text(" ", strip=True)) if date_tag else None
            if not match:
                continue

            day, month = int(match[1]), int(match[2])
            show_date = (month, day)
            if previous_date is None:
                # Metadata kan vise neste ledige forestilling, mens listen også viser tidligere datoer.
                month_offset = month - anchor.month
                show_year = year + (month_offset < -6) - (month_offset > 6)
            else:
                show_year = year + (show_date < previous_date)
            try:
                start, end = self._with_times(datetime(show_year, month, day), match.groups()[2:])
            except ValueError:
                continue
            year, previous_date = show_year, show_date

            ticket = show.select_one("a[href]")
            source_id = f"{event.source_id}-{start:%Y%m%dT%H%M}"
            performances[source_id] = replace(
                event,
                source_id=source_id,
                start_at=start.isoformat(),
                end_at=end.isoformat() if end else None,
                url=urljoin(event.url, ticket["href"]) if ticket else event.url,
            )
        return list(performances.values())

    @staticmethod
    def _structured_times(soup: BeautifulSoup) -> tuple[datetime | None, datetime | None]:
        # Parken kan ha uescapede anførselstegn i JSON-LD-beskrivelsen.
        # Les datofeltene direkte fra Event-blokken.
        for script in soup.select('script[type="application/ld+json"]'):
            text = script.get_text()
            if not re.search(r'"@type"\s*:\s*"Event"', text):
                continue
            start = re.search(r'"startDate"\s*:\s*"([^"]+)"', text)
            end = re.search(r'"endDate"\s*:\s*"([^"]+)"', text)
            try:
                return (
                    ParkenScraper._local_datetime(start[1]) if start else None,
                    ParkenScraper._local_datetime(end[1]) if end else None,
                )
            except ValueError:
                continue
        return None, None

    @staticmethod
    def _local_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone(OSLO).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _with_times(date: datetime, times: tuple) -> tuple[datetime, datetime | None]:
        hour, minute, end_hour, end_minute = times
        start = date.replace(hour=int(hour), minute=int(minute))
        end = None
        if end_hour is not None:
            end = date.replace(hour=int(end_hour), minute=int(end_minute))
            if end < start:
                end += timedelta(days=1)
        return start, end

    @staticmethod
    def _parse_date(date_text: str) -> str | None:
        """Konverter '22. mar 2026' til ISO 8601 dato."""
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "mai": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "okt": 10, "nov": 11, "des": 12,
        }
        match = re.match(r"(\d{1,2})\.\s*(\w+)\s+(\d{4})", date_text)
        if not match:
            return None

        day = int(match.group(1))
        month_str = match.group(2).lower()
        year = int(match.group(3))

        month = months.get(month_str)
        if not month:
            return None

        try:
            dt = datetime(year, month, day)
            return dt.isoformat()
        except ValueError:
            return None
