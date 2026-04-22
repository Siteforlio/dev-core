# board_appliers/ashby.py
"""
Ashby ATS applier — jobs.ashbyhq.com

Ashby forms are React-rendered single-page with custom combobox dropdowns.
Strategy:
  1. Seed structural fields via known selectors
  2. Upload resume
  3. Cover letter (textarea)
  4. Poll until form fields render (React SPA)
  5. Scan all fields via JS
  6. Detect comboboxes (custom dropdowns with role="combobox")
  7. Pre-read real options from each combobox
  8. Gemini maps all fields to exact values
  9. Fill — comboboxes via _interact_combobox, standard via _make_fill_js
 10. Submit and verify confirmation
"""
from __future__ import annotations
import asyncio
import json
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)


class AshbyApplier(BaseBoardApplier):
    board_id = "ashby"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        from app.services.job_hunter.apply_service import (
            ApplyService, _SCAN_FIELDS_JS, _make_fill_js,
        )

        # ── 1. Seed stable structural fields ─────────────────────────────────
        for sel, val in [
            ('input[placeholder*="name" i], input[name*="name"], input[id*="name"]',
             ctx.get("full_name", "")),
            ('input[type="email"], input[placeholder*="email" i]',
             ctx.get("email", "")),
            ('input[type="tel"], input[placeholder*="phone" i]',
             ctx.get("phone", "")),
            ('input[placeholder*="linkedin" i], input[name*="linkedin" i]',
             ctx.get("linkedin_url", "")),
            ('input[placeholder*="github" i], input[name*="github" i]',
             ctx.get("github_url", "")),
            ('input[placeholder*="website" i], input[placeholder*="portfolio" i]',
             ctx.get("portfolio_url", "")),
        ]:
            if not val:
                continue
            try:
                await browser.type_human(page, sel, val)
            except Exception:
                pass

        # ── 2. Resume upload ──────────────────────────────────────────────────
        resume_uploaded = False
        if ctx.get("resume_pdf"):
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                resume_uploaded = True
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # ── 3. Cover letter ───────────────────────────────────────────────────
        if ctx.get("cover_letter"):
            for csel in [
                'textarea[name*="cover" i]',
                'textarea[placeholder*="cover" i]',
                'textarea[placeholder*="letter" i]',
                'textarea',
            ]:
                try:
                    filled = await browser.fill_field(page, csel, ctx["cover_letter"])
                    if filled:
                        break
                except Exception:
                    pass

        # ── 4. Poll for React form to render ──────────────────────────────────
        for _ in range(20):
            await asyncio.sleep(0.5)
            cnt = await page.evaluate(
                "document.querySelectorAll("
                "  'input:not([type=hidden]), select, textarea, [role=\"combobox\"]'"
                ").length"
            ) or 0
            if cnt > 2:
                break

        # ── 5. Scan all fields ────────────────────────────────────────────────
        await asyncio.sleep(0.5)
        raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(raw) if isinstance(raw, str) else (raw or [])
        fillable = [f for f in fields if not str(f.get("selector", "")).startswith("__idx__")]

        if fillable:
            # ── 5a. Detect Ashby custom comboboxes ────────────────────────────
            # Ashby uses role="combobox" divs (not native <select>).
            # The JS scanner marks the next field with __idx__ when a combobox
            # is followed by a hidden required sentinel.
            combobox_selectors: set[str] = set()
            for i, f in enumerate(fields):
                nxt = fields[i + 1] if i + 1 < len(fields) else None
                if (nxt and str(nxt.get("selector", "")).startswith("__idx__")
                        and nxt.get("required")):
                    sel = f.get("selector", "")
                    if sel and not sel.startswith("__idx__"):
                        combobox_selectors.add(sel)

            # Also detect any [role="combobox"] elements directly
            combobox_roles = await page.evaluate("""
                (function() {
                    var els = document.querySelectorAll('[role="combobox"]');
                    var sels = [];
                    els.forEach(function(el) {
                        if (el.id) sels.push('#' + CSS.escape(el.id));
                        else if (el.getAttribute('data-testid'))
                            sels.push('[data-testid="' + el.getAttribute('data-testid') + '"]');
                    });
                    return sels;
                })()
            """) or []
            combobox_selectors.update(combobox_roles)

            # ── 5b. Pre-read real dropdown options ────────────────────────────
            if combobox_selectors:
                logger.info("ashby: pre-reading %d combobox(es)", len(combobox_selectors))
                for field in fillable:
                    sel = field.get("selector", "")
                    if sel in combobox_selectors and not field.get("options"):
                        opts = await ApplyService._read_combobox_options_static(
                            browser, page, sel
                        )
                        if opts:
                            field["options"] = opts
                            logger.info("  [%s] options: %s",
                                        (field.get("label") or sel)[:40], opts[:6])

            # ── 5c. Gemini maps all fields → exact values ─────────────────────
            answers = await ApplyService._ai_map_fields_static(fillable, ctx)

            # ── 5d. Fill every field ──────────────────────────────────────────
            for field in fillable:
                idx      = str(field.get("idx", ""))
                value    = answers.get(idx, "")
                selector = field.get("selector", "")
                ftype    = field.get("type", "text")
                label    = (field.get("label") or "").strip()

                if not value or selector.startswith("__idx__"):
                    continue

                try:
                    if ftype == "file":
                        if ctx.get("resume_pdf") and not resume_uploaded:
                            await browser.upload_file(page, selector, ctx["resume_pdf"])
                            resume_uploaded = True
                    elif selector in combobox_selectors:
                        svc = ApplyService.__new__(ApplyService)
                        await svc._interact_combobox(browser, page, selector, str(value), label)
                    elif len(str(value)) > 80:
                        await browser.fill_field(page, selector, str(value))
                    else:
                        await page.evaluate(_make_fill_js(selector, str(value), ftype))
                    await asyncio.sleep(0.15)
                except Exception as e:
                    logger.debug("ashby: fill failed [%s] %s: %s", ftype, label, e)

        # ── 6. Submit ─────────────────────────────────────────────────────────
        clicked = await browser.click_human(
            page,
            'button[type="submit"], input[type="submit"], [data-testid*="submit"]',
        )
        if not clicked:
            await browser.screenshot(page, "ashby_no_submit")
            return ApplyResult.fail("submit button not found")

        await asyncio.sleep(4)
        url_after = await browser.current_url(page)
        if await ApplyService._is_success_page_static(browser, page, url_after):
            return ApplyResult.ok(f"submitted — {url_after}")
        return ApplyResult.fail(f"no confirmation after submit — url: {url_after}")
