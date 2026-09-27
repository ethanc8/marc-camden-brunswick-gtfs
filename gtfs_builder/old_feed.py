"""Shared access to source-pdf/mdotmta_gtfs_marc/, the pre-2026-09-28 MARC GTFS
feed the project owner supplied as a source for data the new PDFs don't carry
(station coordinates -- see build_reference.py) and, here, as a ground truth
for resolving AM/PM on the new timetable's 12-hour times (see build_gtfs.py).

STATIONS maps this project's stop_id to the old feed's stop_name, expressed as
a regex because the old feed gives one stop_id per station *per direction*
(e.g. "SILVER SPRING MARC eb" / "SILVER SPRING MARC wb") -- see
build_reference.py's module docstring for why we collapse that to one stop.
"""

import csv
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OLD_FEED = REPO_ROOT / "source-pdf" / "mdotmta_gtfs_marc"

# stop_id, current station name, old-feed stop_name regex (see build_reference.py)
STATIONS = [
    ("martinsburg", "Martinsburg, WV", "MARTINSBURG W VA"),
    ("duffields", "Duffields, WV", "DUFFIELDS W VA"),
    ("harpers_ferry", "Harpers Ferry, WV", "HARPERS FERRY W VA"),
    ("brunswick", "Brunswick, MD", "BRUNSWICK MD"),
    ("frederick", "Frederick", "FREDERICK"),
    ("monocacy", "Monocacy", "MONOCACY"),
    ("point_of_rocks", "Point of Rocks", "POINT OF ROCKS"),
    ("dickerson", "Dickerson", "DICKERSON"),
    ("barnesville", "Barnesville", "BARNESVILLE"),
    ("boyds", "Boyds", "BOYDS"),
    ("germantown", "Germantown", "GERMANTOWN"),
    ("metropolitan_grove", "Metropolitan Grove", "METROPOLITAN GROVE"),
    ("gaithersburg", "Gaithersburg", "GAITHERSBURG"),
    ("washington_grove", "Washington Grove", "WASHINGTON GROVE"),
    ("rockville", "Rockville", "ROCKVILLE"),
    ("garrett_park", "Garrett Park", "GARRETT PARK"),
    ("kensington", "Kensington", "KENSINGTON"),
    ("silver_spring", "Silver Spring", "SILVER SPRING"),
    ("washington_union_station", "Washington Union Station", "UNION STATION"),
    ("riverdale_park_town_center", "Riverdale Park Town Center", "RIVERDALE"),
    ("college_park", "College Park", "COLLEGE PARK"),
    ("greenbelt", "Greenbelt", "GREENBELT"),
    ("muirkirk", "Muirkirk", "MUIRKIRK"),
    ("laurel", "Laurel", "LAUREL(?! RACETRACK)"),
    ("laurel_racetrack", "Laurel Racetrack", "LAUREL RACETRACK"),
    ("savage", "Savage", "SAVAGE"),
    ("jessup", "Jessup", "JESSUP"),
    ("dorsey", "Dorsey", "DORSEY"),
    ("st_denis", "St. Denis", "ST DENIS"),
    ("baltimore_camden_station", "Baltimore/Camden Station", "CAMDEN STATION"),
]


def load_old_stops():
    with (OLD_FEED / "stops.txt").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def strip_decorations(stop_name: str) -> str:
    name = stop_name.upper()
    name = re.sub(r"\bMARC\b", "", name)
    name = re.sub(r"\b(EB|WB|SB|NB)\b", "", name)
    return re.sub(r"\s+", " ", name).strip()


def find_matches(old_stops, name_pattern: str):
    pattern = re.compile(name_pattern)
    return [s for s in old_stops if pattern.search(strip_decorations(s["stop_name"]))]


def old_stop_id_to_ours() -> dict[str, str]:
    """old feed stop_id -> this project's stop_id (many-to-one: eb/wb variants
    of the same station both map to our single collapsed stop)."""
    old_stops = load_old_stops()
    mapping = {}
    for stop_id, _name, pattern in STATIONS:
        for old_stop in find_matches(old_stops, pattern):
            mapping[old_stop["stop_id"]] = stop_id
    return mapping


def train_hours_by_stop() -> dict[str, dict[str, int]]:
    """train_number -> {our stop_id -> 24-hour arrival hour}, read from the old
    feed's *unsuffixed* "TrainNNN" trips only (skipping "TrainNNNR",
    "TrainNNNSaturday", etc. -- one clean reference time per stop is enough to
    tell AM from PM, see build_gtfs.py's `resolve_periods`)."""
    stop_id_map = old_stop_id_to_ours()
    train_number_re = re.compile(r"^Train(\d+)$")

    trip_to_train = {}
    with (OLD_FEED / "trips.txt").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m = train_number_re.match(row["trip_id"])
            if m:
                trip_to_train[row["trip_id"]] = m.group(1)

    result: dict[str, dict[str, int]] = {}
    with (OLD_FEED / "stop_times.txt").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            train_number = trip_to_train.get(row["trip_id"])
            our_stop_id = stop_id_map.get(row["stop_id"])
            if train_number is None or our_stop_id is None:
                continue
            hour = int(row["arrival_time"].split(":")[0])
            result.setdefault(train_number, {})[our_stop_id] = hour
    return result
