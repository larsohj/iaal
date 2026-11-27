import re
from datetime import datetime
from math import isfinite

from requests import RequestException

from backend.models import EventData
from backend.scrapers.base import BaseScraper

MUNICIPALITY_NUMBERS = {
    "58057c8b-b578-4082-8c11-97bfe366e5ab": "1508",
    "db3b7632-82c3-4895-8c18-d24a559a42ad": "1531",
    "5900890d-0709-4ea3-bc16-f853e28aaacb": "1532",
}
MUNICIPALITY_NAMES = {"1508": "Ålesund", "1531": "Sula", "1532": "Giske"}

API_URL = "https://api.friskus.com/api/v1"
BASE_URL = f"{API_URL}/events"
KARTVERKET_URL = "https://api.kartverket.no"

EVENT_SOURCE_TAGS = {
    "dnt": ["friluftsliv", "tur"],
}


def _coordinates(lat, lng) -> tuple[float | None, float | None]:
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None
    if isfinite(lat) and isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180:
        return lat, lng
    return None, None


def _dnt_occurrence(detail: dict, start_at: str | None) -> dict:
    if not start_at:
        return {}
    try:
        start = datetime.fromisoformat(start_at)
    except ValueError:
        return {}
    for occurrence in detail.get("occurrences") or []:
        occurrence_start = occurrence.get("start_at")
        if not occurrence_start or occurrence.get("deleted_at"):
            continue
        try:
            if datetime.fromisoformat(occurrence_start) == start:
                return occurrence
        except ValueError:
            continue
    return {}


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
        geocodes = {}
        for item in items.values():
            event = self._event(item, geocodes)
            if event is not None:
                events.append(event)

        self.logger.info("Hentet %d hendelser fra Friskus. %d uten sikker kommune.",
                         len(events), sum(event.city is None for event in events))
        return events

    def _event(self, item: dict, geocodes: dict) -> EventData | None:
        event_id = item["id"]
        event_source = item.get("event_source")
        is_dnt = event_source == "dnt"
        detail_path = "dnt/events" if is_dnt else "events"
        detail = self._optional_json(
            f"{API_URL}/{detail_path}/{event_id}", {"municipality": "default"},
        ).get("data")
        if not isinstance(detail, dict):
            detail = {}

        locality = None
        if is_dnt:
            occurrence = _dnt_occurrence(detail, item.get("start_at"))
            locality = occurrence.get("location_city") or None
            postal_code = occurrence.get("location_postal_code")
            postal_place = f"{postal_code} {locality or ''}".strip() if postal_code else locality
            street = occurrence.get("location_address_line1")
            extra = occurrence.get("location_address_line2")
            location_name = street or locality
            address = None
            if street or extra or postal_code:
                address = ", ".join(filter(None, (street, extra, postal_place)))
            lat, lng = _coordinates(
                occurrence.get("location_latitude"), occurrence.get("location_longitude"),
            )
            municipality_ids = occurrence.get("location_municipalities") or []
            public_path = "events/dnt"
        else:
            place = detail.get("address") or {}
            address = place.get("address") or None
            location_name = place.get("name") or address
            lat, lng = _coordinates(place.get("lat"), place.get("lng"))
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

        return EventData(
            source="friskus",
            source_id=f"friskus-{event_id}",
            title=item["name"],
            start_at=item.get("start_at"),
            end_at=item.get("end_at"),
            is_free=item.get("is_free"),
            is_recurring=item.get("is_recurring", False),
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

    def _venue_municipality(self, address, locality, lat, lng, geocodes) -> str | None:
        # Kartverket avklarer også steder utenfor de tre kommunene.
        key = (address, locality, lat, lng)
        if key not in geocodes:
            number = None
            if lat is not None and lng is not None:
                point = self._optional_json(f"{KARTVERKET_URL}/kommuneinfo/v1/punkt", {
                    "nord": lat, "ost": lng, "koordsys": 4258,
                })
                number = point.get("kommunenummer")

            if number is None and address:
                number = self._address_municipality(address)

            if number is None and locality:
                # DNT oppgir noen ganger bare et stedsnavn, f.eks. «Giske».
                number = next(
                    (code for code, name in MUNICIPALITY_NAMES.items()
                     if locality.strip().casefold() == name.casefold()),
                    None,
                )
            geocodes[key] = number
        return geocodes[key]

    def _address_municipality(self, address: str) -> str | None:
        parts = [part.strip() for part in address.split(",")]
        street = parts[0]
        if not re.fullmatch(r".+\s\d+[a-zA-Z]?", street):
            return None
        params = {"adressetekst": street, "treffPerSide": 20}
        for part in parts[1:]:
            postal_code = re.match(r"^(\d{4})(?:\s|$)", part)
            if postal_code:
                params["postnummer"] = postal_code[1]
                break

        result = self._optional_json(f"{KARTVERKET_URL}/adresser/v1/sok", params)
        matches = result.get("adresser") or []
        if result.get("metadata", {}).get("totaltAntallTreff") != len(matches):
            return None
        numbers = {
            match["kommunenummer"] for match in matches
            if match.get("kommunenummer")
            and match.get("adressetekst", "").casefold() == street.casefold()
        }
        return numbers.pop() if len(numbers) == 1 else None

    def _optional_json(self, url: str, params: dict) -> dict:
        try:
            payload = self._get(url, params=params).json()
        except (RequestException, ValueError) as error:
            self.logger.debug("Kunne ikke hente stedsdata fra %s: %s", url, error)
            return {}
        return payload if isinstance(payload, dict) else {}
