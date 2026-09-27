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

# service_id -> calendar.txt fields (days + date range). "r_schedule" is
# intentionally all-zero: MARC's contingency ("R") schedule for severe
# weather/holidays is never in effect by default, but exists here so a real
# activation only requires calendar_dates.txt exceptions (see PLAN.md §4).
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
    "r_schedule": {
        "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0,
        "saturday": 0, "sunday": 0,
        "start_date": SERVICE_START, "end_date": SERVICE_END,
    },
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
