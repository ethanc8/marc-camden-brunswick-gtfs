"""Build the GTFS feed from extracted/ + reference/ + config.py.

The tricky part is that the source PDFs print times in 12-hour format with no
AM/PM marker (e.g. "6:32", "3:30"). We resolve each stop's AM/PM by looking up
the same (train number, station) pair in the old MARC feed (source-pdf/
mdotmta_gtfs_marc/), which uses unambiguous 24-hour times -- see
`resolve_periods`. That covers every train except the two brand new
through-running trains (830/831), which don't exist in the old feed and are
hardcoded instead (verified by hand against the source PDF -- see PLAN.md §3).
"""

import argparse
import csv
import re
import zipfile
from pathlib import Path

import config
from old_feed import train_hours_by_stop

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTED_DIR = REPO_ROOT / "extracted"
REFERENCE_DIR = REPO_ROOT / "reference"

TIME_CELL_RE = re.compile(r"^([fdL]?)(\d{1,2}):(\d{2})$")

# (table name, route_id, direction_id). 830/831 are excluded when reading
# these -- they're built once from THROUGH_SERVICE_TABLE instead, since that
# table has their complete Brunswick+Camden stop pattern in one place (these
# main tables only show each line's half of it -- see PLAN.md §3).
MAIN_TABLES = [
    ("camden_eastbound", "camden", 0),
    ("camden_westbound", "camden", 1),
    ("brunswick_eastbound", "brunswick", 0),
    ("brunswick_westbound", "brunswick", 1),
]
THROUGH_SERVICE_TABLE = "camden_through_service"  # brunswick_through_service.csv carries the same data

# Brand new trains introduced 2026-09-28; absent from the old feed, so there's
# no ground truth to resolve AM/PM against. Read by hand off the source PDF
# (Brunswick/Camden "Thru Service" panels): 830 is the AM Brunswick->Camden
# run, 831 the PM Camden->Brunswick run.
NEW_TRAIN_PERIOD_OVERRIDE = {"830": "AM", "831": "PM"}

# prefix -> (pickup_type, drop_off_type). See PLAN.md §2 for the legend.
PREFIX_PICKUP_DROPOFF = {"": (0, 0), "f": (3, 0), "d": (1, 0), "L": (0, 0)}
EARLY_DEPARTURE_PREFIXES = {"f", "d", "L"}  # all three mean "may depart early" -> timepoint=0


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def station_stop_id(printed_name: str) -> str:
    stop_id = config.STATION_NAME_TO_STOP_ID.get(printed_name)
    if stop_id is None:
        raise KeyError(f"no stop_id mapping in config.py for station name {printed_name!r}")
    return stop_id


def parse_cell(raw: str):
    """"6:32" -> ("", 6, 32); "f5:09" -> ("f", 5, 9); "" / "—" / "R" / "BUS" -> None."""
    m = TIME_CELL_RE.match(raw.strip())
    return None if not m else (m.group(1), int(m.group(2)), int(m.group(3)))


def r_flagged(flags: str) -> bool:
    return "R" in flags.split("/")


def resolve_periods(train_number: str, stop_ids: list[str], old_hours: dict) -> list[str]:
    """One "AM"/"PM" per stop, preferring the old feed's 24-hour time for that
    exact (train, station) pair and filling any gap (a newly-added stop, or a
    train missing from the old feed entirely) from the nearest resolved
    neighbor -- a timetable's stops are always listed in time order, so the
    nearest neighbor's period is virtually always correct."""
    if train_number in NEW_TRAIN_PERIOD_OVERRIDE:
        return [NEW_TRAIN_PERIOD_OVERRIDE[train_number]] * len(stop_ids)

    train_old_hours = old_hours.get(train_number, {})
    periods = []
    for stop_id in stop_ids:
        hour = train_old_hours.get(stop_id)
        periods.append(None if hour is None else ("PM" if hour >= 12 else "AM"))

    for i, period in enumerate(periods):
        if period is not None:
            continue
        for d in range(1, len(periods)):
            if i - d >= 0 and periods[i - d] is not None:
                periods[i] = periods[i - d]
                break
            if i + d < len(periods) and periods[i + d] is not None:
                periods[i] = periods[i + d]
                break

    if any(p is None for p in periods):
        raise ValueError(f"train {train_number}: could not resolve AM/PM for any of its stops")
    return periods


def build_stop_events(train_number: str, ordered_stops: list[tuple[str, str]], old_hours: dict):
    """ordered_stops: [(stop_id, raw_cell), ...] in chronological order (i.e.
    already reversed for a "READ UP" through-service column). Returns
    [(stop_id, "HH:MM:SS", pickup_type, drop_off_type, timepoint), ...],
    skipping stations this trip doesn't stop at."""
    valid = [(stop_id, parse_cell(raw)) for stop_id, raw in ordered_stops]
    valid = [(stop_id, cell) for stop_id, cell in valid if cell is not None]
    if not valid:
        return []

    periods = resolve_periods(train_number, [s for s, _ in valid], old_hours)

    events = []
    prev_minutes = None
    for (stop_id, (prefix, hour12, minute)), period in zip(valid, periods):
        hour24 = (hour12 % 12) + (12 if period == "PM" else 0)
        minutes = hour24 * 60 + minute
        if prev_minutes is not None and minutes < prev_minutes:
            raise ValueError(
                f"train {train_number}: time goes backwards at stop {stop_id} "
                f"({hour24:02d}:{minute:02d} follows a later stop) -- AM/PM resolution bug"
            )
        prev_minutes = minutes
        pickup_type, drop_off_type = PREFIX_PICKUP_DROPOFF[prefix]
        timepoint = 0 if prefix in EARLY_DEPARTURE_PREFIXES else 1
        events.append((stop_id, f"{hour24:02d}:{minute:02d}:00", pickup_type, drop_off_type, timepoint))
    return events


def _time_to_minutes(time_str: str) -> int:
    hour, minute, _second = map(int, time_str.split(":"))
    return hour * 60 + minute


def _minutes_to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def apply_brunswick_r_extra_stops(train_number: str, events: list):
    """Insert this train's R-schedule extra stops (config.BRUNSWICK_R_EXTRA_STOPS),
    each `minutes_after_anchor` minutes after its anchor stop -- which may
    itself be a stop just inserted earlier in the same list, so anchors are
    resolved against a running list that grows as we go. Extra stops get
    pickup/drop_off_type=0 (regular) but timepoint=0 (estimated, not the
    schedule's real timepoint) -- see config.py for where the minute deltas
    come from."""
    extra_stops = config.BRUNSWICK_R_EXTRA_STOPS.get(train_number, [])
    if not extra_stops:
        return events

    working = [list(event) for event in events]  # [stop_id, time_str, pickup, dropoff, timepoint]
    for anchor_stop_id, new_stop_id, minutes_after_anchor in extra_stops:
        anchor_index = next(i for i, e in enumerate(working) if e[0] == anchor_stop_id)
        new_time = _minutes_to_time(_time_to_minutes(working[anchor_index][1]) + minutes_after_anchor)
        working.insert(anchor_index + 1, [new_stop_id, new_time, 0, 0, 0])

    minutes = [_time_to_minutes(e[1]) for e in working]
    if minutes != sorted(minutes):
        raise ValueError(f"train {train_number}: R-schedule extra stops produced an out-of-order trip")
    return [tuple(e) for e in working]


def make_trips(train_number, route_id, direction_id, events, friday_only, r_capable, stop_names):
    """A trip, plus its R-schedule mirror if this train keeps running under
    the contingency schedule -- see PLAN.md §3 and config.BRUNSWICK_R_EXTRA_STOPS."""
    if not events:
        return []
    base = {
        "trip_id": f"Train{train_number}",
        "route_id": route_id,
        "service_id": "friday" if friday_only else "weekday",
        "trip_headsign": stop_names[events[-1][0]],
        "trip_short_name": f"Train {train_number}",
        "direction_id": direction_id,
        "wheelchair_accessible": 1,
        "bikes_allowed": 1,
        "events": events,
    }
    trips = [base]
    if r_capable:
        r_events = apply_brunswick_r_extra_stops(train_number, events) if route_id == "brunswick" else events
        mirror = dict(
            base,
            trip_id=f"Train{train_number}R",
            service_id=config.R_SERVICE_BY_ROUTE[route_id],
            trip_headsign=stop_names[r_events[-1][0]],
            events=r_events,
        )
        trips.append(mirror)
    return trips


def load_table(name: str):
    rows = load_csv(EXTRACTED_DIR / f"{name}.csv")
    train_numbers = [k for k in rows[0] if k != "station"]
    trains_meta = {t["train_number"]: t for t in load_csv(EXTRACTED_DIR / f"{name}_trains.csv")}
    station_order = [(station_stop_id(r["station"]), r) for r in rows]
    return station_order, train_numbers, trains_meta


def build_main_table_trips(name, route_id, direction_id, old_hours, stop_names):
    station_order, train_numbers, trains_meta = load_table(name)
    trips = []
    for train_number in train_numbers:
        if train_number in NEW_TRAIN_PERIOD_OVERRIDE:
            continue  # built from the through-service table instead
        ordered = [(stop_id, row[train_number]) for stop_id, row in station_order]
        events = build_stop_events(train_number, ordered, old_hours)
        meta = trains_meta[train_number]
        trips += make_trips(
            train_number, route_id, direction_id, events,
            friday_only=meta["friday_only"] == "True",
            r_capable=r_flagged(meta["flags"]),
            stop_names=stop_names,
        )
    return trips


def through_service_events(old_hours) -> dict[str, list]:
    """train_number ("830"/"831") -> its chronologically-ordered events."""
    station_order, _train_numbers, trains_meta = load_table(THROUGH_SERVICE_TABLE)
    events_by_train = {}
    for train_number in ("830", "831"):
        ordered = [(stop_id, row[train_number]) for stop_id, row in station_order]
        if "UP" in trains_meta[train_number]["flags"]:  # "READ UP" -- see PLAN.md §2
            ordered = list(reversed(ordered))
        events_by_train[train_number] = build_stop_events(train_number, ordered, old_hours)
    return events_by_train


def build_through_service_trips(old_hours, stop_names):
    trips = []
    for train_number, direction_id in (("830", 0), ("831", 1)):
        events = through_service_events(old_hours)[train_number]
        trips += make_trips(
            train_number, "brunswick_camden", direction_id, events,
            friday_only=False, r_capable=False, stop_names=stop_names,
        )
    return trips


def check_through_columns_agree_with_main_tables(old_hours):
    """The 830/831 columns embedded in the main EB/WB tables (not used to
    build any trip -- see PLAN.md §3) are a redundant partial view of the same
    trip. Any populated cell there should match the through-service-derived
    trip; this is a free extra correctness check, not required for output."""
    through_events = through_service_events(old_hours)
    problems = []
    for name, _route_id, _direction_id in MAIN_TABLES:
        station_order, train_numbers, _meta = load_table(name)
        for train_number in ("830", "831"):
            if train_number not in train_numbers:
                continue
            by_stop = {stop_id: time for stop_id, time, *_ in through_events[train_number]}
            for stop_id, row in station_order:
                cell = parse_cell(row[train_number])
                if cell is None:
                    continue
                expected = by_stop.get(stop_id)
                _prefix, hour12, minute = cell
                if expected is None:
                    problems.append(f"{name}: train {train_number} at {stop_id}: has a time but through-service trip has no stop there")
                    continue
                expected_hour24, expected_minute = map(int, expected.split(":")[:2])
                if (expected_hour24 % 12, expected_minute) != (hour12 % 12, minute):
                    problems.append(
                        f"{name}: train {train_number} at {stop_id}: table says :{minute:02d} "
                        f"past {hour12}, through-service trip says {expected}"
                    )
    return problems


def write_gtfs(out_dir: Path, trips: list[dict]):
    out_dir.mkdir(parents=True, exist_ok=True)

    agency_rows = load_csv(REFERENCE_DIR / "agency.csv")
    write_csv(out_dir / "agency.txt", list(agency_rows[0]), agency_rows)
    agency_id = agency_rows[0]["agency_id"]

    route_rows = [
        {
            "route_id": route_id,
            "agency_id": agency_id,
            "route_short_name": r["route_short_name"],
            "route_long_name": r["route_long_name"],
            "route_type": 2,  # rail
            "route_color": r["route_color"],
            "route_text_color": r["route_text_color"],
        }
        for route_id, r in config.ROUTES.items()
    ]
    write_csv(
        out_dir / "routes.txt",
        ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color", "route_text_color"],
        route_rows,
    )

    calendar_rows = [{"service_id": service_id, **c} for service_id, c in config.CALENDARS.items()]
    write_csv(
        out_dir / "calendar.txt",
        ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"],
        calendar_rows,
    )
    write_csv(out_dir / "calendar_dates.txt", ["service_id", "date", "exception_type"], [])

    stop_rows = load_csv(REFERENCE_DIR / "stops.csv")
    write_csv(out_dir / "stops.txt", list(stop_rows[0]), stop_rows)

    trip_rows = [{k: v for k, v in t.items() if k != "events"} for t in trips]
    write_csv(
        out_dir / "trips.txt",
        ["trip_id", "route_id", "service_id", "trip_headsign", "trip_short_name", "direction_id", "wheelchair_accessible", "bikes_allowed"],
        trip_rows,
    )

    stop_time_rows = [
        {
            "trip_id": t["trip_id"],
            "arrival_time": time_str,
            "departure_time": time_str,
            "stop_id": stop_id,
            "stop_sequence": seq,
            "pickup_type": pickup_type,
            "drop_off_type": drop_off_type,
            "timepoint": timepoint,
        }
        for t in trips
        for seq, (stop_id, time_str, pickup_type, drop_off_type, timepoint) in enumerate(t["events"], start=1)
    ]
    write_csv(
        out_dir / "stop_times.txt",
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "pickup_type", "drop_off_type", "timepoint"],
        stop_time_rows,
    )

    write_csv(
        out_dir / "feed_info.txt",
        ["feed_publisher_name", "feed_publisher_url", "feed_lang", "feed_start_date", "feed_end_date"],
        [
            {
                "feed_publisher_name": "marc-camden-brunswick-gtfs (unofficial, community-built)",
                "feed_publisher_url": agency_rows[0]["agency_url"],
                "feed_lang": "en",
                "feed_start_date": config.SERVICE_START,
                "feed_end_date": config.SERVICE_END,
            }
        ],
    )


def zip_gtfs(out_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for txt_file in sorted(out_dir.glob("*.txt")):
            zf.write(txt_file, arcname=txt_file.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "build" / "gtfs")
    parser.add_argument("--zip", type=Path, default=REPO_ROOT / "build" / "marc-camden-brunswick-gtfs.zip")
    args = parser.parse_args()

    old_hours = train_hours_by_stop()
    stop_names = {row["stop_id"]: row["stop_name"] for row in load_csv(REFERENCE_DIR / "stops.csv")}

    trips = build_through_service_trips(old_hours, stop_names)
    for name, route_id, direction_id in MAIN_TABLES:
        trips += build_main_table_trips(name, route_id, direction_id, old_hours, stop_names)

    problems = check_through_columns_agree_with_main_tables(old_hours)
    for problem in problems:
        print(f"WARNING: {problem}")

    write_gtfs(args.out_dir, trips)
    zip_gtfs(args.out_dir, args.zip)
    print(f"wrote {len(trips)} trips to {args.out_dir} and {args.zip}")


if __name__ == "__main__":
    main()
