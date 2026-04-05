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
    relative_imports: tuple[str, ...]
    class_lines: tuple[int, ...] = ()
    function_lines: tuple[int, ...] = ()


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
                    "class_lines": list(f.class_lines),
                    "functions": list(f.functions),
                    "function_lines": list(f.function_lines),
                    "imports": list(f.imports),
                    "relative_imports": list(f.relative_imports),
                }
                for f in self.files
            ]
        }, indent=2)

    def find_symbol(self, name: str) -> list[str]:
        results = []
        needle = name.lower()
        for f in self.files:
            for cls, line in zip(f.classes, f.class_lines):
                if needle in cls.lower():
                    results.append(f"{f.path}:{line} → class {cls}")
            for fn, line in zip(f.functions, f.function_lines):
                if needle in fn.lower():
                    results.append(f"{f.path}:{line} → def {fn}")
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

    def resolve_import_graph(
        self,
        file_path: str,
        max_depth: int = 1,
    ) -> dict[str, list[FileIndex]]:
        needle = file_path.lower().replace("\\", "/")
        root_file = next(
            (f for f in self.files
             if needle in f.path.lower().replace("\\", "/")),
            None,
        )
        if root_file is None:
            return {}

        graph: dict[str, list[FileIndex]] = {}
        visited = {root_file.path}
        queue = [(root_file, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            deps = find_local_imports(current, self.files)
            graph[current.path] = deps
            for dep in deps:
                if dep.path not in visited:
                    visited.add(dep.path)
                    queue.append((dep, depth + 1))

        return graph

    def format_trace(self, file_path: str, max_depth: int = 1) -> str:
        needle = file_path.lower().replace("\\", "/")
        root_file = next(
            (f for f in self.files
             if needle in f.path.lower().replace("\\", "/")),
            None,
        )
        if root_file is None:
            return f"file not found in index: {file_path}\nrun 'rozn index' to rebuild."

        graph = self.resolve_import_graph(file_path, max_depth=max_depth)

        lines = [f"{root_file.path}"]

        def render_symbols(f: FileIndex, indent: str) -> None:
            for cls in f.classes[:4]:
                lines.append(f"{indent}  class {cls}")
            for fn in f.functions[:6]:
                lines.append(f"{indent}  def {fn}")
            total = len(f.classes) + len(f.functions)
            shown = min(len(f.classes), 4) + min(len(f.functions), 6)
            if total > shown:
                lines.append(f"{indent}  ... and {total - shown} more")

        deps = graph.get(root_file.path, [])
        if not deps:
            lines.append("  no local dependencies found")
        else:
            for dep in deps:
                lines.append(f"  imports {dep.path}")
                render_symbols(dep, "  ")

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
            relative_imports=(),
        )
    except Exception:
        return None

    classes         = []
    class_lines     = []
    functions       = []
    function_lines  = []
    imports         = []
    relative_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
            class_lines.append(node.lineno)
        elif isinstance(node, ast.FunctionDef):
            if not node.name.startswith("__") or node.name == "__init__":
                functions.append(node.name)
                function_lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(".") or not module:
                # relative import — store the module name without leading dot
                clean = module.lstrip(".")
                if clean:
                    relative_imports.append(clean)
                else:
                    # bare relative import like "from . import models"
                    for alias in node.names:
                        relative_imports.append(alias.name)
            else:
                imports.append(module)

    return FileIndex(
        path=str(path.relative_to(root)),
        classes=tuple(classes),
        class_lines=tuple(class_lines),
        functions=tuple(functions),
        function_lines=tuple(function_lines),
        imports=tuple(dict.fromkeys(imports)),
        relative_imports=tuple(dict.fromkeys(relative_imports)),
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


def find_local_imports(
    file_index: FileIndex,
    all_files: tuple[FileIndex, ...],
) -> list[FileIndex]:
    related = []
    seen = set()

    # check relative imports first — these are the real local dependencies
    for imp in file_index.relative_imports:
        imp_clean = imp.replace(".", "/")
        for candidate in all_files:
            if candidate.path == file_index.path:
                continue
            candidate_stem = Path(candidate.path).stem
            candidate_name = Path(candidate.path).name
            if (
                imp_clean == candidate_stem
                or imp_clean.endswith(f"/{candidate_stem}")
                or imp == candidate_stem
            ):
                if candidate.path not in seen:
                    seen.add(candidate.path)
                    related.append(candidate)

    # also check absolute imports for third-party modules
    # that might shadow local names — keep this secondary
    for imp in file_index.imports:
        imp_clean = imp.replace(".", "/")
        for candidate in all_files:
            if candidate.path == file_index.path:
                continue
            candidate_stem = Path(candidate.path).stem
            if imp_clean.endswith(candidate_stem) or imp == candidate_stem:
                if candidate.path not in seen:
                    seen.add(candidate.path)
                    related.append(candidate)

    return related


def get_file_with_deps(
    filename: str,
    index: ProjectIndex,
    max_depth: int = 1,
) -> list[FileIndex]:
    needle = filename.lower().replace("\\", "/")
    root_file = None
    for f in index.files:
        if needle in f.path.lower().replace("\\", "/"):
            root_file = f
            break

    if root_file is None:
        return []

    result = [root_file]
    if max_depth > 0:
        deps = find_local_imports(root_file, index.files)
        for dep in deps[:3]:
            if dep not in result:
                result.append(dep)

    return result


# ── Index builder ─────────────────────────────────────────────────────────────

INDEX_FILENAME = "rozn.index"


def build_index(root: Path | None = None) -> ProjectIndex:
    from datetime import datetime

    project_root = root or Path.cwd()
    src_root     = project_root / "src"
    scan_root    = src_root if src_root.exists() else project_root

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
                    class_lines=tuple(f.get("class_lines", [])),
                    functions=tuple(f["functions"]),
                    function_lines=tuple(f.get("function_lines", [])),
                    imports=tuple(f["imports"]),
                    relative_imports=tuple(f.get("relative_imports", [])),
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