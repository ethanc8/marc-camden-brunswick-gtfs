"""Extract the same timetable grids from the rider trifold brochures (page 1 of
each), as an independent cross-check against extracted/*.csv (extracted from
the "Changes" PDFs) -- see PLAN.md §2. Same grid technique, same table-parsing
code (see pdf_extract.py), different PDF/page/coordinates: the brochures use a
wider (1674pt) page and lay the whole rider brochure out in one row of panels
instead of two, but draw each timetable with the same vertical-rule-lines
grid.

Only produces drafts, in extracted/brochure_cross_check/. Run `make
diff-sources` afterwards to compare these against the reviewed extracted/*.csv.
"""

import argparse
from pathlib import Path

import pdfplumber

from pdf_extract import SOURCE_PDF_DIR, extract_table, write_table_csv, write_trains_csv

REPO_ROOT = Path(__file__).resolve().parent.parent

TABLES = [
    dict(
        name="camden_eastbound",
        pdf="marc_camden-washington_Sept28.pdf",
        page=0,
        x_min=0, x_max=560, y_header=38, y_data_end=208,
        skip_label_substrings=[],
    ),
    dict(
        name="camden_westbound",
        pdf="marc_camden-washington_Sept28.pdf",
        page=0,
        x_min=0, x_max=560, y_header=242, y_data_end=413,
        skip_label_substrings=[],
    ),
    dict(
        name="brunswick_eastbound",
        pdf="marc_brunswick-washington_Sept28.pdf",
        page=0,
        x_min=0, x_max=820, y_header=42, y_data_end=283,
        skip_label_substrings=[],
    ),
    dict(
        name="brunswick_westbound",
        pdf="marc_brunswick-washington_Sept28.pdf",
        page=0,
        x_min=0, x_max=840, y_header=327, y_data_end=576,
        skip_label_substrings=[],
        drop_words={"*Train", "871", "operates", "Friday", "only"},
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "extracted" / "brochure_cross_check"
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

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
