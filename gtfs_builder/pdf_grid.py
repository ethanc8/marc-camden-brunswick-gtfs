"""Low-level word-grid extraction shared by all MARC timetable tables.

These brochures draw each timetable as a grid of vertical rule lines (one per
column boundary) but *no* horizontal rule lines -- row separation only exists
in the text layout (alternating background shading, not vector lines). So:

- column boundaries come from vector lines (page.lines)
- row boundaries come from clustering word y-positions ("top") by proximity

Row clustering uses a chase-merge: sort every word by top, and start a new row
whenever the gap since the last word exceeds `row_gap`. Real rows in these
tables are never closer than ~11pt apart, while all the same-row jitter and
footnote-box artifacts we've seen (stacked "AM"/direction labels, a footnote
box overlapping a column) are within ~1-3pt, so a mid-single-digit threshold
merges same-row fragments without ever merging two real rows together.
"""

from dataclasses import dataclass


@dataclass
class Word:
    top: float
    x0: float
    text: str


def column_boundaries(page, x_min, x_max, y_min, y_max, merge_tol=2.0):
    """X-positions of vertical rule lines inside the given region, deduped."""
    xs = sorted(
        {
            round(line["x0"], 1)
            for line in page.lines
            if x_min <= line["x0"] <= x_max
            and y_min <= line["top"] <= y_max
            and abs(line["x0"] - line["x1"]) < 1  # vertical line
        }
    )
    merged = []
    for x in xs:
        if merged and x - merged[-1] < merge_tol:
            continue
        merged.append(x)
    return merged


def text_rows(page, x_min, x_max, y_min, y_max, row_gap=3.0, x_tolerance=1):
    """Words in the region, grouped into rows and sorted left-to-right."""
    words = [
        Word(w["top"], w["x0"], w["text"])
        for w in page.extract_words(x_tolerance=x_tolerance)
        if x_min <= w["x0"] < x_max and y_min <= w["top"] < y_max
    ]
    words.sort(key=lambda w: w.top)

    rows: list[list[Word]] = []
    for word in words:
        if rows and word.top - rows[-1][-1].top < row_gap:
            rows[-1].append(word)
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w.x0)
    return rows


def region_text(row: list[Word], lo: float, hi: float) -> str:
    """Join the text of every word in `row` whose x0 falls in [lo, hi)."""
    return " ".join(w.text for w in row if lo <= w.x0 < hi)
