"""
Kjør alle scrapers og skriv events.json til docs/.

Brukes av GitHub Actions for å generere statisk data
som serveres via GitHub Pages / jsDelivr.
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Sørg for at prosjektroten (parent av backend/) er i sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.scrapers.friskus_scraper import FriskusScraper
from backend.scrapers.viti_scraper import VitiScraper
from backend.scrapers.tikkio_scraper import TikkioScraper
from backend.scrapers.parken_scraper import ParkenScraper
from backend.scrapers.bibliotek_scraper import BibliotekScraper
from backend.scrapers.bypatrioten_scraper import BypatriotenScraper
from backend.scrapers.odeon_scraper import OdeonScraper
from backend.scrapers.ticketmaster_scraper import TicketmasterScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("generate")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs"


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
    """Normaliser til Europe/Oslo (UTC+1/+2) uten tidssone-suffix.

    Input-formater:
      - "2026-04-01T19:00:00"           → uendret (antas lokal)
      - "2026-04-01T19:00:00+0200"      → "2026-04-01T19:00:00"
      - "2026-04-01T19:00:00+02:00"     → "2026-04-01T19:00:00"
      - "2026-04-01T17:00:00+0000"      → "2026-04-01T19:00:00" (konvertert til CEST)
      - "2026-04-01T17:00:00.000Z"      → "2026-04-01T19:00:00" (UTC → CEST)
    """
    if not dt_str:
        return None

    # Fjern millisekunder (.000)
    dt_str = re.sub(r"\.\d+", "", dt_str)

    # Prøv å parse med tidssone
    tz_match = re.match(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
        r"(?:Z|([+-])(\d{2}):?(\d{2}))$",
        dt_str,
    )
    if not tz_match:
        # Ingen tidssone — returner som den er
        return dt_str

    naive_str = tz_match.group(1)
    dt = datetime.fromisoformat(naive_str)

    if dt_str.endswith("Z"):
        offset_hours, offset_mins = 0, 0
    else:
        sign = 1 if tz_match.group(2) == "+" else -1
        offset_hours = sign * int(tz_match.group(3))
        offset_mins = sign * int(tz_match.group(4))

    # Konverter til UTC
    utc_dt = dt - timedelta(hours=offset_hours, minutes=offset_mins)

    # Bestem Oslo-offset: CEST (UTC+2) apr-okt, CET (UTC+1) nov-mar
    month = utc_dt.month
    oslo_offset = 2 if 4 <= month <= 10 else 1
    # Mars og oktober har overgangsdager, men ±1 time er akseptabelt
    if month == 3 and utc_dt.day >= 25:
        oslo_offset = 2
    elif month == 10 and utc_dt.day >= 25:
        oslo_offset = 1

    local_dt = utc_dt + timedelta(hours=oslo_offset)
    return local_dt.strftime("%Y-%m-%dT%H:%M:%S")


def filter_past_events(events: list[dict]) -> list[dict]:
    """Fjern events som har starttid i fortiden."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    kept = []
    removed = 0
    for e in events:
        start = e.get("start_at")
        if start and start < now:
            removed += 1
            continue
        kept.append(e)
    if removed:
        logger.info(f"Fjernet {removed} utgåtte hendelser")
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
    events = normalize_events(events)
    events = filter_past_events(events)
    path = write_events_json(events, failed)

    total_sources = 8
    ok_sources = total_sources - len(failed)
    logger.info(f"Ferdig. {len(events)} hendelser fra {ok_sources}/{total_sources} kilder")

    if failed:
        logger.warning(f"Feilede kilder: {', '.join(failed)}")

    return path


if __name__ == "__main__":
    main()
