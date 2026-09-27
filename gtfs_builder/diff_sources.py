"""Compare the reviewed extracted/*.csv (from the "Changes" PDFs) against the
independent extraction from the rider brochures (extracted/brochure_cross_check/),
station by station, train by train. Prints any disagreement -- see PLAN.md §2,
requirement 1: the two PDFs per line are supposed to carry the same schedule,
so a mismatch here means either a real discrepancy in MARC's source PDFs or an
extraction bug, and either way a human needs to look at it.

Station names differ slightly in punctuation/wording between the two PDF
families (e.g. "ST. DENIS" vs "St. Denis"), so rows are matched by a
normalized (alphanumeric-only, uppercased) station name rather than an exact
string match.
"""

import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTED_DIR = REPO_ROOT / "extracted"
BROCHURE_DIR = EXTRACTED_DIR / "brochure_cross_check"

TABLES = ["camden_eastbound", "camden_westbound", "brunswick_eastbound", "brunswick_westbound"]


def normalize_station(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def load_table(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {normalize_station(row["station"]): row for row in rows}


def diff_table(name: str) -> list[str]:
    reference = load_table(EXTRACTED_DIR / f"{name}.csv")
    brochure = load_table(BROCHURE_DIR / f"{name}.draft.csv")
    problems = []

    missing_in_brochure = reference.keys() - brochure.keys()
    missing_in_reference = brochure.keys() - reference.keys()
    for station in sorted(missing_in_brochure):
        problems.append(f"{name}: station {station!r} present in Changes doc but not in brochure")
    for station in sorted(missing_in_reference):
        problems.append(f"{name}: station {station!r} present in brochure but not in Changes doc")

    for station in sorted(reference.keys() & brochure.keys()):
        ref_row, bro_row = reference[station], brochure[station]
        train_numbers = set(ref_row) & set(bro_row) - {"station"}
        for train_number in sorted(train_numbers, key=lambda t: int(re.sub(r"\D", "", t) or 0)):
            ref_val, bro_val = ref_row[train_number].strip(), bro_row[train_number].strip()
            if ref_val != bro_val:
                problems.append(
                    f"{name}: {ref_row['station']!r} train {train_number}: "
                    f"Changes doc={ref_val!r} vs. brochure={bro_val!r}"
                )
    return problems


def main():
    all_problems = []
    for name in TABLES:
        all_problems.extend(diff_table(name))

    if not all_problems:
        print("No discrepancies found between the Changes-doc and brochure timetables.")
        return 0

    print(f"{len(all_problems)} discrepancy(ies) found:\n")
    for problem in all_problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
