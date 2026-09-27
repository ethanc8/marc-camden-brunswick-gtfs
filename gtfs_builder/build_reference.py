"""Derive reference/stops.csv and reference/agency.csv from the old MARC GTFS feed.

The old feed (source-pdf/mdotmta_gtfs_marc/) gives one stop_id per station *per
direction* (e.g. "SILVER SPRING MARC eb" / "SILVER SPRING MARC wb") because its
source system tracks platforms separately. The new PDFs list one row per station
regardless of direction, and the eb/wb coordinate pairs differ by only a few
meters, so we collapse each station to a single stop (averaging eb/wb lat/lon)
for a simpler, more maintainable feed.

This script is meant to be run once to produce reference/stops.csv, which is then
a hand-editable, checked-in file -- not regenerated automatically as part of
`make build`.
"""

import csv
from pathlib import Path

from old_feed import OLD_FEED, STATIONS, find_matches, load_old_stops

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "reference"


def average_latlon(matches):
    lat = sum(float(s["stop_lat"]) for s in matches) / len(matches)
    lon = sum(float(s["stop_lon"]) for s in matches) / len(matches)
    return lat, lon


def build_stops_csv():
    old_stops = load_old_stops()
    rows = []
    for stop_id, stop_name, name_pattern in STATIONS:
        matches = find_matches(old_stops, name_pattern)
        if not matches:
            raise SystemExit(f"No old-feed stop matched pattern {name_pattern!r} for {stop_name!r}")
        lat, lon = average_latlon(matches)
        rows.append(
            {
                "stop_id": stop_id,
                "stop_name": stop_name,
                "stop_lat": f"{lat:.6f}",
                "stop_lon": f"{lon:.6f}",
                # Not confidently known station-by-station from the source PDFs at
                # the time of writing -- see PLAN.md "future / not now". 0 = no
                # information, which is honest and won't mislead riders.
                "wheelchair_boarding": 0,
            }
        )

    out_path = REFERENCE_DIR / "stops.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["stop_id", "stop_name", "stop_lat", "stop_lon", "wheelchair_boarding"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path} ({len(rows)} stops)")


def build_agency_csv():
    with (OLD_FEED / "agency.txt").open(newline="", encoding="utf-8") as f:
        agency_row = next(csv.DictReader(f))

    out_path = REFERENCE_DIR / "agency.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(agency_row.keys()))
        writer.writeheader()
        writer.writerow(agency_row)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    REFERENCE_DIR.mkdir(exist_ok=True)
    build_stops_csv()
    build_agency_csv()
