import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from backend.models import EventData
from backend.scrapers.base import BaseScraper

API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
AALESUND_LAT = 62.4723
AALESUND_LNG = 6.1549
RADIUS_KM = 50
OSLO = ZoneInfo("Europe/Oslo")

# Kun verifiserte oppføringer for 2027. Behold billettlenkene og kilde-ID-ene.
# Festivalperiode: https://alesundlive.no/
# Dagstider: https://www.ticketmaster.no/event/365301346 og /event/1619024008
AALESUND_LIVE_FESTIVAL = "Z698xZb_Z1k7wbt39"
AALESUND_LIVE_UPGRADE = "Z698xZb_Z1k39PwFt"
AALESUND_LIVE_START = "2027-06-18"
AALESUND_LIVE_END = "2027-06-19"
AALESUND_LIVE_DAYS = {
    "Z698xZb_Z1kuPGvuk": ("Ålesund Live – fredag", "2027-06-18T16:30:00"),
    "Z698xZb_Z16vb_Z0ZF": ("Ålesund Live – lørdag", "2027-06-19T15:00:00"),
}


def _date_pending(value: dict) -> bool:
    return value.get("dateTBA") is True or value.get("dateTBD") is True


def _event_date(value: dict, *, date_only: bool = False) -> str | None:
    if _date_pending(value):
        return None

    date_time = value.get("dateTime")
    try:
        timestamp = datetime.fromisoformat(date_time) if "T" in (date_time or "") else None
    except (ValueError, TypeError):
        timestamp = None

    date_only = date_only or value.get("timeTBA") is True or value.get("noSpecificTime") is True
    if timestamp is not None and not date_only:
        return date_time

    try:
        local_date = date.fromisoformat(value.get("localDate"))
    except (ValueError, TypeError):
        if timestamp is None:
            return None
        local_date = timestamp.astimezone(OSLO).date() if timestamp.tzinfo else timestamp.date()

    local_time = value.get("localTime")
    if date_only or not local_time:
        return local_date.isoformat()

    try:
        if isinstance(local_time, dict):
            clock = time(
                local_time["hourOfDay"], local_time["minuteOfHour"],
                local_time.get("secondOfMinute", 0),
            )
        else:
            clock = time.fromisoformat(local_time)
    except (KeyError, ValueError, TypeError):
        return local_date.isoformat()
    return datetime.combine(local_date, clock).isoformat(timespec="seconds")


def _event_schedule(item: dict) -> tuple[str, str | None, str | None]:
    event_id = item["id"]
    dates = item.get("dates") or {}
    start = dates.get("start") or {}
    end = dates.get("end") or {}
    is_festival = event_id == AALESUND_LIVE_FESTIVAL
    start_at = _event_date(start, date_only=is_festival)
    end_at = _event_date(end, date_only=is_festival)
    title = item.get("name", "")

    if is_festival:
        title = "Ålesund Live"
        if start_at is None and not _date_pending(start):
            start_at = AALESUND_LIVE_START
        if end_at is None and start_at == AALESUND_LIVE_START and not _date_pending(end):
            end_at = AALESUND_LIVE_END
    elif event_id in AALESUND_LIVE_DAYS:
        title, published_start = AALESUND_LIVE_DAYS[event_id]
        if not _date_pending(start) and start_at in (None, published_start[:10]):
            start_at = published_start

    return title, start_at, end_at


class TicketmasterScraper(BaseScraper):
    source_name = "ticketmaster"

    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("TICKETMASTER_API_KEY", "")

    def scrape(self) -> list[EventData]:
        if not self.api_key:
            self.logger.warning("TICKETMASTER_API_KEY ikke satt, hopper over")
            return []

        events = []
        page = 0

        while True:
            resp = self._get(API_URL, params={
                "apikey": self.api_key,
                "latlong": f"{AALESUND_LAT},{AALESUND_LNG}",
                "radius": str(RADIUS_KM),
                "unit": "km",
                "locale": "no",
                "page": str(page),
                "size": "50",
            })
            data = resp.json()

            embedded = data.get("_embedded", {})
            tm_events = embedded.get("events", [])

            for item in tm_events:
                if item["id"] == AALESUND_LIVE_UPGRADE:
                    continue
                title, start_at, end_at = _event_schedule(item)

                venue = {}
                venues = item.get("_embedded", {}).get("venues", [])
                if venues:
                    venue = venues[0]

                # Pris
                price_ranges = item.get("priceRanges", [])
                price_text = None
                is_free = None
                if price_ranges:
                    pr = price_ranges[0]
                    min_p = pr.get("min", 0)
                    max_p = pr.get("max", 0)
                    currency = pr.get("currency", "NOK")
                    if min_p == 0 and max_p == 0:
                        is_free = True
                    else:
                        is_free = False
                        price_text = f"{currency} {min_p}" if min_p == max_p else f"{currency} {min_p}–{max_p}"

                # Tags fra genre
                tags = []
                classifications = item.get("classifications", [])
                if classifications:
                    genre = classifications[0].get("genre", {}).get("name")
                    if genre and genre != "Undefined":
                        tags.append(genre.lower())

                # Koordinater
                location = venue.get("location", {})
                lat = None
                lng = None
                try:
                    lat = float(location.get("latitude", 0))
                    lng = float(location.get("longitude", 0))
                except (ValueError, TypeError):
                    pass

                events.append(EventData(
                    source="ticketmaster",
                    source_id=f"ticketmaster-{item['id']}",
                    title=title,
                    start_at=start_at,
                    end_at=end_at,
                    location_name=venue.get("name"),
                    address=venue.get("address", {}).get("line1"),
                    city=venue.get("city", {}).get("name", "Ålesund"),
                    latitude=lat,
                    longitude=lng,
                    is_free=is_free,
                    price_text=price_text,
                    image_url=item.get("images", [{}])[0].get("url") if item.get("images") else None,
                    url=item.get("url"),
                    tags=tags,
                ))

            # Paginering
            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)
            if page + 1 >= total_pages:
                break
            page += 1

        self.logger.info(f"Hentet {len(events)} hendelser fra Ticketmaster")
        return events
