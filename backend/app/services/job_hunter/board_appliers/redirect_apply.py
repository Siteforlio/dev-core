# board_appliers/redirect_apply.py
"""
Redirect-to-company-ATS applier — shared by boards that aggregate jobs
and link to external company career pages (Remotive, RemoteOK, WWR,
Startup Deals Africa, Glassdoor, Google Jobs, ZipRecruiter, Indeed).

Strategy:
  1. Follow the URL (may redirect through the board's own page)
  2. Detect which ATS the final page belongs to
  3. Delegate to the matching ATS applier (Greenhouse / Lever / Ashby)
     or fall back to the universal filler for Workday / generic career pages
  4. If the page is a platform-native apply form (no external ATS), use universal filler

This is "partial" auto-apply — it works when the company uses a supported ATS.
If the final page is completely custom, the universal AI filler handles it.
"""
from __future__ import annotations
import asyncio
import logging
import re

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)

# Patterns to identify the final ATS from the resolved URL
_ATS_URL_PATTERNS = {
    "greenhouse": ["boards.greenhouse.io", "job-boards.greenhouse.io", "grnh.se"],
    "lever":      ["jobs.lever.co", "lever.co/"],
    "ashby":      ["jobs.ashbyhq.com", "ashbyhq.com/"],
    "workday":    ["myworkdayjobs.com", "workday.com/"],
}


def _detect_ats_from_url(url: str) -> str:
    url_lower = url.lower()
    for ats, patterns in _ATS_URL_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return ats
    return "universal"


class RedirectApplier(BaseBoardApplier):
    """
    Used by: remotive, remoteok, weworkremotely, startupdeals_africa,
             glassdoor, google, zip_recruiter, indeed, myjobmag
    """

    def __init__(self, board_id: str):
        self.board_id = board_id

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        # The page is already navigated to `url`. Wait for any JS redirects to settle.
        await asyncio.sleep(2.0)
        final_url = await browser.current_url(page)
        logger.info("[%s] redirect_apply: landed on %s", self.board_id, final_url[:120])

        # If still on the board's own page, look for an Apply button/link
        board_domains = _board_own_domains(self.board_id)
        if any(d in final_url for d in board_domains):
            # Try to find and click an external apply link
            apply_href = await _find_external_apply_link(page, board_domains)
            if apply_href:
                logger.info("[%s] found external apply link: %s", self.board_id, apply_href[:120])
                await browser.goto(page, apply_href, wait=3.0)
                await asyncio.sleep(1.5)
                final_url = await browser.current_url(page)
            else:
                logger.info("[%s] no external link found — using universal filler on current page", self.board_id)

        ats = _detect_ats_from_url(final_url)
        logger.info("[%s] detected ATS: %s on %s", self.board_id, ats, final_url[:80])

        # Delegate to the right applier
        if ats == "greenhouse":
            from .greenhouse import GreenhouseApplier
            # Rewrite URL to embed form if needed
            from app.services.job_hunter.apply_service import ApplyService
            svc = ApplyService.__new__(ApplyService)
            form_url = await svc._detect_form_url(final_url)
            if form_url and form_url != final_url:
                await browser.goto(page, form_url, wait=3.0)
            return await GreenhouseApplier().apply(final_url, ctx, browser, page)

        elif ats == "lever":
            from .lever import LeverApplier
            return await LeverApplier().apply(final_url, ctx, browser, page)

        elif ats == "ashby":
            from .ashby import AshbyApplier
            return await AshbyApplier().apply(final_url, ctx, browser, page)

        else:
            # Workday or fully generic career page — universal AI filler
            return await _universal_fill(url, ctx, browser, page)


async def _find_external_apply_link(page, board_domains: list[str]) -> str | None:
    """Click or return href for an Apply button that leads off-platform."""
    result = await page.evaluate("""
        (function(boardDomains) {
            var exclude = ['reapply','already applied','view application','withdraw'];
            var els = document.querySelectorAll('a[href],button');
            for (var i = 0; i < els.length; i++) {
                var el = els[i];
                var t = (el.innerText || el.textContent || '').toLowerCase().trim();
                if (!t.includes('apply')) continue;
                if (exclude.some(function(x) { return t.includes(x); })) continue;
                var href = el.href || '';
                if (href && !boardDomains.some(function(d) { return href.includes(d); })) {
                    return href;
                }
            }
            return null;
        })(%s)
    """ % str(board_domains).replace("'", '"'))
    return result or None


async def _universal_fill(url: str, ctx: dict, browser, page) -> ApplyResult:
    from app.services.job_hunter.apply_service import ApplyService
    svc = ApplyService.__new__(ApplyService)
    svc._headless = True
    try:
        success = await svc._fill_universal(browser, page, ctx, url=url)
        if success:
            return ApplyResult.ok("universal filler succeeded")
        return ApplyResult.fail("universal filler: success page not detected")
    except Exception as exc:
        return ApplyResult.fail(f"universal filler error: {exc}")


def _board_own_domains(board_id: str) -> list[str]:
    return {
        "remotive":           ["remotive.com"],
        "remoteok":           ["remoteok.com", "remoteok.io"],
        "weworkremotely":     ["weworkremotely.com"],
        "startupdeals_africa":["startupdealsafrica.com"],
        "glassdoor":          ["glassdoor.com"],
        "google":             ["google.com/about/careers", "careers.google"],
        "zip_recruiter":      ["ziprecruiter.com"],
        "indeed":             ["indeed.com"],
        "myjobmag":           ["myjobmag.com"],
    }.get(board_id, [])
