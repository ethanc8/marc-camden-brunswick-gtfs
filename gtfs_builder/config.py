"""Everything about this feed that isn't mechanically extracted from a PDF:
route branding, calendar definitions, and the printed-station-name -> stop_id
lookup. See PLAN.md for the reasoning behind each choice.
"""

SERVICE_START = "20260928"  # 2026-09-28, a Monday
SERVICE_END = "20261101"

# route_id -> GTFS routes.txt fields. Colors/names given by the project owner;
# "brunswick_camden" is the new through-running service introduced 2026-09-28
# (trains 830/831), which bypasses Washington Union Station entirely so it
# doesn't belong under either of the two "- WASHINGTON" branded lines.
ROUTES = {
    "camden": {
        "route_short_name": "Camden",
        "route_long_name": "MARC Camden Line",
        "route_color": "EF5B2A",
        "route_text_color": "FFFFFF",
    },
    "brunswick": {
        "route_short_name": "Brunswick",
        "route_long_name": "MARC Brunswick Line",
        "route_color": "EFAC1F",
        "route_text_color": "000000",
    },
    "brunswick_camden": {
        "route_short_name": "Brunswick-Camden",
        "route_long_name": "MARC Brunswick-Camden Through Service",
        "route_color": "2F3238",
        "route_text_color": "FFFFFF",
    },
}

# service_id -> calendar.txt fields (days + date range). The "r_schedule_*"
# entries are intentionally all-zero: MARC's contingency ("R") schedule for
# severe weather/holidays is never in effect by default, but exists here so a
# real activation only requires calendar_dates.txt exceptions (see PLAN.md
# §4). There's one per line (not one shared service) because the old MARC
# feed's own history shows MTA sometimes activates R for only one line at a
# time (e.g. 2025-02-06 added only the Brunswick R service) -- a single
# shared service_id couldn't represent that. There's no r_schedule for
# brunswick_camden: neither 830 nor 831 is R-flagged in the source PDFs.
#
# "friday" is for train 871, which the Brunswick brochure's fine print marks
# "*Train 871 operates Friday only" -- it's real scheduled weekday service,
# just not a Monday-Friday one, so it can't share the "weekday" service_id.
CALENDARS = {
    "weekday": {
        "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1,
        "saturday": 0, "sunday": 0,
        "start_date": SERVICE_START, "end_date": SERVICE_END,
    },
    "friday": {
        "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 1,
        "saturday": 0, "sunday": 0,
        "start_date": SERVICE_START, "end_date": SERVICE_END,
    },
    "r_schedule_camden": {
        "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0,
        "saturday": 0, "sunday": 0,
        "start_date": SERVICE_START, "end_date": SERVICE_END,
    },
    "r_schedule_brunswick": {
        "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0,
        "saturday": 0, "sunday": 0,
        "start_date": SERVICE_START, "end_date": SERVICE_END,
    },
}

# route_id -> its R-schedule calendar service_id. Looked up when mirroring an
# R-flagged trip -- see PLAN.md §3/§4.
R_SERVICE_BY_ROUTE = {
    "camden": "r_schedule_camden",
    "brunswick": "r_schedule_brunswick",
}

# Station name exactly as printed in extracted/*.csv -> reference/stops.csv
# stop_id. One entry per distinct spelling actually seen across the six
# tables (a couple of stations are printed slightly differently in the
# Thru Service tables, e.g. "BALTIMORE/CAMDEN" vs "BALTIMORE/CAMDEN STATION").
STATION_NAME_TO_STOP_ID = {
    "WASHINGTON UNION STATION": "washington_union_station",
    "RIVERDALE PARK TOWN CENTER": "riverdale_park_town_center",
    "COLLEGE PARK": "college_park",
    "GREENBELT": "greenbelt",
    "MUIRKIRK": "muirkirk",
    "LAUREL": "laurel",
    "LAUREL RACETRACK": "laurel_racetrack",
    "SAVAGE": "savage",
    "JESSUP": "jessup",
    "DORSEY": "dorsey",
    "ST. DENIS": "st_denis",
    "BALTIMORE/CAMDEN STATION": "baltimore_camden_station",
    "BALTIMORE/CAMDEN": "baltimore_camden_station",
    "MARTINSBURG, WV": "martinsburg",
    "DUFFIELDS": "duffields",
    "HARPERS FERRY, WV": "harpers_ferry",
    "BRUNSWICK, MD": "brunswick",
    "FREDERICK": "frederick",
    "MONOCACY": "monocacy",
    "POINT OF ROCKS": "point_of_rocks",
    "DICKERSON": "dickerson",
    "BARNESVILLE": "barnesville",
    "BOYDS": "boyds",
    "GERMANTOWN": "germantown",
    "METROPOLITAN GROVE": "metropolitan_grove",
    "GAITHERSBURG": "gaithersburg",
    "WASHINGTON GROVE": "washington_grove",
    "ROCKVILLE": "rockville",
    "GARRETT PARK": "garrett_park",
    "KENSINGTON": "kensington",
    "SILVER SPRING": "silver_spring",
}

# Brunswick Line R-schedule extra stops: (anchor_stop_id, inserted_stop_id,
# minutes_after_anchor). Camden's R-trips are pure mirrors of their regular
# trip (no extra stops) -- the old feed shows Camden's R-trips are always
# identical to their base trip, matching Camden's own legend text ("Additional
# stops... will be announced prior to operation", i.e. genuinely unpublished).
# Brunswick's legend instead flatly states "Trains will make all stops on the
# R schedule", and the old feed confirms it: most Brunswick R-trips there add
# real, published extra stops. This table is those same extra-stop insertions
# (station + minutes after the previous stop), carried over to this schedule.
#
# Two things had to be re-derived rather than copied verbatim, because this is
# a different schedule than the one the old feed described:
#   - A station the old feed added under R can turn out to already be a
#     *regular* stop in this schedule (e.g. train 892 gained Washington Grove
#     as a real stop on 2026-09-28) -- those are simply left out below.
#   - Conversely, a station this schedule newly skips that the old feed's
#     R-trip never had to add (train 892's Boyds) needs an estimate with no
#     direct precedent -- see the per-train notes.
# Frederick and Monocacy are excluded everywhere even though some trains skip
# them: they're on a branch off the Brunswick mainline, so a train serving the
# Brunswick mainline can't also detour onto that branch under any schedule.
#
# Every inserted stop gets pickup_type/drop_off_type=0 (regular) but
# timepoint=0 (not a timepoint) in build_gtfs.py: unlike the real, printed
# times this schedule is built from, these are estimates.
BRUNSWICK_R_EXTRA_STOPS = {
    # Trains below with no historical R-trip in the old feed have no
    # historical delta to draw on for a given insertion; those specific
    # entries borrow the delta another same-direction train uses for the same
    # station pair, noted inline.
    "872": [("point_of_rocks", "dickerson", 5), ("barnesville", "boyds", 4), ("rockville", "garrett_park", 4)],
    "878": [("gaithersburg", "washington_grove", 2), ("rockville", "garrett_park", 3)],
    "880": [],  # already makes every stop on its regular pattern, same as in the old feed
    "892": [
        ("dickerson", "barnesville", 5),
        ("barnesville", "boyds", 4),  # no old Train892R precedent; borrowed from Train872R's Barnesville->Boyds
    ],
    "875": [("kensington", "garrett_park", 4), ("rockville", "washington_grove", 4), ("germantown", "boyds", 4), ("barnesville", "dickerson", 3)],
    "881": [("rockville", "washington_grove", 4), ("germantown", "boyds", 2), ("barnesville", "dickerson", 3)],
    "893": [],  # every station the old feed's Train893R used to add (Garrett Park, Washington Grove, Boyds, Dickerson) is now a regular stop
    "873": [
        # Train 873 wasn't R-flagged before 2026-09-28, so there's no old
        # Train873R at all. These four deltas are the average, at the same
        # station pairs, of the three other westbound trains above
        # (875/881/893) that do have old-feed precedent.
        ("kensington", "garrett_park", 4),
        ("rockville", "washington_grove", 4),
        ("germantown", "boyds", 3),
        ("barnesville", "dickerson", 3),
    ],
}
