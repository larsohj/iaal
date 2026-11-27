"""Slå sammen oppføringer som beskriver samme forestilling på tvers av kilder."""

import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")
SOURCE_PRIORITY = {
    source: index for index, source in enumerate((
        "parken", "viti", "bibliotek", "odeon", "aafk", "friskus", "ticketmaster", "tikkio", "bypatrioten",
    ))
}
PARKEN_ROOMS = {"hovedscene", "foajeen", "hovedsal scenehus"}
VENUE_ALIASES = {
    "ålesund bibliotek lokalsamlinga": "ålesund bibliotek",
    "klipra seniorsenter kaféen": "klipra seniorsenter",
    "jugendstilsenteret": "jugendstilsenteret og kube",
    "forum galleri": "forum ålesund",
    "innbyggerhjørnet 1 etg inngang fra rådhusplassen": "ålesund rådhus",
}
MOA_LIBRARY_LOCATIONS = {
    "amfi moa syd langelandsvegen 35 6010 ålesund norge",
    "1 etasje thon senter moa nye syd",
    "thon moa nye syd 1 etasje",
}


def _words(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[^\w]+", " ", normalized).strip()


def _start_key(value: str | None) -> tuple[datetime, int] | None:
    if not value or len(value) <= 10:
        return None
    try:
        start = datetime.fromisoformat(value)
    except ValueError:
        return None
    local = start.astimezone(OSLO) if start.tzinfo is not None else start.replace(tzinfo=OSLO)
    if start.tzinfo is None and local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
        return None
    return local.astimezone(timezone.utc), local.year


def _venue(event: dict) -> tuple[str, str]:
    location = _words(event.get("location_name"))
    suffix = location.removeprefix("parken kulturhus ")
    if suffix != location:
        if suffix in PARKEN_ROOMS:
            return "parken kulturhus", suffix
        if event.get("source") == "parken":
            location = suffix
    if location in MOA_LIBRARY_LOCATIONS and _words(event.get("organizer")) == "moa bibliotek":
        location = "moa bibliotek"
    return VENUE_ALIASES.get(location, location), ""


def _same_venue(first: tuple[str, str, str], second: tuple[str, str, str]) -> bool:
    venue, room, city = first
    other_venue, other_room, other_city = second
    return (
        bool(venue) and venue == other_venue
        and (not room or not other_room or room == other_room)
        and (not city or not other_city or city == other_city)
    )


def _merge(events: list[dict], failed_sources: set[str]) -> dict:
    ranked = sorted(events, key=lambda event: (
        event["source"] in failed_sources,
        SOURCE_PRIORITY.get(event["source"], len(SOURCE_PRIORITY)),
        event.get("source_id") or "",
    ))
    primary = ranked[0].copy()
    for field in ("end_at", "address", "city", "image_url", "description", "organizer"):
        if not primary.get(field):
            value = next((event[field] for event in ranked[1:] if event.get(field)), None)
            if value is not None:
                primary[field] = value
    for field in ("tags", "age_groups"):
        values = list(dict.fromkeys(value for event in ranked for value in event.get(field) or []))
        if values:
            primary[field] = values
    return primary


def deduplicate_events(events: list[dict], failed_sources: list[str]) -> list[dict]:
    groups = defaultdict(list)
    for index, event in enumerate(events):
        title = _words(event.get("title"))
        start = _start_key(event.get("start_at"))
        if not title or start is None or not event.get("source"):
            continue
        instant, year = start
        if event["source"] == "bypatrioten":
            title = title.removesuffix(f" {year}")
        place = (*_venue(event), _words(event.get("city")))
        groups[title, instant].append((index, place))

    merged = {}
    removed = set()
    failed = set(failed_sources)
    for candidates in groups.values():
        if len(candidates) < 2:
            continue
        matches = {
            index: tuple(other for other, other_place in candidates if _same_venue(place, other_place))
            for index, place in candidates
        }
        for index, peers in matches.items():
            # En uspesifisert sal kan passe med flere ulike saler. Slå bare sammen entydige treff.
            if len(peers) < 2 or index != peers[0] or any(matches[peer] != peers for peer in peers):
                continue
            rows = [events[peer] for peer in peers]
            if len({event["source"] for event in rows}) > 1:
                merged[index] = _merge(rows, failed)
                removed.update(peers[1:])
    return [merged.get(index, event) for index, event in enumerate(events) if index not in removed]
