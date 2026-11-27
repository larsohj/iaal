import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from requests import Timeout

from backend.geography import KARTVERKET_URL
from backend.scrapers.friskus_scraper import API_URL, BASE_URL, FriskusScraper

FIXTURES = Path(__file__).parent / "fixtures"
ALESUND = "58057c8b-b578-4082-8c11-97bfe366e5ab"
SULA = "db3b7632-82c3-4895-8c18-d24a559a42ad"
GISKE = "5900890d-0709-4ea3-bc16-f853e28aaacb"


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _listing_only(fixture):
    def get(url, **kwargs):
        return _mock_response(fixture if url == BASE_URL else {})

    return get


class TestFriskusScraper:
    def test_parses_events_from_fixture(self):
        with open(FIXTURES / "friskus_page1.json") as f:
            fixture = json.load(f)

        # Sett last_page=1 slik at scraperen kun henter én side
        fixture["meta"]["last_page"] = 1

        scraper = FriskusScraper()

        with patch.object(scraper, "_get", side_effect=_listing_only(fixture)):
            events = scraper.scrape()

        # 3 events i fixture, men 3 kommuner med same mock → dedupliseres
        assert len(events) == 3

        first = events[0]
        assert first.source == "friskus"
        assert first.source_id.startswith("friskus-")
        assert first.title == "Påskeeggjakt - i Moa bibliotek"
        assert first.organizer == "Moa Bibliotek"
        assert first.start_at is not None
        assert "friskus.com/events/" in first.url

    def test_maps_age_groups(self):
        with open(FIXTURES / "friskus_page1.json") as f:
            fixture = json.load(f)
        fixture["meta"]["last_page"] = 1

        scraper = FriskusScraper()
        with patch.object(scraper, "_get", side_effect=_listing_only(fixture)):
            events = scraper.scrape()

        first = events[0]
        assert "children" in first.age_groups
        assert "family" in first.age_groups

    def test_maps_is_free(self):
        with open(FIXTURES / "friskus_page1.json") as f:
            fixture = json.load(f)
        fixture["meta"]["last_page"] = 1

        scraper = FriskusScraper()
        with patch.object(scraper, "_get", side_effect=_listing_only(fixture)):
            events = scraper.scrape()

        # Første event: is_free=false, andre: is_free=true
        assert events[0].is_free is False
        assert events[1].is_free is True

    def test_dnt_event_gets_friluftsliv_tag(self):
        fixture = {
            "data": [{
                "id": "test-dnt-1",
                "name": "DNT-tur til Sukkertoppen",
                "start_at": "2026-04-01T10:00:00+0200",
                "end_at": "2026-04-01T15:00:00+0200",
                "is_free": True,
                "is_recurring": False,
                "organization": {"name": "DNT Sunnmøre"},
                "age_group": [],
                "event_source": "dnt",
                "slug": "dnt-tur-sukkertoppen",
            }],
            "meta": {"total": 1, "page": 1, "last_page": 1, "per_page": 15},
        }

        scraper = FriskusScraper()
        with patch.object(scraper, "_get", side_effect=_listing_only(fixture)):
            events = scraper.scrape()

        assert len(events) == 1
        assert "friluftsliv" in events[0].tags
        assert "tur" in events[0].tags


def test_sula_library_events_use_real_address_across_municipality_searches():
    reading = {
        "id": "af9f7a1f-c6ec-4e05-95b8-7659e3ca423b",
        "name": "Samlesing / Shared reading",
        "organization": {"name": "Sula bibliotek"},
    }
    workshop = {
        "id": "ded62311-b6c4-4976-8e86-63806f27e58d",
        "name": "Juleverkstad for barn med Sula husflidslag",
        "organization": {"name": "Sula bibliotek"},
    }

    def get(url, params):
        if url == BASE_URL:
            pages = {
                (ALESUND, 1): {"data": [], "meta": {"last_page": 2}},
                (ALESUND, 2): {"data": [reading]},
                (SULA, 1): {"data": [reading, workshop]},
                (GISKE, 1): {"data": [], "meta": []},
            }
            return _mock_response(pages[params["municipalities[]"], params["page"]])
        if url == f"{API_URL}/events/{reading['id']}":
            return _mock_response({"data": {
                "municipalities": [{"id": ALESUND}, {"id": SULA}],
                "address": {"name": "Sula bibliotek", "address": "Fyllingvegen 11", "lat": "", "lng": ""},
            }})
        if url == f"{API_URL}/events/{workshop['id']}":
            return _mock_response({"data": {
                "municipalities": [{"id": SULA}],
                "address": {
                    "name": "Sula bibliotek", "address": "Fyllingvegen 11, 6030 Langevåg, Norge",
                    "lat": 62.442167, "lng": 6.190452,
                },
            }})
        if url == f"{KARTVERKET_URL}/adresser/v1/sok":
            assert params["adressetekst"] == "Fyllingvegen 11"
            return _mock_response({
                "metadata": {"totaltAntallTreff": 1},
                "adresser": [{"adressetekst": "Fyllingvegen 11", "kommunenummer": "1531"}],
            })
        assert url == f"{KARTVERKET_URL}/kommuneinfo/v1/punkt"
        assert params == {"nord": 62.442167, "ost": 6.190452, "koordsys": 4258}
        return _mock_response({"kommunenummer": "1531"})

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get) as fetch:
        reading_event, workshop_event = scraper.scrape()

    assert reading_event.city == workshop_event.city == "Sula"
    assert reading_event.location_name == workshop_event.location_name == "Sula bibliotek"
    assert reading_event.address == "Fyllingvegen 11"
    assert reading_event.latitude is None
    assert workshop_event.address == "Fyllingvegen 11, 6030 Langevåg, Norge"
    assert workshop_event.latitude == 62.442167
    assert sum(call.args[0] == f"{API_URL}/events/{reading['id']}" for call in fetch.call_args_list) == 1


def test_giske_dnt_event_uses_matching_occurrence_across_municipality_searches():
    item = {
        "id": "oaaYF26bZKTes",
        "name": "Friluftsjazz for hele familien på Giske ved hytta på hjul (gratis)",
        "organization": {"name": "DNT Sunnmøre"},
        "event_source": "dnt",
        "start_at": "2026-11-29T14:00:00+0100",
    }

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [] if params["municipalities[]"] == SULA else [item]})
        assert url == f"{API_URL}/dnt/events/{item['id']}"
        return _mock_response({"data": {"occurrences": [
            {"start_at": "2026-11-29T12:00:00Z", "location_city": "Ålesund"},
            {
                "start_at": "2026-11-29T13:00:00.000000Z",
                "deleted_at": None,
                "location_city": "Giske",
                "location_municipalities": [ALESUND, GISKE],
            },
        ]}})

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get) as fetch:
        [event] = scraper.scrape()

    assert event.city == event.location_name == "Giske"
    assert event.organizer == "DNT Sunnmøre"
    assert event.address is None
    assert event.url == f"https://alesund.friskus.com/events/dnt/{item['id']}"
    assert sum(call.args[0] != BASE_URL for call in fetch.call_args_list) == 1


def test_giske_native_event_keeps_venue_and_organizer_separate():
    item = {
        "id": "15d5a376-60e2-4e4f-91df-9d38ea3d0b42",
        "name": "Friluftsjazz for barn på Giske",
        "organization": {"name": "Jazzsirkelen 04"},
    }

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [item] if params["municipalities[]"] == GISKE else []})
        if url == f"{API_URL}/events/{item['id']}":
            return _mock_response({"data": {
                "municipalities": [{"id": GISKE}],
                "address": {
                    "name": "Hytta på hjul, Giskestranda, Giske",
                    "address": "6052 Giske, Norge", "lat": 62.503891, "lng": 6.0500416,
                },
            }})
        assert url == f"{KARTVERKET_URL}/kommuneinfo/v1/punkt"
        return _mock_response({"kommunenummer": "1532"})

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get):
        [event] = scraper.scrape()

    assert event.city == "Giske"
    assert event.location_name == "Hytta på hjul, Giskestranda, Giske"
    assert event.address == "6052 Giske, Norge"
    assert event.organizer == "Jazzsirkelen 04"


def test_event_advertised_in_all_three_municipalities_can_take_place_outside():
    item = {"id": "toralfbuda", "name": "Adventstur til Toralfbuda"}

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [item]})
        if url == f"{API_URL}/events/{item['id']}":
            return _mock_response({"data": {
                "municipalities": [{"id": ALESUND}, {"id": SULA}, {"id": GISKE}],
                "address": {"address": "Eiksundvegen 555, 6068 Eiksund, Norge"},
            }})
        assert url == f"{KARTVERKET_URL}/adresser/v1/sok"
        assert params["postnummer"] == "6068"
        return _mock_response({
            "metadata": {"totaltAntallTreff": 1},
            "adresser": [{"adressetekst": "Eiksundvegen 555", "kommunenummer": "1516"}],
        })

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get):
        assert scraper.scrape() == []


def test_missing_detail_keeps_event_without_inventing_city_or_venue():
    item = {"id": "unknown", "name": "Arrangement", "organization": {"name": "Arrangørlaget"}}

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [item]})
        raise Timeout("Detail lookup timed out")

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get):
        [event] = scraper.scrape()

    assert event.city is None
    assert "city" not in event.to_dict()
    assert event.location_name is None
    assert event.organizer == "Arrangørlaget"


@pytest.mark.parametrize(("dnt_start", "expected_count"), [
    ("2026-11-29T13:00:00Z", 1),
    ("2026-11-29T13:30:00Z", 2),
])
def test_only_merges_friskus_and_dnt_with_same_registration_and_start(dnt_start, expected_count):
    path = "/register/friluftsjazzgiske_13112026133427"
    dnt = {
        "id": "oaaYF26bZKTes", "name": "Friluftsjazz for hele familien på Giske",
        "event_source": "dnt", "start_at": dnt_start,
    }
    native = {
        "id": "15d5a376-60e2-4e4f-91df-9d38ea3d0b42",
        "name": "Friluftsjazz for barn på Giske",
        "start_at": "2026-11-29T14:00:00+0100",
    }

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [dnt, native]})
        if url == f"{API_URL}/dnt/events/{dnt['id']}":
            return _mock_response({"data": {
                "url": f"http://aktiviteter.dnt.no{path}",
                "occurrences": [{"start_at": dnt_start, "location_city": "Giske"}],
            }})
        assert url == f"{API_URL}/events/{native['id']}"
        return _mock_response({"data": {
            "external_links": [{"url": f"https://aktiviteter.dnt.no{path}#/"}],
            "municipalities": [{"id": GISKE}],
            "address": {"name": "Hytta på hjul, Giskestranda, Giske", "address": "6052 Giske, Norge"},
        }})

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get):
        events = scraper.scrape()

    assert len(events) == expected_count
    if expected_count == 1:
        [event] = events
        assert event.source_id == f"friskus-{native['id']}"
        assert event.city == "Giske"
        assert event.address == "6052 Giske, Norge"
        assert event.tags == ["friluftsliv", "tur"]


@pytest.mark.parametrize(("venue", "address"), [
    ("Kommunehuset på Sjøholt", "Ørskog  frivilligsentral"),
    ("Ørskog Frivillighetssentral.", "Øyravegen 11"),
])
def test_known_sjoholt_venue_resolves_ambiguous_municipalities(venue, address):
    item = {"id": "test-sjoholt", "name": "Arrangement"}

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [item]})
        if url == f"{API_URL}/events/{item['id']}":
            return _mock_response({"data": {
                "municipalities": [{"id": SULA}, {"id": ALESUND}],
                "address": {"name": venue, "address": address, "lat": "", "lng": ""},
            }})
        assert url == f"{KARTVERKET_URL}/adresser/v1/sok"
        assert params["postnummer"] == "6240"
        return _mock_response({
            "metadata": {"totaltAntallTreff": 1},
            "adresser": [{"adressetekst": "Øyravegen 11", "kommunenummer": "1508"}],
        })

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get):
        [event] = scraper.scrape()

    assert event.city == "Ålesund"
    assert event.address == "Øyravegen 11, 6240 Ørskog"


@pytest.mark.parametrize(("title", "place", "expected_city", "expected_location"), [
    ("Friluftsforedrag: vintertelting",
     {"location_address_line1": "TAFJORDs auditorium i Retirovegen 4, Ålesund."},
     "Ålesund", "TAFJORDs auditorium"),
    ("Kom deg ut-dagen på Vipphytta i Vaksvika",
     {"location_city": "Vaksvika"}, "Ålesund", "Vaksvika"),
    ("Nissetur til Rollonhytta", {}, "Sula", "Rollonhytta"),
    ("Introduksjon til vintertelting", {}, None, None),
])
def test_dnt_places_with_partial_or_missing_location(title, place, expected_city, expected_location):
    start = "2026-12-06T11:00:00+0100"
    item = {"id": "test-dnt", "name": title, "start_at": start, "event_source": "dnt"}

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [item]})
        if url == f"{API_URL}/dnt/events/{item['id']}":
            return _mock_response({"data": {"occurrences": [{
                "start_at": "2026-12-06T10:00:00Z",
                "location_municipalities": [ALESUND, SULA],
                **place,
            }]}})
        assert url == f"{KARTVERKET_URL}/adresser/v1/sok"
        assert params["adressetekst"] == "Retirovegen 4"
        return _mock_response({
            "metadata": {"totaltAntallTreff": 2},
            "adresser": [
                {"adressetekst": "Retirovegen 4", "poststed": "MOLDE", "kommunenummer": "1506"},
                {"adressetekst": "Retirovegen 4", "poststed": "ÅLESUND", "kommunenummer": "1508"},
            ],
        })

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get):
        [event] = scraper.scrape()

    assert event.city == expected_city
    assert event.location_name == expected_location
    if "location_address_line1" in place:
        assert event.address == "Retirovegen 4, Ålesund"


def test_recurring_friskus_event_has_one_row_per_published_occurrence():
    item = {
        "id": "d8d2e930-8716-440b-abe8-5fe1dacc7e4e",
        "name": "Putti Plutti Pott",
        "start_at": "2026-11-28T13:00:00+0100",
        "end_at": "2026-12-06T18:00:00+0100",
        "is_recurring": True,
    }
    early = {"id": "early", "start_at": "2026-11-28T12:00:00Z", "end_at": "2026-11-28T13:30:00Z"}
    late = {"id": "late", "start_at": "2026-11-28T15:00:00Z", "end_at": "2026-11-28T16:30:00Z"}
    detail = {"data": {"occurrences": [
        early, late, early, {**late, "id": "unpublished", "published": False},
        {**late, "id": "canceled", "is_canceled": True},
    ]}}

    def get(url, params):
        if url == BASE_URL:
            return _mock_response({"data": [item]})
        assert url == f"{API_URL}/events/{item['id']}"
        return _mock_response(detail)

    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=get) as fetch:
        events = scraper.scrape()

    assert [(e.source_id, e.start_at, e.end_at) for e in events] == [
        (f"friskus-{item['id']}-early", early["start_at"], early["end_at"]),
        (f"friskus-{item['id']}-late", late["start_at"], late["end_at"]),
    ]
    assert sum(call.args[0] != BASE_URL for call in fetch.call_args_list) == 1


def test_dnt_series_uses_each_occurrences_own_location_and_skips_deleted():
    item = {"id": "dnt-series", "name": "Serietur", "event_source": "dnt", "is_recurring": True}
    detail = {"data": {"occurrences": [
        {"id": "first", "start_at": "2026-12-01T18:00:00Z", "location_city": "Ålesund"},
        {"id": "second", "start_at": "2026-12-08T18:00:00Z", "location_city": "Giske"},
        {"id": "deleted", "start_at": "2026-12-15T18:00:00Z", "deleted_at": "2026-11-30"},
    ]}}
    scraper = FriskusScraper()

    def get(url, params):
        return _mock_response({"data": [item]} if url == BASE_URL else detail)

    with patch.object(scraper, "_get", side_effect=get):
        events = scraper.scrape()
    assert [(e.source_id, e.city) for e in events] == [
        ("friskus-dnt-series-first", "Ålesund"),
        ("friskus-dnt-series-second", "Giske"),
    ]


def test_missing_series_details_do_not_reuse_series_end_as_occurrence_end():
    item = {
        "id": "series", "name": "Kurs", "is_recurring": True,
        "start_at": "2026-11-28T13:00:00+0100", "end_at": "2026-12-06T18:00:00+0100",
    }
    scraper = FriskusScraper()
    with patch.object(scraper, "_get", side_effect=_listing_only({"data": [item]})):
        [event] = scraper.scrape()

    assert event.start_at == item["start_at"]
    assert event.end_at is None
