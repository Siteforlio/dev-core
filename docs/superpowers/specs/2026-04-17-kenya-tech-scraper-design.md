# Kenya Tech Scraper — Design Spec
**Date:** 2026-04-17
**Status:** Approved

## Overview

Extend the Job Hunter scraper to (a) filter results to tech roles only, (b) add all missing job boards — including Kenya-specific boards — to reliably hit 100+ matched tech jobs per day, and (c) prefer SMB/startup companies over large corporations.

---

## 1. Tech-Role Pre-filter

### Goal
Drop non-tech jobs (sales, HR, marketing, finance, etc.) before they reach Claude Haiku scoring, reducing cost and noise.

### Implementation
New method `_tech_role_prefilter(title: str, description: str) -> bool` on `ScraperService`.

**Logic:**
1. Lowercase the title. Check against non-tech reject signals (fast exit, returns `False`):
   - Reject signals: `sales`, `marketing`, `accountant`, `recruiter`, `hr `, `human resources`, `legal`, `logistics`, `driver`, `cook`, `nurse`, `doctor`, `cleaner`
2. Check lowercased title against tech accept signals (returns `True`):
   - Engineering: `engineer`, `developer`, `architect`, `devops`, `sre`, `backend`, `frontend`, `fullstack`, `full-stack`, `full stack`, `mobile`, `ios`, `android`, `embedded`, `firmware`, `cloud`, `platform`
   - Data/AI: `data scientist`, `data analyst`, `data engineer`, `machine learning`, `ml engineer`, `ai engineer`
   - Product/Design: `product manager`, `ux`, `ui designer`, `product designer`
   - Security/IT: `security`, `cybersecurity`, `penetration`, `sysadmin`, `network engineer`, `it support`, `database admin`, `dba`
   - Adjacent: `technical lead`, `tech lead`, `engineering manager`, `cto`, `vp engineering`, `staff engineer`, `solutions engineer`, `developer advocate`, `technical writer`, `qa engineer`, `test engineer`
3. If title is ambiguous (no reject or accept signal matched): strip HTML tags from `description` using `re.sub(r'<[^>]+>', ' ', description)`, then take the first 300 characters of the **post-strip** lowercased text and check against tech accept signals only (not reject signals — intentionally permissive). Returns `True` if any accept signal found.
4. Default: **return `True`** — ambiguous jobs pass through to the AI scorer. This is intentional: better to let Haiku reject a borderline case than silently drop a real tech job.

### `skipped_non_tech` counter
A new `skipped_non_tech: int = 0` counter is initialized alongside `skipped_location`, `skipped_duplicate`, and `matches_found` at the start of `scrape_campaign`. It increments for each job rejected by `_tech_role_prefilter`. The mid-pass log `🔧 {n} jobs rejected by tech-role filter` is emitted **after the full batch-collection step completes** (before AI scoring). It is also included in the final summary line.

### Call site
```
passes_work_type_filter → _tech_role_prefilter → (batch collect) → score_job_match
```

---

## 2. New Sources

### 2a. HTTP-based (added to `startup_scrapers.py`)

| Scraper | Source field value | Source | Method |
|---------|-------------------|--------|--------|
| `scrape_weworkremotely` | `"weworkremotely"` | weworkremotely.com | RSS feed (XML parse, no auth) |
| `scrape_zindi` | `"zindi"` | zindi.africa | Public REST API |
| `scrape_startupdeals_africa` | `"startupdeals_africa"` | startupdeals.africa | HTTP + HTML parse |

All three added to `scrape_all_startup_boards` gather call.

### 2b. Browser-based (new file `kenya_scrapers.py`)

Attempt `httpx` first; fall back to `BrowserService` (nodriver) if JS rendering is required. Each scraper function catches its own exceptions and returns `[]` on failure — matching the existing `scrape_greenhouse`, `scrape_lever`, `scrape_ashby` pattern. Failed boards appear in the per-board count line as `0` (not omitted), e.g. `↳ Fuzu: 0 | BrighterMonday: 41 | ...`.

| Scraper | Source field value | Source | Notes |
|---------|-------------------|--------|-------|
| `scrape_fuzu` | `"fuzu"` | fuzu.com | SPA — needs nodriver |
| `scrape_brightermonday` | `"brightermonday"` | brightermonday.co.ke | SPA — needs nodriver |
| `scrape_myjobmag` | `"myjobmag"` | myjobmag.co.ke | May work with httpx |
| `scrape_kuhustle` | `"kuhustle"` | kuhustle.com | httpx sufficient |
| `scrape_andela` | `"andela"` | andela.com/talent | nodriver |
| `scrape_arc` | `"arc"` | arc.dev | nodriver |

All source field values are lowercase strings. Public entry point: `scrape_all_kenya_boards(search_term, publish_fn) -> list[dict]` — mirrors `scrape_all_startup_boards` signature exactly.

### 2c. Already covered (no changes needed)
- Deel → already in `LEVER_SLUGS` in `ats_scrapers.py`
- RemoteOK (`"remoteok"`), Remotive (`"remotive"`), HN Who's Hiring (`"hn_hiring"`) → already in `startup_scrapers.py`

---

## 3. Integration into `scrape_campaign`

### First-pass gather — updated coroutine list and result indices

```python
results = await asyncio.gather(
    run_jobspy(...),            # results[0]
    scrape_all_ats(...),        # results[1]
    scrape_all_startup_boards(...),  # results[2]  ← now includes WWR, Zindi, Startup Deals Africa
    scrape_all_kenya_boards(...),    # results[3]  ← NEW
    linkedin_coro,              # results[4]  ← was results[3]; only present when linkedin_creds set
    return_exceptions=True,
)
jobspy_jobs   = results[0] if not isinstance(results[0], Exception) else []
ats_jobs      = results[1] if not isinstance(results[1], Exception) else []
startup_jobs  = results[2] if not isinstance(results[2], Exception) else []
kenya_jobs    = results[3] if not isinstance(results[3], Exception) else []
li_jobs       = results[4] if len(results) > 4 and not isinstance(results[4], Exception) else []
```

The existing LinkedIn error-handling guard changes from `len(results) > 3` to `len(results) > 4`.

### Subsequent-pass gather (after first pass)

The `else` branch (subsequent passes) includes: jobspy + startup boards + LinkedIn. It does **not** include `scrape_all_ats` (guarded by `ats_fetched`) and does **not** include `scrape_all_kenya_boards` (guarded by `kenya_fetched`). Kenya boards are one-time-only per campaign run — their listings don't change within a 24h window.

### `kenya_fetched` flag

A new `kenya_fetched: bool = False` is introduced alongside `ats_fetched`. Its placement and failure behavior differ from `ats_fetched`:

- `ats_fetched = True` is set after the first-pass gather block completes (current code line 444), regardless of whether the fallback path ran.
- `kenya_fetched = True` is set **only when the first-pass gather succeeds** (i.e., inside the `try` block, after `scrape_all_kenya_boards` results are extracted). If the outer gather raises and the fallback runs, `kenya_fetched` remains `False` so Kenya boards are retried on the next pass.

### Failure modes

Two distinct scenarios:

1. **Individual board failure** (scraper raises inside `scrape_all_kenya_boards`): handled internally — scraper returns `[]`, count logged as `0`. `kenya_fetched` is still set to `True` (the gather itself succeeded). No retry.
2. **Full gather failure** (outer `asyncio.gather` raises, fallback fires): Kenya boards excluded from fallback — same as ATS. `kenya_fetched` remains `False`; Kenya boards included in the next pass's gather.

### Activity log additions
- `🇰🇪 Querying Kenya boards (Fuzu + BrighterMonday + MyJobMag + Kuhustle + Andela + Arc.dev)...`
- Per-board count: `↳ Fuzu: 23 | BrighterMonday: 41 | MyJobMag: 0 | ...` (failed boards shown as 0)
- Mid-pass tech filter (after batch-collection, before scoring): `🔧 {n} jobs rejected by tech-role filter`
- Final summary line extended to: `✔ Done — {matches} matches | {partial} partial, {skip} skipped | {loc} filtered by location | {non_tech} filtered non-tech | {dup} duplicates`

---

## 4. Volume Estimate

| Source | Raw jobs/pass |
|--------|--------------|
| jobspy (4 boards) | 200–400 |
| ATS (~200 companies) | 500–1000 |
| Startup boards (existing + 3 new) | 200–400 |
| Kenya boards (6 new) | 100–300 |
| LinkedIn (optional) | ~150 |
| **Total** | **~1150–2250** |

After tech-role pre-filter (~40% rejection rate for mixed boards) and AI scoring: **100–200 MATCH jobs per day**. Target of 100/day is comfortably met.

---

## 5. SMB Preference

### Goal
Surface startups and small companies first, without hard-blocking large corporations.

### `_smb_score(job: dict) -> int`

New method on `ScraperService`. Rules are additive (max score = 3):

- **+2:** `job["source"]` (exact lowercase match) is in startup-native set:
  `{"hn_hiring", "remotive", "remoteok", "weworkremotely", "zindi", "startupdeals_africa", "fuzu", "brightermonday", "myjobmag", "kuhustle", "andela", "arc"}`
- **+1:** `job["company"]` is non-empty AND its lowercase form does NOT contain any large-corp signal.
- **+0:** `job["company"]` is empty/missing, OR its lowercase form contains a large-corp signal.

**Large-corp signal list** (case-insensitive substring): `google`, `microsoft`, `amazon`, `meta`, `apple`, `ibm`, `oracle`, `sap`, `accenture`, `deloitte`, `pwc`, `kpmg`, `ernst`, `capgemini`, `infosys`, `wipro`, `tcs`, `cognizant`

Example scores:
- Fuzu job, unknown startup → +2 + 1 = **3**
- Greenhouse job, unknown startup → +0 + 1 = **1**
- Greenhouse job, Google → +0 + 0 = **0**
- HN Hiring job, "HN Startup" → +2 + 1 = **3**

### `_SCORE_ORDER` constant

Module-level dict (not class attribute):
```python
_SCORE_ORDER = {"MATCH": 0, "PARTIAL": 1, "SKIP": 2}
```

### Loop restructure

The current `for job in raw_jobs` loop is replaced per pass with:

1. **Batch-filter:** Iterate `raw_jobs`. For each job run `passes_work_type_filter` then `_tech_role_prefilter`. Jobs passing both accumulate in `filtered: list[dict]`. Increment `skipped_location` or `skipped_non_tech` accordingly. Emit `🔧 {n} jobs rejected by tech-role filter` after this step.

2. **Batch-score:** For each job in `filtered`, call `await score_job_match(...)` sequentially (no concurrency change) and attach result: `job["_score"] = score`. **Early exit during scoring:** if `matches_found >= target` before scoring a job, skip the remaining AI calls and break — no point scoring jobs that won't be dispatched.

3. **Sort:** `filtered.sort(key=lambda j: (_SCORE_ORDER[j["_score"]], -_smb_score(j)))`

4. **Dispatch:** Iterate sorted `filtered`:
   - Call `listing = await save_listing(..., job, job["_score"])`
   - If `listing` is not None and `job["_score"] == "MATCH"`: increment `matches_found`, dispatch Celery task
   - If `listing` is None and `job["_score"] == "MATCH"`: increment `skipped_duplicate` (duplicate detected — same logic as current code)
   - Check `matches_found >= target`: break if met

5. **Log:** Count jobs where `job["company"]` is non-empty and its lowercase contains a large-corp signal. Emit `🏢 {n} large-corp jobs deprioritized`.

The `job["_score"]` key is temporary — it is never passed to `save_listing` as part of the dict. `save_listing` receives `score` as a separate positional argument (unchanged interface).

---

## 6. What Does NOT Change

- No DB schema changes
- No Alembic migrations
- No API route changes
- No worker changes (`tailor_worker`, `apply_worker` unchanged)
- No frontend changes
- No changes to `score_job_match`, `save_listing`, `passes_work_type_filter`
- `skipped_location`, `skipped_duplicate`, `matches_found`, `match_counts` counter semantics unchanged; `skipped_non_tech` is the only new counter

---

## 7. Files Changed

| File | Change |
|------|--------|
| `backend/app/services/job_hunter/scraper_service.py` | Add `_tech_role_prefilter`, `_smb_score`, `_SCORE_ORDER`; restructure per-pass loop (batch filter → score → sort → dispatch); add `kenya_fetched` flag; update first-pass result indices; add `scrape_all_kenya_boards` to first-pass gather and exclude from subsequent-pass gather; extend final summary log; add `skipped_non_tech` counter |
| `backend/app/services/job_hunter/startup_scrapers.py` | Add `scrape_weworkremotely`, `scrape_zindi`, `scrape_startupdeals_africa`; wire into `scrape_all_startup_boards` |
| `backend/app/services/job_hunter/kenya_scrapers.py` | New file — 6 scrapers + `scrape_all_kenya_boards` |
