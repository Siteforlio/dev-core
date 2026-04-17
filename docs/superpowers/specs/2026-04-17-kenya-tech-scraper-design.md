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
1. Check title against non-tech reject signals first (fast O(1) exit):
   - Reject: `sales`, `marketing`, `accountant`, `recruiter`, `hr `, `human resources`, `legal`, `logistics`, `driver`, `cook`, `nurse`, `doctor`, `cleaner`
2. Check title against tech accept signals:
   - Engineering: `engineer`, `developer`, `architect`, `devops`, `sre`, `backend`, `frontend`, `fullstack`, `full-stack`, `full stack`, `mobile`, `ios`, `android`, `embedded`, `firmware`, `cloud`, `platform`
   - Data/AI: `data scientist`, `data analyst`, `data engineer`, `machine learning`, `ml engineer`, `ai engineer`
   - Product/Design: `product manager`, `ux`, `ui designer`, `product designer`
   - Security/IT: `security`, `cybersecurity`, `penetration`, `sysadmin`, `network engineer`, `it support`, `database admin`, `dba`
   - Adjacent: `technical lead`, `tech lead`, `engineering manager`, `cto`, `vp engineering`, `staff engineer`, `solutions engineer`, `developer advocate`, `technical writer`, `qa engineer`, `test engineer`
3. If title is ambiguous (no signal either way), check first 300 chars of description against tech accept signals.
4. Default: **pass** (let ambiguous jobs reach AI scorer — avoids false negatives).

### Call site in `scrape_campaign`:
```
passes_work_type_filter → _tech_role_prefilter → score_job_match
```
Jobs failing `_tech_role_prefilter` are counted in a `skipped_non_tech` counter and logged in the activity feed.

---

## 2. New Sources

### 2a. HTTP-based (added to `startup_scrapers.py`)

| Scraper | Source | Method |
|---------|--------|--------|
| `scrape_weworkremotely` | weworkremotely.com | RSS feed (XML parse, no auth) |
| `scrape_zindi` | zindi.africa | Public REST API (`/api/v1/competitions` + jobs endpoint) |
| `scrape_startupdeals_africa` | startupdeals.africa | HTTP + HTML parse (BeautifulSoup/regex) |

All three added to `scrape_all_startup_boards` gather call.

### 2b. Browser-based (new file `kenya_scrapers.py`)

Uses `httpx` first (attempt lightweight scrape); falls back to `BrowserService` (nodriver) if the page requires JS rendering.

| Scraper | Source | Notes |
|---------|--------|-------|
| `scrape_fuzu` | fuzu.com | SPA — needs nodriver |
| `scrape_brightermonday` | brightermonday.co.ke | SPA — needs nodriver |
| `scrape_myjobmag` | myjobmag.co.ke | May work with httpx |
| `scrape_kuhustle` | kuhustle.com | httpx sufficient |
| `scrape_andela` | andela.com/talent | nodriver |
| `scrape_arc` | arc.dev | nodriver |

Public entry point: `scrape_all_kenya_boards(search_term, publish_fn) -> list[dict]` — mirrors `scrape_all_startup_boards` signature exactly.

### 2c. Already covered (no changes needed)
- Deel → already in `LEVER_SLUGS` in `ats_scrapers.py`
- RemoteOK, Remotive, HN Who's Hiring → already in `startup_scrapers.py`

---

## 3. Integration into `scrape_campaign`

### First pass gather (currently):
```python
asyncio.gather(
    run_jobspy,
    scrape_all_ats,
    scrape_all_startup_boards,
    [linkedin if enabled],
)
```

### After this change:
```python
asyncio.gather(
    run_jobspy,
    scrape_all_ats,
    scrape_all_startup_boards,   # now includes WWR, Zindi, Startup Deals Africa
    scrape_all_kenya_boards,     # new
    [linkedin if enabled],
)
```

Kenya boards run on first pass only (same rationale as ATS — `ats_fetched` flag extended to `kenya_fetched`). Subsequent passes: jobspy + startup boards + LinkedIn only (Kenya boards are relatively static within a 24h window).

### Activity log additions
- `🇰🇪 Querying Kenya boards (Fuzu + BrighterMonday + MyJobMag + Kuhustle + Andela + Arc.dev)...`
- Per-board count: `↳ Fuzu: 23 | BrighterMonday: 41 | ...`
- Tech filter: `🔧 {n} jobs rejected by tech-role filter`

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
Surface startups and small companies first, without hard-blocking large corporations (which still count toward the 100/day target if nothing better is available).

### Implementation
New method `_smb_score(company: str) -> int` on `ScraperService`. Returns a boost value added to job priority ordering:

- **+2:** Company is from a startup-native source (`hn_hiring`, `remotive`, `remoteok`, `fuzu`, `brightermonday`, `myjobmag`, `kuhustle`, `startupdeals_africa`)
- **+1:** Company name not in a known large-corp blocklist (see below)
- **0:** Company name matches known large-corp signals

**Large-corp signal list** (name contains any of): `google`, `microsoft`, `amazon`, `meta`, `apple`, `ibm`, `oracle`, `sap`, `accenture`, `deloitte`, `pwc`, `kpmg`, `ernst`, `capgemini`, `infosys`, `wipro`, `tcs`, `cognizant`

**Sorting:** After filtering and AI scoring, jobs within the same score tier (`MATCH` vs `PARTIAL`) are sorted by SMB score descending before being saved/dispatched. Large corps are not removed — they just appear later in the queue and are applied to last if the 100-job target is already met by SMBs.

**Activity log:** `🏢 {n} large-corp jobs deprioritized in favor of SMBs`

---

## 6. What Does NOT Change

- No DB schema changes
- No Alembic migrations
- No API route changes
- No worker changes (`tailor_worker`, `apply_worker` unchanged)
- No frontend changes
- No changes to `score_job_match`, `save_listing`, `passes_work_type_filter`

---

## 7. Files Changed

| File | Change |
|------|--------|
| `backend/app/services/job_hunter/scraper_service.py` | Add `_tech_role_prefilter`, `_smb_score`, wire into loop, add `kenya_fetched` flag, add `scrape_all_kenya_boards` to gather |
| `backend/app/services/job_hunter/startup_scrapers.py` | Add `scrape_weworkremotely`, `scrape_zindi`, `scrape_startupdeals_africa` |
| `backend/app/services/job_hunter/kenya_scrapers.py` | New file — 6 scrapers + `scrape_all_kenya_boards` |
