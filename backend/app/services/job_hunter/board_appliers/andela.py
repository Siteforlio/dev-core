# board_appliers/andela.py
"""
Andela applier — andela.com

Andela has a talent network profile-based apply flow:
  - Jobs are applied to via the Andela platform profile
  - The apply URL is typically andela.com/jobs/<id>
  - Clicking Apply opens a modal: "Apply with your Andela profile"
  - If not logged in, redirects to sign-in

We fill what we can via universal filler. An Andela account improves
success rate significantly but isn't strictly required for the initial form.
"""
from __future__ import annotations
import asyncio
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)

ANDELA_LOGIN_URL = "https://andela.com/login"


class AndelaApplier(BaseBoardApplier):
    board_id = "andela"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        andela_email    = ctx.get("andela_email") or ctx.get("email")
        andela_password = ctx.get("andela_password")

        if andela_password:
            await browser.goto(page, ANDELA_LOGIN_URL, wait=3.0)
            try:
                await browser.type_human(page, 'input[type="email"]', andela_email)
                await browser.type_human(page, 'input[type="password"]', andela_password)
                await browser.click_human(page, 'button[type="submit"]')
                await asyncio.sleep(2.5)
                await browser.goto(page, url, wait=3.0)
            except Exception as exc:
                logger.warning("andela: login failed (%s) — continuing unauthenticated", exc)
                await browser.goto(page, url, wait=3.0)
        else:
            # Already on the job page from scrape navigation
            pass

        # Click Apply button if present
        try:
            await browser.click_human(
                page,
                'button:has-text("Apply"), a:has-text("Apply Now"), [data-testid*="apply"]'
            )
            await asyncio.sleep(2.0)
        except Exception:
            pass

        # Fill whatever form is shown
        from app.services.job_hunter.apply_service import ApplyService
        svc = ApplyService.__new__(ApplyService)
        svc._headless = True
        try:
            success = await svc._fill_universal(browser, page, ctx, url=url)
            return ApplyResult.ok() if success else ApplyResult.fail("success not detected")
        except Exception as exc:
            return ApplyResult.fail(str(exc))
