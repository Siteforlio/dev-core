"""
Rolling interview summariser.

Runs as a background asyncio task per session. Every SUMMARY_INTERVAL_S seconds,
it picks up new transcript bubbles since the last run, merges them into the
existing rolling summary, and extracts key facts. Both are stored in-memory
(in-process cache) so the LLM prompt always has full 2-hour context in ~375 tokens.

Three-layer context model injected into every LLM call:
  [key facts]        — named entities, tech, decisions  (~75 tokens, always current)
  [rolling summary]  — narrative of full interview      (~300 tokens, 2-min lag)
  [last 15 verbatim] — exact recent words               (~400 tokens, real-time)
"""
import asyncio
import logging
from app.services.cluely.context_manager import ContextManager

logger = logging.getLogger(__name__)

SUMMARY_INTERVAL_S = 120   # run every 2 minutes
MIN_NEW_BUBBLES    = 3     # don't summarise unless at least this many new bubbles


async def _call_deepseek(prompt: str) -> str:
    """One-shot DeepSeek call — not streamed, just returns text."""
    from app.services.cluely.deepseek_client import deepseek_generate
    return await deepseek_generate(prompt, temperature=0.3, max_tokens=600)


async def _update_summary(ctx_mgr: ContextManager) -> None:
    """Incremental update: summarise only new bubbles, merge into existing summary."""
    summarized_up_to = await ctx_mgr.get_summarized_index()
    total            = await ctx_mgr.get_total_count()
    new_count        = total - summarized_up_to

    if new_count < MIN_NEW_BUBBLES:
        return

    new_entries = await ctx_mgr.get_all_since(summarized_up_to)
    if not new_entries:
        return

    existing_summary = await ctx_mgr.get_summary()
    existing_facts   = await ctx_mgr.get_facts()

    new_text = "\n".join(f"{e.speaker}: {e.text}" for e in new_entries)

    # Build summary prompt — 400-word budget supports 2-hour interviews
    if existing_summary:
        summary_prompt = (
            "You are summarising a live job interview for an AI assistant.\n\n"
            f"EXISTING SUMMARY SO FAR:\n{existing_summary}\n\n"
            f"NEW CONVERSATION SINCE LAST SUMMARY:\n{new_text}\n\n"
            "Update the summary to include the new content. Keep it under 400 words. "
            "Write in third person (e.g. 'The interviewer asked...', 'The candidate explained...'). "
            "Preserve all important technical details, decisions, and topics discussed. "
            "Do not truncate existing important content — merge and compress instead."
        )
    else:
        summary_prompt = (
            "You are summarising a live job interview for an AI assistant.\n\n"
            f"CONVERSATION:\n{new_text}\n\n"
            "Summarise this interview conversation in under 400 words. "
            "Write in third person. Capture all technical topics, questions asked, "
            "and candidate responses. Be specific about technologies and decisions mentioned."
        )

    # Build key facts prompt — 150-word budget preserves structured detail across 2hrs
    facts_prompt = (
        "Extract key facts from this interview conversation as a compact bullet list.\n\n"
        f"EXISTING FACTS:\n{existing_facts}\n\n"
        f"NEW CONVERSATION:\n{new_text}\n\n"
        "Update the facts list. Include: programming languages, frameworks, tools mentioned; "
        "company tech stack details; role requirements stated; candidate's stated experience; "
        "any constraints or preferences expressed. "
        "Keep the entire list under 150 words. Remove duplicates. Be terse."
    )

    try:
        summary, facts = await asyncio.gather(
            _call_deepseek(summary_prompt),
            _call_deepseek(facts_prompt),
        )
        await ctx_mgr.set_summary(summary)
        await ctx_mgr.set_facts(facts)
        await ctx_mgr.set_summarized_index(total)
        logger.info("[summariser] updated — bubbles=%d summary_len=%d", total, len(summary))
    except Exception as e:
        logger.error("[summariser] failed: %s", e)


async def run_summarizer(ctx_mgr: ContextManager, stop_event: asyncio.Event) -> None:
    """
    Background task: run every SUMMARY_INTERVAL_S until stop_event is set.
    Designed to be launched with asyncio.create_task() from _start_session.
    """
    logger.info("[summariser] started for session %s", ctx_mgr._sid)
    try:
        while not stop_event.is_set():
            await asyncio.sleep(SUMMARY_INTERVAL_S)
            if stop_event.is_set():
                break
            await _update_summary(ctx_mgr)
    except asyncio.CancelledError:
        pass
    finally:
        # Final summary pass on session end so nothing is lost
        try:
            await _update_summary(ctx_mgr)
        except Exception:
            pass
        logger.info("[summariser] stopped for session %s", ctx_mgr._sid)
