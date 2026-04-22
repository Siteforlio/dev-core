# board_appliers/fuzu.py
"""
Fuzu applier — fuzu.com (Kenya)

Fuzu has a consistent multi-step application flow:
  1. Job detail page → "Apply Now" button
  2. Step 1: Personal details (name, email, phone, location)
  3. Step 2: Resume/CV upload
  4. Step 3: Cover letter / motivation
  5. Submit

Fuzu requires an account — we create/login a session before applying.
If no Fuzu credentials are in ctx, falls back to universal filler.
"""
from __future__ import annotations
import asyncio
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)

FUZU_LOGIN_URL = "https://fuzu.com/sign_in"


class FuzuApplier(BaseBoardApplier):
    board_id = "fuzu"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        # Fuzu needs an account — check for credentials in ctx
        fuzu_email    = ctx.get("fuzu_email") or ctx.get("email")
        fuzu_password = ctx.get("fuzu_password")

        if not fuzu_password:
            logger.info("fuzu: no fuzu_password in ctx — falling back to universal filler")
            return await _universal(url, ctx, browser, page)

        # 1. Login
        await browser.goto(page, FUZU_LOGIN_URL, wait=3.0)
        try:
            await browser.type_human(page, 'input[type="email"], input[name="email"]', fuzu_email)
            await browser.type_human(page, 'input[type="password"]', fuzu_password)
            await browser.click_human(page, 'button[type="submit"], input[type="submit"]')
            await asyncio.sleep(2.5)
        except Exception as exc:
            return ApplyResult.fail(f"fuzu login failed: {exc}")

        # 2. Navigate to job and click Apply
        await browser.goto(page, url, wait=3.0)
        try:
            await browser.click_human(page, 'a[href*="apply"], button:has-text("Apply")')
            await asyncio.sleep(2.0)
        except Exception:
            pass  # might already be on apply form

        # 3. Fill form steps with universal filler (handles multi-step)
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
