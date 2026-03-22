import logging
import time
from abc import ABC, abstractmethod

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.models import EventData


class BaseScraper(ABC):
    """Abstrakt baseklasse for alle scrapers."""

    source_name: str  # Må settes i subklasser

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "iaal-kulturapp/1.0 (+hobbyprosjekt)"

        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.logger = logging.getLogger(f"scraper.{self.source_name}")

    @abstractmethod
    def scrape(self) -> list[EventData]:
        """Hent alle hendelser fra kilden. Returnerer liste med EventData."""
        ...

    def _get(self, url: str, **kwargs) -> requests.Response:
        """GET med rate limiting (1s delay) og timeout."""
        time.sleep(1)
        response = self.session.get(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response
