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
    """Fuzu.com — Kenya's most active job board for SMBs. Uses nodriver (SPA)."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            url = f"https://www.fuzu.com/kenya/jobs?q={search_term.replace(' ', '+')}"
            await browser.goto(page, url, wait=3.0)
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerText")
            titles = re.findall(r'"title"\s*:\s*"([^"]{5,100})"', html)
            companies = re.findall(r'"hiringOrganization"[^}]*"name"\s*:\s*"([^"]{2,80})"', html)
            urls_found = re.findall(r'"url"\s*:\s*"(https://www\.fuzu\.com/kenya/jobs/[^"]+)"', html)
            for i, title in enumerate(titles[:50]):
                company = companies[i] if i < len(companies) else "Fuzu Company"
                job_url = urls_found[i] if i < len(urls_found) else "https://www.fuzu.com/kenya/jobs"
                jobs.append(_normalize({
                    "source": "fuzu",
                    "title": title,
                    "company": company,
                    "location": "Kenya",
                    "location_country": "KE",
                    "remote": False,
                    "url": job_url,
                    "apply_url": job_url,
                    "description": f"Job listing on Fuzu Kenya: {title} at {company}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_brightermonday(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """BrighterMonday Kenya — high-volume local board. Uses nodriver (SPA)."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            query = search_term.replace(' ', '%20')
            url = f"https://www.brightermonday.co.ke/jobs?q={query}"
            await browser.goto(page, url, wait=3.0)
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerHTML")
            titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]{5,100})<', html)
            companies = re.findall(r'class="[^"]*company[^"]*"[^>]*>([^<]{2,80})<', html)
            links = re.findall(r'href="(/jobs/[^"?]+)"', html)
            for i, title in enumerate(titles[:50]):
                company = companies[i] if i < len(companies) else "BrighterMonday Company"
                path = links[i] if i < len(links) else "/jobs"
                job_url = f"https://www.brightermonday.co.ke{path}"
                jobs.append(_normalize({
                    "source": "brightermonday",
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": "Kenya",
                    "location_country": "KE",
                    "remote": False,
                    "url": job_url,
                    "apply_url": job_url,
                    "description": f"Job on BrighterMonday Kenya: {title.strip()} at {company.strip()}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_myjobmag(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """MyJobMag Kenya — standard HTML, httpx sufficient."""
    try:
        query = search_term.replace(' ', '+')
        r = await client.get(
            f"https://www.myjobmag.co.ke/jobs-by-field/{query}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        html = r.text
        titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]{5,100})<', html)
        companies = re.findall(r'class="[^"]*company-name[^"]*"[^>]*>([^<]{2,80})<', html)
        links = re.findall(r'href="(https://www\.myjobmag\.co\.ke/job/[^"]+)"', html)
        jobs = []
        for i, title in enumerate(titles[:50]):
            company = companies[i] if i < len(companies) else "MyJobMag Company"
            url = links[i] if i < len(links) else "https://www.myjobmag.co.ke"
            jobs.append(_normalize({
                "source": "myjobmag",
                "title": title.strip(),
                "company": company.strip(),
                "location": "Kenya",
                "location_country": "KE",
                "remote": False,
                "url": url,
                "apply_url": url,
                "description": f"Job on MyJobMag Kenya: {title.strip()} at {company.strip()}",
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
