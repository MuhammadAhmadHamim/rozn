from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


MEMORY_FILENAME = "rozn.memory"
MAX_MEMORIES = 40


@dataclass(frozen=True)
class MemoryEntry:
    content: str
    created_at: str
    source: str = "user"


@dataclass
class ProjectMemory:
    project_root: str
    entries: list[MemoryEntry] = field(default_factory=list)

    def add(self, content: str, source: str = "user") -> MemoryEntry:
        entry = MemoryEntry(
            content=content.strip(),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            source=source,
        )
        self.entries.append(entry)
        if len(self.entries) > MAX_MEMORIES:
            self.entries = self.entries[-MAX_MEMORIES:]
        return entry

    def clear(self) -> int:
        count = len(self.entries)
        self.entries.clear()
        return count

    def remove(self, index: int) -> MemoryEntry | None:
        if 0 <= index < len(self.entries):
            return self.entries.pop(index)
        return None

    def search(self, query: str) -> list[tuple[int, MemoryEntry]]:
        needle = query.lower()
        return [
            (i, entry) for i, entry in enumerate(self.entries)
            if needle in entry.content.lower()
        ]

    def for_model(self, limit: int = 8) -> str:
        if not self.entries:
            return ""
        recent = self.entries[-limit:]
        lines = ["[rozn memory — things you told me about this project]"]
        for entry in recent:
            lines.append(f"- {entry.content}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({
            "project_root": self.project_root,
            "entries": [
                {
                    "content": e.content,
                    "created_at": e.created_at,
                    "source": e.source,
                }
                for e in self.entries
            ]
        }, indent=2)


def load_memory(root: Path | None = None) -> ProjectMemory:
    project_root = root or Path.cwd()
    path = project_root / MEMORY_FILENAME

    if not path.exists():
        return ProjectMemory(project_root=str(project_root))

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectMemory(
            project_root=data.get("project_root", str(project_root)),
            entries=[
                MemoryEntry(
                    content=e["content"],
                    created_at=e.get("created_at", "unknown"),
                    source=e.get("source", "user"),
                )
                for e in data.get("entries", [])
            ]
        )
    except Exception:
        return ProjectMemory(project_root=str(project_root))


def save_memory(memory: ProjectMemory, root: Path | None = None) -> Path:
    project_root = root or Path.cwd()
    path = project_root / MEMORY_FILENAME
    path.write_text(memory.to_json(), encoding="utf-8")
    return path


def add_and_save(
    content: str,
    source: str = "user",
    root: Path | None = None,
) -> tuple[MemoryEntry, Path]:
    memory = load_memory(root)
    entry = memory.add(content, source=source)
    path = save_memory(memory, root)
    return entry, path