from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortingTask:
    name: str
    description: str
    status: str = 'pending'