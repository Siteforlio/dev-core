# board_appliers/greenhouse.py
"""
Greenhouse ATS applier — boards.greenhouse.io

Strategy:
  1. Seed stable structural fields (name/email/phone/links) via known selectors
  2. Upload resume
  3. Pre-read real options from every custom dropdown (React Select)
  4. Run Gemini to map ALL fields to exact values using real option lists
  5. Fill all fields — dropdowns via _interact_combobox, text via type_human
  6. Leave browser open for user to review and submit manually
     (Greenhouse forms often have reCAPTCHA and require a real person to confirm)
"""
from __future__ import annotations
import asyncio
import json
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)


class GreenhouseApplier(BaseBoardApplier):
    board_id = "greenhouse"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        from app.services.job_hunter.apply_service import (
            ApplyService, _SCAN_FIELDS_JS, _make_fill_js,
        )

        # ── 1. Seed stable structural fields ─────────────────────────────────
        first = (ctx.get("full_name") or "").split()[0]
        last  = " ".join((ctx.get("full_name") or "").split()[1:]) or "."
        for sel, val in [
            ('#first_name, input[name="first_name"]',                  first),
            ('#last_name,  input[name="last_name"]',                   last),
            ('#email,      input[name="email"]',                       ctx.get("email", "")),
            ('#phone,      input[name="phone"]',                       ctx.get("phone", "")),
            ('input[name*="linkedin"]',                                 ctx.get("linkedin_url", "")),
            ('input[name*="github"]',                                   ctx.get("github_url", "")),
            ('input[name*="website"], input[name*="portfolio"]',        ctx.get("portfolio_url", "")),
        ]:
            if not val:
                continue
            try:
                await browser.type_human(page, sel, val)
            except Exception:
                pass

        # ── 2. Location (City) — Google Places autocomplete ───────────────────
        # Type city, wait for Places dropdown, click first suggestion.
        city = ctx.get("city", "")
        if city:
            for city_sel in [
                'input[id*="candidate_location"], input[id*="location_autocomplete"]',
                'input[name*="location"]',
                'input[placeholder*="City"], input[placeholder*="city"]',
                'input[placeholder*="Location"]',
            ]:
                try:
                    await browser.type_human(page, city_sel, city)
                    await asyncio.sleep(1.5)  # wait for Places suggestions
                    # Click first suggestion in the pac-container
                    clicked = await page.evaluate("""
                        (function() {
                            var item = document.querySelector(
                                '.pac-container .pac-item, [role="listbox"] [role="option"]'
                            );
                            if (item) { item.click(); return true; }
                            return false;
                        })()
                    """)
                    if clicked:
                        await asyncio.sleep(0.5)
                    break
                except Exception:
                    pass

        # ── 3. Upload resume ──────────────────────────────────────────────────
        resume_uploaded = False
        if ctx.get("resume_pdf"):
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                resume_uploaded = True
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # ── 4. Cover letter textarea ──────────────────────────────────────────
        if ctx.get("cover_letter"):
            for csel in ['textarea[name*="cover"]', 'textarea[name*="letter"]',
                         '#cover_letter', 'textarea.cover-letter']:
                try:
                    await browser.fill_field(page, csel, ctx["cover_letter"])
                    break
                except Exception:
                    pass

        # ── 5. Scan all remaining fields ──────────────────────────────────────
        await asyncio.sleep(1.0)
        raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(raw) if isinstance(raw, str) else (raw or [])
        fillable = [f for f in fields if not str(f.get("selector", "")).startswith("__idx__")]

        if fillable:
            # ── 5a. Detect combobox fields ────────────────────────────────────
            combobox_selectors: set[str] = set()
            for i, f in enumerate(fields):
                nxt = fields[i + 1] if i + 1 < len(fields) else None
                if (nxt and str(nxt.get("selector", "")).startswith("__idx__")
                        and nxt.get("required")):
                    sel = f.get("selector", "")
                    if sel and not sel.startswith("__idx__"):
                        combobox_selectors.add(sel)

            # ── 5b. Pre-read real dropdown options so Gemini gets exact choices ─
            if combobox_selectors:
                logger.info("greenhouse: pre-reading %d combobox(es)", len(combobox_selectors))
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

            # ── 5c. Gemini maps every field to exact value ────────────────────
            answers = await ApplyService._ai_map_fields_static(fillable, ctx)

            # ── 5d. Fill fields ───────────────────────────────────────────────
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
                        await ApplyService._read_combobox_options_static  # ensure import
                        svc = ApplyService.__new__(ApplyService)
                        await svc._interact_combobox(browser, page, selector, str(value), label)
                    elif len(str(value)) > 80:
                        await browser.fill_field(page, selector, str(value))
                    else:
                        await page.evaluate(_make_fill_js(selector, str(value), ftype))
                    await asyncio.sleep(0.15)
                except Exception as e:
                    logger.debug("greenhouse: fill failed [%s] %s: %s", ftype, label, e)

        # ── 6. Prefill complete — leave browser open for user ─────────────────
        # Greenhouse forms may have reCAPTCHA or multi-step verification that
        # requires a human to complete. We surface ApplyResult.skip() so the
        # caller knows the form was prefilled but NOT submitted.
        logger.info("greenhouse: prefill complete — leaving for user review")
        return ApplyResult.skip(
            "Greenhouse form prefilled — user must review and submit "
            "(reCAPTCHA or multi-step verification required)"
        )


async def _is_success(browser, page, url: str) -> bool:
    from app.services.job_hunter.apply_service import ApplyService
    return await ApplyService._is_success_page_static(browser, page, url)
