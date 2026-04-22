# board_appliers/brightermonday.py
"""
BrighterMonday applier — brightermonday.com (Kenya)

BrighterMonday has a consistent apply flow:
  1. Job detail page → "Apply" button (opens modal or new page)
  2. Uploads CV + fills contact details
  3. Optional cover letter
  4. Submit

Requires a BrighterMonday account. Falls back to universal filler without one.
"""
from __future__ import annotations
import asyncio
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)

BM_LOGIN_URL = "https://www.brightermonday.com/login"


class BrighterMondayApplier(BaseBoardApplier):
    board_id = "brightermonday"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        bm_email    = ctx.get("bm_email") or ctx.get("email")
        bm_password = ctx.get("bm_password")

        if not bm_password:
            logger.info("brightermonday: no bm_password — using universal filler")
            return await _universal(url, ctx, browser, page)

        # 1. Login
        await browser.goto(page, BM_LOGIN_URL, wait=3.0)
        try:
            await browser.type_human(page, 'input[name="email"], input[type="email"]', bm_email)
            await browser.type_human(page, 'input[name="password"], input[type="password"]', bm_password)
            await browser.click_human(page, 'button[type="submit"]')
            await asyncio.sleep(2.5)
        except Exception as exc:
            return ApplyResult.fail(f"brightermonday login failed: {exc}")

        # 2. Navigate to job
        await browser.goto(page, url, wait=3.0)

        # 3. Click Apply button
        try:
            await browser.click_human(
                page,
                'a[data-action*="apply"], button[data-action*="apply"], '
                'a:has-text("Apply"), button:has-text("Apply Now")'
            )
            await asyncio.sleep(2.0)
        except Exception:
            pass

        # 4. Upload CV if file input present
        if ctx["resume_pdf"]:
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # 5. Fill remaining fields via universal filler
        return await _universal(url, ctx, browser, page)


async def _universal(url: str, ctx: dict, browser, page) -> ApplyResult:
    from app.services.job_hunter.apply_service import ApplyService
    svc = ApplyService.__new__(ApplyService)
    svc._headless = True
    try:
        success = await svc._fill_universal(browser, page, ctx, url=url)
        return ApplyResult.ok() if success else ApplyResult.fail("success page not detected")
    except Exception as exc:
        return ApplyResult.fail(str(exc))
