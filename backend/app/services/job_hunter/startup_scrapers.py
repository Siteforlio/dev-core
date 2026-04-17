# backend/app/services/job_hunter/startup_scrapers.py
"""
Startup & small-company job board scrapers.
These cover companies that never appear on Greenhouse/Lever/Ashby:
  - Remotive: remote startup jobs globally
  - RemoteOK: remote-first dev/startup roles
  - HN Who's Hiring: Hacker News monthly thread (seed/Series A companies)
All APIs are free, no auth required.
"""
import asyncio
import re
import httpx
from datetime import datetime, timezone

_HTTP_TIMEOUT = 15.0


def _normalize(job: dict) -> dict:
    return {
        "source": job.get("source", "startup"),
        "title": (job.get("title") or "").strip(),
        "company": (job.get("company") or "").strip(),
        "location": job.get("location"),
        "location_country": job.get("location_country"),
        "remote": job.get("remote", False),
        "url": job.get("url", ""),
        "apply_url": job.get("apply_url") or job.get("url", ""),
        "description": (job.get("description") or "")[:5000],
    }


async def scrape_remotive(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Remotive public API — free, no auth.
    Note: search param is limited on free tier; we fetch all and let AI score filter.
    """
    try:
        r = await client.get(
            "https://remotive.com/api/remote-jobs",
            params={"limit": 100},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            candidate_country = (j.get("candidate_required_location") or "").strip()
            description = re.sub(r'<[^>]+>', ' ', j.get("description") or "")
            category = j.get("category", "")
            jobs.append(_normalize({
                "source": "remotive",
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": candidate_country or "Remote",
                "location_country": None,
                "remote": True,
                "url": j.get("url", ""),
                "apply_url": j.get("url", ""),
                "description": f"Category: {category}\n{description}",
            }))
        return jobs
    except Exception:
        return []


async def scrape_remoteok(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    RemoteOK public API — free, no auth.
    Fetches all listings; AI scorer will filter by relevance.
    """
    try:
        r = await client.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        listings = [item for item in data if isinstance(item, dict) and item.get("position")]
        jobs = []
        for j in listings:
            tags = j.get("tags") or []
            description = re.sub(r'<[^>]+>', ' ', j.get("description") or "")
            jobs.append(_normalize({
                "source": "remoteok",
                "title": j.get("position", ""),
                "company": j.get("company", ""),
                "location": j.get("location") or "Remote",
                "location_country": None,
                "remote": True,
                "url": j.get("url", ""),
                "apply_url": j.get("apply_url") or j.get("url", ""),
                "description": f"Tags: {', '.join(tags)}\n{description}",
            }))
        return jobs
    except Exception:
        return []


async def scrape_hn_who_is_hiring(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Hacker News 'Who is Hiring' monthly thread via Algolia HN API.
    These are raw startup posts — often seed/Series A companies you won't find anywhere else.
    """
    try:
        # Find the most recent "Ask HN: Who is hiring?" post
        r = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": "Ask HN: Who is hiring?",
                "tags": "story",
                "hitsPerPage": 3,
            },
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []

        hits = r.json().get("hits", [])
        if not hits:
            return []

        # Use the most recent thread
        thread_id = hits[0]["objectID"]

        # Search comments in that thread matching the search term
        r2 = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": search_term,
                "tags": f"comment,story_{thread_id}",
                "hitsPerPage": 50,
            },
            timeout=_HTTP_TIMEOUT,
        )
        if r2.status_code != 200:
            return []

        jobs = []
        for comment in r2.json().get("hits", []):
            text = comment.get("comment_text") or ""
            if len(text) < 100:
                continue  # too short to be a real job post

            # Strip HTML tags
            clean = re.sub(r'<[^>]+>', ' ', text).strip()

            # Try to extract company name from first line
            first_line = clean.split('\n')[0][:100].strip()
            company = first_line.split('|')[0].split('-')[0].strip()[:60]
            if not company:
                company = "HN Startup"

            # Try to extract remote signal
            is_remote = bool(re.search(r'\bremote\b', clean, re.IGNORECASE))

            # Build apply URL from HN comment
            hn_url = f"https://news.ycombinator.com/item?id={comment.get('objectID', '')}"

            # Extract any direct URL from the post
            url_match = re.search(r'https?://[^\s<>"\']+', clean)
            apply_url = url_match.group(0) if url_match else hn_url

            jobs.append(_normalize({
                "source": "hn_hiring",
                "title": search_term,  # HN posts don't have structured titles
                "company": company,
                "location": "Remote" if is_remote else None,
                "location_country": None,
                "remote": is_remote,
                "url": hn_url,
                "apply_url": apply_url,
                "description": clean[:5000],
            }))

        return jobs
    except Exception:
        return []


async def scrape_all_startup_boards(
    search_term: str,
    publish_fn=None,
) -> list[dict]:
    """
    Query Remotive, RemoteOK, and HN Who's Hiring in parallel.
    Returns all jobs — caller filters by relevance.
    """
    if publish_fn:
        await publish_fn(
            f"🚀 Querying startup job boards (Remotive + RemoteOK + HN Who's Hiring)..."
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        remotive_jobs, remoteok_jobs, hn_jobs = await asyncio.gather(
            scrape_remotive(search_term, client),
            scrape_remoteok(search_term, client),
            scrape_hn_who_is_hiring(search_term, client),
        )

    all_jobs = remotive_jobs + remoteok_jobs + hn_jobs

    if publish_fn:
        await publish_fn(
            f"  ↳ Remotive: {len(remotive_jobs)} | RemoteOK: {len(remoteok_jobs)} | "
            f"HN Hiring: {len(hn_jobs)} = {len(all_jobs)} startup listings"
        )

    return all_jobs
