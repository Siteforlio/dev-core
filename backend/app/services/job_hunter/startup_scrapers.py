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
        "description": (job.get("description") or "")[:10000],
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
                "description": clean[:10000],
            }))

        return jobs
    except Exception:
        return []


async def scrape_weworkremotely(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    We Work Remotely — RSS feed, no auth.
    Fetches programming + devops categories which cover tech roles.
    """
    import xml.etree.ElementTree as ET
    urls = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
    ]
    jobs = []
    for url in urls:
        try:
            r = await client.get(url, timeout=_HTTP_TIMEOUT)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = re.sub(r'<[^>]+>', ' ', item.findtext("description") or "")
                region = (item.findtext("{https://weworkremotely.com}region") or "Worldwide").strip()
                if not title or not link:
                    continue
                # Title format: "Company: Job Title"
                parts = title.split(":", 1)
                company = parts[0].strip() if len(parts) == 2 else "Unknown"
                job_title = parts[1].strip() if len(parts) == 2 else title
                jobs.append(_normalize({
                    "source": "weworkremotely",
                    "title": job_title,
                    "company": company,
                    "location": region,
                    "location_country": None,
                    "remote": True,
                    "url": link,
                    "apply_url": link,
                    "description": desc[:10000],
                }))
        except Exception:
            continue
    return jobs


async def scrape_zindi(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Zindi Jobs — Africa's largest data science community.
    Moved to zindi.global; job data is embedded as JSON in the page title patterns.
    """
    try:
        r = await client.get(
            "https://zindi.global/jobs",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []

        # Data is in JSON embedded as "title":"Job, Company" pairs
        raw_titles = re.findall(r'"title":"([^"]{5,120})"', r.text)
        urls_found = re.findall(r'href="(/jobs/[^"]+)"', r.text)

        jobs = []
        seen: set[str] = set()
        for i, raw in enumerate(raw_titles[:60]):
            raw = raw.strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            # Format is often "Job Title, Company"
            if ", " in raw:
                parts = raw.rsplit(", ", 1)
                title   = parts[0].strip()
                company = parts[1].strip()
            else:
                title   = raw
                company = "Zindi"
            path    = urls_found[i] if i < len(urls_found) else "/jobs"
            job_url = f"https://zindi.global{path}"
            jobs.append(_normalize({
                "source":   "zindi",
                "title":    title,
                "company":  company,
                "location": "Africa / Remote",
                "remote":   True,
                "url":      job_url,
                "apply_url": job_url,
                "description": f"Data science / ML role at {company} via Zindi.",
            }))
        return jobs
    except Exception:
        return []


async def scrape_startupdeals_africa(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Startup Deals Africa — lists funded African startups.
    Scrapes their jobs/careers page for open roles.
    """
    try:
        r = await client.get(
            "https://startupdeals.africa/jobs/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        titles = re.findall(r'<h[23][^>]*>([^<]{5,80})</h[23]>', r.text)
        links = re.findall(r'href="(https://startupdeals\.africa/jobs/[^"]+)"', r.text)
        jobs = []
        seen: set[str] = set()
        for i, title in enumerate(titles[:50]):
            title = title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            url = links[i] if i < len(links) else "https://startupdeals.africa/jobs/"
            jobs.append(_normalize({
                "source": "startupdeals_africa",
                "title": title,
                "company": "African Startup",
                "location": "Africa",
                "location_country": None,
                "remote": False,
                "url": url,
                "apply_url": url,
                "description": f"Role at an African startup. See {url} for details.",
            }))
        return jobs
    except Exception:
        return []


async def scrape_wellfound(search_term: str, client: httpx.AsyncClient, scrapfly_key: str = "") -> list[dict]:
    """
    Wellfound (formerly AngelList Talent) via ScrapFly.
    Uses ScrapFly's ASP bypass + residential proxies + JS rendering to extract
    the Apollo GraphQL state embedded in __NEXT_DATA__ on each search page.

    Requires a Scrapfly API key — set it in Settings → API Keys (key name: scrapfly_key).
    Raises RuntimeError when the key is not configured so the board card shows an error.
    """
    import json as _json
    import os
    from datetime import datetime

    if not scrapfly_key:
        raise RuntimeError("No Scrapfly API key — add it in Settings → API Keys (key: scrapfly_key)")

    try:
        from scrapfly import ScrapeConfig, ScrapflyClient

        scrapfly = ScrapflyClient(key=scrapfly_key)

        role = search_term.replace(" ", "-").lower()
        url  = f"https://wellfound.com/role/{role}"

        response = await scrapfly.async_scrape(ScrapeConfig(
            url,
            asp=True,
            country="US",
            render_js=True,
            proxy_pool="public_residential_pool",
        ))

        # ── Extract Apollo graph from __NEXT_DATA__ ───────────────────────
        raw = response.selector.css("script#__NEXT_DATA__::text").get()
        if not raw:
            return []
        graph = _json.loads(raw)["props"]["pageProps"]["apolloState"]["data"]

        # ── Extract jobs — same logic as get_jobs.py ──────────────────────
        jobs = []
        for key, value in graph.items():
            if not key.startswith("JobListingSearchResult:"):
                continue

            job_id    = value.get("id")
            title     = (value.get("title") or "").strip()
            posted_ts = value.get("liveStartAt")
            desc      = re.sub(r'<[^>]+>', ' ', value.get("description") or "")
            remote    = bool(value.get("remote"))
            locations = value.get("locationNames") or []
            location  = locations[0] if locations else ("Remote" if remote else None)
            job_url   = f"https://wellfound.com/jobs/{job_id}" if job_id else ""

            # Company name: walk StartupResult nodes, find the one that
            # references this job in highlightedJobListings via __ref
            company_name = ""
            ref_key = f"JobListingSearchResult:{job_id}"
            for skey, sval in graph.items():
                if not (skey.startswith("StartupResult:") or skey.startswith("Startup:")):
                    continue
                for ref in (sval.get("highlightedJobListings") or []):
                    if isinstance(ref, dict) and ref.get("__ref") == ref_key:
                        company_name = sval.get("name", "")
                        break
                if company_name:
                    break

            if not title or not job_url:
                continue

            jobs.append(_normalize({
                "source":    "wellfound",
                "title":     title,
                "company":   company_name,
                "location":  location,
                "remote":    remote,
                "url":       job_url,
                "apply_url": job_url,
                "description": desc[:10000],
            }))

        return jobs

    except Exception:
        return []


async def scrape_all_startup_boards(
    search_term: str,
    publish_fn=None,
) -> list[dict]:
    """
    Query Remotive, RemoteOK, HN Who's Hiring, WeWorkRemotely, Zindi,
    and Startup Deals Africa in parallel.
    Returns all jobs — caller filters by relevance.
    """
    if publish_fn:
        await publish_fn(
            "🚀 Querying startup job boards "
            "(Wellfound + Remotive + RemoteOK + HN Who's Hiring + WeWorkRemotely + Zindi + Startup Deals Africa)..."
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        (
            wellfound_jobs, remotive_jobs, remoteok_jobs, hn_jobs,
            wwr_jobs, zindi_jobs, sda_jobs,
        ) = await asyncio.gather(
            scrape_wellfound(search_term, client),
            scrape_remotive(search_term, client),
            scrape_remoteok(search_term, client),
            scrape_hn_who_is_hiring(search_term, client),
            scrape_weworkremotely(search_term, client),
            scrape_zindi(search_term, client),
            scrape_startupdeals_africa(search_term, client),
        )

    all_jobs = wellfound_jobs + remotive_jobs + remoteok_jobs + hn_jobs + wwr_jobs + zindi_jobs + sda_jobs

    if publish_fn:
        await publish_fn(
            f"  ↳ Wellfound: {len(wellfound_jobs)} | Remotive: {len(remotive_jobs)} | "
            f"RemoteOK: {len(remoteok_jobs)} | HN Hiring: {len(hn_jobs)} | "
            f"WeWorkRemotely: {len(wwr_jobs)} | Zindi: {len(zindi_jobs)} | "
            f"Startup Deals Africa: {len(sda_jobs)} = {len(all_jobs)} total startup listings"
        )

    return all_jobs
