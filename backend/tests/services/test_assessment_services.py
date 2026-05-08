"""
Unit tests for assessment-mode services:
  - TerminalService
  - ScreenService
  - BrowserService (_parse_input_output, graceful degradation)
  - FileService     (path sandboxing, read/write/patch/list/search)
  - AssessmentAgent (utility functions + agent logic via mocks)

All network, subprocess, and filesystem calls are mocked so tests run
offline and without any real binaries.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_png_b64() -> str:
    """Return a minimal valid base64-encoded 1x1 PNG."""
    try:
        from PIL import Image as _Image  # type: ignore
        buf = io.BytesIO()
        img = _Image.new("RGB", (1, 1), color=(0, 0, 0))
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # If Pillow not installed, return empty — tests skip where needed
        return ""


# ===========================================================================
# TerminalService
# ===========================================================================

class TestTerminalService:

    @pytest.mark.asyncio
    async def test_run_yields_stdout(self):
        """A command that prints to stdout should produce stdout events."""
        from app.services.cluely.terminal_service import TerminalService

        events = []
        async for ev in TerminalService().run([sys.executable, "-c", "print('hello')"]):
            events.append(ev)

        stdout_texts = [e["text"] for e in events if e["stream"] == "stdout"]
        assert any("hello" in t for t in stdout_texts)

    @pytest.mark.asyncio
    async def test_run_yields_stderr(self):
        """A command that writes to stderr should produce stderr events."""
        from app.services.cluely.terminal_service import TerminalService

        events = []
        async for ev in TerminalService().run(
            [sys.executable, "-c", "import sys; sys.stderr.write('oops\\n')"]
        ):
            events.append(ev)

        stderr_texts = [e["text"] for e in events if e["stream"] == "stderr"]
        assert any("oops" in t for t in stderr_texts)

    @pytest.mark.asyncio
    async def test_run_exit_event(self):
        """Last event must be a system exit line."""
        from app.services.cluely.terminal_service import TerminalService

        events = []
        async for ev in TerminalService().run([sys.executable, "-c", "pass"]):
            events.append(ev)

        last = events[-1]
        assert last["stream"] == "system"
        assert "exit" in last["text"].lower()

    @pytest.mark.asyncio
    async def test_run_command_not_found(self):
        """Running a nonexistent binary yields a system error event, not an exception."""
        from app.services.cluely.terminal_service import TerminalService

        events = []
        async for ev in TerminalService().run(["__nonexistent_binary__"]):
            events.append(ev)

        system_texts = " ".join(e["text"] for e in events if e["stream"] == "system")
        assert "not found" in system_texts.lower() or "command" in system_texts.lower()

    @pytest.mark.asyncio
    async def test_run_invalid_working_dir(self):
        """Passing a non-existent working_dir yields a system error, no exception."""
        from app.services.cluely.terminal_service import TerminalService

        events = []
        async for ev in TerminalService().run(
            [sys.executable, "-c", "pass"],
            working_dir="/this/does/not/exist/xyz"
        ):
            events.append(ev)

        system_texts = " ".join(e["text"] for e in events if e["stream"] == "system")
        assert "does not exist" in system_texts.lower()

    @pytest.mark.asyncio
    async def test_run_events_have_required_fields(self):
        """Every event must have stream, text, timestamp_ms, and cwd fields."""
        from app.services.cluely.terminal_service import TerminalService

        async for ev in TerminalService().run([sys.executable, "-c", "print('x')"]):
            assert "stream" in ev
            assert "text" in ev
            assert "timestamp_ms" in ev
            assert "cwd" in ev

    def test_resolve_cwd_expands_tilde(self):
        """_resolve_cwd should expand ~ to home directory."""
        from app.services.cluely.terminal_service import _resolve_cwd
        result = _resolve_cwd("~")
        assert os.path.isdir(result)
        assert "~" not in result

    def test_resolve_cwd_rejects_missing(self):
        from app.services.cluely.terminal_service import _resolve_cwd
        with pytest.raises(ValueError, match="does not exist"):
            _resolve_cwd("/no/such/directory/abc123")


# ===========================================================================
# ScreenService
# ===========================================================================

class TestScreenService:

    def test_available_false_when_deps_missing(self):
        """ScreenService.available should be False if mss/pytesseract not importable."""
        from app.services.cluely import screen_service
        # Patch the module-level globals to simulate missing deps
        with patch.object(screen_service, "_mss", None), \
             patch.object(screen_service, "_pytesseract", None):
            from app.services.cluely.screen_service import ScreenService
            svc = ScreenService()
            assert not svc.available

    @pytest.mark.asyncio
    async def test_capture_base64_returns_empty_when_unavailable(self):
        """capture_base64 returns '' when deps are missing."""
        from app.services.cluely import screen_service
        with patch.object(screen_service, "_mss", None):
            from app.services.cluely.screen_service import ScreenService
            svc = ScreenService()
            result = await svc.capture_base64()
            assert result == ""

    @pytest.mark.asyncio
    async def test_extract_text_returns_empty_when_unavailable(self):
        """extract_text returns '' when deps are missing."""
        from app.services.cluely import screen_service
        with patch.object(screen_service, "_mss", None), \
             patch.object(screen_service, "_pytesseract", None):
            from app.services.cluely.screen_service import ScreenService
            svc = ScreenService()
            result = await svc.extract_text("fakeb64")
            assert result == ""

    @pytest.mark.asyncio
    async def test_stitch_and_extract_deduplicates_lines(self):
        """stitch_and_extract must not repeat lines that appear in multiple images."""
        from app.services.cluely.screen_service import ScreenService

        svc = ScreenService()
        # Mock extract_text to simulate overlapping OCR output
        svc.extract_text = AsyncMock(side_effect=[
            "Line A\nLine B\nLine C",
            "Line B\nLine C\nLine D",  # B and C overlap
        ])

        result = await svc.stitch_and_extract(["img1", "img2"])
        lines = [l for l in result.splitlines() if l.strip()]

        assert lines.count("Line B") == 1, "Duplicate 'Line B' should be removed"
        assert lines.count("Line C") == 1, "Duplicate 'Line C' should be removed"
        assert "Line A" in result
        assert "Line D" in result

    @pytest.mark.asyncio
    async def test_stitch_empty_list(self):
        """stitch_and_extract returns '' for an empty image list."""
        from app.services.cluely.screen_service import ScreenService
        result = await ScreenService().stitch_and_extract([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_capture_and_extract_chains_calls(self):
        """capture_and_extract calls capture_base64 then extract_text."""
        from app.services.cluely.screen_service import ScreenService

        svc = ScreenService()
        svc.capture_base64 = AsyncMock(return_value="fakeb64")
        svc.extract_text   = AsyncMock(return_value="extracted text")

        result = await svc.capture_and_extract()
        svc.capture_base64.assert_called_once_with(1)
        svc.extract_text.assert_called_once_with("fakeb64")
        assert result == "extracted text"


# ===========================================================================
# BrowserService — unit-testable logic (no real browser)
# ===========================================================================

class TestBrowserServiceParsing:

    def test_parse_input_output_leetcode_format(self):
        """Standard LeetCode Input/Output blocks should parse correctly."""
        from app.services.cluely.browser_service import _parse_input_output
        text = """
Example 1:
Input: nums = [2,7,11,15], target = 9
Output: [0,1]

Example 2:
Input: nums = [3,2,4], target = 6
Output: [1,2]
"""
        cases = _parse_input_output(text)
        assert len(cases) >= 1
        assert any("9" in c["input"] or "6" in c["input"] for c in cases)
        assert any("[0,1]" in c["output"] or "[1,2]" in c["output"] for c in cases)

    def test_parse_input_output_empty(self):
        from app.services.cluely.browser_service import _parse_input_output
        assert _parse_input_output("no input output pairs here") == []

    def test_parse_input_output_caps_at_10(self):
        from app.services.cluely.browser_service import _parse_input_output
        # Generate 12 pairs
        text = ""
        for i in range(12):
            text += f"Input: {i}\nOutput: {i*2}\n\n"
        cases = _parse_input_output(text)
        assert len(cases) <= 10

    @pytest.mark.asyncio
    async def test_ensure_browser_returns_none_when_playwright_missing(self):
        """When playwright is not importable, _browser stays None."""
        from app.services.cluely.browser_service import BrowserService
        svc = BrowserService()
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            with patch("builtins.__import__", side_effect=ImportError("no playwright")):
                await svc._ensure_browser()
        # No exception raised — browser simply stays None
        assert svc._browser is None

    @pytest.mark.asyncio
    async def test_fetch_text_returns_empty_without_browser(self):
        from app.services.cluely.browser_service import BrowserService
        svc = BrowserService()
        svc._ensure_browser = AsyncMock()   # does nothing — browser stays None
        result = await svc.fetch_text("http://example.com")
        assert result == ""

    @pytest.mark.asyncio
    async def test_close_is_safe_with_no_browser(self):
        from app.services.cluely.browser_service import BrowserService
        svc = BrowserService()
        await svc.close()  # must not raise


# ===========================================================================
# FileService — path sandboxing + CRUD
# ===========================================================================

class TestFileService:

    @pytest.fixture
    def tmp_project(self, tmp_path: Path) -> Path:
        """Create a temporary project directory with some files."""
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "utils.py").write_text("def add(a, b): return a + b\n")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "helper.py").write_text("# helper\n")
        return tmp_path

    def make_service(self, tmp_project: Path):
        from app.services.cluely.file_service import FileService
        return FileService(str(tmp_project))

    # ---- construction -------------------------------------------------------

    def test_init_raises_for_missing_root(self):
        from app.services.cluely.file_service import FileService
        with pytest.raises(ValueError, match="does not exist"):
            FileService("/no/such/path/xyz")

    # ---- path sandboxing ----------------------------------------------------

    def test_path_escape_rejected(self, tmp_project: Path):
        from app.services.cluely.file_service import FileService, PathEscapeError
        svc = self.make_service(tmp_project)
        with pytest.raises(PathEscapeError):
            svc._safe_resolve("../../etc/passwd")

    def test_absolute_path_outside_root_rejected(self, tmp_project: Path):
        from app.services.cluely.file_service import FileService, PathEscapeError
        svc = self.make_service(tmp_project)
        other = tempfile.mkdtemp()
        with pytest.raises(PathEscapeError):
            svc._safe_resolve(other)

    def test_safe_resolve_stays_within_root(self, tmp_project: Path):
        from app.services.cluely.file_service import FileService
        svc = self.make_service(tmp_project)
        resolved = svc._safe_resolve("main.py")
        assert resolved == tmp_project / "main.py"

    # ---- read_file ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_read_file_returns_content(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        content = await svc.read_file("main.py")
        assert "hello" in content

    @pytest.mark.asyncio
    async def test_read_file_missing_returns_placeholder(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        content = await svc.read_file("does_not_exist.py")
        assert "not found" in content.lower()

    # ---- write_file ---------------------------------------------------------

    @pytest.mark.asyncio
    async def test_write_file_creates_file(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        await svc.write_file("new_file.py", "x = 42\n")
        assert (tmp_project / "new_file.py").read_text() == "x = 42\n"

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        await svc.write_file("deep/nested/file.py", "y = 1\n")
        assert (tmp_project / "deep" / "nested" / "file.py").exists()

    @pytest.mark.asyncio
    async def test_write_file_escape_rejected(self, tmp_project: Path):
        from app.services.cluely.file_service import PathEscapeError
        svc = self.make_service(tmp_project)
        with pytest.raises(PathEscapeError):
            await svc.write_file("../../evil.py", "rm -rf /")

    # ---- list_directory -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_directory_returns_files(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        files = await svc.list_directory(".")
        names = [Path(f).name for f in files]
        assert "main.py" in names
        assert "utils.py" in names

    @pytest.mark.asyncio
    async def test_list_directory_prunes_pycache(self, tmp_project: Path):
        pycache = tmp_project / "__pycache__"
        pycache.mkdir()
        (pycache / "junk.pyc").write_bytes(b"\x00")
        svc = self.make_service(tmp_project)
        files = await svc.list_directory(".")
        assert not any("__pycache__" in f for f in files)

    @pytest.mark.asyncio
    async def test_list_directory_respects_depth(self, tmp_project: Path):
        deep = tmp_project / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("pass")
        svc = self.make_service(tmp_project)
        files = await svc.list_directory(".", depth=2)
        # With depth=2, 'a/b/c/deep.py' at depth 3 should not appear
        assert not any("deep.py" in f for f in files)

    # ---- patch_file ---------------------------------------------------------

    @pytest.mark.asyncio
    async def test_patch_file_replaces_lines(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        await svc.patch_file("main.py", start_line=1, end_line=1, new_content="print('patched')\n")
        content = (tmp_project / "main.py").read_text()
        assert "patched" in content
        assert "hello" not in content

    @pytest.mark.asyncio
    async def test_patch_file_missing_raises(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        with pytest.raises(FileNotFoundError):
            await svc.patch_file("ghost.py", 1, 1, "pass\n")

    # ---- search_in_files ----------------------------------------------------

    @pytest.mark.asyncio
    async def test_search_finds_pattern(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        results = await svc.search_in_files("def add")
        assert len(results) >= 1
        assert any("utils.py" in r["file"] for r in results)

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        results = await svc.search_in_files("DEF ADD")
        assert any("utils.py" in r["file"] for r in results)

    @pytest.mark.asyncio
    async def test_search_no_match_returns_empty(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        results = await svc.search_in_files("zzznomatch_xyz")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self, tmp_project: Path):
        svc = self.make_service(tmp_project)
        # Write a file with 25 matching lines
        many = "\n".join(f"# match line {i}" for i in range(25))
        (tmp_project / "many.py").write_text(many)
        results = await svc.search_in_files("match line", max_results=5)
        assert len(results) <= 5


# ===========================================================================
# AssessmentAgent — utility functions (no LLM, no network)
# ===========================================================================

class TestAssessmentAgentUtils:

    def test_strip_code_fences_removes_fences(self):
        from app.services.cluely.assessment_agent import _strip_code_fences
        raw = "```python\nprint('hello')\n```"
        assert _strip_code_fences(raw) == "print('hello')"

    def test_strip_code_fences_no_fences(self):
        from app.services.cluely.assessment_agent import _strip_code_fences
        raw = "print('hello')"
        assert _strip_code_fences(raw) == raw

    def test_parse_test_cases_standard(self):
        from app.services.cluely.assessment_agent import _parse_test_cases_from_text
        text = (
            "Example 1:\n"
            "Input: nums = [1,2,3], target = 4\n"
            "Output: [0,2]\n\n"
            "Example 2:\n"
            "Input: nums = [5,6], target = 11\n"
            "Output: [0,1]\n"
        )
        cases = _parse_test_cases_from_text(text)
        assert len(cases) >= 1
        assert any("target" in c["input"] for c in cases)

    def test_parse_test_cases_caps_at_5(self):
        from app.services.cluely.assessment_agent import _parse_test_cases_from_text
        text = ""
        for i in range(8):
            text += f"Input: {i}\nOutput: {i*2}\n\n"
        cases = _parse_test_cases_from_text(text)
        assert len(cases) <= 5

    def test_parse_test_cases_empty_text(self):
        from app.services.cluely.assessment_agent import _parse_test_cases_from_text
        assert _parse_test_cases_from_text("") == []

    def test_extract_problem_name_leetcode_format(self):
        from app.services.cluely.assessment_agent import _extract_problem_name
        text = "1. Two Sum\nGiven an array of integers..."
        assert _extract_problem_name(text) == "Two Sum"

    def test_extract_problem_name_problem_keyword(self):
        from app.services.cluely.assessment_agent import _extract_problem_name
        text = "Problem: Longest Substring Without Repeating Characters"
        name = _extract_problem_name(text)
        assert name is not None
        assert "Longest" in name

    def test_extract_problem_name_falls_back_to_first_line(self):
        from app.services.cluely.assessment_agent import _extract_problem_name
        # Avoid words like "Title" or "Problem" which trigger keyword patterns
        text = "Maximum Subarray Sum\nGiven an array of integers, find the contiguous subarray..."
        assert _extract_problem_name(text) == "Maximum Subarray Sum"

    def test_extract_problem_name_empty(self):
        from app.services.cluely.assessment_agent import _extract_problem_name
        assert _extract_problem_name("") is None

    def test_build_run_script_creates_file(self):
        from app.services.cluely.assessment_agent import _build_run_script
        script, cmd, cwd = _build_run_script("print('hi')", "python", stdin="")
        assert os.path.isfile(script)
        assert cmd[0] == sys.executable
        assert script in cmd
        os.unlink(script)

    def test_build_run_script_injects_stdin_mock(self):
        from app.services.cluely.assessment_agent import _build_run_script
        script, cmd, cwd = _build_run_script("x = input()", "python", stdin="hello\nworld")
        content = Path(script).read_text()
        assert "_STDIN" in content
        assert "iter(" in content
        os.unlink(script)

    def test_build_run_script_no_stdin_skips_injection(self):
        from app.services.cluely.assessment_agent import _build_run_script
        script, cmd, cwd = _build_run_script("x = 1", "python", stdin="")
        content = Path(script).read_text()
        assert "_STDIN" not in content
        os.unlink(script)


# ===========================================================================
# AssessmentAgent — high-level logic via mocks
# ===========================================================================

class TestAssessmentAgentLogic:
    """
    Tests for the agent loop — all LLM, screen, and terminal calls are mocked
    so tests are fast, offline, and deterministic.
    """

    def _make_agent(self, mode: str = "coding"):
        from app.services.cluely.assessment_agent import AssessmentAgent
        events: list[dict] = []

        async def _send(ev: dict):
            events.append(ev)

        agent = AssessmentAgent(mode=mode, session_ctx={}, send=_send)
        agent._events = events

        # Replace every service with a mock
        agent._screen  = AsyncMock()
        agent._browser = AsyncMock()
        agent._search  = AsyncMock()
        agent._terminal = MagicMock()
        return agent, events

    @pytest.mark.asyncio
    async def test_coding_loop_sends_solution_event(self):
        """_run_coding_loop should emit an agent:solution event."""
        agent, events = self._make_agent("coding")

        agent._screen.capture_and_extract = AsyncMock(
            return_value="1. Two Sum\nInput: [2,7], target=9\nOutput: [0,1]"
        )
        agent._search.search = AsyncMock(return_value=[])

        async def _fake_terminal_run(cmd, working_dir=None, env=None):
            yield {"stream": "stdout", "text": "[0,1]", "timestamp_ms": 0, "cwd": ""}
            yield {"stream": "system", "text": "[exit 0]", "timestamp_ms": 0, "cwd": ""}

        agent._terminal.run = _fake_terminal_run

        with patch("app.services.cluely.assessment_agent.deepseek_generate",
                   new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "def twoSum(nums, target): return [0,1]"
            await agent._run_coding_loop()

        solution_events = [e for e in events if e.get("type") == "agent:solution"]
        assert len(solution_events) >= 1

    @pytest.mark.asyncio
    async def test_reread_screen_updates_problem(self):
        """_reread_screen should update self._problem_text from screen OCR."""
        agent, events = self._make_agent()
        agent._screen.capture_and_extract = AsyncMock(
            return_value="3. Longest Palindromic Substring"
        )
        await agent._reread_screen()
        assert "Longest Palindromic" in agent._problem_text

    @pytest.mark.asyncio
    async def test_handle_manual_ask_answer_path(self):
        """manual_ask with ANSWER decision should emit guidance event."""
        agent, events = self._make_agent()

        with patch("app.services.cluely.assessment_agent.deepseek_generate",
                   new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "ANSWER Use a sliding window approach."
            await agent._handle_manual_ask("How do I solve this?")

        guidance = [e for e in events if e.get("type") == "agent:guidance"]
        assert any("sliding window" in e.get("text", "").lower() for e in guidance)

    @pytest.mark.asyncio
    async def test_handle_manual_ask_search_path(self):
        """manual_ask with SEARCH decision should emit a search tool event."""
        agent, events = self._make_agent()
        agent._search.search = AsyncMock(return_value=["Result snippet"])

        with patch("app.services.cluely.assessment_agent.deepseek_generate",
                   new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "SEARCH two sum python solution"
            await agent._handle_manual_ask("Find a solution online")

        tool_events = [e for e in events if e.get("type") == "tool:event" and e.get("tool") == "search"]
        assert any(e.get("status") in ("start", "done") for e in tool_events)

    @pytest.mark.asyncio
    async def test_ai_model_coach_emits_guidance(self):
        """AI model mode should emit at least one guidance event."""
        agent, events = self._make_agent("ai_model")
        agent._screen.capture_and_extract = AsyncMock(return_value="GPT-3.5 interface loaded")

        with patch("app.services.cluely.assessment_agent.deepseek_generate",
                   new_callable=AsyncMock) as mock_llm, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            # First call = initial strategy, subsequent = GOOD evaluation
            mock_llm.side_effect = [
                "Type: 'Solve this problem step by step'",
                "GOOD: Response was clear and complete.",
            ]
            await agent._run_ai_model_coach("")

        guidance = [e for e in events if e.get("type") == "agent:guidance"]
        assert len(guidance) >= 1

    @pytest.mark.asyncio
    async def test_run_against_test_cases_counts_passes(self):
        """_run_against_test_cases should count correct outputs as passes."""
        agent, events = self._make_agent()
        agent._test_cases = [{"input": "3", "output": "6"}]
        agent._solution = "print(int(input())*2)"
        agent._language = "python"

        async def _fake_run(cmd, working_dir=None, env=None):
            yield {"stream": "stdout", "text": "6", "timestamp_ms": 0, "cwd": ""}
            yield {"stream": "system", "text": "[exit 0]", "timestamp_ms": 0, "cwd": ""}

        agent._terminal.run = _fake_run

        passed, failed = await agent._run_against_test_cases(agent._solution, agent._language)
        assert passed == 1
        assert failed == []

    @pytest.mark.asyncio
    async def test_run_against_test_cases_detects_failure(self):
        """_run_against_test_cases should record wrong output as failure."""
        agent, events = self._make_agent()
        agent._test_cases = [{"input": "3", "output": "6"}]

        async def _fake_run(cmd, working_dir=None, env=None):
            yield {"stream": "stdout", "text": "99", "timestamp_ms": 0, "cwd": ""}
            yield {"stream": "system", "text": "[exit 0]", "timestamp_ms": 0, "cwd": ""}

        agent._terminal.run = _fake_run

        passed, failed = await agent._run_against_test_cases("print(99)", "python")
        assert passed == 0
        assert len(failed) == 1
        assert failed[0]["expected"] == "6"
        assert failed[0]["actual"] == "99"
