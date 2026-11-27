import json
from unittest.mock import Mock, patch

from requests import Timeout

from backend.generate import main
from backend.geography import KARTVERKET_URL, apply_geography


def test_production_generator_corrects_venue_and_excludes_confirmed_outside_events(tmp_path):
    events = [
        {"source": "bypatrioten", "source_id": "a", "location_name": "Alnes Fyr og Opplevelsessenter", "city": "Ålesund"},
        {"source": "bypatrioten", "source_id": "t", "location_name": "Låven, Tennfjordvegen 182", "city": "Ålesund"},
        {"source": "ticketmaster", "source_id": "h", "location_name": "Herøy Kyrkje", "city": "Fosnavåg"},
        {"source": "bypatrioten", "source_id": "d", "location_name": "Devoldfabrikken", "city": "Ålesund"},
    ]
    response = Mock()
    response.json.return_value = {
        "metadata": {"totaltAntallTreff": 1},
        "adresser": [{"kommunenummer": "1580", "adressetekst": "Tennfjordvegen 182"}],
    }
    with patch("backend.generate.run_scrapers", return_value=(events, [])), \
            patch("backend.generate.OUTPUT_DIR", tmp_path), \
            patch("backend.geography.requests.Session.get", return_value=response) as get:
        path = main()

    data = json.loads(path.read_text())
    assert [(event["source_id"], event["city"]) for event in data["events"]] == [("a", "Giske"), ("d", "Sula")]
    assert get.call_count == 1
    assert get.call_args.args[0] == f"{KARTVERKET_URL}/adresser/v1/sok"
    assert get.call_args.kwargs["params"]["adressetekst"].casefold() == "tennfjordvegen 182"


def test_coordinates_override_default_city_and_reuse_venue_lookup():
    events = [
        {"source": "tikkio", "source_id": "one", "latitude": 62.44, "longitude": 6.19, "city": "Ålesund"},
        {"source": "tikkio", "source_id": "two", "latitude": 62.44, "longitude": 6.19, "city": "Ålesund"},
        {"source": "tikkio", "source_id": "three", "latitude": 62.73, "longitude": 7.15, "city": "Ålesund"},
    ]
    replies = [Mock(), Mock()]
    replies[0].json.return_value = {"kommunenummer": "1531"}
    replies[1].json.return_value = {"kommunenummer": "1506"}
    with patch("backend.geography.requests.Session.get", side_effect=replies) as get:
        result = apply_geography(events)

    assert [(event["source_id"], event["city"]) for event in result] == [("one", "Sula"), ("two", "Sula")]
    assert get.call_count == 2


def test_keeps_unresolved_places_when_lookup_fails():
    unresolved = {"source": "tikkio", "latitude": 62.44, "longitude": 6.19, "city": "Ålesund"}
    placeholder = {"source": "tikkio", "latitude": 0, "longitude": 0, "city": "Ålesund"}
    friskus = {"source": "friskus", "location_name": "Alnes fyr", "city": "Giske"}
    with patch("backend.geography.requests.Session.get", side_effect=Timeout) as get:
        assert apply_geography([unresolved, placeholder, friskus]) == [unresolved, placeholder, friskus]
    assert get.call_count == 1
