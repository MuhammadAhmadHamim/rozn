from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path


# ── Index data structures ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class FileIndex:
    path: str
    classes: tuple[str, ...]
    functions: tuple[str, ...]
    imports: tuple[str, ...]


@dataclass(frozen=True)
class ProjectIndex:
    root: str
    files: tuple[FileIndex, ...]
    generated_at: str

    def to_compact_text(self) -> str:
        lines = [f"rozn project index — {self.root}", ""]
        for f in self.files:
            lines.append(f"  {f.path}")
            for cls in f.classes:
                lines.append(f"    class {cls}")
            for fn in f.functions:
                lines.append(f"    def {fn}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({
            "root": self.root,
            "generated_at": self.generated_at,
            "files": [
                {
                    "path": f.path,
                    "classes": list(f.classes),
                    "functions": list(f.functions),
                    "imports": list(f.imports),
                }
                for f in self.files
            ]
        }, indent=2)

    def find_symbol(self, name: str) -> list[str]:
        results = []
        needle = name.lower()
        for f in self.files:
            for cls in f.classes:
                if needle in cls.lower():
                    results.append(f"{f.path} → class {cls}")
            for fn in f.functions:
                if needle in fn.lower():
                    results.append(f"{f.path} → def {fn}")
        return results

    def summary_for_model(self) -> str:
        lines = ["Project structure (classes and functions only):", ""]
        for f in self.files:
            if not f.classes and not f.functions:
                continue
            lines.append(f"  {f.path}")
            for cls in f.classes:
                lines.append(f"    class {cls}")
            for fn in f.functions:
                lines.append(f"    def {fn}")
        return "\n".join(lines)


# ── AST scanner ───────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__",
    "node_modules", ".claude", "reference_data",
    "rust", "assets", "tests",
}

SKIP_FILES = {
    "cost_tracker.py", "costHook.py",
}


def scan_file(path: Path, root: Path) -> FileIndex | None:
    if path.name in SKIP_FILES:
        return None

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return FileIndex(
            path=str(path.relative_to(root)),
            classes=(),
            functions=(),
            imports=(),
        )
    except Exception:
        return None

    classes   = []
    functions = []
    imports   = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            # skip private dunders except __init__
            if not node.name.startswith("__") or node.name == "__init__":
                functions.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not module.startswith("."):
                imports.append(module)

    return FileIndex(
        path=str(path.relative_to(root)),
        classes=tuple(classes),
        functions=tuple(functions),
        imports=tuple(dict.fromkeys(imports)),
    )


def scan_directory(root: Path) -> list[FileIndex]:
    results = []
    for path in sorted(root.rglob("*.py")):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        index = scan_file(path, root)
        if index is not None:
            results.append(index)
    return results


# ── Index builder ─────────────────────────────────────────────────────────────

INDEX_FILENAME = "rozn.index"


def build_index(root: Path | None = None) -> ProjectIndex:
    from datetime import datetime

    project_root = root or Path.cwd()
    src_root     = project_root / "src"

    scan_root = src_root if src_root.exists() else project_root

    files = scan_directory(scan_root)

    return ProjectIndex(
        root=str(project_root),
        files=tuple(files),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def save_index(index: ProjectIndex, root: Path | None = None) -> Path:
    project_root = root or Path.cwd()
    path = project_root / INDEX_FILENAME
    path.write_text(index.to_json(), encoding="utf-8")
    return path


def load_index(root: Path | None = None) -> ProjectIndex | None:
    project_root = root or Path.cwd()
    path = project_root / INDEX_FILENAME

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectIndex(
            root=data["root"],
            generated_at=data.get("generated_at", "unknown"),
            files=tuple(
                FileIndex(
                    path=f["path"],
                    classes=tuple(f["classes"]),
                    functions=tuple(f["functions"]),
                    imports=tuple(f["imports"]),
                )
                for f in data["files"]
            ),
        )
    except Exception:
        return None


def build_and_save_index(root: Path | None = None) -> tuple[ProjectIndex, Path]:
    index = build_index(root)
    path  = save_index(index, root)
    return index, path