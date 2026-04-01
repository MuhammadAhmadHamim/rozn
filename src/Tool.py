from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    purpose: str
    real: bool = False  # True = actually implemented, False = mirrored/snapshot only


DEFAULT_TOOLS = (
    ToolDefinition('port_manifest',  'Summarize the active Python workspace'),
    ToolDefinition('query_engine',   'Render a Python-first porting summary'),
)

ROZN_TOOLS = (
    ToolDefinition('FileReadTool',  'Read a file from disk and return its contents',  real=True),
    ToolDefinition('BashTool',      'Run a shell command and return stdout/stderr',    real=True),
    ToolDefinition('FileEditTool',  'Replace a specific section of a file on disk',   real=True),
    ToolDefinition('ListDirTool',   'List the contents of a directory',               real=True),    
)

ALL_TOOLS = DEFAULT_TOOLS + ROZN_TOOLS