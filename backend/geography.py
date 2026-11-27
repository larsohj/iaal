"""Fastslå arrangementsstedets kommune fra kildedata og Kartverket."""

import logging
import re
from collections.abc import Callable, Container
from math import isfinite

import requests

KARTVERKET_URL = "https://api.kartverket.no"
MUNICIPALITY_NAMES = {"1508": "Ålesund", "1531": "Sula", "1532": "Giske"}
STREET_ADDRESS = re.compile(r".+\s\d+[a-zA-Z]?")
EMBEDDED_STREET = re.compile(r".*(?:vegen|veien|gata|gaten|gate|allé|plass)\s+\d+[a-z]?", re.IGNORECASE)
VENUE_MUNICIPALITIES = {
    "alnes fyr": "1532",
    "alnes fyr og opplevelsessenter": "1532",
    "vigra kirke": "1532",
    "øygardshallen": "1532",
    "vigra kyrkje": "1532",
    "devoldfabrikken": "1531",
    "langevåg kirke": "1531",
    "langevåg kyrkje": "1531",
    "herøy kyrkje": "1515",
    "herøy kirke": "1515",
}
POST_PLACES = {
    "ålesund": "1508", "sula": "1531",
    "giske": "1532", "fosnavåg": "1515",
}
logger = logging.getLogger("geography")
LoadJSON = Callable[[str, dict], dict]


def coordinates(latitude, longitude) -> tuple[float | None, float | None]:
    try:
        lat, lng = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None, None
    if isfinite(lat) and isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180:
        return lat, lng
    return None, None


def point_municipality(load_json: LoadJSON, latitude: float, longitude: float) -> str | None:
    data = load_json(f"{KARTVERKET_URL}/kommuneinfo/v1/punkt", {
        "nord": latitude, "ost": longitude, "koordsys": 4258,
    })
    return data.get("kommunenummer")


def address_municipality(
    load_json: LoadJSON, address: str, post_places: Container[str],
) -> str | None:
    parts = [part.strip() for part in address.split(",")]
    street = parts[0]
    if not STREET_ADDRESS.fullmatch(street):
        return None
    params = {"adressetekst": street, "treffPerSide": 20}
    for part in parts[1:]:
        postal_code = re.match(r"^(\d{4})(?:\s|$)", part)
        if postal_code:
            params["postnummer"] = postal_code[1]
            break

    result = load_json(f"{KARTVERKET_URL}/adresser/v1/sok", params)
    matches = result.get("adresser") or []
    if result.get("metadata", {}).get("totaltAntallTreff") != len(matches):
        return None
    if len(parts) > 1 and parts[1].rstrip(".").casefold() in post_places:
        poststed = parts[1].rstrip(".").casefold()
        matches = [match for match in matches if (match.get("poststed") or "").strip().casefold() == poststed]
    numbers = {
        match["kommunenummer"] for match in matches
        if match.get("kommunenummer") and match.get("adressetekst", "").casefold() == street.casefold()
    }
    return numbers.pop() if len(numbers) == 1 else None


def _classify_events(events: list[dict], load_json: LoadJSON) -> list[dict]:
    points = {}
    addresses = {}
    kept = []
    removed = 0
    corrected = 0
    for event in events:
        source = event.get("source")
        if source == "friskus":
            # Friskus avklarer allerede kommuner per forekomst, med egne stedsfelt.
            kept.append(event)
            continue

        venue = (event.get("location_name") or "").strip().casefold()
        if source == "parken":
            venue = venue.removeprefix("parken kulturhus – ")
        number = VENUE_MUNICIPALITIES.get(venue)

        lat, lng = coordinates(event.get("latitude"), event.get("longitude"))
        if number is None and lat is not None and lng is not None and (lat, lng) != (0, 0):
            point = (lat, lng)
            if point not in points:
                points[point] = point_municipality(load_json, lat, lng)
            number = points[point]

        if number is None:
            address = event.get("address")
            if not address:
                embedded = venue.rsplit(",", 1)[-1].strip()
                if EMBEDDED_STREET.fullmatch(embedded):
                    address = embedded
            if address:
                if address not in addresses:
                    addresses[address] = address_municipality(load_json, address, POST_PLACES)
                number = addresses[address]

        if number is None and source == "ticketmaster":
            # Ticketmaster leverer poststed. De andre kildene kan ha Ålesund som standard.
            number = POST_PLACES.get((event.get("city") or "").strip().casefold())

        if number is None:
            kept.append(event)
        elif number in MUNICIPALITY_NAMES:
            city = MUNICIPALITY_NAMES[number]
            corrected += event.get("city") != city
            kept.append({**event, "city": city})
        else:
            removed += 1
    logger.info("Rettet kommune for %d oppføringer og filtrerte %d utenfor dekningsområdet", corrected, removed)
    return kept


def apply_geography(events: list[dict]) -> list[dict]:
    with requests.Session() as session:
        def load_json(url, params):
            try:
                response = session.get(url, params=params, timeout=8)
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as error:
                logger.debug("Kunne ikke avklare kommune hos Kartverket: %s", error)
                return {}
            return data if isinstance(data, dict) else {}

        return _classify_events(events, load_json)
