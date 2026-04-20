# backend/app/services/job_hunter/kenya_scrapers.py
"""
Kenya and Africa-focused job board scrapers.
Fuzu, BrighterMonday, MyJobMag, Kuhustle, Andela, Arc.dev

Strategy: attempt lightweight httpx scrape first; use BrowserService (nodriver)
as fallback for SPAs that require JS rendering.

Each scraper catches all exceptions and returns [] — callers never see errors.
"""
import asyncio
import re
import httpx

_HTTP_TIMEOUT = 15.0


def _normalize(job: dict) -> dict:
    return {
        "source": job.get("source", "kenya"),
        "title": (job.get("title") or "").strip(),
        "company": (job.get("company") or "").strip(),
        "location": job.get("location"),
        "location_country": job.get("location_country"),
        "remote": job.get("remote", False),
        "url": job.get("url", ""),
        "apply_url": job.get("apply_url") or job.get("url", ""),
        "description": (job.get("description") or "")[:5000],
    }


async def scrape_fuzu(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Fuzu.com — uses the browser-use autonomous agent (Vertex Gemini).

    The agent navigates the category page, dismisses popups, and extracts
    job listings autonomously — no brittle CSS selectors needed.
    """
    try:
        from app.services.job_hunter.fuzu_agent import scrape_fuzu_agent
        return await scrape_fuzu_agent(search_term)
    except Exception:
        return []


async def scrape_brightermonday(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """BrighterMonday Kenya — high-volume local board. Uses nodriver (SPA).
    Selectors confirmed 2026-04: data-cy=listing-title-link + text-blue-700 company line.
    """
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            query = search_term.replace(' ', '%20')
            url = f"https://www.brightermonday.co.ke/jobs?q={query}"
            # 8s wait gives the JS time to inject listing cards
            await browser.goto(page, url, wait=8.0)
            html = await page.evaluate("document.body.innerHTML")
            # Full listing URLs (e.g. /listings/support-engineer-7wn4dx)
            links = re.findall(
                r'href="(https://www\.brightermonday\.co\.ke/listings/[^"]+)"',
                html,
            )
            # Title is inside the <p> nested in the listing-title-link anchor
            titles = re.findall(
                r'data-cy="listing-title-link"[^>]*>\s*<p[^>]*>([^<]{5,120})</p>',
                html,
            )
            # Company name in the sibling <p class="text-sm text-blue-700 ...">
            companies = re.findall(
                r'class="text-sm text-blue-700[^"]*"[^>]*>\s*([^\n<]{2,80}?)\s*</p>',
                html,
            )
            for i, title in enumerate(titles[:50]):
                company = companies[i].strip() if i < len(companies) else "BrighterMonday Company"
                job_url = links[i] if i < len(links) else "https://www.brightermonday.co.ke/jobs"
                jobs.append(_normalize({
                    "source": "brightermonday",
                    "title": title.strip(),
                    "company": company,
                    "location": "Kenya",
                    "location_country": "KE",
                    "remote": False,
                    "url": job_url,
                    "apply_url": job_url,
                    "description": f"Job on BrighterMonday Kenya: {title.strip()} at {company}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_myjobmag(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """MyJobMag Kenya — standard HTML, httpx sufficient.
    Selectors confirmed 2026-04: <h2><a href="/job/...">Title at Company</a></h2>
    """
    try:
        r = await client.get(
            "https://www.myjobmag.co.ke/jobs/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        html = r.text
        # Each listing: <h2><a href="/job/slug">Title at Company Name</a></h2>
        entries = re.findall(r'<h2><a[^>]+href="(/job/[^"]+)"[^>]*>([^<]{5,200})</a></h2>', html)
        jobs = []
        for path, raw_title in entries[:50]:
            raw_title = raw_title.strip()
            # Format is "Job Title at Company Name"
            if " at " in raw_title:
                parts = raw_title.rsplit(" at ", 1)
                title = parts[0].strip()
                company = parts[1].strip()
            else:
                title = raw_title
                company = "MyJobMag Company"
            job_url = f"https://www.myjobmag.co.ke{path}"
            jobs.append(_normalize({
                "source": "myjobmag",
                "title": title,
                "company": company,
                "location": "Kenya",
                "location_country": "KE",
                "remote": False,
                "url": job_url,
                "apply_url": job_url,
                "description": f"Job on MyJobMag Kenya: {title} at {company}",
            }))
        return jobs
    except Exception:
        return []


async def scrape_kuhustle(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Kuhustle — Kenyan freelance/gig platform, httpx sufficient."""
    try:
        r = await client.get(
            "https://kuhustle.com/jobs",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        html = r.text
        titles = re.findall(r'<h[23][^>]*>([^<]{5,100})</h[23]>', html)
        links = re.findall(r'href="(https://kuhustle\.com/(?:jobs|project)/[^"]+)"', html)
        jobs = []
        seen: set[str] = set()
        for i, title in enumerate(titles[:50]):
            title = title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            url = links[i] if i < len(links) else "https://kuhustle.com/jobs"
            is_remote = "remote" in title.lower()
            jobs.append(_normalize({
                "source": "kuhustle",
                "title": title,
                "company": "Kuhustle",
                "location": "Remote" if is_remote else "Kenya",
                "location_country": "KE",
                "remote": is_remote,
                "url": url,
                "apply_url": url,
                "description": f"Gig/job on Kuhustle: {title}",
            }))
        return jobs
    except Exception:
        return []


async def scrape_andela(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Andela Talent Network — tech-focused Africa roles. Uses nodriver."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            await browser.goto(page, "https://andela.com/ats/#/jobs", wait=3.0)
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerHTML")
            titles = re.findall(r'"title"\s*:\s*"([^"]{5,100})"', html)
            urls_found = re.findall(r'"url"\s*:\s*"(https://andela\.com[^"]+)"', html)
            for i, title in enumerate(titles[:50]):
                url = urls_found[i] if i < len(urls_found) else "https://andela.com/ats/#/jobs"
                jobs.append(_normalize({
                    "source": "andela",
                    "title": title,
                    "company": "Andela Network",
                    "location": "Africa / Remote",
                    "location_country": None,
                    "remote": True,
                    "url": url,
                    "apply_url": url,
                    "description": f"Tech role via Andela Talent Network: {title}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_arc(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Arc.dev — remote startup network, vets developers. Uses nodriver."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            query = search_term.replace(' ', '-')
            await browser.goto(
                page,
                f"https://arc.dev/remote-jobs?technology={query}",
                wait=3.0,
            )
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerHTML")
            titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]{5,100})<', html)
            companies = re.findall(r'class="[^"]*company[^"]*"[^>]*>([^<]{2,80})<', html)
            links = re.findall(r'href="(https://arc\.dev/remote-jobs/[^"]+)"', html)
            for i, title in enumerate(titles[:50]):
                company = companies[i] if i < len(companies) else "Arc.dev Company"
                url = links[i] if i < len(links) else "https://arc.dev/remote-jobs"
                jobs.append(_normalize({
                    "source": "arc",
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": "Remote",
                    "location_country": None,
                    "remote": True,
                    "url": url,
                    "apply_url": url,
                    "description": f"Remote tech role via Arc.dev: {title.strip()} at {company.strip()}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_all_kenya_boards(
    search_term: str,
    publish_fn=None,
) -> list[dict]:
    """
    Query all 6 Kenya/Africa boards in parallel.
    Returns all jobs — caller filters by relevance.
    Each individual scraper is fault-tolerant (returns [] on failure).
    """
    if publish_fn:
        await publish_fn(
            "🇰🇪 Querying Kenya boards "
            "(Fuzu + BrighterMonday + MyJobMag + Kuhustle + Andela + Arc.dev)..."
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        (
            fuzu_jobs, bm_jobs, mjm_jobs,
            kh_jobs, andela_jobs, arc_jobs,
        ) = await asyncio.gather(
            scrape_fuzu(search_term, client),
            scrape_brightermonday(search_term, client),
            scrape_myjobmag(search_term, client),
            scrape_kuhustle(search_term, client),
            scrape_andela(search_term, client),
            scrape_arc(search_term, client),
        )

    all_jobs = fuzu_jobs + bm_jobs + mjm_jobs + kh_jobs + andela_jobs + arc_jobs

    if publish_fn:
        await publish_fn(
            f"  ↳ Fuzu: {len(fuzu_jobs)} | BrighterMonday: {len(bm_jobs)} | "
            f"MyJobMag: {len(mjm_jobs)} | Kuhustle: {len(kh_jobs)} | "
            f"Andela: {len(andela_jobs)} | Arc: {len(arc_jobs)} "
            f"= {len(all_jobs)} Kenya listings"
        )

    return all_jobs
