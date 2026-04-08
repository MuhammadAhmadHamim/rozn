from __future__ import annotations

import json
import requests
from dataclasses import dataclass
from pathlib import Path

from .language_detector import detect_language, ProjectLanguage
from .indexer import load_index, ProjectIndex
from .real_tools import read_file


OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5-coder:3b"
DOC_TIMEOUT  = 300


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class DocumentationResult:
    success: bool
    content: str
    error: str = ""


# ── Core model call — lean, no tool loop needed for docs ──────────────────────

def _ask_model(prompt: str, system: str) -> DocumentationResult:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                "stream": False,
            },
            timeout=DOC_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"].strip()
        return DocumentationResult(success=True, content=content)
    except requests.exceptions.Timeout:
        return DocumentationResult(
            success=False,
            error="model timed out — try a smaller file or section"
        )
    except Exception as exc:
        return DocumentationResult(success=False, error=str(exc))


# ── File explanation ──────────────────────────────────────────────────────────

EXPLAIN_SYSTEM = """You are Rozn — a precise local coding assistant.
Explain code files clearly and concisely.
Focus on: what the file does, what its main classes and functions are,
how it fits into the larger project.
Be direct. No filler. No marketing language.
Write in plain English that a developer would actually find useful.
Maximum 200 words."""

EXPLAIN_SYSTEM_BY_LANG: dict[str, str] = {
    "C++": EXPLAIN_SYSTEM + "\nFor C++ files: note any classes, their inheritance, and key methods.",
    "Java": EXPLAIN_SYSTEM + "\nFor Java files: note the class hierarchy, interfaces implemented, and public methods.",
    "SQL": """You are Rozn — a precise local coding assistant.
Explain SQL files clearly.
For each query or statement: what it does, which tables it touches, what it returns.
Note any JOINs, subqueries, or performance concerns.
Be direct. Maximum 200 words.""",
    "Jupyter Notebook": EXPLAIN_SYSTEM + "\nFor notebooks: describe each cell's purpose and the overall analysis flow.",
}


def explain_file(
    path: str,
    language: ProjectLanguage,
    index: ProjectIndex | None = None,
) -> DocumentationResult:
    p = Path(path)
    if not p.exists():
        for candidate in Path(".").rglob(p.name):
            p = candidate
            break

    if not p.exists():
        return DocumentationResult(
            success=False,
            error=f"file not found: {path}"
        )

    size = p.stat().st_size
    if size < 8000:
        result = read_file(str(p))
    else:
        result = read_file(str(p), start_line=1, end_line=60)

    if not result.success:
        return DocumentationResult(success=False, error=result.error)

    symbol_hint = ""
    if index:
        entry = next(
            (f for f in index.files if p.name.lower() in f.path.lower()),
            None
        )
        if entry:
            classes   = ", ".join(entry.classes) if entry.classes else "none"
            functions = ", ".join(entry.functions[:10]) if entry.functions else "none"
            symbol_hint = (
                f"\nKnown classes: {classes}"
                f"\nKnown functions: {functions}"
            )

    system = EXPLAIN_SYSTEM_BY_LANG.get(language.primary, EXPLAIN_SYSTEM)

    prompt = (
        f"File: {p}\n"
        f"Language: {language.primary}\n"
        f"{symbol_hint}\n\n"
        f"Content:\n{result.content}"
    )

    return _ask_model(prompt, system)


# ── Docstring generation ──────────────────────────────────────────────────────

DOCSTRING_TEMPLATES: dict[str, str] = {
    "Python": '''Generate a Python docstring for this function.
Use Google style format:
"""
One line summary.

Args:
    param_name (type): Description.

Returns:
    type: Description.

Raises:
    ExceptionType: When this happens.
"""
Output ONLY the docstring, nothing else.''',

    "Java": '''Generate a Javadoc comment for this method.
Format:
/**
 * One line summary.
 *
 * @param name description
 * @return description
 * @throws ExceptionType when this happens
 */
Output ONLY the Javadoc comment, nothing else.''',

    "C++": '''Generate a Doxygen comment for this function.
Format:
/**
 * @brief One line summary.
 *
 * @param name description
 * @return description
 */
Output ONLY the Doxygen comment, nothing else.''',

    "C": '''Generate a Doxygen comment for this function.
Format:
/**
 * @brief One line summary.
 *
 * @param name description
 * @return description
 */
Output ONLY the comment block, nothing else.''',

    "JavaScript": '''Generate a JSDoc comment for this function.
Format:
/**
 * One line summary.
 *
 * @param {type} name - description
 * @returns {type} description
 */
Output ONLY the JSDoc comment, nothing else.''',

    "TypeScript": '''Generate a TSDoc comment for this function.
Format:
/**
 * One line summary.
 *
 * @param name - description
 * @returns description
 */
Output ONLY the TSDoc comment, nothing else.''',
}

DEFAULT_DOCSTRING_TEMPLATE = '''Generate a documentation comment for this function.
Include: what it does, its parameters, and what it returns.
Use the appropriate comment style for the language.
Output ONLY the comment block, nothing else.'''


def generate_docstring(
    file_path: str,
    function_name: str,
    language: ProjectLanguage,
    index: ProjectIndex | None = None,
) -> DocumentationResult:
    p = Path(file_path)
    if not p.exists():
        for candidate in Path(".").rglob(p.name):
            p = candidate
            break

    if not p.exists():
        return DocumentationResult(
            success=False,
            error=f"file not found: {file_path}"
        )

    # find the function line from index
    start_line = 1
    if index:
        entry = next(
            (f for f in index.files if p.name.lower() in f.path.lower()),
            None
        )
        if entry:
            for fn, line in zip(entry.functions, entry.function_lines):
                if fn.lower() == function_name.lower():
                    start_line = max(1, line - 1)
                    break

    result = read_file(str(p), start_line=start_line, end_line=start_line + 40)
    if not result.success:
        return DocumentationResult(success=False, error=result.error)

    template = DOCSTRING_TEMPLATES.get(
        language.primary, DEFAULT_DOCSTRING_TEMPLATE
    )

    prompt = (
        f"Language: {language.primary}\n"
        f"Function: {function_name}\n\n"
        f"Code:\n{result.content}\n\n"
        f"{template}"
    )

    return _ask_model(prompt, "You are Rozn — a precise local coding assistant.")


# ── Project README generation ─────────────────────────────────────────────────

README_SYSTEM = """You are Rozn — a precise local coding assistant.
Generate a clean professional README.md for this project.
Use this exact structure:

# Project Name

One paragraph description — what it does and why it exists.

## Requirements

List dependencies and versions.

## Installation

Step by step install instructions.

## Usage

How to run it. Include actual commands.

## Project Structure

Brief description of key files and folders.

## Notes

Any important caveats or known limitations.

Rules:
- Be specific, not generic. Use actual file names and commands from the project.
- Do not invent features that are not evident from the code.
- Keep each section concise — developers read READMEs fast.
- Output ONLY the markdown, no preamble."""


def generate_project_readme(
    root: Path | None = None,
    index: ProjectIndex | None = None,
    language: ProjectLanguage | None = None,
    memory_entries: list[str] | None = None,
) -> DocumentationResult:
    project_root = root or Path.cwd()

    if language is None:
        language = detect_language(project_root)

    if index is None:
        index = load_index(project_root)

    # build project summary for the model
    sections = []

    # project name from folder
    project_name = project_root.name
    sections.append(f"Project name: {project_name}")
    sections.append(f"Primary language: {language.display()}")

    if language.secondary:
        sections.append(f"Also uses: {', '.join(language.secondary)}")

    # key files snapshot
    key_files = []
    for fname in [
        "README.md", "pyproject.toml", "requirements.txt",
        "package.json", "pom.xml", "CMakeLists.txt",
        "Makefile", "setup.py", "Cargo.toml",
    ]:
        p = project_root / fname
        if p.exists() and p.stat().st_size < 3000:
            result = read_file(str(p))
            if result.success:
                key_files.append(f"--- {fname} ---\n{result.content}")

    if key_files:
        sections.append("\nKey project files:\n" + "\n\n".join(key_files))

    # entry points from index
    if index:
        entry_points = []
        for fname in ["main.py", "main.cpp", "Main.java", "index.js",
                      "app.py", "server.py", "manage.py"]:
            entry = next(
                (f for f in index.files if fname.lower() in f.path.lower()),
                None
            )
            if entry:
                entry_points.append(
                    f"{entry.path}: "
                    + ", ".join(
                        [f"class {c}" for c in entry.classes[:3]] +
                        [f"def {f}" for f in entry.functions[:5]]
                    )
                )
        if entry_points:
            sections.append(
                "\nEntry points:\n" +
                "\n".join(entry_points)
            )

        # top level structure
        top_level = sorted({
            Path(f.path).parts[0]
            for f in index.files
            if len(Path(f.path).parts) > 1
        })
        if top_level:
            sections.append(
                "\nTop level directories: " + ", ".join(top_level)
            )

        # file count
        sections.append(f"\nTotal indexed files: {len(index.files)}")

    # memory entries
    if memory_entries:
        sections.append(
            "\nProject notes (from memory):\n" +
            "\n".join(f"- {m}" for m in memory_entries[:6])
        )

    prompt = "\n".join(sections)
    return _ask_model(prompt, README_SYSTEM)