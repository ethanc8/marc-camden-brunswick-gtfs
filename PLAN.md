# MARC Camden & Brunswick Line GTFS — Build Plan

Status: **planning, not yet implemented**. This file is the living plan; update it as decisions
change instead of re-litigating them in chat.

## 1. What we're building

A GTFS feed for the MARC **Camden Line** and **Brunswick Line**, weekday-only, covering the
service change effective 2026-09-28 (new Brunswick↔Camden through-running trains 830/831),
sourced from the PDFs in `source-pdf/`.

## 2. Source data findings

Four PDFs, forming two pairs (one per line). Both members of a pair should contain the same
schedule — we extract both and diff them, and surface any mismatch rather than silently picking one.

| File | Role |
|---|---|
| `marc_{camden,brunswick}-washington_Sept28.pdf` | Rider trifold brochure: timetable + connecting-bus info + system map + code of conduct. |
| `{Camden,Brunswick} Line Sept 28 Changes.pdf` | Page 1: prose description of what changed vs. the prior schedule. **Page 2: a second, cleanly-gridded full timetable** + a "Thru Service" table + the clearest symbol legend. |

Plan: extract the timetable grid from **page 2 of the "Changes" PDF** for each line (cleanest
layout), and separately extract the brochure's timetable panel as a cross-check. Report any
numeric discrepancy found between the two.

Also present: `source-pdf/mdotmta_gtfs_marc/` — a full GTFS export of the *current* (pre-9/28)
MARC feed, provided by the user as a source for data the new PDFs don't contain (station
coordinates, wheelchair boarding, agency info). Verified that **every station name in the new
Camden/Brunswick timetables already exists in this old feed** (e.g. "RIVERDALE" →
"Riverdale Park Town Center", "CAMDEN STATION" → "Baltimore/Camden Station") — no new stations
were added in this service change, so no geocoding is needed.

### Symbol legend (confirmed from both lines' "Key to symbols" boxes)

| Symbol | Meaning | GTFS mapping |
|---|---|---|
| plain `H:MM` | regular stop | `pickup_type=0, drop_off_type=0` |
| `f` prefix (e.g. `f5:09`) | flag stop — passengers must be visible on platform; train may leave up to 5 min early | `pickup_type=3` (coordinate with driver), `timepoint=0` |
| `d` prefix (e.g. `d2:16`) | discharge only | `pickup_type=1` (no pickup), `drop_off_type=0` |
| `L` prefix (e.g. `L5:38`) | train may depart up to 5 min early | regular pickup/drop-off, `timepoint=0` |
| `—` (em dash) | train never stops here | no `stop_times` row for this trip |
| `R` (as a cell value, not a time) | stop is made *only* if the R (severe-weather/holiday) contingency schedule is in effect | no `stop_times` row on the regular trip; see §4 |
| `R`/`Q`/`Q/R` under train number | `Q` = train has a quiet car (cosmetic, ignored); `R` = this train is one of the trains that keeps running under the R contingency schedule | drives which trips get an `r_schedule` mirror, see §4 |
| `M` / wheelchair icon next to station name | Metrorail transfer / station accessibility | wheelchair icon → `wheelchair_boarding` in stops; `M` is informational only, not modeled |

## 3. Decisions made (with you)

- **Routes** (`routes.txt`):

  | route_id | short_name | long_name | route_color | route_text_color |
  |---|---|---|---|---|
  | `camden` | Camden | MARC Camden Line | `EF5B2A` | `FFFFFF` |
  | `brunswick` | Brunswick | MARC Brunswick Line | `EFAC1F` | `000000` |
  | `brunswick-camden` | Brunswick-Camden | MARC Brunswick-Camden Through Service | `2F3238` | `FFFFFF` |

  Trains 830 (AM, Brunswick→Camden) and 831 (PM, Camden→Brunswick) bypass Washington Union
  Station and appear on *both* lines' printed tables as the same train number — each is **one
  continuous trip** on route `brunswick-camden` spanning both lines' stops, not two trips.

- **Stop coordinates / accessibility**: reuse from `source-pdf/mdotmta_gtfs_marc/stops.txt`
  (never edit that file — it's a raw source). The subset of stops we use gets **copied** into
  `reference/stops.csv` (new directory, not under `source-pdf/`), renamed to current station
  names, so it can be hand-edited independently of the original download.

- **shapes.txt**: skipped for now. May integrate `pfaedle-rs` later to derive shapes from real
  track geometry — **not now** (see §6).

- **R (contingency) schedule**: `calendar.txt` gets a second service_id, `r_schedule`, with all
  seven days set to `0` (so it never runs on its own) but a valid date range — inert until the
  user adds `calendar_dates.txt` exceptions. Every train flagged `R` under its train number gets
  a **mirrored trip** under `r_schedule`, id suffixed `R` (matching the old feed's own
  `TrainNNNR` convention), reusing the train's normal stop pattern. This is a known
  simplification: the brochures say the *actual* extra stops made under the R schedule are
  announced day-of and aren't published. Revisit using the old feed's `*R` trips as a reference
  for what real extra stops look like — **not now**.

## 4. Calendar design

```
calendar.txt
  weekday:    Mon-Fri=1, Sat/Sun=0, 2026-09-28..2026-11-01
  r_schedule: all days=0,            2026-09-28..2026-11-01   (inert by default)

calendar_dates.txt
  header only, no rows initially.
  (documented example in README: add exception_type=1 for r_schedule + exception_type=2
   for weekday on a given date to simulate an R-schedule day)
```

Columbus Day (2026-10-12, a Monday) falls inside our 9/28–11/1 window, and the brochures' fine
print mentions MARC runs a *modified* schedule on Columbus Day (among other federal holidays),
published 30 days ahead of time. As of this writing that modified schedule has not been published
yet. **Decision: treat 2026-10-12 as a regular weekday service day** (no exception). See §9 —
the user will need to email MARC once the modified-schedule info would normally have been posted.

## 5. Repository layout (proposed)

```
source-pdf/                  # raw inputs — never modified
  *.pdf
  mdotmta_gtfs_marc/          # old feed, as downloaded — never modified

reference/                    # data copied/derived from source-pdf and then hand-maintained
  stops.csv                   # trimmed + renamed subset of the old feed's stops.txt
  agency.csv                  # agency.txt template (reused from old feed)

extracted/                    # timetable data pulled from the PDFs, hand-verified against
                               # the rendered page images before being treated as truth
  camden_eastbound.csv
  camden_westbound.csv
  brunswick_eastbound.csv
  brunswick_westbound.csv
  through_service.csv         # trains 830/831 combined stop pattern
  brochure_cross_check/       # same tables re-extracted from the trifold brochures, for diffing

gtfs_builder/                  # Python package (pixi env)
  pdf_extract.py               # pdfplumber-based draft extraction (produces extracted/ drafts)
  diff_sources.py              # compares brochure vs. changes-doc extraction, reports mismatches
  build_gtfs.py                # extracted/ + reference/ + config -> build/gtfs/*.txt + zip
  config.py                    # route table, calendar dates, symbol->pickup/dropoff mapping

validator/                     # Rust crate (cargo), optional sanity check
  src/main.rs                  # loads build output with `gtfs-structures`, checks referential
                                # integrity (every stop_id/route_id/service_id resolves, etc.)

build/                         # generated output (gitignored)
  gtfs/*.txt
  marc-camden-brunswick-gtfs.zip

pixi.toml / pixi.lock          # Python + pdfplumber + pytest, from conda-forge
Cargo.toml                     # validator crate, gtfs-structures via cargo
Makefile                       # render-pdfs, extract-draft, build, validate, all
PLAN.md                        # this file
README.md                      # short usage doc
```

## 6. Pipeline (Makefile targets)

- `make render-pdfs` — render each PDF page to PNG at 150dpi into `build/pdf-preview/`, for
  visual review while authoring/checking `extracted/*.csv`.
- `make extract-draft` — run `pdf_extract.py` to (re)generate draft CSVs from the PDFs. Writes to
  `extracted/*.draft.csv`, never overwrites the reviewed `extracted/*.csv` directly, so manual
  corrections aren't silently clobbered.
- `make diff-sources` — run `diff_sources.py` comparing the two PDFs per line; prints any
  discrepancy.
- `make build` — run `build_gtfs.py`: `extracted/` + `reference/` + `gtfs_builder/config.py` →
  `build/gtfs/*.txt` → zip.
- `make validate` — build the Rust validator crate and run it against `build/*.zip`.
- `make all` — the above in order.

## 7. Defaults I'm assuming unless told otherwise

- `agency_id`/`agency_name`/etc. copied as-is from the old feed (`30034`,
  `Maryland Transit Administration`) for continuity with any consumer that already expects that
  agency_id.
- `trip_id` convention mirrors the old feed: `TrainNNN` (e.g. `Train846`), R-mirror trips as
  `Train846R`.
- `wheelchair_accessible=1` and `bikes_allowed=1` on every trip (brochures state all MARC trains
  have full-size bike access; old feed sets these uniformly too).
- No `fares.txt` / zone data — out of scope.

## 8. TODO

- [ ] Build `reference/stops.csv` from the old feed (trim to Camden/Brunswick/WUS stations, rename
      per current signage, keep `wheelchair_boarding`).
- [ ] Build `reference/agency.csv`.
- [ ] Write `pdf_extract.py` (pdfplumber word-position clustering) and produce draft CSVs for all
      4 timetable tables + the through-service table, from the "Changes" PDF page 2 of each line.
- [ ] Manually verify every drafted cell against the rendered PNG images.
- [ ] Re-extract the same tables from the brochure PDFs and diff; report discrepancies.
- [ ] Encode the symbol → pickup/drop-off/timepoint mapping from §2 in `config.py`.
- [ ] Write `build_gtfs.py` (agency/routes/calendar/calendar_dates/stops/trips/stop_times/feed_info).
- [ ] Write the Rust `validator` crate using `gtfs-structures`.
- [ ] Write `Makefile`, `pixi.toml`, `Cargo.toml`.
- [ ] Run `make all`, review output, fix issues.
- [ ] Write short `README.md`.

## 9. Future / not now

- Integrate `pfaedle-rs` to generate real-track-aligned `shapes.txt`.
- Look at the old feed's actual `TrainNNNR` stop patterns to model real R-schedule additional
  stops instead of mirroring the regular pattern.
- MARC Penn Line (out of scope — this repo is Camden + Brunswick only).
- Saturday/Sunday and other non-weekday calendars (out of scope per requirements).
- Fare data (`fares.txt`/`fare_products.txt`).
- Holiday-specific `calendar_dates.txt` exceptions beyond the R-schedule placeholder (e.g. actual
  federal-holiday modified schedules), if wanted later.
- **Columbus Day 2026-10-12**: MARC's brochures promise a modified schedule published 30 days
  ahead; as of this build that info was not yet published, so we assumed a regular weekday. The
  user needs to email MARC (marc@mdot.maryland.gov) once that modified schedule should be out,
  and we should add a `calendar_dates.txt` exception if it turns out to differ.
