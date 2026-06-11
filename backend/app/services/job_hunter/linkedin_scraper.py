# backend/app/services/job_hunter/linkedin_scraper.py
"""
LinkedIn job scraper using BrowserService (nodriver — stealth Chrome).

Strategy:
  1. Log in once with user's LinkedIn credentials (stored encrypted)
  2. Search jobs by keyword + location filters
  3. Scroll listing panel, click each card, extract full description
  4. Return normalized job dicts → fed into existing score → tailor → apply pipeline

Anti-ban measures:
  - Human-like typing with gaussian delays (BrowserService)
  - Random 2-5s pauses between job card clicks
  - Max 150 jobs per scrape run (safe daily quota)
  - Randomized scroll amounts
  - nodriver: no WebDriver fingerprint, real Chrome CDP
"""
import asyncio
import json
import logging
import random
import re

from app.services.job_hunter.browser_service import BrowserService

logger = logging.getLogger(__name__)

# LinkedIn URLs
LI_LOGIN_URL = "https://www.linkedin.com/login"
LI_JOBS_URL  = "https://www.linkedin.com/jobs/search/"

MAX_JOBS_PER_RUN = 150   # stay well under LinkedIn's bot-detection threshold
JOBS_PER_PAGE    = 25    # LinkedIn shows 25 cards per page


def _normalize(job: dict) -> dict:
    return {
        "source":           "linkedin",
        "title":            (job.get("title") or "").strip(),
        "company":          (job.get("company") or "").strip(),
        "location":         job.get("location"),
        "location_country": job.get("location_country"),
        "remote":           job.get("remote", False),
        "url":              job.get("url", ""),
        "apply_url":        job.get("apply_url") or job.get("url", ""),
        "description":      (job.get("description") or "")[:10000],
    }


class LinkedInScraper:
    def __init__(self, email: str | None = None, password: str | None = None,
                 session_cookie: str | None = None):
        self.email          = email
        self.password       = password
        self.session_cookie = session_cookie

    async def scrape(
        self,
        search_term: str,
        location: str = "",
        remote_only: bool = False,
        max_jobs: int = MAX_JOBS_PER_RUN,
        publish_fn=None,
    ) -> list[dict]:
        """
        Main entry point. Returns list of normalized job dicts.
        publish_fn: optional async callable(str) for activity log messages.
        """
        async def _pub(msg: str):
            if publish_fn:
                await publish_fn(msg)

        auth_method = "session cookie" if self.session_cookie else "email/password"
        await _pub(f"🔗 LinkedIn: testing authentication ({auth_method})…")

        try:
            async with BrowserService(headless=True) as browser:
                page = await browser.new_page()

                # ── Auth ─────────────────────────────────────────────────────
                if self.session_cookie:
                    logged_in = await self._auth_via_cookie(browser, page)
                else:
                    logged_in = await self._login(browser, page)

                if not logged_in:
                    await _pub("❌ LinkedIn: auth failed — cookie may have expired, re-paste it from DevTools → Application → Cookies → li_at")
                    return []

                await _pub("✅ LinkedIn: authenticated — starting job scrape…")

                # ── Search ───────────────────────────────────────────────────
                await self._navigate_to_search(browser, page, search_term, location, remote_only)
                await self._wait_for_job_cards(page)

                jobs: list[dict] = []
                page_num = 0

                while len(jobs) < max_jobs:
                    new_jobs = await self._extract_jobs_from_page(browser, page)
                    jobs.extend(new_jobs)

                    await _pub(
                        f"  ↳ LinkedIn page {page_num + 1}: {len(new_jobs)} listings found "
                        f"({len(jobs)} total so far)"
                    )

                    if len(new_jobs) < JOBS_PER_PAGE or len(jobs) >= max_jobs:
                        break

                    next_ok = await self._next_page(browser, page, page_num + 1)
                    if not next_ok:
                        break
                    page_num += 1
                    await asyncio.sleep(random.uniform(3, 6))

                await _pub(f"✅ LinkedIn: scrape complete — {len(jobs)} listings collected")
                return [_normalize(j) for j in jobs[:max_jobs]]

        except Exception as e:
            await _pub(f"❌ LinkedIn: unexpected error — {type(e).__name__}: {e or repr(e)}")
            return []

    # ── Cookie auth ───────────────────────────────────────────────────────────

    async def _auth_via_cookie(self, browser: BrowserService, page) -> bool:
        """Set li_at session cookie via CDP — skips login page entirely.
        Works for Google/SSO accounts. Uses Network.setCookie (CDP) because li_at is
        HttpOnly and cannot be set via document.cookie from JavaScript."""
        try:
            import nodriver as uc
            # Navigate to linkedin.com first so Chrome has the domain context
            await browser.goto(page, "https://www.linkedin.com", wait=2.0)
            # Set via CDP — the only way to set HttpOnly cookies programmatically
            await page.send(uc.cdp.network.set_cookie(
                name="li_at",
                value=self.session_cookie,
                domain=".linkedin.com",
                path="/",
                secure=True,
                http_only=True,
                same_site=uc.cdp.network.CookieSameSite.NONE,
            ))
            await browser.goto(page, "https://www.linkedin.com/feed/", wait=4.0)
            url = await browser.current_url(page)
            return "feed" in url or "mynetwork" in url or "linkedin.com/in/" in url
        except Exception:
            logger.exception("LinkedIn _auth_via_cookie failed")
            return False

    # ── Login ─────────────────────────────────────────────────────────────────

    async def _login(self, browser: BrowserService, page) -> bool:
        try:
            await browser.goto(page, LI_LOGIN_URL, wait=2.0)
            await browser.wait_past_cloudflare(page, timeout=10)

            filled_email = await browser.type_human(page, '#username', self.email)
            if not filled_email:
                return False
            await asyncio.sleep(random.uniform(0.5, 1.2))

            filled_pw = await browser.type_human(page, '#password', self.password)
            if not filled_pw:
                return False
            await asyncio.sleep(random.uniform(0.3, 0.8))

            await browser.click_human(page, 'button[type="submit"]')
            await asyncio.sleep(random.uniform(3, 5))

            # Check we landed on feed or jobs, not still on login
            url = await browser.current_url(page)
            return "feed" in url or "jobs" in url or "mynetwork" in url or "linkedin.com/in/" in url
        except Exception:
            logger.exception("LinkedIn _login failed")
            return False

    # ── Search navigation ──────────────────────────────────────────────────────

    async def _navigate_to_search(
        self,
        browser: BrowserService,
        page,
        search_term: str,
        location: str,
        remote_only: bool,
    ) -> None:
        # Build search URL with filters
        params = [
            f"keywords={search_term.replace(' ', '%20')}",
            "f_TPR=r86400",   # posted in last 24h
        ]
        if location:
            params.append(f"location={location.replace(' ', '%20')}")
        if remote_only:
            params.append("f_WT=2")  # remote filter

        url = f"{LI_JOBS_URL}?{'&'.join(params)}"
        await browser.goto(page, url, wait=3.0)

    # ── Extract jobs from current page ────────────────────────────────────────

    async def _extract_jobs_from_page(self, browser: BrowserService, page) -> list[dict]:
        jobs = []

        # Scroll the job list panel to load all cards
        await self._scroll_job_list(page)

        # Get all job card IDs from the listing panel
        card_ids_raw = await page.evaluate("""
            (function() {
                var cards = document.querySelectorAll('li[data-occludable-job-id]');
                var ids = [];
                for (var i = 0; i < cards.length; i++) {
                    var id = cards[i].getAttribute('data-occludable-job-id') || cards[i].getAttribute('data-job-id') || '';
                    if (id) ids.push(id);
                }
                return ids.join(',');
            })()
        """)
        card_ids: list[str] = [x for x in (card_ids_raw or "").split(",") if x]

        for job_id in card_ids:
            try:
                job = await self._extract_job_card(browser, page, job_id)
                if job:
                    jobs.append(job)
                # Human-like pause between clicking cards
                await asyncio.sleep(random.uniform(1.5, 4.0))
            except Exception:
                continue

        return jobs

    async def _extract_job_card(self, browser: BrowserService, page, job_id: str) -> dict | None:
        # Click the card to load details in the right panel
        clicked = await page.evaluate(
            "(function() {"
            f"  var card = document.querySelector('[data-occludable-job-id=\"{job_id}\"]') || document.querySelector('[data-job-id=\"{job_id}\"]');"
            "  if (card) { card.click(); return true; }"
            "  return false;"
            "})()"
        )
        if not clicked:
            return None

        await asyncio.sleep(random.uniform(1.5, 3.0))

        # Extract from detail panel — use querySelector with fallbacks, no optional chaining
        data_raw = await page.evaluate("""
            (function() {
                function txt(sel) {
                    var el = document.querySelector(sel);
                    return el ? (el.innerText || el.textContent || '').trim() : '';
                }
                var title = txt('.jobs-unified-top-card__job-title') || txt('h1.t-24') || txt('h1');
                var company = txt('.jobs-unified-top-card__company-name a') || txt('.jobs-unified-top-card__company-name') || txt('[class*="company-name"]');
                var location = txt('.jobs-unified-top-card__bullet') || txt('.jobs-unified-top-card__workplace-type') || txt('[class*="workplace-type"]');
                var desc = txt('.jobs-description-content__text') || txt('.jobs-description__content') || txt('[class*="description"]');
                var applyBtn = document.querySelector('.jobs-apply-button') || document.querySelector('a[data-control-name="jobdetails_topcard_inapply"]');
                var applyUrl = applyBtn ? (applyBtn.href || '') : window.location.href;
                var isRemote = /remote/i.test(location) ? '1' : '0';
                return title + '||' + company + '||' + location + '||' + applyUrl + '||' + isRemote + '||' + desc.substring(0, 3000);
            })()
        """)

        if not data_raw:
            return None

        parts = (data_raw or "").split("||", 5)
        if len(parts) < 5:
            return None

        title, company, location, apply_url, is_remote_flag = parts[0], parts[1], parts[2], parts[3], parts[4]
        desc = parts[5] if len(parts) > 5 else ""

        if not title:
            return None

        job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        return {
            "title":            title,
            "company":          company,
            "location":         location or None,
            "location_country": self._extract_country(location),
            "remote":           is_remote_flag == "1",
            "url":              job_url,
            "apply_url":        apply_url or job_url,
            "description":      desc[:10000],
        }

    # ── Wait helpers ─────────────────────────────────────────────────────────

    async def _wait_for_job_cards(self, page, timeout: float = 20.0) -> bool:
        """Poll until li[data-occludable-job-id] cards appear (React renders them lazily)."""
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            count = await page.evaluate(
                "document.querySelectorAll('li[data-occludable-job-id]').length"
            )
            if count and int(count) > 0:
                await asyncio.sleep(random.uniform(0.5, 1.0))  # small settle
                return True
            await asyncio.sleep(1.5)
        return False

    # ── Pagination ────────────────────────────────────────────────────────────

    async def _next_page(self, browser: BrowserService, page, page_num: int) -> bool:
        """Click the next page button. Returns False if no next page."""
        clicked = await page.evaluate(
            "(function() {"
            f"  var btn = document.querySelector('button[aria-label=\"Page {page_num + 1}\"]') || document.querySelector('li[data-test-pagination-page-btn=\"{page_num + 1}\"] button');"
            "  if (btn && !btn.disabled) { btn.click(); return true; }"
            "  return false;"
            "})()"
        )
        if clicked:
            await self._wait_for_job_cards(page)
        return bool(clicked)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _scroll_job_list(self, page) -> None:
        """Scroll the job list panel to trigger lazy loading."""
        for _ in range(3):
            await page.evaluate(
                "(function() {"
                "  var list = document.querySelector('.jobs-search-results-list') || document.querySelector('.scaffold-layout__list');"
                "  if (list) list.scrollBy(0, 600);"
                "})()"
            )
            await asyncio.sleep(random.uniform(0.8, 1.5))

    def _extract_country(self, location: str) -> str | None:
        """Very rough country extraction from LinkedIn location string."""
        if not location:
            return None
        # "San Francisco, CA, United States" → "US"
        country_map = {
            "united states": "US", "usa": "US",
            "united kingdom": "GB", "uk": "GB",
            "canada": "CA", "australia": "AU",
            "germany": "DE", "france": "FR",
            "india": "IN", "singapore": "SG",
            "netherlands": "NL", "kenya": "KE",
            "south africa": "ZA", "nigeria": "NG",
        }
        loc_lower = location.lower()
        for name, code in country_map.items():
            if name in loc_lower:
                return code
        return None
