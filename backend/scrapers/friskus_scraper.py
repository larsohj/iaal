import re
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from requests import RequestException

from backend.geography import (
    MUNICIPALITY_NAMES,
    STREET_ADDRESS,
    address_municipality,
    coordinates,
    point_municipality,
)
from backend.models import EventData
from backend.scrapers.base import BaseScraper

SULA_UUID = "db3b7632-82c3-4895-8c18-d24a559a42ad"
MUNICIPALITY_NUMBERS = {
    "58057c8b-b578-4082-8c11-97bfe366e5ab": "1508",
    SULA_UUID: "1531",
    "5900890d-0709-4ea3-bc16-f853e28aaacb": "1532",
}
LOCALITY_NUMBERS = {
    **{name.casefold(): number for number, name in MUNICIPALITY_NAMES.items()},
    "sjøholt": "1508",
    "vaksvika": "1508",
    "rollonhytta": "1531",
}
# Ålesund kommune oppgir samme besøksadresse for frivilligsentralen og tenestehuset.
SJOHOLT_VENUES = {
    "kommunehuset på sjøholt", "tenestehuset på sjøholt",
    "ørskog frivilligsentral", "ørskog frivillighetssentral",
}
SJOHOLT_ADDRESS = "Øyravegen 11, 6240 Ørskog"

API_URL = "https://api.friskus.com/api/v1"
BASE_URL = f"{API_URL}/events"

OSLO = ZoneInfo("Europe/Oslo")

# Disse lokale Friskus-oppslagene beskriver samme vintersesong, også når
# påminnelsene har ulike datoer. Friluftsrådet oppgir felles start og slutt.
STIKK_UT_WINTER_IDS = (
    "ab9dde43-e525-4767-9345-c2e6be70270e",  # Ålesund frivilligsentral
    "d3a46024-4c51-4fe0-ad3b-0cdcb30812ae",  # Skodje
    "b4d201a6-b87f-4e04-ac88-4e53468a54c9",  # Sandøy
    "9a0692e8-56d9-47e8-982a-a6ef68ef7f66",  # Ørskog
)
STIKK_UT_WINTER_DATES = ("2026-12-01", "2027-04-15")
# Bekreftede, løpende utlysninger som Friskus likevel har merket som tidsfestet.
ONGOING_VOLUNTEER_IDS = {
    "f0cf0e1b-8516-4d9c-9299-aae7f4a67072",  # Dugnad hele året
    "fb482108-e841-4933-856c-6ea9de65b87c",  # Dagsenteret søker frivillige
    "6fe8aabb-b7b4-4ecb-927e-cc4941d7baf2",  # Frivillig for Stikk UT!
}

EVENT_SOURCE_TAGS = {
    "dnt": ["friluftsliv", "tur"],
}


def _instant(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _local_date(value: str | None) -> str | None:
    instant = _instant(value)
    if instant is None:
        return None
    return (instant.astimezone(OSLO) if instant.tzinfo is not None else instant).date().isoformat()


def _listing_period(item: dict, detail: dict, is_recurring: bool) -> tuple[str, str] | None:
    if item["id"] in STIKK_UT_WINTER_IDS:
        return STIKK_UT_WINTER_DATES
    if not is_recurring:
        return None

    is_open = detail.get("event_type") == "open"
    ongoing_volunteering = (
        item["id"] in ONGOING_VOLUNTEER_IDS and (detail.get("type") or {}).get("key") == "TASK"
    )
    if not (is_open or ongoing_volunteering):
        return None

    rule = detail.get("rrule")
    rule = rule if isinstance(rule, dict) else {}
    start = _local_date(rule.get("start_at")) or _local_date(detail.get("start_at"))
    end = _local_date(rule.get("until")) or _local_date(detail.get("end_at"))
    return (start, end) if start and end and start < end else None


def _merge_stikk_ut_season(events: list[EventData]) -> list[EventData]:
    priority = {f"friskus-{event_id}": rank for rank, event_id in enumerate(STIKK_UT_WINTER_IDS)}
    groups = defaultdict(list)
    for index, event in enumerate(events):
        if event.source_id in priority and event.city and (event.start_at, event.end_at) == STIKK_UT_WINTER_DATES:
            groups[event.city].append(index)

    suppressed = set()
    for city, indexes in groups.items():
        primary = min(indexes, key=lambda index: priority[events[index].source_id])
        event = events[primary]
        event.source_id = f"friskus-stikk-ut-vinter-{event.start_at}-{city.casefold()}"
        if len(indexes) > 1:
            # En deltaker velger turmål. Oppslaget har ikke et felles oppmøtested.
            event.location_name = f"{city} kommune"
            event.address = None
            event.latitude = None
            event.longitude = None
        suppressed.update(index for index in indexes if index != primary)
    return [event for index, event in enumerate(events) if index not in suppressed]


def _active_occurrence(occurrence: dict) -> bool:
    return (
        occurrence.get("published") is not False
        and not occurrence.get("is_canceled")
        and not occurrence.get("deleted_at")
    )


def _matching_occurrence(detail: dict, start_at: str | None) -> dict:
    start = _instant(start_at)
    if start is None:
        return {}
    occurrences = detail.get("occurrences") or [detail.get("occurrence") or {}]
    matches = [entry for entry in occurrences if _instant(entry.get("start_at")) == start]
    return next((entry for entry in matches if _active_occurrence(entry)), matches[0] if matches else {})


def _occurrence_id(occurrence: dict, start: datetime) -> str:
    stamp = start.astimezone(timezone.utc) if start.tzinfo is not None else start
    return occurrence.get("id") or occurrence.get("dnt_id") or stamp.isoformat()


def _text_key(value: str) -> str:
    return " ".join(value.strip().rstrip(".").casefold().split())


def _registration_key(detail: dict, is_dnt: bool, start_at: str | None) -> tuple | None:
    if not start_at:
        return None
    try:
        start = datetime.fromisoformat(start_at)
    except ValueError:
        return None
    if start.tzinfo is None:
        return None

    urls = [detail.get("url")] if is_dnt else [
        link.get("url") for link in detail.get("external_links") or []
    ]
    registrations = set()
    for url in filter(None, urls):
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        path = parsed.path.rstrip("/")
        if (parsed.scheme in {"http", "https"}
                and parsed.netloc.lower() == "aktiviteter.dnt.no"
                and re.fullmatch(r"/register/[^/]+", path)
                and parsed.fragment in {"", "/"}):
            registrations.add((path, parsed.query, start))
    return registrations.pop() if len(registrations) == 1 else None


def _location_quality(event: EventData) -> tuple[bool, ...]:
    return (
        event.city is not None,
        bool(event.address),
        event.latitude is not None and event.longitude is not None,
        bool(event.location_name),
    )


class FriskusScraper(BaseScraper):
    source_name = "friskus"

    def scrape(self) -> list[EventData]:
        items = {}
        for municipality_id in MUNICIPALITY_NUMBERS:
            page = 1
            while True:
                response = self._get(BASE_URL, params={
                    "municipalities[]": municipality_id,
                    "page": page,
                }).json()

                for item in response.get("data", []):
                    # Søkene overlapper. Kommune bestemmes fra detaljene etter deduplisering.
                    items.setdefault(item["id"], item)

                meta = response.get("meta") or {}
                if page >= meta.get("last_page", 1):
                    break
                page += 1

        events = []
        registrations = defaultdict(list)
        geocodes = {}
        for item in items.values():
            for event, registration in self._events(item, geocodes):
                if registration is not None:
                    registrations[registration].append((len(events), item.get("event_source") == "dnt"))
                events.append(event)

        suppressed = set()
        for entries in registrations.values():
            if len(entries) != 2:
                continue
            (first_index, first_is_dnt), (second_index, second_is_dnt) = entries
            if first_is_dnt == second_is_dnt:
                continue
            native_index, dnt_index = (
                (second_index, first_index) if first_is_dnt else (first_index, second_index)
            )
            native, dnt = events[native_index], events[dnt_index]
            if native.city and dnt.city and native.city != dnt.city:
                continue
            keep, duplicate = native_index, dnt_index
            if _location_quality(dnt) > _location_quality(native):
                keep, duplicate = dnt_index, native_index
            kept = events[keep]
            kept.tags = list(dict.fromkeys([*kept.tags, *events[duplicate].tags]))
            suppressed.add(duplicate)
        events = _merge_stikk_ut_season([event for index, event in enumerate(events) if index not in suppressed])

        self.logger.info("Hentet %d hendelser fra Friskus. %d uten sikker kommune.",
                         len(events), sum(event.city is None for event in events))
        return events

    def _events(self, item: dict, geocodes: dict) -> Iterator[tuple[EventData, tuple | None]]:
        event_id = item["id"]
        is_dnt = item.get("event_source") == "dnt"
        detail_path = "dnt/events" if is_dnt else "events"
        detail = self._optional_json(
            f"{API_URL}/{detail_path}/{event_id}", {"municipality": "default"},
        ).get("data")
        if not isinstance(detail, dict):
            detail = {}
        if detail.get("is_canceled") or detail.get("is_published") is False:
            return

        is_recurring = bool(item.get("is_recurring")) or detail.get("is_once") is False
        occurrences = detail.get("occurrences")
        period = _listing_period(item, detail, is_recurring) if not is_dnt else None
        if period is not None:
            if isinstance(occurrences, list) and not any(
                _instant(entry.get("start_at")) and _active_occurrence(entry) for entry in occurrences
            ):
                return
            occurrence = detail.get("occurrence")
            if occurrence and not _active_occurrence(occurrence):
                return
            start, end = period
            result = self._event(
                {**item, "start_at": start, "end_at": end}, geocodes, detail, {}, False,
            )
            if result is not None:
                yield result
            return

        if is_recurring and isinstance(occurrences, list):
            seen = set()
            for occurrence in occurrences:
                start = _instant(occurrence.get("start_at"))
                if start is None or not _active_occurrence(occurrence):
                    continue
                occurrence_id = _occurrence_id(occurrence, start)
                if occurrence_id in seen:
                    continue
                seen.add(occurrence_id)
                result = self._event(item, geocodes, detail, occurrence, is_recurring, occurrence_id)
                if result is not None:
                    yield result
            return

        occurrence = _matching_occurrence(detail, item.get("start_at"))
        if occurrence and not _active_occurrence(occurrence):
            return
        start = _instant(occurrence.get("start_at"))
        occurrence_id = _occurrence_id(occurrence, start) if is_recurring and start is not None else None
        result = self._event(item, geocodes, detail, occurrence, is_recurring, occurrence_id)
        if result is not None:
            yield result

    def _event(
        self, item: dict, geocodes: dict, detail: dict, occurrence: dict,
        is_recurring: bool, occurrence_id: str | None = None,
    ) -> tuple[EventData, tuple | None] | None:
        event_id = item["id"]
        event_source = item.get("event_source")
        is_dnt = event_source == "dnt"
        locality = None
        if is_dnt:
            locality = occurrence.get("location_city") or None
            postal_code = occurrence.get("location_postal_code")
            postal_place = f"{postal_code} {locality or ''}".strip() if postal_code else locality
            street = occurrence.get("location_address_line1")
            extra = occurrence.get("location_address_line2")
            lat, lng = coordinates(
                occurrence.get("location_latitude"), occurrence.get("location_longitude"),
            )
            municipality_ids = occurrence.get("location_municipalities") or []
            # Rollonhytta er et bekreftet turmål i Sula. Krev også Sula i forekomstens kommuneliste.
            if (not (street or extra or postal_code or locality) and lat is None
                    and SULA_UUID in municipality_ids
                    and _text_key(item["name"]).endswith(" til rollonhytta")):
                locality = "Rollonhytta"
            location_name = street or locality
            address = None
            if street or extra or postal_code:
                address = ", ".join(filter(None, (street, extra, postal_place)))
            if street and ", " in street and not (extra or postal_place):
                first_line, suffix = street.split(", ", 1)
                venue_and_street = re.split(r"\s+(?:i|på)\s+", first_line)
                if (len(venue_and_street) == 2 and STREET_ADDRESS.fullmatch(venue_and_street[1])
                        and _text_key(suffix) in LOCALITY_NUMBERS):
                    location_name, street = venue_and_street
                    address = f"{street}, {suffix.rstrip(' .')}"
            public_path = "events/dnt"
        else:
            place = detail.get("address") or {}
            address = place.get("address") or None
            location_name = place.get("name") or address
            if _text_key(location_name or "") in SJOHOLT_VENUES:
                reported_address = _text_key(address or "")
                if reported_address in SJOHOLT_VENUES | {"", "øyravegen 11"}:
                    address = SJOHOLT_ADDRESS
                    locality = "Sjøholt"
            lat, lng = coordinates(place.get("lat"), place.get("lng"))
            municipality_ids = [
                entry["id"] for entry in detail.get("municipalities") or [] if entry.get("id")
            ]
            public_path = "events"

        number = self._venue_municipality(address, locality, lat, lng, geocodes)
        if number is None and len(set(municipality_ids)) == 1:
            municipality_id = municipality_ids[0]
            number = MUNICIPALITY_NUMBERS.get(municipality_id, municipality_id)
        if number is not None and number not in MUNICIPALITY_NAMES:
            return None

        start_at = occurrence["start_at"] if occurrence else item.get("start_at")
        end_at = occurrence.get("end_at") if occurrence or is_recurring else item.get("end_at")
        source_id = f"friskus-{event_id}"
        if occurrence_id is not None:
            source_id = f"{source_id}-{occurrence_id}"

        event = EventData(
            source="friskus",
            source_id=source_id,
            title=item["name"],
            start_at=start_at,
            end_at=end_at,
            is_free=item.get("is_free"),
            is_recurring=is_recurring,
            organizer=(item.get("organization") or {}).get("name"),
            location_name=location_name,
            address=address,
            city=MUNICIPALITY_NAMES.get(number),
            latitude=lat,
            longitude=lng,
            image_url=item.get("thumbnail_url"),
            url=f"https://alesund.friskus.com/{public_path}/{event_id}",
            age_groups=item.get("age_group", []),
            tags=EVENT_SOURCE_TAGS.get(event_source, []),
        )
        return event, _registration_key(detail, is_dnt, event.start_at)

    def _venue_municipality(self, address, locality, lat, lng, geocodes) -> str | None:
        # Kartverket avklarer også steder utenfor de tre kommunene.
        key = (address, locality, lat, lng)
        if key not in geocodes:
            number = None
            if lat is not None and lng is not None:
                number = point_municipality(self._optional_json, lat, lng)

            if number is None and address:
                number = address_municipality(self._optional_json, address, LOCALITY_NUMBERS.keys())

            if number is None and locality:
                # DNT oppgir noen ganger bare et stedsnavn, f.eks. «Giske».
                number = LOCALITY_NUMBERS.get(_text_key(locality))
            geocodes[key] = number
        return geocodes[key]

    def _optional_json(self, url: str, params: dict) -> dict:
        try:
            payload = self._get(url, params=params).json()
        except (RequestException, ValueError) as error:
            self.logger.debug("Kunne ikke hente stedsdata fra %s: %s", url, error)
            return {}
        return payload if isinstance(payload, dict) else {}
