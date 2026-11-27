from backend.deduplicate import deduplicate_events


def test_uses_library_listing_and_does_not_merge_distinct_venues():
    base = {"start_at": "2026-12-01T17:00:00", "title": "Samlesing", "city": "Ålesund"}
    events = [
        {**base, "source": "friskus", "location_name": "Ålesund bibliotek, lokalsamlinga"},
        {**base, "source": "bypatrioten", "location_name": "Ålesund bibliotek"},
        {**base, "source": "bibliotek", "location_name": "Ålesund bibliotek", "source_id": "bibliotek-1"},
        {**base, "source": "bibliotek", "location_name": "Moa bibliotek", "source_id": "bibliotek-2"},
    ]
    result = deduplicate_events(events, [])
    assert [e["source_id"] for e in result] == ["bibliotek-1", "bibliotek-2"]


def test_general_venue_cannot_merge_showings_in_two_rooms():
    base = {"start_at": "2026-11-28T13:00:00", "title": "Konsert", "city": "Ålesund"}
    events = [
        {**base, "source": "parken", "location_name": "Parken kulturhus – Hovedscene"},
        {**base, "source": "friskus", "location_name": "Parken kulturhus"},
        {**base, "source": "parken", "location_name": "Parken kulturhus – Foajeen"},
    ]
    assert deduplicate_events(events, []) == events


def test_keeps_date_only_and_distinct_instants_on_daylight_saving_transition():
    base = {"title": "Konsert", "city": "Ålesund", "location_name": "Parken kulturhus"}
    events = [
        {**base, "source": "parken", "start_at": "2026-10-25T02:30:00+02:00"},
        {**base, "source": "friskus", "start_at": "2026-10-25T02:30:00+01:00"},
        {**base, "source": "tikkio", "start_at": "2026-10-25T02:30:00"},
        {**base, "source": "parken", "start_at": "2026-10-25"},
        {**base, "source": "friskus", "start_at": "2026-10-25"},
    ]
    assert deduplicate_events(events, []) == events
