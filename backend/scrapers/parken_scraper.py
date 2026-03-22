import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend.models import EventData
from backend.scrapers.base import BaseScraper

PROGRAM_URL = "https://www.parkenkulturhus.no/program/"


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
                import json
                categories = json.loads(data_category)
                tags.extend(categories)
            except (json.JSONDecodeError, TypeError):
                pass

            sale_status = article.select_one(".sale-status p")
            if sale_status:
                tags.append(sale_status.get_text(strip=True).lower())

            # Parse dato til ISO 8601
            start_at = self._parse_date(date_text) if date_text else None

            events.append(EventData(
                source="parken",
                source_id=f"parken-{slug}",
                title=title,
                organizer=organizer,
                start_at=start_at,
                location_name=location_name,
                image_url=image_url,
                url=detail_url,
                tags=tags,
            ))

        self.logger.info(f"Hentet {len(events)} hendelser fra Parken")
        return events

    @staticmethod
    def _parse_date(date_text: str) -> str | None:
        """Konverter '22. mar 2026' til ISO 8601 dato."""
        import locale
        from datetime import datetime

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
