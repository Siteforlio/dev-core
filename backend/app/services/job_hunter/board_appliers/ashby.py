# board_appliers/ashby.py
"""
Ashby ATS applier — jobs.ashbyhq.com

Minimal stable form: name, email, phone, LinkedIn, resume, cover letter.
No multi-step — single submit.
"""
from __future__ import annotations
import asyncio
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)


class AshbyApplier(BaseBoardApplier):
    board_id = "ashby"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        try:
            await browser.type_human(
                page,
                'input[placeholder*="name" i], input[name*="name"]',
                ctx["full_name"],
            )
        except Exception:
            pass
        try:
            await browser.type_human(page, 'input[type="email"]', ctx["email"])
        except Exception:
            pass
        try:
            await browser.type_human(page, 'input[type="tel"]', ctx["phone"])
        except Exception:
            pass
        if ctx["linkedin_url"]:
            try:
                await browser.type_human(page, 'input[placeholder*="linkedin" i]', ctx["linkedin_url"])
            except Exception:
                pass

        if ctx["resume_pdf"]:
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                await asyncio.sleep(1.0)
            except Exception:
                pass

        if ctx["cover_letter"]:
            try:
                await browser.fill_field(page, 'textarea', ctx["cover_letter"])
            except Exception:
                pass

        clicked = await browser.click_human(page, 'button[type="submit"]')
        if not clicked:
            return ApplyResult.fail("submit button not found")

        await page.sleep(2)
        found = await browser.wait_for(
            page,
            '[class*="success"], [class*="confirm"], [class*="thank"]',
            timeout=8,
        )
        if found:
            return ApplyResult.ok()
        return ApplyResult.fail("success confirmation not found")
