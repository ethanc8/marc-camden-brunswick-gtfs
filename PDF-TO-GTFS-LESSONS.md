# Building GTFS feeds from PDF timetables: lessons from this project

This project (MARC Camden/Brunswick GTFS, built from MTA's rider brochures and timetable
PDFs) is a worked example of turning an agency's PDF timetables into GTFS. This document
is written for a **different** future project doing the same kind of thing for a
**different** agency's PDFs. Section 1 is the generalizable technique; section 2 is a
frank assessment of which files in this repo you can actually reuse versus which are
MARC-specific and should just be read as a worked example.

If you're updating *this* repo for a new MARC PDF, see `UPDATING.md` instead — this
document is for starting a *new* PDF-to-GTFS project.

## 1. What generalizes

### 1.1 Don't trust automatic table extraction for agency timetables

Tools like `camelot` and `pdfplumber`'s `extract_table()`/`find_tables()` work by
detecting a grid (from ruling lines, or from whitespace gaps) and slicing text into
cells. Agency timetables produced by design software (InDesign, in this case) often
violate the assumptions those heuristics make:

- **Row separation may have no vector lines at all.** This project's tables used
  alternating background shading for row zebra-striping, not horizontal rules — and
  critically, *unshaded* rows had no drawn rectangle either, so a naive scan of "rect"
  objects only found half the rows. `find_tables()` misread this and merged two visually
  adjacent rows into one, silently producing a corrupted table shifted by one row.
- **Column separation usually *does* have vector lines** in this kind of table, and is
  much more reliable to detect than rows.

The technique that worked, and that we'd recommend by default rather than as a fallback:

1. Pull the raw vertical rule-line x-positions in the table's region
   (`page.lines`, filtered to near-vertical) → these are your column boundaries.
2. Pull raw words with position (`page.extract_words()`) in the region, sort by y
   ("top"), and cluster into rows by proximity — a "start a new row when the gap since
   the last word exceeds N points" scan, where N is comfortably between the intra-row
   jitter (sub-point to a couple points, from baseline/kerning quirks) and the real
   row-to-row spacing (which for a dense timetable is usually 10+ points). This is far
   more robust than trusting the library's row grouping.
3. **Identify columns by their header content, not by hardcoded pixel ranges.** Match
   each column region's header-row text against what you expect (e.g. "is this an
   integer?" for a train-number header) and only keep columns that match. This
   automatically discards decorative/annotation columns (e.g. an icon or a "DP"/"AR"
   departure/arrival label column that has no header of its own) without you needing to
   know in advance that they exist, and it fails loudly (wrong column count) if the PDF
   layout shifts.
4. Treat footnote/callout boxes that overlap the table grid (they will exist) as a
   content-based problem, not a geometry problem: identify their exact text and filter
   those words out before row-clustering, rather than trying to carve out their pixel
   region perfectly. Geometry-only approaches are fragile against boxes with rounded
   corners, drop shadows, or slightly-off bounding boxes.

### 1.2 Extract every source document you have, and diff them

If the agency publishes more than one document with overlapping schedule data (in this
project: a full rider brochure and a separate "changes" announcement, both containing a
full timetable), extract both independently and diff them by content (normalize station
names, match by an identifier that's stable across documents, compare cell by cell).
This is cheap and either gives you confidence (as it did here — zero discrepancies found)
or catches a real error in your extraction or in the agency's own PDFs before it ships.
Don't extract from just the "more convenient" document and assume the other agrees.

### 1.3 AM/PM (and other ambiguity) resolution: use a prior machine-readable schedule if one exists

Commuter-rail timetables commonly print 12-hour times with no AM/PM marker, using page
position (an "AM"/"PM" watermark, or just document convention) to disambiguate for human
readers. Don't try to reverse-engineer this purely from the printed grid — a
monotonic-time heuristic looks appealing but breaks on ordinary cases (a column whose
first populated cell isn't its first chronological stop, an express train's known times
happening to be "out of order" relative to a neighboring column, etc.). We built and then
discarded exactly this kind of heuristic during design; it's a trap.

**If you can get *any* prior GTFS feed for the same agency/route** (even an outdated one,
even downloaded from a project like OpenMobilityData/Transitland rather than the agency
directly), it almost certainly has unambiguous 24-hour times. Match its trips to your new
PDF's trips by the most stable identifier available (train/run number, here) and its
stops to your new PDF's stations by name (expect to write a small
regex/normalization table — station names are rarely spelled identically across sources).
Then, per new trip: resolve each stop's AM/PM directly from the matching old stop if one
exists; for stops with no old match (a newly-added stop), infer from the nearest
neighboring stop in the same trip that *does* have a resolved period (chronological order
within one trip is something you can rely on); only fall back to a hardcoded,
hand-verified value for a trip identifier with no history at all (a genuinely brand-new
run). Always add a monotonicity assertion (each trip's stop times must be
non-decreasing) — it's a free, high-value correctness check on this whole process and
will catch both bugs in your resolution and real mistakes in your source data.

### 1.4 A prior GTFS feed is useful for much more than times

Beyond disambiguating AM/PM, an old feed for the same agency is usually your best source
for:

- **Stop coordinates and accessibility flags** — geocoding a few dozen stations by hand
  or via a live web lookup is much more error-prone and slower than reusing coordinates
  the agency already published, even if slightly stale (stations don't move).
- **Naming/ID conventions** worth mirroring for continuity with other tools that already
  expect them (agency_id, a `TrainNNN`-style trip_id convention, etc.).
- **Historical precedent for schedule variants the new PDF documents only vaguely.** This
  project's biggest example: the new PDFs said a "contingency" schedule exists and which
  trains participate, but not what it actually looks like. The old feed had the *actual*
  stop-by-stop difference for that contingency schedule from the previous timetable
  revision, which — after checking it still applied to the new schedule (some of it
  didn't; the new schedule had already absorbed a few of the old contingency-only stops
  as regular ones) — was directly reusable. Always check whether "the last time this
  documented-but-unavailable variant was in effect" is sitting in an old feed before
  assuming you have to fabricate or omit it.

If you use an old feed as a source for anything, keep it untouched in your raw-inputs
directory and only ever produce *derived, hand-editable* copies of the parts you need —
don't let your generator depend on live-parsing a large third-party feed on every build.

### 1.5 Modeling patterns that generalize to any agency's GTFS

- **Collapsing direction-specific duplicate stops.** If a source feed models the same
  physical station as two stop_ids (one per direction/platform, a few meters apart),
  consider collapsing to one stop per station (e.g. averaging coordinates) if your new
  PDF's timetables don't distinguish them either. Simpler downstream code is usually
  worth a few meters of precision for a feed like this.
- **Model a documented-but-inactive schedule variant (snow day, holiday, etc.) as an
  inert calendar service** (all days = 0) with real trips referencing it, rather than
  omitting it or fabricating an activation date. This keeps the feed technically
  complete and lets a human flip it on later with a `calendar_dates.txt` exception,
  without your generator needing to know or guess when that'll happen. If more than one
  route can have that variant active independently, give each route its own service_id
  rather than one shared one — check whether the agency's own history shows
  route-independent activation (ours did) before assuming a single shared flag is enough.
- **Use `timepoint=0` honestly.** Any stop time you interpolated, estimated, or carried
  over from a different schedule revision rather than read directly off the current
  primary source should be marked non-timepoint. It's the correct GTFS mechanism for
  exactly this, and costs nothing.
- **Look for redundant renderings of the same data inside your source material**, and use
  them as free cross-checks. A through-running trip that's shown in full on its own panel
  *and* partially embedded in two other tables is redundant information — verify they
  agree instead of picking one and ignoring the other.
- **Validate with a second, independently-implemented tool**, not just your own
  generator's self-checks. A GTFS parser in a different language (`gtfs-structures` in
  Rust here, but any actively-maintained GTFS library in any language works) will
  round-trip-parse your output and catch spec violations or referential-integrity bugs a
  hand-rolled CSV writer can silently produce.

### 1.6 Project structure that generalizes

- Treat hand-extracted, hand-verified timetable data as a **checked-in artifact**, not
  just parser output: draft extraction writes to `*.draft.csv`, a human promotes it to
  `*.csv` after checking every cell against the rendered PDF, and the build reads only
  the promoted files. This keeps re-running extraction cheap while keeping a stable,
  reviewable source of truth — a CSV diff in a PR is something a human can actually check;
  a parser's internal state is not.
- Keep raw inputs, derived-but-editable reference data, extracted timetable data, and
  generated output in four clearly separate directories (here: `source-pdf/`,
  `reference/`, `extracted/`, `build/`), each with a one-sentence rule for what's allowed
  to write to it. This makes "where does this number actually come from" answerable at a
  glance months later.
- Write a small number of unit tests for the genuinely tricky pure functions (cell
  parsing, AM/PM resolution, any interpolation logic) rather than trying to test the PDF
  extraction itself — the extraction's real test is the manual verification step, and the
  cross-document diff.

## 2. What's reusable from this specific repo

### Reusable close to as-is

| File | Why |
|---|---|
| `gtfs_builder/pdf_grid.py` | Fully agency-agnostic: column-boundary detection from vector lines, and row-clustering from word positions. This is the piece most worth copying wholesale into a new project. |
| `validator/` (the whole Rust crate) | Generic GTFS validation via `gtfs-structures` — works on any GTFS zip, no MARC-specific code at all. |
| `Makefile`'s overall shape | The render/extract/diff/build/validate/test target structure isn't tied to MARC; only the specific commands each target runs are. |

### Reusable as a pattern, not as code

| File | What to reuse | What to redo |
|---|---|---|
| `gtfs_builder/pdf_extract.py` | The *approach*: a declarative list of `(pdf, page, bbox, skip-labels, drop-words)` per table, header-driven column identification, wide-CSV output. | Every `TABLES` entry's pixel coordinates — specific to this PDF's layout and font sizes. Re-derive per agency (and per PDF, if an agency's different lines use different templates) using the technique in §1.1. |
| `gtfs_builder/diff_sources.py` | The *approach*: extract the same data two ways, normalize a join key, diff. | The table list and station-name normalization are MARC-specific field names. |
| `gtfs_builder/build_gtfs.py`'s `resolve_periods`/`build_stop_events` | The *algorithm* in §1.3 (old-feed lookup, neighbor-fill, hardcoded-with-comment fallback, monotonicity assertion). | The specific old-feed field names/paths it reads. |
| `gtfs_builder/old_feed.py` | The *idea* of isolating "how do I read the old feed and map its stops to mine" into one small module. | The `STATIONS` regex table is entirely MARC's station names vs. this specific old feed's naming convention. |

### Not reusable — MARC/this-schedule-specific, read only as a worked example

- `gtfs_builder/config.py`'s `STATION_NAME_TO_STOP_ID`, `ROUTES`, `CALENDARS`, and
  especially `BRUNSWICK_R_EXTRA_STOPS` — all hand-derived facts about MARC's Camden and
  Brunswick Lines specifically.
- `gtfs_builder/build_reference.py` — tied to the exact CSV schema of MTA's old GTFS
  export.
- The whole "brunswick_camden through-service" concept in `build_gtfs.py`
  (`THROUGH_SERVICE_TABLE`, `NEW_TRAIN_PERIOD_OVERRIDE`, the reversed-direction "READ
  UP" handling) — specific to this one schedule change introducing a new
  through-running service. Worth reading as an example of how to handle a trip that
  spans two "lines," but not something to copy in.
- The R-schedule modeling in general — most agencies won't have this exact concept, and
  the ones that have something similar (a documented-but-rare contingency schedule) will
  need the general technique from §1.5, not this code.

### If you're starting a new agency's PDF-to-GTFS project

Copy `pdf_grid.py` and the Rust `validator/` crate as-is. Set up the same four-directory
split (`source-pdf/` / `reference/` / `extracted/` / `build/`) and the
draft-then-promote extraction workflow. Write a fresh `pdf_extract.py` for the new PDF's
layout using the §1.1 technique, a fresh `config.py` with that agency's actual station
names/routes/calendars, and — if you can find any prior GTFS feed for the agency — a
fresh `old_feed.py` plus the §1.3 AM/PM-resolution algorithm. Everything else in
`gtfs_builder/` and `build_gtfs.py` should be treated as a worked example to read, not a
library to import.
