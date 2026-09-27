"""Unit tests for the trickiest logic in build_gtfs.py: parsing a printed cell,
the R-flag check (which has to avoid matching "READ DOWN"/"READ UP"), and
AM/PM resolution (old-feed lookup + neighbor-fill + the hardcoded override for
the two brand-new trains). See PLAN.md §2-3 for why each rule exists.

Run with `pixi run -- pytest gtfs_builder`.
"""

import pytest

from build_gtfs import apply_brunswick_r_extra_stops, build_stop_events, parse_cell, r_flagged, resolve_periods


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("6:32", ("", 6, 32)),
        ("f5:09", ("f", 5, 9)),
        ("d5:31", ("d", 5, 31)),
        ("L5:38", ("L", 5, 38)),
        ("", None),
        ("—", None),
        ("R", None),
        ("BUS", None),
        ("C", None),
        ("Connection From 872", None),
    ],
)
def test_parse_cell(raw, expected):
    assert parse_cell(raw) == expected


@pytest.mark.parametrize(
    "flags,expected",
    [
        ("R", True),
        ("Q/R", True),
        ("Q", False),
        ("", False),
        ("READ DOWN", False),  # must not false-positive on the letter R inside "READ"
        ("READ UP", False),
    ],
)
def test_r_flagged(flags, expected):
    assert r_flagged(flags) == expected


def test_resolve_periods_uses_old_feed_reference():
    old_hours = {"840": {"washington_union_station": 6, "baltimore_camden_station": 7}}
    periods = resolve_periods("840", ["washington_union_station", "baltimore_camden_station"], old_hours)
    assert periods == ["AM", "AM"]


def test_resolve_periods_fills_a_newly_added_stop_from_its_neighbor():
    # "boyds" is a new stop for this train (not in the old feed's stop_times),
    # sandwiched between two stops that are -- it should inherit their period.
    old_hours = {"874": {"martinsburg": 5, "germantown": 6}}
    periods = resolve_periods("874", ["martinsburg", "boyds", "germantown"], old_hours)
    assert periods == ["AM", "AM", "AM"]


def test_resolve_periods_uses_override_for_brand_new_trains():
    assert resolve_periods("830", ["brunswick", "point_of_rocks"], {}) == ["AM", "AM"]
    assert resolve_periods("831", ["baltimore_camden_station", "laurel"], {}) == ["PM", "PM"]


def test_resolve_periods_raises_without_any_reference():
    with pytest.raises(ValueError):
        resolve_periods("999999", ["frederick"], {})


def test_build_stop_events_applies_prefix_semantics_and_orders_chronologically():
    old_hours = {"831": {}}
    ordered = [
        ("baltimore_camden_station", "5:00"),
        ("laurel", "5:26"),
        ("point_of_rocks", "d6:46"),
    ]
    events = build_stop_events("831", ordered, old_hours)
    assert events == [
        ("baltimore_camden_station", "17:00:00", 0, 0, 1),
        ("laurel", "17:26:00", 0, 0, 1),
        ("point_of_rocks", "18:46:00", 1, 0, 0),
    ]


def test_build_stop_events_skips_non_stops():
    events = build_stop_events("999999", [("frederick", "—"), ("monocacy", "BUS")], {})
    assert events == []


def test_apply_brunswick_r_extra_stops_inserts_at_the_right_time_and_timepoint():
    # Train 872 has three configured insertions: Dickerson (after Point of
    # Rocks), Boyds (after Barnesville), and Garrett Park (after Rockville).
    events = [
        ("point_of_rocks", "05:51:00", 0, 0, 1),
        ("barnesville", "06:01:00", 0, 0, 1),
        ("germantown", "06:09:00", 0, 0, 1),
        ("rockville", "06:26:00", 0, 0, 1),
        ("kensington", "06:32:00", 0, 0, 1),
    ]
    result = apply_brunswick_r_extra_stops("872", events)
    assert result == [
        ("point_of_rocks", "05:51:00", 0, 0, 1),
        ("dickerson", "05:56:00", 0, 0, 0),
        ("barnesville", "06:01:00", 0, 0, 1),
        ("boyds", "06:05:00", 0, 0, 0),
        ("germantown", "06:09:00", 0, 0, 1),
        ("rockville", "06:26:00", 0, 0, 1),
        ("garrett_park", "06:30:00", 0, 0, 0),
        ("kensington", "06:32:00", 0, 0, 1),
    ]


def test_apply_brunswick_r_extra_stops_chains_off_a_just_inserted_anchor():
    # Train 892's second insertion (Boyds) anchors off Barnesville, which is
    # itself the first insertion -- not one of the original stops.
    events = [("dickerson", "06:55:00", 0, 0, 1), ("germantown", "07:09:00", 0, 0, 1)]
    result = apply_brunswick_r_extra_stops("892", events)
    assert [stop_id for stop_id, *_ in result] == ["dickerson", "barnesville", "boyds", "germantown"]
    assert [time for _, time, *_ in result] == ["06:55:00", "07:00:00", "07:04:00", "07:09:00"]


def test_apply_brunswick_r_extra_stops_is_a_noop_for_trains_with_none_configured():
    events = [("brunswick", "07:45:00", 0, 0, 1), ("point_of_rocks", "07:55:00", 0, 0, 1)]
    assert apply_brunswick_r_extra_stops("880", events) == events
    assert apply_brunswick_r_extra_stops("not-a-real-train", events) == events


def test_build_stop_events_detects_backwards_time_as_a_bug():
    # Deliberately wrong old-feed reference (PM then AM) should be caught, not
    # silently produce a trip that goes back in time.
    old_hours = {"1": {"frederick": 13, "monocacy": 6}}
    with pytest.raises(ValueError, match="backwards"):
        build_stop_events("1", [("frederick", "1:00"), ("monocacy", "6:30")], old_hours)
