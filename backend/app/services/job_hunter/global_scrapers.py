# backend/app/services/job_hunter/global_scrapers.py
"""
Global job board scrapers for broad continental coverage.
All boards are public and free to use; some require a free API key.

Boards:
  - The Muse:    global tech companies, no auth required
  - Jobicy:      global remote, no auth required
  - Himalayas:   global remote, no auth required
  - GetOnBoard:  LATAM tech jobs, no auth required
  - Adzuna:      20+ countries (requires ADZUNA_APP_ID + ADZUNA_API_KEY, free tier)
  - Reed:        UK / EU (requires REED_API_KEY, free tier)

Countries covered by Adzuna:
  NA:   us, ca
  EU:   gb, de, fr, it, es, nl, pl, se, at, be
  LATAM: br
  AsiaPac: au, sg, in
  Africa: za
"""
from __future__ import annotations

import asyncio
import base64
import os
import re
import httpx

_HTTP_TIMEOUT = 15.0

# Adzuna country codes — one API call per country, all in parallel
_ADZUNA_COUNTRIES = [
    "us", "ca",            # North America
    "gb", "de", "fr",      # EU core
    "it", "es", "nl",
    "pl", "se", "at",
    "br",                  # Latin America
    "au",                  # Oceania
    "za",                  # Africa
    "sg", "in",            # Asia
]


def _normalize(job: dict) -> dict:
    return {
        "source":           job.get("source", "global"),
        "title":            (job.get("title") or "").strip(),
        "company":          (job.get("company") or "").strip(),
        "location":         job.get("location"),
        "location_country": job.get("location_country"),
        "remote":           job.get("remote", False),
        "url":              job.get("url", ""),
        "apply_url":        job.get("apply_url") or job.get("url", ""),
        "description":      (job.get("description") or "")[:10000],
    }


# ── The Muse ──────────────────────────────────────────────────────────────────

async def scrape_the_muse(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    The Muse public API — no auth required.
    Returns up to 100 listings from global tech companies.
    Docs: https://www.themuse.com/developers/api/v2
    """
    try:
        r = await client.get(
            "https://www.themuse.com/api/public/jobs",
            params={"page": 0, "descending": "true"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for j in (r.json().get("results") or [])[:100]:
            company   = (j.get("company") or {}).get("name", "")
            locations = j.get("locations") or []
            location  = locations[0].get("name") if locations else "Remote"
            is_remote = any("remote" in (loc.get("name") or "").lower() for loc in locations)
            levels    = " | ".join(l.get("name", "") for l in (j.get("levels") or []))
            cats      = " | ".join(c.get("name", "") for c in (j.get("categories") or []))
            job_url   = (j.get("refs") or {}).get("landing_page", "")
            jobs.append(_normalize({
                "source":   "the_muse",
                "title":    j.get("name", ""),
                "company":  company,
                "location": location,
                "remote":   is_remote,
                "url":      job_url,
                "apply_url": job_url,
                "description": f"Level: {levels} | Categories: {cats}",
            }))
        return jobs
    except Exception:
        return []


# ── Jobicy ────────────────────────────────────────────────────────────────────

async def scrape_jobicy(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Jobicy public API — no auth required.
    Remote-first job board with global coverage.
    Docs: https://jobicy.com/jobs-rss-feed
    """
    try:
        r = await client.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": 50, "tag": search_term},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for j in (r.json().get("jobs") or []):
            desc = re.sub(r'<[^>]+>', ' ', j.get("jobDescription") or "")
            jobs.append(_normalize({
                "source":   "jobicy",
                "title":    j.get("jobTitle", ""),
                "company":  j.get("companyName", ""),
                "location": j.get("jobGeo") or "Worldwide",
                "remote":   True,
                "url":      j.get("url", ""),
                "apply_url": j.get("url", ""),
                "description": f"{j.get('jobIndustry', '')} | {j.get('jobType', '')}\n{desc}",
            }))
        return jobs
    except Exception:
        return []


# ── Himalayas ─────────────────────────────────────────────────────────────────

async def scrape_himalayas(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Himalayas public API — no auth required.
    Remote-first job board popular with international candidates.
    """
    try:
        r = await client.get(
            "https://himalayas.app/jobs/api",
            params={"limit": 100, "q": search_term},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return await _scrape_himalayas_html(search_term, client)

        data     = r.json()
        job_list = data.get("jobs") or data.get("results") or []
        if not job_list:
            return await _scrape_himalayas_html(search_term, client)

        jobs = []
        for j in job_list:
            company     = j.get("company") or {}
            company_name = company.get("name") if isinstance(company, dict) else str(company or "")
            apply_url   = j.get("applicationLink") or j.get("applyUrl") or j.get("url") or ""
            jobs.append(_normalize({
                "source":           "himalayas",
                "title":            j.get("title", ""),
                "company":          company_name,
                "location":         j.get("location") or "Remote",
                "location_country": j.get("countryCode") or j.get("country"),
                "remote":           True,
                "url":              apply_url,
                "apply_url":        apply_url,
                "description":      (j.get("description") or "")[:10000],
            }))
        return jobs
    except Exception:
        return await _scrape_himalayas_html(search_term, client)


async def _scrape_himalayas_html(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Fallback: parse Himalayas search results HTML for embedded JSON."""
    try:
        query = search_term.replace(" ", "-").lower()
        r = await client.get(
            f"https://himalayas.app/jobs?q={query}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        import json as _json
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not m:
            return []
        page_data = _json.loads(m.group(1))
        job_list  = (
            page_data.get("props", {}).get("pageProps", {}).get("jobs") or []
        )
        jobs = []
        for j in job_list[:80]:
            company = j.get("company") or {}
            company_name = company.get("name") if isinstance(company, dict) else ""
            apply_url = j.get("applicationLink") or j.get("url") or ""
            jobs.append(_normalize({
                "source":   "himalayas",
                "title":    j.get("title", ""),
                "company":  company_name,
                "location": j.get("location") or "Remote",
                "remote":   True,
                "url":      apply_url,
                "apply_url": apply_url,
                "description": (j.get("description") or "")[:10000],
            }))
        return jobs
    except Exception:
        return []


# ── GetOnBoard (LATAM) ────────────────────────────────────────────────────────

async def scrape_getonboard(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    GetOnBoard — LATAM's largest tech job board. No auth required.
    Covers Argentina, Chile, Brazil, Mexico, Colombia and remote roles.
    """
    try:
        r = await client.get(
            "https://www.getonbrd.com/api/v0/jobs/",
            params={"q": search_term, "per_page": 100},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept":     "application/json",
            },
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []

        data     = r.json()
        job_list = data if isinstance(data, list) else (data.get("data") or data.get("jobs") or [])
        jobs     = []

        for j in job_list:
            attrs    = j.get("attributes") or j
            rels     = j.get("relationships") or {}
            company_data = ((rels.get("company") or {}).get("data") or {})
            company_name = (
                company_data.get("attributes", {}).get("name")
                or attrs.get("company_name", "")
            )
            remote   = attrs.get("remote") or (attrs.get("remote_modality") == "remote")
            country  = (attrs.get("country") or "LATAM")[:2].upper()
            location = attrs.get("city") or attrs.get("country") or "LATAM"
            job_url  = attrs.get("url") or f"https://www.getonbrd.com/jobs/{j.get('id', '')}"
            desc     = re.sub(r'<[^>]+>', ' ', attrs.get("description") or "")

            jobs.append(_normalize({
                "source":           "getonboard",
                "title":            attrs.get("title") or attrs.get("name", ""),
                "company":          company_name,
                "location":         location,
                "location_country": country,
                "remote":           bool(remote),
                "url":              job_url,
                "apply_url":        job_url,
                "description":      desc[:10000],
            }))
        return jobs
    except Exception:
        return []


# ── Adzuna ────────────────────────────────────────────────────────────────────

async def scrape_adzuna(search_term: str, client: httpx.AsyncClient, api_key: str = "") -> list[dict]:
    """
    Adzuna API — broadest continental coverage of any free API (20+ countries).
    Requires ADZUNA_APP_ID + ADZUNA_API_KEY — set in Settings → API Keys.
    Sign up free at: https://developer.adzuna.com/
    Queries all configured countries in parallel.
    """
    try:
        from app.core.config import settings
        app_id = settings.adzuna_app_id or os.environ.get("ADZUNA_APP_ID", "")
        if not api_key:
            api_key = settings.adzuna_api_key or os.environ.get("ADZUNA_API_KEY", "")
    except Exception:
        app_id = os.environ.get("ADZUNA_APP_ID", "")
        if not api_key:
            api_key = os.environ.get("ADZUNA_API_KEY", "")
    if not app_id or not api_key:
        raise RuntimeError("No Adzuna API key — add it in Settings → API Keys (key: adzuna_api_key)")

    async def _fetch(country: str) -> list[dict]:
        try:
            r = await client.get(
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                params={
                    "app_id":           app_id,
                    "app_key":          api_key,
                    "what":             search_term,
                    "results_per_page": 50,
                    "content-type":     "application/json",
                },
                timeout=_HTTP_TIMEOUT,
            )
            if r.status_code != 200:
                return []
            jobs = []
            for j in r.json().get("results", []):
                loc_data = j.get("location") or {}
                location = ", ".join(loc_data.get("display_name", "").split(",")[:2])
                company  = (j.get("company") or {}).get("display_name", "")
                url      = j.get("redirect_url", "")
                text     = f"{j.get('title', '')} {j.get('description', '') or ''}"
                jobs.append(_normalize({
                    "source":           "adzuna",
                    "title":            j.get("title", ""),
                    "company":          company,
                    "location":         location or country.upper(),
                    "location_country": country.upper(),
                    "remote":           "remote" in text.lower(),
                    "url":              url,
                    "apply_url":        url,
                    "description":      (j.get("description") or "")[:10000],
                }))
            return jobs
        except Exception:
            return []

    batches = await asyncio.gather(*[_fetch(c) for c in _ADZUNA_COUNTRIES])
    all_jobs: list[dict] = []
    for batch in batches:
        all_jobs.extend(batch)
    return all_jobs


# ── Reed ──────────────────────────────────────────────────────────────────────

async def scrape_reed(search_term: str, client: httpx.AsyncClient, api_key: str = "") -> list[dict]:
    """
    Reed.co.uk API — strong UK and EU coverage.
    Requires REED_API_KEY — set in Settings → API Keys.
    Sign up free at: https://www.reed.co.uk/developers/jobseeker
    """
    try:
        from app.core.config import settings
        if not api_key:
            api_key = settings.reed_api_key or os.environ.get("REED_API_KEY", "")
    except Exception:
        if not api_key:
            api_key = os.environ.get("REED_API_KEY", "")
    if not api_key:
        raise RuntimeError("No Reed API key — add it in Settings → API Keys (key: reed_api_key)")
    try:
        # Reed uses HTTP Basic auth: api_key as username, empty password
        creds = base64.b64encode(f"{api_key}:".encode()).decode()
        r = await client.get(
            "https://www.reed.co.uk/api/1.0/search",
            params={
                "keywords":      search_term,
                "resultsToTake": 100,
            },
            headers={"Authorization": f"Basic {creds}"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("results", []):
            job_id  = j.get("jobId", "")
            job_url = f"https://www.reed.co.uk/jobs/{job_id}"
            jobs.append(_normalize({
                "source":           "reed",
                "title":            j.get("jobTitle", ""),
                "company":          j.get("employerName", ""),
                "location":         j.get("locationName", "UK"),
                "location_country": "GB",
                "remote":           bool(j.get("locationName", "").lower().find("remote") >= 0),
                "url":              job_url,
                "apply_url":        j.get("jobUrl") or job_url,
                "description":      (j.get("jobDescription") or "")[:10000],
            }))
        return jobs
    except Exception:
        return []


# ── Batch helper ──────────────────────────────────────────────────────────────

async def scrape_all_global_boards(
    search_term: str,
    publish_fn=None,
) -> list[dict]:
    """
    Query all global boards in parallel.
    Adzuna and Reed return [] silently if API keys are not configured.
    """
    if publish_fn:
        await publish_fn(
            "🌍 Querying global boards "
            "(The Muse + Jobicy + Himalayas + GetOnBoard + Adzuna + Reed)..."
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        (
            muse_jobs, jobicy_jobs, himal_jobs,
            gob_jobs, adzuna_jobs, reed_jobs,
        ) = await asyncio.gather(
            scrape_the_muse(search_term, client),
            scrape_jobicy(search_term, client),
            scrape_himalayas(search_term, client),
            scrape_getonboard(search_term, client),
            scrape_adzuna(search_term, client),
            scrape_reed(search_term, client),
        )

    all_jobs = muse_jobs + jobicy_jobs + himal_jobs + gob_jobs + adzuna_jobs + reed_jobs

    if publish_fn:
        await publish_fn(
            f"  ↳ The Muse: {len(muse_jobs)} | Jobicy: {len(jobicy_jobs)} | "
            f"Himalayas: {len(himal_jobs)} | GetOnBoard: {len(gob_jobs)} | "
            f"Adzuna: {len(adzuna_jobs)} | Reed: {len(reed_jobs)} "
            f"= {len(all_jobs)} global listings"
        )

    return all_jobs
