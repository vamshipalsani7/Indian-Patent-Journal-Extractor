# V6 Implementation Plan — Patent Search, Discovery, Filtering & Analysis

**Status:** in progress — **Phase 1 implemented, tested and committed**
(`dataset.py`, `search_index.py`, `query_parser.py`, `search_engine.py`);
Phases 2–8 pending. Reconciled against the live Windows repo
`C:\Users\V\Desktop\Indian-Patent-Journal-Extractor`.
**Target release:** v6.0.0.
**Guiding rule:** v5.0.0 extraction engines are production code and stay
**untouched**. v6 is a *layer on top* that consumes their output.

---

## 1. Current architecture (v5.0.0 audit)

```
PDF(s) ──► Extraction backends ──► list[dict] records ──► excel_writer ──► .xlsx
                                         │
                          gui_v4.py orchestrates + names + popup
```

Extraction is a set of pure functions returning `list[dict]`. The GUI selects
files, calls one backend, writes Excel. There is **no persistent data model**
between extraction and Excel — records live only for the duration of a run.
That is the seam v6 plugs into: capture the `list[dict]` in memory instead of
letting it flow straight to Excel and disappear.

### Existing modules

| Module | Role | v6 classification |
|---|---|---|
| `patent_extractor.py` | Published extractor: `extract_patents(pdf, cb)` → records; `PatentExtractionError`; per-patent logging | **EXTRACTION — untouched** |
| `patterns.py` | Published INID regex dict | **EXTRACTION — untouched** |
| `grant_extractor.py` | Granted extractor: `extract_grants(pdfs, cb, cb)`; section detection, `find_tables`, FER exclusion, sort | **EXTRACTION — untouched** |
| `batch_extractor.py` | Published multi-file orchestrator: `extract_published(pdfs, cb, cb)`; date resolve, annotate, sort | **EXTRACTION — untouched** |
| `range_extractor.py` | Date-range + content date resolution helpers (used by batch) | **EXTRACTION — untouched** |
| `journal_utils.py` | `get_journal_metadata(pdf)` header issue/date | **EXTRACTION — untouched** |
| `journal_number.py` | `journal_number_range(pdfs)` for output naming | **REUSABLE (read-only)** |
| `cleaner.py` | `clean(text)` whitespace normaliser | **REUSABLE (generic)** |
| `excel_writer.py` | `save_to_excel(records, path)` — DataFrame → xlsx, **control-char sanitised** | **REUSABLE (generic)** — v6 export reuses it |
| `gui_v4.py` | v5 GUI: Published/Granted modes, multi-file picker, progress, structured error dialog, summary popup, journal-range naming | **GUI — minimal additive hook only** |
| `gui.py` | v3 legacy single-PDF GUI | untouched, unused by v6 |

### Existing Excel schemas (the data v6 must represent)

**Published** (18 cols, `batch_extractor`): `Application No, Filing Date,
Publication Date, Title, IPC, Priority Document No, Priority Date, Priority
Country, International Application No, International Publication No, Patent of
Addition, Divisional Application, Applicant, Inventor, Abstract, Page, Journal
Date, Source PDF`.

**Granted** (12 cols, `grant_extractor`): `Serial Number, Patent Number,
Application Number, Date of Application, Date of Priority, Title of Invention,
Name of Patentee, Date of Publication of Abstract u/s 11(A), Appropriate Office,
Journal Date, Source PDF, Page`.

`Journal Date`, `Source PDF`, `Page` are present in **both** schemas (identical
key names) — the natural join/provenance columns. **`Source PDF` currently
stores the basename only.**

### Critical schema reality (drives the whole design)

The two schemas name the same concepts **differently**, and some fields exist in
only one type. This is the single most important fact for v6:

| Concept | Published key | Granted key |
|---|---|---|
| Title | `Title` | `Title of Invention` |
| Applicant / owner | `Applicant` | `Name of Patentee` |
| Inventor | `Inventor` | *(absent)* |
| Application number | `Application No` | `Application Number` |
| Patent number | *(absent)* | `Patent Number` |
| IPC | `IPC` | *(absent)* |
| Abstract | `Abstract` | *(absent — grant table has only a "Date of Publication of Abstract")* |
| Filing date | `Filing Date` | `Date of Application` |
| Priority | `Priority Document No/Date/Country` | `Date of Priority` |
| Office | *(absent)* | `Appropriate Office` |
| **Claims** | *(absent)* | *(absent)* |

**Honest consequences, documented up front:**
- **Claims** are not in the v5 dataset at all. The v6 field model will *define*
  a `claims` field so the UI/index are future-ready, but it will be empty until
  extraction is extended (a future engine change, out of v6 scope). The Claims
  checkbox will be shown but marked "not available in current data".
- **Granted records have no IPC, Inventor, or Abstract.** IPC Explorer, Inventor
  Explorer, and Abstract search therefore cover **Published records only**. The
  UI must state this rather than silently returning nothing for grants.
- Field-specific search must **gracefully skip** fields a record type lacks.

---

## 2. Proposed v6 architecture

```
Extraction backends (unchanged) ─► list[dict]
                                      │
                         ┌────────────▼─────────────┐
                         │  dataset.py               │  normalise → canonical
                         │  PatentRecord / Dataset   │  fields + keep raw schema
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │  search_index.py          │  inverted index per field
                         └────────────┬─────────────┘
              ┌───────────────┬───────┴────────┬────────────────┐
              ▼               ▼                ▼                 ▼
      query_parser.py   search_engine.py   filters.py      facets.py
      (AST: AND/OR/     (exact/phrase/     (type,date,      (applicant/
       NOT/parens/      boolean + fuzzy    applicant,ipc,   inventor/ipc/
       phrase)          + related + rank)  number, source)  source counts)
              └───────────────┴───────┬────────┴────────────────┘
                                      ▼
                          search_ui.py (discovery window)
              results table · detail view · highlight · explorers ·
              analytics · export · saved searches · history · tags
                                      │
                         result_export.py ─► excel_writer (reused, sanitised)
```

**Design stance on the index/DB question (requirement 22):** an **in-memory
inverted index** (plain Python dicts: `field → token → set[record_id]`, plus the
normalised text per field for phrase/fuzzy). For tens of thousands of records
with a handful of short text fields this is fast (sub-100 ms queries) and needs
**zero new dependency**, stays fully offline, and has no temp-file lifecycle.
SQLite FTS5 (stdlib `sqlite3`, BM25) was evaluated and is **deferred**: it adds
DB lifecycle complexity for scale we don't yet need. The index lives behind a
small interface (`SearchIndex`) so FTS5 can drop in later without touching
callers. This is a documented future extension point, not v6.0 work.

### New modules (all additive; none import *into* the extraction engine)

| Module | Responsibility |
|---|---|
| `dataset.py` | `PatentRecord` (raw dict + canonical fields + stable id + full source path + patent_type) and `Dataset` (collection, build from extractor output, facet accessors). The unification layer. |
| `search_index.py` | Build/hold the inverted index; tokeniser (unicode-aware, lowercase, punctuation-split); vocabulary for fuzzy. |
| `query_parser.py` | Parse a query string into an AST: quoted phrases, `AND`/`OR`/`NOT`, parentheses, bare terms (default `AND`). Pure, unit-testable. |
| `search_engine.py` | Execute AST over the index for selected fields; add fuzzy + related expansion; produce ranked `SearchResult`s with per-field match reasons + heuristic relevance. |
| `thesaurus.py` + `thesaurus.json` | Curated, **editable** synonym/expansion map for related search (seeded: pesticide→insecticide/herbicide/fungicide/agrochemical/crop protection; electric vehicle→EV/BEV/electric car…). Offline, updatable. |
| `filters.py` | Combinable filter predicates (type, journal-date range, applicant, inventor, IPC, application/patent number partial, publication-date range, source PDF). |
| `facets.py` | Applicant/Inventor/IPC/Source counts + IPC hierarchy builder (parse `A61K 31/00` → A / A61 / A61K / A61K31), all **derived from data**, nothing hard-coded. |
| `categories.py` + `categories.json` | Rule-based technology classification (keyword→category, multi-label, editable). Analysis only; never writes IPC/official fields. |
| `annotations.py` | User tags/custom categories + "Important" stars, stored **separately** in a local JSON keyed by stable record id. Never mixed into extracted data. |
| `duplicates.py` | Detect likely duplicates (application number; patent number; application+title). Report only; never auto-delete. |
| `analytics.py` | Journal comparison (new/recurring applicants, IPC deltas, counts) + trends (counts by journal date, applicant/IPC activity, categories, granted vs published). |
| `charts.py` | Minimal dependency-free bar chart on a Tk `Canvas` (readable, lightweight). matplotlib remains a possible future upgrade, not v6.0. |
| `result_export.py` | Export a result subset to Excel via the reused sanitising `save_to_excel`, preserving each record's **original** schema; optional additive `Match`/`Relevance`/`Category` columns; optional clickable `Source PDF` hyperlink when the absolute local path is known. |
| `search_ui.py` | The discovery window (customtkinter + ttk.Treeview): search bar, field checkboxes, filter panel, results table, detail view w/ highlighting, explorers, analytics, export, saved searches, history, tags. |
| `store.py` | Tiny JSON persistence helper for saved searches, search history, annotations, and user thesaurus/category edits — all **local only**. |

### Modules that MUST remain untouched (regression-locked)

`patent_extractor.py`, `patterns.py`, `grant_extractor.py`, `batch_extractor.py`,
`range_extractor.py`, `journal_utils.py`, `journal_number.py`, `cleaner.py`,
`excel_writer.py`. The **only** edit to existing code is a small additive hook in
`gui_v4.py` (see §4). If any feature ever seems to require an extraction change,
stop and document why first (requirement 27).

---

## 3. Data flow & dataset representation

1. User picks Published or Granted + PDF file(s) and clicks **Extract** (v5 flow,
   unchanged) — still writes the Excel exactly as today.
2. **Additively**, the returned `list[dict]` is captured and loaded into a
   `Dataset`. The API (as implemented in Phase 1): `Dataset.from_records(records,
   patent_type, source_paths)` constructs a dataset from the first batch, and
   `dataset.add_records(records, patent_type, source_paths)` appends further
   batches (`from_records` is a thin convenience over `add_records`).
3. Each record becomes a `PatentRecord`:
   - `id`: stable, deterministic (e.g. `patent_type|application_number|patent_number|page`).
   - `raw`: the original dict (untouched — used for faithful export).
   - `type`: `"Published"` / `"Granted"`.
   - `canonical`: normalised view via the schema map in §1 — keys like
     `title, abstract, claims, applicant, inventor, ipc, application_number,
     patent_number, filing_date, priority, publication_date, journal_date,
     source_pdf, page, office`. Missing → empty string (never fabricated).
   - `source_path`: the **absolute** PDF path (from the selection), retained for
     "Open Source PDF" and Excel hyperlinks (the Excel `Source PDF` column keeps
     the basename for portability).
4. `Dataset` builds the `SearchIndex` once. Subsequent searches/filters hit the
   index — never re-scan raw cells (requirement 22).
5. Loading more PDFs (or another mode) **appends** to the same `Dataset` so mixed
   Published+Granted datasets are searchable together; `duplicates.py` flags
   accidental re-loads.

Export always writes from `raw` so the original schema is preserved and the
original dataset is never mutated (requirements 8, 13, 16, 17).

---

## 4. UI architecture & evolution

Keep the clean philosophy (requirement 26). The v5 window stays as the
**launcher/extractor**. One additive change: after a successful extraction,
records are held in memory and a **"Search / Explore"** button becomes enabled;
clicking it opens the new discovery window. Extraction-to-Excel is unchanged;
users who only want Excel never see the new surface.

Workflow: `Select PDFs → Extract (Load Dataset) → Search / Filter / Explore →
Select Results → Export`.

**Discovery window (`search_ui.py`)**, a single resizable `CTkToplevel`:
- **Top:** search bar + Search button; mode chips (Exact / Related / Fuzzy);
  field checkboxes (Title, Abstract, Claims*, Applicant, Inventor, IPC,
  Application No, Patent No, Priority) — greyed with a note where a field is
  absent for the loaded data.
- **Left:** filter panel (type, journal-date range, applicant/inventor/IPC/source
  multiselect w/ search, number partial) + explorer tabs (Applicant / Inventor /
  IPC tree) showing counts; clicking a facet adds a filter.
- **Center:** results table — `ttk.Treeview`, sortable/resizable columns,
  scrolling, selection: `Application/Patent No | Title | Applicant | IPC |
  Journal Date | Type | Match`. Compact by design (no giant fields).
- **Right/bottom:** detail view — a `CTk`/`tk.Text` pane showing the full record
  incl. long fields, with **keyword highlighting via Text tags**.
- **Tabs/buttons:** Analytics (charts), Export Results, Saved Searches, Recent
  Searches, Tags/Categories, Data Quality (expandable details), Duplicates review.

**Honest UI limitation (documented):** `ttk.Treeview` cannot colour substrings
inside a cell, so **rich substring highlighting lives in the detail pane** (Text
widget). In the results table, "why it matched" is conveyed by the **Match**
column (e.g. `Exact — Title`) and matched rows can be tagged/emphasised. This is
a real tkinter constraint, chosen over a heavier UI toolkit to preserve the
lightweight single-exe app.

---

## 5. Search architecture (details)

- **Tokenisation:** unicode-aware, casefold, split on non-alphanumerics; keep
  IPC/number tokens intact (e.g. `H01M`, `202317012934`).
- **Exact:** token lookup in the inverted index for selected fields.
- **Phrase (`"..."`):** candidate set from token index ∩, then verify contiguous
  sequence against the field's normalised text.
- **Boolean:** `query_parser` → AST (`AND`/`OR`/`NOT`, parentheses, default
  `AND`); `search_engine` evaluates set operations over posting lists.
- **Fuzzy:** only for terms with no exact hit; match against index vocabulary
  with a bounded edit distance (`difflib.SequenceMatcher`/Levenshtein, ratio ≥
  ~0.8, min length 4, max edits 1–2) to avoid nonsense. Labeled **Fuzzy**.
- **Related/semantic:** expand query terms via `thesaurus.json` (+ light
  stemming). Expanded hits labeled **Related**, never **Exact**. Fully offline,
  editable, extensible; explicitly a curated thesaurus, **not** ML embeddings —
  a local-embedding option is a future extension point (requirements 2, 23).
- **Match reason & relevance:** each result carries per-field reasons
  (`Exact — Title`, `Related — Abstract`, `Fuzzy — Applicant`). Relevance is a
  **heuristic** integer % from field weights (title > abstract > applicant > …)
  × match-type weight (exact 1.0 / related 0.7 / fuzzy 0.5), shown as whole
  numbers (e.g. `92%`), documented as heuristic (requirement 14).

---

## 6. Backward-compatibility & v5 protection

- Extraction modules imported read-only; **not edited**. Their public
  signatures/returns are the v6 contract.
- `gui_v4.py` change is **purely additive** (one button + one in-memory capture +
  launch of `search_ui`), behind the existing successful-extraction path; the
  Excel output, naming, popup, progress, error dialog, sanitisation, sort, FER
  exclusion, and multi-PDF behaviour are unchanged.
- Export reuses `excel_writer.save_to_excel` — same sanitisation guarantees.
- A **regression test set** (see §8) pins v5 behaviour and runs before each commit.
- Git tag `v5.0.0` is created **before** any v6 code, enabling clean rollback.

---

## 7. Risks

1. **Schema asymmetry / missing fields** (grants: no IPC/inventor/abstract;
   neither has claims). *Mitigation:* canonical model with empty-safe fields; UI
   states coverage; never fabricate. **Highest-impact risk — handled in the core
   design.**
2. **tkinter results-table highlighting** limits. *Mitigation:* rich highlight in
   detail pane + Match column in table; documented.
3. **Performance at scale.** *Mitigation:* in-memory inverted index, build-once;
   benchmark on a synthetic 50k dataset; FTS5 interface reserved.
4. **Semantic expectations.** *Mitigation:* label Related vs Exact; document
   thesaurus approach; keep offline.
5. **Excel hyperlink portability.** *Mitigation:* link only when absolute local
   path known; always retain filename + page; never break portability.
6. **PDF page navigation unreliable** across viewers. *Mitigation:* best-effort
   `#page=N`, fallback to plain open; documented (requirement 11).
7. **Scope creep** (30 features). *Mitigation:* strict phased roadmap §9;
   implement→test→verify→commit per phase.

---

## 8. Testing strategy

**v5 regression (must stay green, every phase):** Published single/multi/mixed
order, Granted single/multi, **FER never appears** in grant output, journal-date
detection, chronological sort, Excel generation + sanitisation, Source PDF, Page,
error handling. Anchored on known counts (e.g. ViewJournal 7 → 2187 published;
ViewJournal 1–4 → 3129 granted).

**v6 unit/integration (headless where possible):**
- `query_parser`: exact, phrase, `AND/OR/NOT`, parentheses, precedence, malformed.
- `search_engine`: field-specific scoping; fuzzy thresholds (finds `vehcle→
  vehicle`, rejects nonsense); related expansion labeled correctly; relevance
  monotonicity.
- `filters`: each filter + combined (keyword+applicant+IPC+date) as in requirement 5.
- `facets`/IPC hierarchy from data; counts correct.
- `duplicates`: double-loaded journal flagged, none deleted.
- `result_export`: subset only; original schema preserved; unicode + injected
  control chars survive/strip via `excel_writer`; original dataset unmutated.
- `annotations`/saved searches/history: JSON round-trip, isolation from raw data.
- **Scale:** synthetic 50k records → index build + query latency budget.

**UI (manual on Windows):** search/filter/highlight/detail/export/explorers/
analytics/tags; both modes; offline.

---

## 9. Rollback strategy

- Tag `v5.0.0` before starting; each phase is its own commit.
- v6 is additive files + one additive `gui_v4.py` hook. Rollback = revert that
  hook and delete v6 modules → byte-identical v5 behaviour. Extraction engine is
  never touched, so no extraction rollback is ever needed.
- Per-phase commits mean any single feature can be reverted without unwinding the
  rest.

---

## 10. Phased roadmap (implement → test → verify → commit each)

- **Phase 0** — tag `v5.0.0`; add regression harness. *(tag pending on Windows)*
- **Phase 1 — Core (headless): ✅ DONE.** `dataset.py`, `search_index.py`,
  `query_parser.py`, `search_engine.py` (exact/phrase/boolean + field-specific).
  Verified on 5,316 real records; committed.
- **Phase 2 — Filter/facets (headless):** `filters.py`, `facets.py` (+IPC tree),
  `duplicates.py`, data-quality stats.
- **Phase 3 — Ranking (headless):** fuzzy, `thesaurus.py`+json related search,
  match-reason + relevance.
- **Phase 4 — Discovery UI:** `search_ui.py` (search bar, field checks, filter
  panel, results table, detail view + highlighting) + additive `gui_v4.py` hook.
- **Phase 5 — Output:** `result_export.py`, Excel hyperlinks, source-PDF open.
- **Phase 6 — Personalisation:** `categories.py`+json, `annotations.py` (tags),
  saved searches, history (`store.py`).
- **Phase 7 — Analytics:** `analytics.py` (compare + trends) + `charts.py`.
- **Phase 8 — Docs/packaging:** README, `CHANGELOG.md`, `RELEASE_NOTES_v6.0.0.md`;
  PyInstaller spec picks up new pure-Python modules automatically (verify);
  full regression + manual pass.

**Future extension points (designed-for, not built):** SQLite FTS5 index;
local-embedding semantic search; Claims extraction; prior-art / family / citation
/ competitor / landscape / heatmap / alerting — all consume the `Dataset`/`Search`
interfaces without touching extraction.

---

## Open questions for you before Phase 1

1. **Dataset persistence:** keep the loaded dataset **in-memory per session**
   (simplest; re-extract to search again), or also **cache to a local file** so a
   dataset can be reopened without re-extracting? (Recommend in-memory for v6.0,
   file cache as a fast-follow.)
2. **Charts dependency:** dependency-free Tk-`Canvas` bar charts (keeps single-exe
   lean) vs adding **matplotlib** (nicer charts, bigger exe)? (Recommend Canvas.)
3. **Semantic depth for v6.0:** curated editable **thesaurus** only (fast, offline,
   predictable) vs also bundling a small **local word-embedding** model (better
   recall, ~tens of MB, larger exe)? (Recommend thesaurus for v6.0; embeddings as
   documented future option.)
