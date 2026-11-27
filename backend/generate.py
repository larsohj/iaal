"""
Kjør alle scrapers og skriv events.json til docs/.

Brukes av GitHub Actions for å generere statisk data
som serveres via GitHub Pages / jsDelivr.
"""

import json
import logging
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Sørg for at prosjektroten (parent av backend/) er i sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.deduplicate import deduplicate_events
from backend.scrapers.friskus_scraper import FriskusScraper
from backend.scrapers.viti_scraper import VitiScraper
from backend.scrapers.tikkio_scraper import TikkioScraper
from backend.scrapers.parken_scraper import ParkenScraper
from backend.scrapers.bibliotek_scraper import BibliotekScraper
from backend.scrapers.bypatrioten_scraper import BypatriotenScraper
from backend.scrapers.odeon_scraper import OdeonScraper
from backend.scrapers.ticketmaster_scraper import TicketmasterScraper
from backend.scrapers.aafk_scraper import AafkScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("generate")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs"
OSLO = ZoneInfo("Europe/Oslo")


def run_scrapers() -> tuple[list[dict], list[str]]:
    """Kjør alle scrapers. Returnerer (events_dicts, failed_sources)."""
    scrapers = [
        FriskusScraper(),
        VitiScraper(),
        TikkioScraper(),
        ParkenScraper(),
        BibliotekScraper(),
        BypatriotenScraper(),
        OdeonScraper(),
        TicketmasterScraper(),
        AafkScraper(),
    ]

    all_events = []
    failed = []

    for scraper in scrapers:
        try:
            events = scraper.scrape()
            logger.info(f"{scraper.source_name}: {len(events)} hendelser")
            all_events.extend(e.to_dict() for e in events)
        except Exception as e:
            logger.error(f"{scraper.source_name} feilet: {e}")
            failed.append(scraper.source_name)

    return all_events, failed


def merge_with_existing(new_events: list[dict], failed_sources: list[str]) -> list[dict]:
    """Bevar events fra kilder som feilet ved å merge med forrige events.json.

    Hvis en scraper feiler returnerer den 0 events. Uten denne logikken
    ville alle hendelser fra den kilden forsvinne fra events.json.
    Vi beholder derfor forrige versjon av events fra feilede kilder.
    """
    existing_path = OUTPUT_DIR / "events.json"
    if not failed_sources or not existing_path.exists():
        return new_events

    try:
        with open(existing_path) as f:
            existing = json.load(f)
        old_events = existing.get("events", [])
    except (json.JSONDecodeError, KeyError):
        return new_events

    # Behold events fra feilede kilder
    preserved = [e for e in old_events if e.get("source") in failed_sources]
    if preserved:
        logger.info(
            f"Bevarer {len(preserved)} hendelser fra feilede kilder: {failed_sources}"
        )

    return new_events + preserved


def normalize_datetime(dt_str: str | None) -> str | None:
    """Behold datoer og skriv tidsfestede arrangementer som lokal tid i Oslo."""
    if not dt_str or len(dt_str) == 10:
        return dt_str
    try:
        value = datetime.fromisoformat(dt_str)
    except ValueError:
        return dt_str
    if value.tzinfo is not None:
        value = value.astimezone(OSLO).replace(tzinfo=None)
    return value.isoformat(timespec="seconds")


def _utc_deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        deadline = datetime.fromisoformat(value)
    except ValueError:
        return None
    if len(value) == 10:
        # En dato uten klokkeslett gjelder hele den lokale dagen.
        deadline = datetime.combine(deadline.date(), time.max)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=OSLO)
    return deadline.astimezone(timezone.utc)


def filter_past_events(events: list[dict], *, now: datetime | None = None) -> list[dict]:
    """Behold pågående og kommende arrangementer med eller uten tidssone."""
    now = now if now is not None else datetime.now(timezone.utc)
    kept = []
    for event in events:
        start = _utc_deadline(event.get("start_at"))
        end = _utc_deadline(event.get("end_at"))
        deadline = max(start, end) if start is not None and end is not None else end or start
        if deadline is None or deadline >= now:
            kept.append(event)
    if len(kept) < len(events):
        logger.info("Fjernet %d utgåtte hendelser", len(events) - len(kept))
    return kept


def normalize_events(events: list[dict]) -> list[dict]:
    """Normaliser tidssoner for alle events."""
    for e in events:
        e["start_at"] = normalize_datetime(e.get("start_at"))
        e["end_at"] = normalize_datetime(e.get("end_at"))
    return events


def write_events_json(events: list[dict], failed: list[str]) -> Path:
    """Skriv events.json til docs/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(events),
        "failed_sources": failed,
        "events": events,
    }

    output_path = OUTPUT_DIR / "events.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Skrev {len(events)} hendelser til {output_path}")
    return output_path


def main():
    logger.info("Starter scraping...")
    events, failed = run_scrapers()
    events = merge_with_existing(events, failed)
    events = filter_past_events(events)
    before_deduplication = len(events)
    events = deduplicate_events(events, failed)
    logger.info("Slo sammen %d dublettoppføringer", before_deduplication - len(events))
    events = normalize_events(events)
    path = write_events_json(events, failed)

    total_sources = 9
    ok_sources = total_sources - len(failed)
    logger.info(f"Ferdig. {len(events)} hendelser fra {ok_sources}/{total_sources} kilder")

    if failed:
        logger.warning(f"Feilede kilder: {', '.join(failed)}")

    return path


if __name__ == "__main__":
    main()
