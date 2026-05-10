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

MAX_TOOL_STEPS = 5

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
            "description": "Read the text content of a file from the project. Requires a project root to be configured.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file, relative to the project root",
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
            "description": "Write or overwrite a file in the project with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file"},
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
            "description": "List files and directories in the project. Use to explore structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to list (defaults to project root '.')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Take a screenshot of the user's screen and extract its text via OCR. Use to read what's currently visible on screen.",
            "parameters": {"type": "object", "properties": {}},
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
        has_file = self._file is not None
        has_project = bool(self._ctx.get("projectRoot") or self._ctx.get("project_root"))

        parts = [
            "You are a highly capable AI assistant embedded in an overlay window during a live session. "
            "You have access to tools: terminal (run commands), web search, file read/write, "
            "screen capture (OCR), and browser. "
            "Use tools whenever the user's request requires real information or action — "
            "don't refuse, just act. After using tools, give a clear, direct answer. "
            "Be concise. Never ask for clarification you don't need.",
        ]
        if company or role:
            parts.append(f"Session context: {role or 'unknown role'} at {company or 'unknown company'}.")
        if mode:
            parts.append(f"Session mode: {mode}.")
        if not has_file or not has_project:
            parts.append(
                "Note: file tools (read_file, write_file, list_files) require a project root "
                "configured at session start. If unavailable, say so briefly."
            )
        return " ".join(parts)

    async def handle(
        self,
        user_text: str,
        rag_chunks: list[str],
        summary: str,
        facts: str,
        recent: list,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator — yields text deltas for the final streamed answer.
        Emits tool:event WS frames via self._send during the tool loop.
        """
        # Build initial messages
        system = self._system_prompt()
        context_block = _build_context_block(facts, summary, recent, rag_chunks)
        user_content = user_text
        if context_block:
            user_content = f"{context_block}\n\nUser: {user_text}"

        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

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
                return await self._run_capture_screen()
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

        try:
            cmd = shlex.split(command_str)
        except ValueError:
            cmd = command_str.split()

        lines: list[str] = []
        async for ev in self._terminal.run(cmd, working_dir=working_dir):
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
        if not self._file:
            return "[file tool unavailable — no project root configured]"
        await self._send(_tool_event("file", "start", {"path": path, "action": "read"}))
        try:
            content = await self._file.read_file(path)
            await self._send(_tool_event("file", "done", {"path": path, "chars": len(content)}))
            return content
        except PathEscapeError as e:
            await self._send(_tool_event("file", "error", {"error": e.message}))
            return f"[access denied: {e.message}]"

    async def _run_write_file(self, args: dict) -> str:
        path = args.get("path", "")
        content = args.get("content", "")
        if not self._file:
            return "[file tool unavailable — no project root configured]"
        await self._send(_tool_event("file", "start", {"path": path, "action": "write"}))
        try:
            await self._file.write_file(path, content)
            await self._send(_tool_event("file", "done", {"path": path, "wrote": len(content)}))
            return f"Written {len(content)} chars to {path}"
        except PathEscapeError as e:
            await self._send(_tool_event("file", "error", {"error": e.message}))
            return f"[access denied: {e.message}]"

    async def _run_list_files(self, args: dict) -> str:
        path = args.get("path", ".")
        if not self._file:
            return "[file tool unavailable — no project root configured]"
        await self._send(_tool_event("file", "start", {"path": path, "action": "list"}))
        files = await self._file.list_directory(path, depth=2)
        await self._send(_tool_event("file", "done", {"files": files[:50]}))
        return "\n".join(files[:50]) or "[empty directory]"

    async def _run_capture_screen(self) -> str:
        await self._send(_tool_event("screen", "start"))
        text = await self._screen.capture_and_extract()
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
