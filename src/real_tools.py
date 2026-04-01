from __future__ import annotations

import json
import subprocess
import difflib
from dataclasses import dataclass
from pathlib import Path


# ── hard limits — protect your 8GB machine ────────────────────────────────────

MAX_FILE_BYTES   = 100_000   # 100KB — files larger than this get refused
MAX_OUTPUT_CHARS = 8_000     # truncate bash output before sending to model
TOOL_LOOP_LIMIT  = 4         # max tool calls per single turn


# ── result dataclasses ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FileReadResult:
    path: str
    content: str
    success: bool
    error: str = ""
    line_count: int = 0
    size_bytes: int = 0


@dataclass(frozen=True)
class BashResult:
    command: str
    stdout: str
    stderr: str
    returncode: int
    success: bool
    error: str = ""


@dataclass(frozen=True)
class FileEditResult:
    path: str
    original: str
    updated: str
    diff: str
    success: bool
    error: str = ""


# ── FileReadTool ──────────────────────────────────────────────────────────────

def read_file(path: str) -> FileReadResult:
    try:
        p = Path(path).resolve()

        if not p.exists():
            return FileReadResult(
                path=path, content="", success=False,
                error=f"file not found: {path}"
            )
        if not p.is_file():
            return FileReadResult(
                path=path, content="", success=False,
                error=f"path is not a file: {path}"
            )

        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            return FileReadResult(
                path=path, content="", success=False,
                error=(
                    f"file too large ({size} bytes, limit is {MAX_FILE_BYTES}). "
                    f"ask rozn to read a specific line range instead."
                )
            )

        content = p.read_text(encoding="utf-8", errors="replace")
        return FileReadResult(
            path=str(p),
            content=content,
            success=True,
            line_count=content.count("\n") + 1,
            size_bytes=size,
        )

    except PermissionError:
        return FileReadResult(
            path=path, content="", success=False,
            error=f"permission denied: {path}"
        )
    except Exception as exc:
        return FileReadResult(
            path=path, content="", success=False,
            error=str(exc)
        )


# ── BashTool ──────────────────────────────────────────────────────────────────

# commands that could destroy your machine — hard blocked regardless of context
BLOCKED_COMMANDS = {
    "rm", "rmdir", "del", "rd",
    "format", "mkfs", "fdisk",
    "shutdown", "reboot", "halt", "poweroff",
    "reg", "regedit",              # windows registry
    ":(){:|:&};:",                 # fork bomb
}

def run_bash(
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> BashResult:
    if not command.strip():
        return BashResult(
            command=command, stdout="", stderr="",
            returncode=-1, success=False,
            error="empty command"
        )

    first_word = command.strip().split()[0].lower()
    if first_word in BLOCKED_COMMANDS:
        return BashResult(
            command=command, stdout="", stderr="",
            returncode=-1, success=False,
            error=f"'{first_word}' is blocked by rozn for safety."
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

        stdout = result.stdout
        stderr = result.stderr

        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = (
                stdout[:MAX_OUTPUT_CHARS]
                + f"\n... [truncated — {len(result.stdout)} total chars]"
            )
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = (
                stderr[:MAX_OUTPUT_CHARS]
                + f"\n... [truncated — {len(result.stderr)} total chars]"
            )

        return BashResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            returncode=result.returncode,
            success=result.returncode == 0,
        )

    except subprocess.TimeoutExpired:
        return BashResult(
            command=command, stdout="", stderr="",
            returncode=-1, success=False,
            error=f"command timed out after {timeout}s"
        )
    except Exception as exc:
        return BashResult(
            command=command, stdout="", stderr="",
            returncode=-1, success=False,
            error=str(exc)
        )


# ── FileEditTool ──────────────────────────────────────────────────────────────

def edit_file(
    path: str,
    old_content: str,
    new_content: str,
) -> FileEditResult:
    try:
        p = Path(path).resolve()

        if not p.exists():
            return FileEditResult(
                path=path, original="", updated="",
                diff="", success=False,
                error=f"file not found: {path}"
            )

        current = p.read_text(encoding="utf-8", errors="replace")

        if old_content not in current:
            return FileEditResult(
                path=path, original=current, updated="",
                diff="", success=False,
                error=(
                    "could not find the specified text in the file. "
                    "the file may have changed since rozn last read it. "
                    "ask rozn to re-read the file before editing."
                )
            )

        updated = current.replace(old_content, new_content, 1)

        diff_lines = list(difflib.unified_diff(
            current.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"{path} (before)",
            tofile=f"{path} (after)",
            lineterm="",
        ))
        diff = "".join(diff_lines)

        p.write_text(updated, encoding="utf-8")

        return FileEditResult(
            path=str(p),
            original=current,
            updated=updated,
            diff=diff,
            success=True,
        )

    except PermissionError:
        return FileEditResult(
            path=path, original="", updated="",
            diff="", success=False,
            error=f"permission denied: {path}"
        )
    except Exception as exc:
        return FileEditResult(
            path=path, original="", updated="",
            diff="", success=False,
            error=str(exc)
        )


# ── ListDirTool — bonus: lets rozn explore your project structure ──────────────

@dataclass(frozen=True)
class ListDirResult:
    path: str
    entries: tuple[str, ...]
    success: bool
    error: str = ""


def list_dir(path: str = ".", max_entries: int = 80) -> ListDirResult:
    try:
        p = Path(path).resolve()

        if not p.exists():
            return ListDirResult(path=path, entries=(), success=False,
                                 error=f"path not found: {path}")
        if not p.is_dir():
            return ListDirResult(path=path, entries=(), success=False,
                                 error=f"not a directory: {path}")

        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = []
        for entry in entries[:max_entries]:
            prefix = "  " if entry.is_file() else "/ "
            lines.append(f"{prefix}{entry.name}")

        if len(entries) > max_entries:
            lines.append(f"... and {len(entries) - max_entries} more entries")

        return ListDirResult(
            path=str(p),
            entries=tuple(lines),
            success=True,
        )

    except PermissionError:
        return ListDirResult(path=path, entries=(), success=False,
                             error=f"permission denied: {path}")
    except Exception as exc:
        return ListDirResult(path=path, entries=(), success=False,
                             error=str(exc))


# ── central dispatcher — called from query_engine._call_ollama ────────────────

def dispatch_tool(tool_name: str, payload: dict) -> str:
    if tool_name == "FileReadTool":
        result = read_file(payload.get("path", ""))
        if not result.success:
            return f"FileReadTool error: {result.error}"
        return (
            f"file: {result.path}\n"
            f"lines: {result.line_count}   size: {result.size_bytes} bytes\n"
            f"{'─' * 40}\n"
            f"{result.content}"
        )

    if tool_name == "BashTool":
        result = run_bash(
            payload.get("command", ""),
            cwd=payload.get("cwd"),
            timeout=int(payload.get("timeout", 30)),
        )
        if not result.success and result.error:
            return f"BashTool error: {result.error}"
        parts = []
        if result.stdout:
            parts.append(f"stdout:\n{result.stdout}")
        if result.stderr:
            parts.append(f"stderr:\n{result.stderr}")
        parts.append(f"exit code: {result.returncode}")
        return "\n".join(parts)

    if tool_name == "FileEditTool":
        result = edit_file(
            payload.get("path", ""),
            payload.get("old_content", ""),
            payload.get("new_content", ""),
        )
        if not result.success:
            return f"FileEditTool error: {result.error}"
        return f"edit applied.\n\ndiff:\n{result.diff}"

    if tool_name == "ListDirTool":
        result = list_dir(
            payload.get("path", "."),
            int(payload.get("max_entries", 80)),
        )
        if not result.success:
            return f"ListDirTool error: {result.error}"
        return f"directory: {result.path}\n\n" + "\n".join(result.entries)

    return f"unknown tool: {tool_name}"