"""
file_service.py — Filesystem read/write for the assessment agent.

Gives the agent the ability to:
  - Read files and directories from a scoped project folder
  - Write or patch files (full replace or targeted line-range patch)
  - List directory contents
  - Search for a pattern across files (grep-style)

Security
--------
All paths are resolved against the configured project_root.  Any path that
escapes the root via traversal (../../etc) is rejected with PathEscapeError.
The agent can only access the folder the user explicitly provided at session
setup — nothing outside it.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
from pathlib import Path
from typing import Optional

from app.core.exceptions import DevCoreException

logger = logging.getLogger(__name__)

# Maximum file size we'll read in one call — 256 KB
MAX_READ_BYTES = 256 * 1024

# Extensions we treat as text (everything else is skipped in directory search)
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cpp",
    ".c", ".h", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh", ".fish",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".env", ".sql", ".html", ".css", ".scss", ".less", ".xml",
}


class PathEscapeError(DevCoreException):
    def __init__(self, path: str):
        super().__init__(
            code="PATH_ESCAPE",
            message=f"Path {path!r} is outside the allowed project root",
            status_code=403,
        )


class FileService:
    """
    Scoped filesystem operations for a session's project directory.

    Instantiate with the project root provided by the user at session setup.
    All operations are sandboxed to that root.
    """

    def __init__(self, project_root: str) -> None:
        self._root = Path(os.path.expanduser(os.path.expandvars(project_root))).resolve()
        if not self._root.exists():
            raise ValueError(f"Project root does not exist: {self._root}")
        logger.info("[file] Service scoped to: %s", self._root)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _safe_resolve(self, rel_path: str) -> Path:
        """Resolve rel_path within root; raise PathEscapeError if it escapes."""
        target = (self._root / rel_path).resolve()
        try:
            target.relative_to(self._root)
        except ValueError:
            raise PathEscapeError(rel_path)
        return target

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def read_file(self, path: str) -> str:
        """
        Return the text content of a file.
        Files larger than MAX_READ_BYTES are truncated with a warning comment.
        """
        target = self._safe_resolve(path)

        def _read() -> str:
            if not target.is_file():
                return f"# [file not found: {path}]"
            size = target.stat().st_size
            with target.open("r", encoding="utf-8", errors="replace") as f:
                if size > MAX_READ_BYTES:
                    content = f.read(MAX_READ_BYTES)
                    return content + f"\n# [truncated — file is {size} bytes]"
                return f.read()

        return await asyncio.to_thread(_read)

    async def list_directory(self, path: str = ".", depth: int = 2) -> list[str]:
        """
        Return a list of relative file paths within *path* up to *depth* levels.
        Hidden files (dotfiles) and __pycache__ / node_modules are excluded.
        """
        target = self._safe_resolve(path)

        def _walk() -> list[str]:
            results: list[str] = []
            base_depth = len(target.parts)
            for root, dirs, files in os.walk(target):
                current_depth = len(Path(root).parts) - base_depth
                if current_depth >= depth:
                    dirs.clear()
                    continue
                # Prune noisy directories
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git", "venv", ".venv")
                ]
                for fname in files:
                    if fname.startswith("."):
                        continue
                    full = Path(root) / fname
                    results.append(str(full.relative_to(self._root)))
            return sorted(results)

        return await asyncio.to_thread(_walk)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def write_file(self, path: str, content: str) -> None:
        """
        Write (or overwrite) a file with the given content.
        Parent directories are created if they don't exist.
        """
        target = self._safe_resolve(path)

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            logger.info("[file] wrote %d chars → %s", len(content), target)

        await asyncio.to_thread(_write)

    async def patch_file(self, path: str, start_line: int, end_line: int, new_content: str) -> None:
        """
        Replace lines [start_line, end_line] (1-indexed, inclusive) with new_content.
        Useful for targeted edits without rewriting the whole file.
        """
        target = self._safe_resolve(path)

        def _patch() -> None:
            if not target.is_file():
                raise FileNotFoundError(f"File not found: {path}")
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            if not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            patched = lines[:start_line - 1] + new_lines + lines[end_line:]
            target.write_text("".join(patched), encoding="utf-8")
            logger.info("[file] patched lines %d-%d in %s", start_line, end_line, target)

        await asyncio.to_thread(_patch)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_in_files(
        self,
        pattern: str,
        glob: str = "**/*",
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search for a text pattern across all text files in the project.

        Returns a list of {file, line_number, line} dicts (up to max_results).
        Case-insensitive substring match.
        """
        def _search() -> list[dict]:
            results: list[dict] = []
            pattern_lower = pattern.lower()
            for rel_path in self._root.glob(glob):
                if rel_path.is_dir():
                    continue
                if rel_path.suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                try:
                    text = rel_path.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(text.splitlines(), start=1):
                        if pattern_lower in line.lower():
                            results.append({
                                "file":        str(rel_path.relative_to(self._root)),
                                "line_number": i,
                                "line":        line.rstrip(),
                            })
                            if len(results) >= max_results:
                                return results
                except Exception:
                    continue
            return results

        return await asyncio.to_thread(_search)
