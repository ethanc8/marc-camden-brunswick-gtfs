# Updating this feed for a new schedule PDF

MARC periodically republishes the Camden/Brunswick timetables (a new service change, a
seasonal adjustment, etc.). This is the checklist for bringing this repo up to date when
that happens. Read `PLAN.md` first if you haven't -- this assumes you know the pipeline
it describes (`source-pdf/` → `extracted/` → `gtfs_builder/` → `build/`).

Work through the sections in order; later steps assume earlier ones are done.

## 1. Add the new PDFs

Drop the new PDFs into `source-pdf/` (keep the old ones too, or move them into a
subdirectory like `source-pdf/2026-09-28/` -- either way, don't delete history you might
need to diff against later). You need the same two documents per line as last time: the
rider trifold brochure and the "Changes" PDF (or whatever MTA calls the standalone
timetable insert this time). If MTA's PDF layout is materially different (not just new
numbers in the same template), skip to **§5 (re-tuning extraction)** before continuing.

If you can get a copy of MTA's own GTFS export as of just before the new effective date,
add it alongside `source-pdf/mdotmta_gtfs_marc/` (e.g.
`source-pdf/mdotmta_gtfs_marc_2026-09/`) -- see **§4**, it's more useful there than the
one currently in the repo will be.

## 2. Extract the new timetables

```sh
make render-pdfs     # PNGs in build/pdf-preview/, for eyeballing cells
make extract-draft   # writes extracted/*.draft.csv from the new PDFs
```

`pdf_extract.py`'s `TABLES` list hardcodes which PDF/page/pixel-region each table comes
from (`camden_eastbound`, `camden_westbound`, `camden_through_service`, and the Brunswick
equivalents). If MTA kept the same InDesign template, the draft output should already
look right -- diff a couple of drafted cells against the rendered PNG to confirm, then
promote the drafts:

```sh
cp extracted/camden_eastbound.draft.csv extracted/camden_eastbound.csv
# ...and the _trains.draft.csv counterpart for each table, and the Brunswick tables
```

Then do the same against the brochure PDFs and cross-check:

```sh
pixi run -- python gtfs_builder/pdf_extract_brochure.py
make diff-sources
```

**Manually verify every cell of every promoted `extracted/*.csv` against the rendered PDF
before moving on.** This project's whole premise is that the timetable is exact -- don't
skip this because the extraction "usually works."

If a table's column/row count comes out wrong, or cells contain garbage from a footnote
box (like the "*Train 871 operates Friday only" box from the 2026-09-28 PDFs), see **§5**.

## 3. Update `config.py`

- **`SERVICE_START` / `SERVICE_END`**: the new effective-date range.
- **`STATION_NAME_TO_STOP_ID`**: if MTA added, removed, or renamed a station, this
  dict needs a new entry. Run `make build` and let it fail -- `station_stop_id()` raises
  a clear `KeyError` naming the unmapped printed station string. If it's a genuinely new
  station (not just a new spelling of an existing one), you also need a new row in
  `reference/stops.csv` (see **§4**) before you can map to it.
- **`ROUTES`**: only touch this if MTA rebrands a line or introduces another new
  through-service pattern like `brunswick_camden`. Get the new route's official name and
  color from the project owner, same as `brunswick_camden` was — don't invent one.
- **`CALENDARS`** / **`R_SERVICE_BY_ROUTE`**: add a `friday`-style one-off calendar if a
  new train shows up with a footnote like "operates Friday only" (or Saturday, holidays,
  etc.) — grep the fine print for anything that isn't a plain Monday-Friday note. Add a
  new `r_schedule_<line>` pair if a new route gains R-flagged trains.
- **`BRUNSWICK_R_EXTRA_STOPS`**: needs full re-derivation — see **§4**, this is the part
  most likely to need real thought rather than a mechanical edit.

## 4. Re-derive the R-schedule extra stops

This project models the "R" contingency schedule (severe weather/holidays) by comparing
each `TrainNNN` to its `TrainNNNR` counterpart in a reference GTFS feed and carrying the
difference forward — see `PLAN.md` §3 for the full reasoning and `config.BRUNSWICK_R_EXTRA_STOPS`
for the current table. When the schedule changes, redo this analysis:

1. **Pick the reference feed.** Use whatever GTFS export best represents the schedule
   *right before* this new change — that's `source-pdf/mdotmta_gtfs_marc/` today, but
   next time it should usually be **the feed this repo itself just built**
   (`build/gtfs/`, or a copy of it committed somewhere), since it's a closer, more
   accurate description of "yesterday's" schedule than an increasingly stale download.
   Update `old_feed.py`'s `OLD_FEED` path (and `STATIONS`, if the reference feed's
   stop-naming convention differs) accordingly.
2. **List the R-flagged trains per line** in the new timetables (the `flags` column of
   each `extracted/*_trains.csv`) and compare against the reference feed's `TrainNNNR`
   trip list. Expect drift: some trains keep the flag, some lose it, some gain it for the
   first time (2026-09-28's update: Brunswick's 877 dropped the flag, 873 gained it).
3. **For each line, check whether R-trips there historically added real stops or were
   pure mirrors of the base trip** (diff `TrainNNN` vs `TrainNNNR` stop_times in the
   reference feed). This determined the Camden-mirrors-exactly /
   Brunswick-adds-real-stops split last time; it could change if MTA changes how a line's
   R schedule works, so don't assume it still holds — check the legend text on the new
   PDFs too (Camden's said "will be announced prior to operation"; Brunswick's said
   "Trains will make all stops").
4. **For a line that does add real stops**, and for each train that kept its R flag,
   compute `(anchor_stop, inserted_stop, minutes_after_anchor)` the same way the current
   table was built: find what the reference feed's `TrainNNNR` added versus its base
   trip, then check each candidate insertion against the **new** schedule's own base
   pattern — a station the old R-trip added might now already be a **regular** stop
   (drop it, like 2026-09-28's Train 892 gaining Washington Grove), or the new schedule
   might skip a station the old R-trip never had to touch (no direct precedent — borrow
   the delta another same-direction train uses at the same station pair, and say so in a
   comment, like Train 892's Boyds insertion borrowing from Train 872R).
5. **For a train with no R precedent in the reference feed at all** (like 2026-09-28's
   Train 873), estimate all of its insertions this way, and comment that they're
   estimates.
6. **Never add a stop that's on a different branch than the train's actual route** (e.g.
   Frederick/Monocacy are on a branch off the Brunswick mainline — a Brunswick mainline
   train's R-schedule can't detour onto it, no matter what a naive "all local stops" rule
   would suggest). If you're not sure whether a skipped station is on-route or on a
   branch, ask rather than guess.

Update the comments in `config.BRUNSWICK_R_EXTRA_STOPS` (or `config.CAMDEN_R_EXTRA_STOPS`,
if Camden ever needs one) to explain each entry's provenance the way the current ones do
— a future update needs to redo this same analysis, and it's much easier starting from
"here's why this number is what it is" than from bare numbers.

## 5. Re-tuning PDF extraction (only if the layout changed)

`pdf_extract.py` and `pdf_grid.py`'s docstrings explain the technique: these tables have
vertical rule lines (giving column boundaries) but no horizontal rule lines (row
boundaries come from clustering word y-positions instead). If MTA changes column counts,
page size, or the trifold layout, the hardcoded `x_min`/`x_max`/`y_header`/`y_data_end`
per table in `pdf_extract.py`'s `TABLES` (and `pdf_extract_brochure.py`'s) will need new
values. To find them for a table:

```python
import pdfplumber
pdf = pdfplumber.open("source-pdf/<the new pdf>")
page = pdf.pages[<page index>]
# vertical rule lines inside a rough region -> column boundaries
[round(l['x0'],1) for l in page.lines if X0<=l['x0']<=X1 and Y0<=l['top']<=Y1 and abs(l['x0']-l['x1'])<1]
# raw words with position, to find row y-values and spot decorative/footnote text to exclude
for w in page.extract_words(x_tolerance=1):
    if X0<=w['x0']<=X1 and Y0<=w['top']<=Y1: print(w['top'], w['x0'], w['text'])
```

Widen `(X0,X1,Y0,Y1)` and repeat until you've found the real table boundaries (see the
docstrings for what a healthy dump looks like). If a new footnote box overlaps a table
the way "*Train 871 operates Friday only" did, add its exact words to that table's
`drop_words` the same way; if a row is a note rather than a station (like the Thru
Service tables' "Direct service, does not serve Washington, DC" divider), add a matching
substring to `skip_label_substrings`.

## 6. Build, validate, and spot-check

```sh
make all
```

If `build_gtfs.py` raises:
- **`KeyError` from `station_stop_id`**: a printed station name has no entry in
  `config.STATION_NAME_TO_STOP_ID` — see §3.
- **`ValueError: could not resolve AM/PM`**: a train number has no reference-feed match
  and isn't in `NEW_TRAIN_PERIOD_OVERRIDE` — it's a brand new train (like 830/831 were);
  read its AM/PM off the source PDF by hand and add it to the override, with a comment.
- **`ValueError: time goes backwards`**: either a genuine AM/PM resolution bug, or (for
  the Brunswick R-mirrors) a bad delta in `BRUNSWICK_R_EXTRA_STOPS` — the inserted stop's
  computed time doesn't fall between its neighbors. Recheck the delta against §4.

Once it builds clean, spot-check `build/gtfs/stop_times.txt` for a handful of trips
against the rendered PDFs — the automated checks (unit tests, `make diff-sources`, the
Rust validator, the 830/831 cross-check in `build_gtfs.py`) catch structural problems, not
"the extraction quietly picked up the wrong number."

## 7. Update the docs

- `PLAN.md` §2 (symbol legend) and §3 (decisions) if anything about how a symbol or the R
  schedule works turned out to differ this time.
- `PLAN.md` §9 (future / not now) and this file, if the update surfaced a new recurring
  wrinkle worth remembering for next time.
- Anything in `README.md`'s "Known limitations" that this update resolved or changed.
