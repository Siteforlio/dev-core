"""
chat_agent.py — Tool-augmented natural language chat for all session modes.

The user types naturally ("read main.py", "run the tests", "search for X").
The agent uses DeepSeek function-calling to decide which tools to invoke,
executes them, feeds results back, and streams a final answer.

ReAct loop (max MAX_TOOL_STEPS rounds):
  1. Call DeepSeek with tool schemas + conversation history
  2. If tool_calls → execute each tool, emit tool:event over WS, append result
  3. Repeat until no tool_calls or max steps reached
  4. Stream final text answer token-by-token
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import time
from typing import AsyncGenerator, Callable

from app.services.cluely.terminal_service import TerminalService
from app.services.cluely.browser_service import BrowserService
from app.services.cluely.screen_service import ScreenService
from app.services.cluely.file_service import FileService, PathEscapeError
from app.services.cluely.search_service import SearchService
from app.services.cluely.deepseek_client import deepseek_with_tools, deepseek_stream_messages

logger = logging.getLogger(__name__)

MAX_TOOL_STEPS = 8

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": (
                "Run a shell command and capture its stdout/stderr. "
                "Use for executing code, running tests, builds, or any CLI operation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run (e.g. 'python main.py', 'npm test', 'git status')",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory path",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return top result snippets. Use for looking up docs, errors, or current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full text content of a single file. "
                "Accepts absolute paths (e.g. C:\\Users\\...\\file.py) or relative paths when a project root is set. "
                "To explore a folder first, call list_files, then read individual files. "
                "You can call read_file multiple times to read several files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with the given content. Accepts absolute or relative paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to the file"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List all files in a directory tree (up to 2 levels deep). "
                "Use this to explore a project's folder structure before deciding which files to read. "
                "Accepts absolute paths (e.g. C:\\Users\\...\\my-project) or relative paths. "
                "After listing, call read_file on the relevant files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the directory to list",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": (
                "Take a screenshot of the user's screen and understand it with AI vision. "
                "Can answer specific questions about what's visible — tabs, windows, UI elements, text, counts, etc. "
                "Pass the user's exact question as the 'question' parameter for best results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Specific question to ask about the screen, e.g. 'How many browser tabs are open?' or 'What application is in focus?'",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Open a URL in a headless browser and extract its readable text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to open (must start with http/https)"},
                },
                "required": ["url"],
            },
        },
    },
]


def _tool_event(tool: str, status: str, data: dict | None = None) -> dict:
    return {
        "type": "tool:event",
        "tool": tool,
        "status": status,
        "data": data or {},
        "ts": int(time.time() * 1000),
    }


class ChatAgent:
    """
    Stateless agent that handles a single chat message with full tool access.

    Parameters
    ----------
    session_ctx   : the overlay session context dict (has company, role, etc.)
    send          : async callable(dict) — sends a WS event to the overlay
    file_service  : optional FileService scoped to the user's project
    """

    def __init__(
        self,
        session_ctx: dict,
        send: Callable[[dict], asyncio.Future],
        file_service: FileService | None = None,
    ) -> None:
        self._ctx = session_ctx
        self._send = send
        self._terminal = TerminalService()
        self._browser = BrowserService()
        self._screen = ScreenService()
        self._search = SearchService()
        self._file = file_service

    def _system_prompt(self) -> str:
        company = self._ctx.get("company", "")
        role = self._ctx.get("job_title", "")
        mode = self._ctx.get("assessmentMode") or self._ctx.get("assessment_mode", "")
        resume_text   = self._ctx.get("resume_text", "")[:600]
        jd_text       = self._ctx.get("jd_text", "")[:400]
        extra_context = self._ctx.get("extra_context", "")

        # Always speak AS the user — first person, in their voice.
        # Context tells us what situation they're in. No context = general conversation.
        # The rule is absolute: never answer as an AI, always as the person.
        if role or company:
            situation_parts = ["You are in a live job interview"]
            if role:    situation_parts.append(f"for {role}")
            if company: situation_parts.append(f"at {company}")
            situation = " ".join(situation_parts) + "."
        elif extra_context:
            situation = "You are in a live session."
        else:
            situation = "You are in a live conversation."

        parts = [
            f"{situation} "
            "Speak entirely in the first person as the person being asked — "
            "naturally, confidently, as if saying this aloud. "
            "Never identify as an AI. Never say 'as an AI' or 'I can help with that'. "
            "No bullet points, no preamble, no meta-commentary unless explicitly asked. "
            "You also have tools (terminal, web search, file read/write, screen capture, browser) — "
            "use them silently when the request needs real information or action, then speak the answer as yourself.",
        ]
        if resume_text:
            parts.append(f"Resume: {resume_text}.")
        if jd_text:
            parts.append(f"Job description: {jd_text}.")

        if mode:
            parts.append(f"Session mode: {mode}.")
        if extra_context:
            parts.append(f"ADDITIONAL CONTEXT DOCUMENTS:\n{extra_context}")
        parts.append(
            "File tools accept absolute paths directly (e.g. C:\\Users\\...\\file.txt or /home/user/file.txt). "
            "If the user mentions a file path in their message, extract it and use the file tool immediately — "
            "do NOT ask them to provide it again."
        )
        return " ".join(parts)

    async def handle(
        self,
        user_text: str,
        rag_chunks: list[str],
        summary: str,
        facts: str,
        recent: list,
        chat_history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator — yields text deltas for the final streamed answer.
        Emits tool:event WS frames via self._send during the tool loop.

        chat_history: list of {role: 'user'|'assistant', text: str} from
        the frontend — prior turns in this chat session.
        """
        system = self._system_prompt()
        context_block = _build_context_block(facts, summary, recent, rag_chunks)

        messages: list[dict] = [{"role": "system", "content": system}]

        # Inject prior chat turns so the AI remembers the conversation
        if chat_history:
            for turn in chat_history:
                role = turn.get("role", "user")
                text = turn.get("text", "")
                if text:
                    messages.append({"role": role, "content": text})

        # Current user message — prepend context block on first or only message
        user_content = user_text
        if context_block and not chat_history:
            user_content = f"{context_block}\n\nUser: {user_text}"

        messages.append({"role": "user", "content": user_content})

        # ReAct loop
        for step in range(MAX_TOOL_STEPS):
            try:
                choice = await deepseek_with_tools(messages, _TOOL_SCHEMAS, temperature=0.4, max_tokens=1024)
            except Exception as e:
                logger.error("[chat_agent] LLM call failed: %s", e)
                yield "Sorry, I couldn't reach the AI. Please try again."
                return

            assistant_msg = choice["message"]
            tool_calls = assistant_msg.get("tool_calls") or []

            if not tool_calls:
                # Final answer — stream it
                # The non-streaming call already gave us the full text; stream it char by char
                # for consistent UX. Or re-call with streaming using the full conversation.
                messages.append({"role": "assistant", "content": assistant_msg.get("content", "")})
                # Re-run as streaming for proper token-by-token feel
                break

            # Append the assistant message (with tool_calls) to history
            messages.append(assistant_msg)

            # Execute each tool call
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tc_id = tc.get("id", fn_name)

                result_text = await self._execute_tool(fn_name, args)

                # Append tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_text,
                })

        # Stream final answer
        # Build a clean final-answer message set (no tool schemas needed now)
        # Use last assistant content if the loop ended with no tool_calls
        last = messages[-1]
        if last.get("role") == "assistant" and last.get("content"):
            # Already have the final text — just yield it
            yield last["content"]
            return

        # Otherwise stream from the full conversation
        try:
            async for delta in deepseek_stream_messages(messages, temperature=0.7, max_tokens=512):
                yield delta
        except Exception as e:
            logger.error("[chat_agent] streaming failed: %s", e)
            yield "An error occurred generating the response."

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool and return its result as a string. Also fires WS tool events."""
        try:
            if name == "run_terminal":
                return await self._run_terminal(args)
            elif name == "web_search":
                return await self._run_search(args)
            elif name == "read_file":
                return await self._run_read_file(args)
            elif name == "write_file":
                return await self._run_write_file(args)
            elif name == "list_files":
                return await self._run_list_files(args)
            elif name == "capture_screen":
                return await self._run_capture_screen(args)
            elif name == "browse_url":
                return await self._run_browse(args)
            else:
                return f"[unknown tool: {name}]"
        except Exception as e:
            logger.warning("[chat_agent] tool %s failed: %s", name, e)
            return f"[tool error: {e}]"

    async def _run_terminal(self, args: dict) -> str:
        command_str = args.get("command", "")
        working_dir = args.get("working_dir") or None

        await self._send(_tool_event("terminal", "start", {"command": command_str}))

        lines: list[str] = []
        async for ev in self._terminal.run(command_str, working_dir=working_dir):
            await self._send(_tool_event("terminal", "data", ev))
            lines.append(f"[{ev.get('stream','')}] {ev.get('text','')}")

        result = "\n".join(lines)
        await self._send(_tool_event("terminal", "done", {"lines": len(lines)}))
        return result or "[no output]"

    async def _run_search(self, args: dict) -> str:
        query = args.get("query", "")
        await self._send(_tool_event("search", "start", {"query": query}))
        snippets = await self._search.search(query, num=3)
        await self._send(_tool_event("search", "done", {"results": snippets}))
        return "\n\n".join(snippets) if snippets else "[no results]"

    async def _run_read_file(self, args: dict) -> str:
        path = args.get("path", "")
        await self._send(_tool_event("file", "start", {"path": path, "action": "read"}))
        # Absolute path — read directly without FileService scoping
        if os.path.isabs(path):
            return await self._read_absolute(path)
        if not self._file:
            return "[file tool unavailable — provide an absolute path or configure a project root at session start]"
        try:
            content = await self._file.read_file(path)
            await self._send(_tool_event("file", "done", {"path": path, "chars": len(content), "content": content[:2000]}))
            return content
        except PathEscapeError as e:
            await self._send(_tool_event("file", "error", {"error": e.message}))
            return f"[access denied: {e.message}]"

    async def _read_absolute(self, path: str) -> str:
        import asyncio as _asyncio
        def _read():
            import os as _os
            if not _os.path.isfile(path):
                return f"[file not found: {path}]"
            size = _os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(256 * 1024)
            if size > 256 * 1024:
                content += f"\n# [truncated — file is {size} bytes]"
            return content
        content = await _asyncio.to_thread(_read)
        await self._send(_tool_event("file", "done", {"path": path, "chars": len(content), "content": content[:2000]}))
        return content

    async def _run_write_file(self, args: dict) -> str:
        path = args.get("path", "")
        content = args.get("content", "")
        await self._send(_tool_event("file", "start", {"path": path, "action": "write"}))
        if os.path.isabs(path):
            import asyncio as _asyncio
            def _write():
                import os as _os
                _os.makedirs(_os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            await _asyncio.to_thread(_write)
            await self._send(_tool_event("file", "done", {"path": path, "wrote": len(content)}))
            return f"Written {len(content)} chars to {path}"
        if not self._file:
            return "[file tool unavailable — provide an absolute path or configure a project root at session start]"
        try:
            await self._file.write_file(path, content)
            await self._send(_tool_event("file", "done", {"path": path, "wrote": len(content)}))
            return f"Written {len(content)} chars to {path}"
        except PathEscapeError as e:
            await self._send(_tool_event("file", "error", {"error": e.message}))
            return f"[access denied: {e.message}]"

    async def _run_list_files(self, args: dict) -> str:
        path = args.get("path", ".")
        await self._send(_tool_event("file", "start", {"path": path, "action": "list"}))
        if os.path.isabs(path):
            import asyncio as _asyncio
            def _list():
                import os as _os
                results = []
                # Noisy dirs to skip — but keep dotfiles like .env
                _SKIP_DIRS = {"__pycache__", "node_modules", ".git", "venv", ".venv", ".mypy_cache", "dist", "build", ".next"}
                for root, dirs, files in _os.walk(path):
                    dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                    depth = root.replace(path, "").count(_os.sep)
                    if depth >= 2:
                        dirs.clear()
                        continue
                    for fname in files:
                        results.append(_os.path.join(root, fname).replace(path, "").lstrip(_os.sep))
                return sorted(results)
            files = await _asyncio.to_thread(_list)
            listing = "\n".join(files[:80]) or "[empty directory]"
            await self._send(_tool_event("file", "done", {"files": files[:80], "listing": listing}))
            return listing
        if not self._file:
            return "[file tool unavailable — provide an absolute path or configure a project root at session start]"
        files = await self._file.list_directory(path, depth=2)
        listing = "\n".join(files[:50]) or "[empty directory]"
        await self._send(_tool_event("file", "done", {"files": files[:50], "listing": listing}))
        return listing

    async def _run_capture_screen(self, args: dict | None = None) -> str:
        question = (args or {}).get("question", "")
        await self._send(_tool_event("screen", "start"))
        text = await self._screen.capture_and_extract(question=question)
        await self._send(_tool_event("screen", "done", {"preview": text[:200], "text": text}))
        return text or "[screen capture returned no text]"

    async def _run_browse(self, args: dict) -> str:
        url = args.get("url", "")
        await self._send(_tool_event("browser", "start", {"url": url}))
        try:
            text = await self._browser.fetch_text(url)
            await self._send(_tool_event("browser", "done", {"url": url, "chars": len(text)}))
            return text[:3000] or "[no content extracted]"
        except Exception as e:
            await self._send(_tool_event("browser", "error", {"error": str(e)}))
            return f"[browser error: {e}]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_context_block(facts: str, summary: str, recent: list, rag_chunks: list[str]) -> str:
    parts = []
    if facts:
        parts.append(f"KEY FACTS:\n{facts}")
    if summary:
        parts.append(f"SESSION SUMMARY:\n{summary}")
    if recent:
        history = "\n".join(
            f"{e.speaker}: {e.text}" for e in recent
            if hasattr(e, "speaker") and hasattr(e, "text")
        )
        if history:
            parts.append(f"RECENT CONVERSATION:\n{history}")
    if rag_chunks:
        parts.append(f"RELEVANT CONTEXT:\n{chr(10).join(rag_chunks)}")
    return "\n\n".join(parts)
