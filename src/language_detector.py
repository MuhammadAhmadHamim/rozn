from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


# ── Language definitions ──────────────────────────────────────────────────────

EXTENSION_MAP: dict[str, str] = {
    # Python ecosystem
    ".py":     "Python",
    ".ipynb":  "Jupyter Notebook",
    ".pyw":    "Python",
    # C family
    ".c":      "C",
    ".h":      "C",
    ".cpp":    "C++",
    ".cc":     "C++",
    ".cxx":    "C++",
    ".hpp":    "C++",
    ".hxx":    "C++",
    ".hh":     "C++",
    # JVM
    ".java":   "Java",
    ".kt":     "Kotlin",
    ".kts":    "Kotlin",
    ".scala":  "Scala",
    ".groovy": "Groovy",
    # .NET
    ".cs":     "C#",
    ".vb":     "Visual Basic",
    ".fs":     "F#",
    # Web
    ".js":     "JavaScript",
    ".jsx":    "JavaScript",
    ".ts":     "TypeScript",
    ".tsx":    "TypeScript",
    ".html":   "HTML",
    ".css":    "CSS",
    ".php":    "PHP",
    # Data and query
    ".sql":    "SQL",
    ".psql":   "SQL",
    ".mysql":  "SQL",
    ".sqlite": "SQL",
    # Systems
    ".rs":     "Rust",
    ".go":     "Go",
    ".zig":    "Zig",
    ".s":      "Assembly",
    ".asm":    "Assembly",
    # Scripting
    ".rb":     "Ruby",
    ".pl":     "Perl",
    ".lua":    "Lua",
    ".sh":     "Shell",
    ".bash":   "Shell",
    ".zsh":    "Shell",
    ".ps1":    "PowerShell",
    ".bat":    "Batch",
    ".cmd":    "Batch",
    # Data science
    ".r":      "R",
    ".rmd":    "R Markdown",
    ".m":      "MATLAB",
    ".jl":     "Julia",
    # Config and data
    ".yaml":   "YAML",
    ".yml":    "YAML",
    ".toml":   "TOML",
    ".json":   "JSON",
    ".xml":    "XML",
    # Functional
    ".hs":     "Haskell",
    ".ml":     "OCaml",
    ".ex":     "Elixir",
    ".exs":    "Elixir",
    ".erl":    "Erlang",
    # Mobile
    ".swift":  "Swift",
    ".dart":   "Dart",
}

# skip these when counting — they're not source languages
SKIP_EXTENSIONS = {
    ".md", ".txt", ".rst", ".log", ".lock",
    ".gitignore", ".env", ".ini", ".cfg",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".docx", ".xlsx",
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
    ".zip", ".tar", ".gz", ".whl",
}

SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__",
    "node_modules", ".claude", "build", "dist",
    "target", "bin", "obj", ".idea", ".vscode",
}


# ── SQL dialect detection ─────────────────────────────────────────────────────

SQL_DIALECT_HINTS: dict[str, list[str]] = {
    "PostgreSQL": ["psycopg2", "postgresql", "postgres", "pg8000", "asyncpg"],
    "MySQL":      ["pymysql", "mysql-connector", "mysqlclient", "mysql"],
    "SQLite":     ["sqlite3", "sqlite", "aiosqlite"],
    "MSSQL":      ["pyodbc", "pymssql", "mssql"],
    "Oracle":     ["cx_Oracle", "oracledb"],
    "MongoDB":    ["pymongo", "motor", "mongoengine"],
}


# ── Language-specific error patterns ─────────────────────────────────────────

ERROR_PATTERNS: dict[str, list[str]] = {
    "Python": [
        "traceback (most recent call last)",
        "indentationerror",
        "syntaxerror",
        "nameerror",
        "typeerror",
        "valueerror",
        "importerror",
        "modulenotfounderror",
        "attributeerror",
        "indexerror",
        "keyerror",
        "runtimeerror",
        "oserror",
        "filenotfounderror",
        "permissionerror",
        "recursionerror",
        "zerodivisionerror",
        "stopiteration",
        "assertionerror",
    ],
    "Jupyter Notebook": [
        "traceback (most recent call last)",
        "kernel died",
        "kernel restarting",
        "nameerror",
        "typeerror",
    ],
    "C++": [
        "segmentation fault",
        "segfault",
        "undefined reference",
        "no such file or directory",
        "expected primary-expression",
        "was not declared in this scope",
        "no matching function",
        "invalid conversion",
        "cannot convert",
        "multiple definition",
        "linker error",
        "core dumped",
        "stack smashing",
        "double free",
        "use after free",
        "memory leak",
        "abort called",
        "terminate called",
    ],
    "C": [
        "segmentation fault",
        "segfault",
        "undefined reference",
        "implicit declaration",
        "incompatible pointer",
        "core dumped",
        "stack smashing",
        "double free",
        "use after free",
        "malloc",
        "free(): invalid",
    ],
    "Java": [
        "nullpointerexception",
        "classnotfoundexception",
        "arrayindexoutofboundsexception",
        "stackoverflowerror",
        "outofmemoryerror",
        "cannot find symbol",
        "incompatible types",
        "illegal argument",
        "classcastexception",
        "concurrentmodificationexception",
        "nosuchmethodexception",
        "illegalstateexception",
        "arithmeticexception",
        "stringindexoutofboundsexception",
    ],
    "C#": [
        "nullreferenceexception",
        "indexoutofrangeexception",
        "invalidoperationexception",
        "stackoverflow",
        "outofmemoryexception",
        "dividebyzeroexception",
        "formatexception",
        "argumentexception",
        "notimplementedexception",
    ],
    "JavaScript": [
        "typeerror",
        "referenceerror",
        "syntaxerror",
        "rangeerror",
        "cannot read property",
        "cannot read properties",
        "is not a function",
        "is not defined",
        "unexpected token",
        "uncaught",
    ],
    "TypeScript": [
        "type error",
        "ts(",
        "is not assignable to type",
        "property does not exist",
        "cannot find name",
        "object is possibly",
    ],
    "SQL": [
        "syntax error",
        "no such table",
        "no such column",
        "column not found",
        "table not found",
        "foreign key constraint",
        "unique constraint",
        "not null constraint",
        "ambiguous column",
        "divide by zero",
        "invalid input syntax",
        "relation does not exist",
        "duplicate key",
    ],
    "Rust": [
        "borrow checker",
        "cannot borrow",
        "does not live long enough",
        "mismatched types",
        "use of moved value",
        "cannot move out",
        "thread panicked",
        "called unwrap() on",
        "index out of bounds",
    ],
    "Go": [
        "panic:",
        "goroutine",
        "nil pointer dereference",
        "index out of range",
        "interface conversion",
        "deadlock",
        "runtime error",
    ],
    "Shell": [
        "command not found",
        "permission denied",
        "no such file",
        "syntax error near",
        "bad substitution",
        "unbound variable",
    ],
    "R": [
        "error in",
        "object not found",
        "undefined columns",
        "subscript out of bounds",
        "non-numeric argument",
        "replacement has length zero",
    ],
    "MATLAB": [
        "undefined function",
        "undefined variable",
        "index exceeds",
        "dimensions must agree",
        "matrix dimensions",
    ],
}

# ── Language-specific advice ──────────────────────────────────────────────────

LANGUAGE_CONTEXT: dict[str, str] = {
    "Python": """Detected language: Python
Common issues: indentation errors, import errors, type mismatches, missing dependencies.
When debugging: read the traceback bottom to top. The last line is the error. The line above it is where it happened.
Useful commands: python -m pytest, python -m py_compile file.py, pip install -r requirements.txt""",

    "Jupyter Notebook": """Detected language: Jupyter Notebook (Python)
Common issues: kernel dying, variable state from previous cells, import errors, out-of-order execution.
Remember: cells share state. If a variable is undefined, check if an earlier cell was run.
When reading notebooks: cells execute top to bottom. Order matters.""",

    "C++": """Detected language: C++
Common issues: segmentation faults (bad pointer), undefined references (linker errors), memory leaks.
When debugging: ask for the full compiler output with -Wall -Wextra flags.
Read segfaults by checking which pointer was dereferenced — it is almost always NULL or out of bounds.
Useful commands: g++ -Wall -Wextra -g file.cpp -o output, valgrind ./output, gdb ./output""",

    "C": """Detected language: C
Common issues: segmentation faults, buffer overflows, use-after-free, uninitialized variables.
When debugging: always ask for the compiler warning output. C hides many errors without -Wall.
Useful commands: gcc -Wall -Wextra -g file.c -o output, valgrind ./output""",

    "Java": """Detected language: Java
Common issues: NullPointerException, ClassNotFoundException, ArrayIndexOutOfBoundsException.
When debugging: read the stack trace top to bottom. The first line after 'Exception in thread' is the error.
The first 'at' line that mentions your code (not java.lang) is where it happened.
Useful commands: javac File.java, java ClassName, mvn test, gradle test""",

    "C#": """Detected language: C#
Common issues: NullReferenceException, async/await deadlocks, LINQ errors.
When debugging: check if the object is null before the crash line.
Useful commands: dotnet build, dotnet run, dotnet test""",

    "JavaScript": """Detected language: JavaScript
Common issues: undefined is not a function, cannot read property of undefined, async callback errors.
When debugging: check if the variable exists before accessing its properties.
Remember: JavaScript is asynchronous — errors in callbacks may show up in unexpected places.""",

    "TypeScript": """Detected language: TypeScript
Common issues: type assignment errors, null/undefined not handled, missing type definitions.
When debugging: read the TS error code in parentheses — it points to the exact rule being violated.""",

    "SQL": """Detected language: SQL
When analysing queries:
- Check JOIN conditions before WHERE clauses — a bad JOIN multiplies rows silently.
- NULL handling: NULL != NULL, use IS NULL not = NULL.
- Check if indexes exist on columns used in WHERE and JOIN.
- Identify the dialect (SQLite/MySQL/PostgreSQL) before suggesting syntax — they differ.
Useful commands: EXPLAIN query, EXPLAIN ANALYZE query (PostgreSQL), .schema (SQLite)""",

    "Rust": """Detected language: Rust
Common issues: borrow checker errors, lifetime issues, unwrap() on None/Err.
When debugging: read the borrow checker message carefully — it tells you exactly what conflicts.
The error message in Rust is unusually precise. Trust it.""",

    "Go": """Detected language: Go
Common issues: nil pointer dereference, goroutine deadlocks, interface mismatches.
When debugging: panic messages include a full goroutine stack trace. Read it from the top.
Useful commands: go build ./..., go test ./..., go vet ./...""",

    "Shell": """Detected language: Shell/Bash
Common issues: command not found, permission denied, unquoted variables with spaces.
When debugging: run with bash -x script.sh to see every command as it executes.
Always quote variables: use "$var" not $var.""",

    "R": """Detected language: R
Common issues: object not found, subscript out of bounds, non-numeric argument to binary operator.
When debugging: check that the data frame column name is spelled correctly — R is case sensitive.""",

    "MATLAB": """Detected language: MATLAB
Common issues: matrix dimension mismatches, undefined function or variable, index exceeding dimensions.
When debugging: check array sizes with size() before operations that require matching dimensions.""",
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ProjectLanguage:
    primary: str
    secondary: list[str] = field(default_factory=list)
    sql_dialect: str = ""
    jupyter: bool = False
    file_counts: dict[str, int] = field(default_factory=dict)
    confidence: str = "high"

    def context_for_model(self) -> str:
        ctx = LANGUAGE_CONTEXT.get(self.primary, "")
        if self.sql_dialect and self.primary == "SQL":
            ctx += f"\nDialect detected: {self.sql_dialect}"
        if self.secondary:
            ctx += f"\nSecondary languages also present: {', '.join(self.secondary)}"
        return ctx

    def error_patterns(self) -> list[str]:
        patterns = list(ERROR_PATTERNS.get(self.primary, []))
        for lang in self.secondary:
            patterns.extend(ERROR_PATTERNS.get(lang, []))
        return patterns

    def display(self) -> str:
        parts = [self.primary]
        if self.sql_dialect:
            parts[0] = f"{self.primary} ({self.sql_dialect})"
        if self.secondary:
            parts.append(f"+ {', '.join(self.secondary)}")
        return " ".join(parts)


# ── Detection logic ───────────────────────────────────────────────────────────

def detect_language(root: Path | None = None) -> ProjectLanguage:
    project_root = root or Path.cwd()
    counts: dict[str, int] = {}

    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        ext = path.suffix.lower()
        if ext in SKIP_EXTENSIONS or not ext:
            continue
        lang = EXTENSION_MAP.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    if not counts:
        return ProjectLanguage(
            primary="Unknown",
            confidence="none",
            file_counts=counts,
        )

    sorted_langs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_langs[0][0]
    secondary = [
        lang for lang, count in sorted_langs[1:]
        if count >= 2 and lang not in {"YAML", "JSON", "TOML", "XML", "HTML", "CSS"}
    ][:3]

    has_jupyter = "Jupyter Notebook" in counts

    sql_dialect = ""
    if primary == "SQL" or "SQL" in secondary:
        sql_dialect = _detect_sql_dialect(project_root)

    confidence = "high" if sorted_langs[0][1] >= 3 else "low"

    return ProjectLanguage(
        primary=primary,
        secondary=secondary,
        sql_dialect=sql_dialect,
        jupyter=has_jupyter,
        file_counts=counts,
        confidence=confidence,
    )


def _detect_sql_dialect(root: Path) -> str:
    search_files = [
        root / "requirements.txt",
        root / "requirements-dev.txt",
        root / "Pipfile",
        root / "pyproject.toml",
        root / "package.json",
        root / "pom.xml",
        root / "build.gradle",
    ]

    for path in search_files:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace").lower()
            for dialect, hints in SQL_DIALECT_HINTS.items():
                if any(hint.lower() in content for hint in hints):
                    return dialect
        except Exception:
            continue

    return ""


def classify_error(message: str, language: ProjectLanguage) -> str:
    lowered = message.lower()
    patterns = ERROR_PATTERNS.get(language.primary, [])
    for pattern in patterns:
        if pattern in lowered:
            return language.primary
    for lang in language.secondary:
        for pattern in ERROR_PATTERNS.get(lang, []):
            if pattern in lowered:
                return lang
    for lang, patterns in ERROR_PATTERNS.items():
        for pattern in patterns:
            if pattern in lowered:
                return lang
    return ""


def extract_jupyter_python(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cells = data.get("cells", [])
        code_cells = []
        for i, cell in enumerate(cells):
            if cell.get("cell_type") == "code":
                source = "".join(cell.get("source", []))
                if source.strip():
                    code_cells.append(f"# Cell {i + 1}\n{source}")
        return "\n\n".join(code_cells)
    except Exception as exc:
        return f"could not extract notebook cells: {exc}"