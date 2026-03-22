import logging
import sys

from backend.db import upsert_events
from backend.scrapers.friskus_scraper import FriskusScraper
from backend.scrapers.viti_scraper import VitiScraper
from backend.scrapers.tikkio_scraper import TikkioScraper
from backend.scrapers.parken_scraper import ParkenScraper
from backend.scrapers.bibliotek_scraper import BibliotekScraper
from backend.scrapers.bypatrioten_scraper import BypatriotenScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("aggregator")


def main():
    scrapers = [
        FriskusScraper(),
        VitiScraper(),
        TikkioScraper(),
        ParkenScraper(),
        BibliotekScraper(),
        BypatriotenScraper(),
    ]

    all_events = []
    failed = []

    for scraper in scrapers:
        try:
            events = scraper.scrape()
            logger.info(f"{scraper.source_name}: {len(events)} hendelser")
            all_events.extend(events)
        except Exception as e:
            logger.error(f"{scraper.source_name} feilet: {e}")
            failed.append(scraper.source_name)

    if all_events:
        upsert_events(all_events)

    logger.info(f"Ferdig. Totalt: {len(all_events)} hendelser fra {len(scrapers) - len(failed)}/{len(scrapers)} kilder")
    if failed:
        logger.warning(f"Feilet: {', '.join(failed)}")


if __name__ == "__main__":
    main()
