"""Extract MARC Camden/Brunswick timetable grids from the "Changes" PDFs (page 2
of each, which is a cleanly-gridded full timetable -- see PLAN.md §2).

Each table is a grid of vertical rule lines with two stacked header lines
(train numbers, then a per-train flag line) followed by one row per station.
Output is a "wide" CSV per table -- one row per station, one column per train
number, cell text exactly as printed (e.g. "6:32", "—", "f5:59", "R", "BUS") --
plus a small `<table>_trains.csv` with the per-train flag/Friday-only metadata
read off the header lines. Wide format mirrors the printed brochure layout so
it's easy to eyeball a cell against the rendered PNG from `make render-pdfs`.

This script only produces DRAFTS (`--out-dir` defaults to `extracted`, written
as `*.draft.csv`). The reviewed, ground-truth `extracted/*.csv` files are
promoted by hand after checking every cell against the source PDF -- see
PLAN.md §6 and §8.
"""

import argparse
import csv
import re
from pathlib import Path

import pdfplumber

from pdf_grid import column_boundaries, region_text, text_rows

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PDF_DIR = REPO_ROOT / "source-pdf"

# Each table: two stacked header lines (train numbers, then flags/read-dir)
# followed by data rows. `skip_label_substrings` drops rows that are really a
# footnote/note sharing the table's column grid (e.g. the Thru Service tables'
# "Direct service, does not serve Washington, DC" divider).
TABLES = [
    dict(
        name="camden_eastbound",
        pdf="Camden Line Sept 28 Changes.pdf",
        page=1,
        x_min=19, x_max=540, y_header=98, y_data_end=283,
        skip_label_substrings=[],
    ),
    dict(
        name="camden_westbound",
        pdf="Camden Line Sept 28 Changes.pdf",
        page=1,
        x_min=19, x_max=540, y_header=350, y_data_end=533,
        skip_label_substrings=[],
    ),
    dict(
        name="camden_through_service",
        pdf="Camden Line Sept 28 Changes.pdf",
        page=1,
        x_min=545, x_max=780, y_header=120, y_data_end=357,
        skip_label_substrings=["DIRECT SERVICE"],
    ),
    dict(
        name="brunswick_eastbound",
        pdf="Brunswick Line Sept 28 Changes.pdf",
        page=1,
        x_min=14, x_max=542, y_header=64, y_data_end=298,
        skip_label_substrings=[],
    ),
    dict(
        name="brunswick_westbound",
        pdf="Brunswick Line Sept 28 Changes.pdf",
        page=1,
        x_min=14, x_max=542, y_header=330, y_data_end=580,
        skip_label_substrings=[],
        # The "*Train 871 operates Friday only" footnote is drawn as a box
        # overlapping the 871 column for Harpers Ferry/Duffields/Martinsburg
        # (871 doesn't reach those stations, so there's no real time under
        # the box). Its words share those rows' y-position, so without this
        # they'd land in the 871 column's cells instead of being recognized
        # as "no stop" -- harmless downstream (they don't match the time
        # regex either way) but confusing to a human reviewing the CSV.
        drop_words={"*Train", "871", "operates", "Friday", "only"},
    ),
    dict(
        name="brunswick_through_service",
        pdf="Brunswick Line Sept 28 Changes.pdf",
        page=1,
        x_min=545, x_max=780, y_header=120, y_data_end=357,
        skip_label_substrings=["DIRECT SERVICE"],
    ),
]

TRAIN_NUMBER_RE = re.compile(r"^\*?(\d+)$")


def region_bounds(col_bounds, x_max):
    """[(lo, hi), ...] for each candidate data column, given the sorted
    vertical-line x-positions found inside the table (the region before the
    first line is the row-label column, handled separately)."""
    edges = col_bounds + [x_max]
    return list(zip(edges[:-1], edges[1:]))


def identify_train_columns(header_row, bounds):
    """Match header-line-1 text in each column region against a train number.
    Columns with no valid number (e.g. Brunswick's "DP"/"AR" annotation
    column) are dropped -- this is what makes column identification robust to
    extra decorative columns without hand-listing them per table."""
    columns = []
    for lo, hi in bounds:
        text = region_text(header_row, lo, hi).strip()
        m = TRAIN_NUMBER_RE.match(text)
        if not m:
            continue
        columns.append(
            {
                "train_number": m.group(1),
                "friday_only": text.startswith("*"),
                "lo": lo,
                "hi": hi,
            }
        )
    return columns


def extract_table(pdf, table):
    page = pdf.pages[table["page"]]
    x_min, x_max = table["x_min"], table["x_max"]
    bounds = column_boundaries(page, x_min, x_max, table["y_header"], table["y_data_end"])
    rows = text_rows(page, x_min, x_max, table["y_header"], table["y_data_end"])

    drop_words = table.get("drop_words", set())
    if drop_words:
        rows = [[w for w in row if w.text not in drop_words] for row in rows]

    header_line1, header_line2, *data_rows = rows
    columns = identify_train_columns(header_line1, region_bounds(bounds, x_max))
    flags = {
        col["train_number"]: region_text(header_line2, col["lo"], col["hi"]).strip()
        for col in columns
    }

    station_rows = []
    for row in data_rows:
        label = region_text(row, x_min, bounds[0]).strip()
        if not label:
            continue  # pure continuation fragment (e.g. a footnote box) already
            # folded into the previous/next row by text_rows' row_gap merging
        if any(s in label.upper() for s in table["skip_label_substrings"]):
            continue
        cells = {col["train_number"]: region_text(row, col["lo"], col["hi"]).strip() for col in columns}
        station_rows.append((label, cells))

    return columns, flags, station_rows


def write_table_csv(out_dir, table, columns, station_rows):
    train_numbers = [c["train_number"] for c in columns]
    path = out_dir / f"{table['name']}.draft.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["station", *train_numbers])
        for label, cells in station_rows:
            writer.writerow([label, *(cells.get(tn, "") for tn in train_numbers)])
    print(f"wrote {path} ({len(station_rows)} stations x {len(train_numbers)} trains)")


def write_trains_csv(out_dir, table, columns, flags):
    path = out_dir / f"{table['name']}_trains.draft.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["train_number", "flags", "friday_only"])
        for col in columns:
            writer.writerow([col["train_number"], flags[col["train_number"]], col["friday_only"]])
    print(f"wrote {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "extracted")
    args = parser.parse_args()
    args.out_dir.mkdir(exist_ok=True)

    pdfs = {}
    for table in TABLES:
        if table["pdf"] not in pdfs:
            pdfs[table["pdf"]] = pdfplumber.open(SOURCE_PDF_DIR / table["pdf"])
        pdf = pdfs[table["pdf"]]
        columns, flags, station_rows = extract_table(pdf, table)
        write_table_csv(args.out_dir, table, columns, station_rows)
        write_trains_csv(args.out_dir, table, columns, flags)
    for pdf in pdfs.values():
        pdf.close()


if __name__ == "__main__":
    main()
