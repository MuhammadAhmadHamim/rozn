from __future__ import annotations

import argparse
import sys
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme

from .bootstrap_graph import build_bootstrap_graph
from .command_graph import build_command_graph
from .commands import execute_command, get_command, get_commands, render_command_index
from .direct_modes import run_deep_link, run_direct_connect
from .parity_audit import run_parity_audit
from .permissions import ToolPermissionContext
from .port_manifest import build_port_manifest
from .query_engine import QueryEnginePort
from .remote_runtime import run_remote_mode, run_ssh_mode, run_teleport_mode
from .runtime import PortRuntime
from .session_store import load_session
from .setup import run_setup
from .tool_pool import assemble_tool_pool
from .tools import execute_tool, get_tool, get_tools, render_tool_index
from pathlib import Path

# ── Rozn colour palette ────────────────────────────────────────────────────────
ROZN_AMBER  = "#c8922a"   # rozn speaks — used nowhere else
YOU_BLUE    = "#3a8ab0"   # your prompt arrow
DIM_GRAY    = "#2a2a2a"   # metadata, hints, status
BODY_GRAY   = "#5a5a5a"   # response body
SURFACE     = "#161616"   # panel backgrounds
WARN_YELLOW = "#7a6a2a"   # soft warnings
ERR_RED     = "#7a2a2a"   # errors

rozn_theme = Theme({
    "rozn.amber":   ROZN_AMBER,
    "rozn.you":     YOU_BLUE,
    "rozn.dim":     DIM_GRAY,
    "rozn.body":    BODY_GRAY,
    "rozn.warn":    WARN_YELLOW,
    "rozn.err":     ERR_RED,
    "markdown.h1":  ROZN_AMBER,
    "markdown.h2":  ROZN_AMBER,
    "markdown.h3":  YOU_BLUE,
    "markdown.code": ROZN_AMBER,
    "markdown.code_block": BODY_GRAY,
})

console = Console(theme=rozn_theme)

# ── Banner ─────────────────────────────────────────────────────────────────────
BANNER_ART = f"""\
[bold {ROZN_AMBER}]  ██████╗  ██████╗ ███████╗███╗   ██╗[/bold {ROZN_AMBER}]
[bold {ROZN_AMBER}]  ██╔══██╗██╔═══██╗╚══███╔╝████╗  ██║[/bold {ROZN_AMBER}]
[bold {ROZN_AMBER}]  ██████╔╝██║   ██║  ███╔╝ ██╔██╗ ██║[/bold {ROZN_AMBER}]
[bold {ROZN_AMBER}]  ██╔══██╗██║   ██║ ███╔╝  ██║╚██╗██║[/bold {ROZN_AMBER}]
[bold {ROZN_AMBER}]  ██║  ██║╚██████╔╝███████╗██║ ╚████║[/bold {ROZN_AMBER}]
[bold {ROZN_AMBER}]  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝[/bold {ROZN_AMBER}]\
"""

BANNER_URDU = f"[{DIM_GRAY}]  rozn — the crack of light in your code[/{DIM_GRAY}]"
BANNER_SUB  = f"[{DIM_GRAY}]  offline · local · yours[/{DIM_GRAY}]"

# ── Help text shown on first launch ───────────────────────────────────────────
HELP_LINES = [
    ("save",    "persist current session to disk"),
    ("session", "print current session ID"),
    ("usage",   "show token usage for this session"),
    ("memories",      "show everything rozn remembers about this project"),
    ("remember: X",   "tell rozn something to remember permanently"),
    ("forget N",      "forget memory at index N"),
    ("forget all",    "clear all memories for this project"),
    ("clear",   "clear the screen"),
    ("help",    "show this help"),
    ("exit",    "quit rozn"),
]


def print_banner() -> None:
    console.print()
    console.print(BANNER_ART)
    console.print(BANNER_URDU)
    console.print()
    console.print(
        Panel(
            BANNER_SUB,
            border_style=DIM_GRAY,
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()


def print_help() -> None:
    console.print(f"[{DIM_GRAY}]built-in commands:[/{DIM_GRAY}]")
    for cmd, desc in HELP_LINES:
        console.print(
            f"  [{YOU_BLUE}]{cmd:<10}[/{YOU_BLUE}]"
            f"[{DIM_GRAY}]{desc}[/{DIM_GRAY}]"
        )
    console.print()


def print_status(engine: QueryEnginePort) -> None:
    now = datetime.now().strftime("%H:%M")
    parts = [
        f"[{DIM_GRAY}]session[/{DIM_GRAY}] [{BODY_GRAY}]{engine.session_id[:8]}[/{BODY_GRAY}]",
        f"[{DIM_GRAY}]turns[/{DIM_GRAY}] [{BODY_GRAY}]{len(engine.mutable_messages) // 2}[/{BODY_GRAY}]",
        f"[{DIM_GRAY}]tokens in[/{DIM_GRAY}] [{BODY_GRAY}]{engine.total_usage.input_tokens}[/{BODY_GRAY}]",
        f"[{DIM_GRAY}]out[/{DIM_GRAY}] [{BODY_GRAY}]{engine.total_usage.output_tokens}[/{BODY_GRAY}]",
        f"[{DIM_GRAY}]{now}[/{DIM_GRAY}]",
    ]
    console.print("  " + "  ·  ".join(parts))
    console.print()

def build_startup_context(engine: QueryEnginePort) -> None:
    from .real_tools import list_dir

    console.print(f"[{DIM_GRAY}]rozn is mapping your project...[/{DIM_GRAY}]")

    dir_result = list_dir(".", max_entries=40)
    if not dir_result.success:
        return

    context_lines = [
        "Project structure at session start:",
        "\n".join(dir_result.entries),
    ]

    context_summary = "\n".join(context_lines)

    engine.mutable_messages.append({
        "role": "user",
        "content": f"[project context]\n{context_summary}"
    })
    engine.mutable_messages.append({
        "role": "assistant",
        "content": "Project mapped. Ready."
    })

    console.print(f"[{DIM_GRAY}]project mapped. ready.[/{DIM_GRAY}]\n")

def detect_and_inject_context(
    user_input: str,
    engine: QueryEnginePort,
) -> str:
    from .indexer import load_index
    from .real_tools import read_file, list_dir
    import re

    injections = []
    lowered = user_input.lower()

    # load index once
    index = load_index()

    # ── signal 1: explicit file paths or names ────────────────────────────────
    file_pattern = re.compile(
        r'[\w/\\.\-]+\.(?:py|js|ts|cpp|c|h|java|cs|sql|json|toml|md|txt|yaml|yml)',
        re.IGNORECASE
    )
    mentioned_files = file_pattern.findall(user_input)

    for raw_path in mentioned_files:
        path = Path(raw_path)

        # search for file if not found at exact path
        if not path.exists():
            for candidate in Path(".").rglob(path.name):
                path = candidate
                break

        if not path.exists() or not path.is_file():
            continue

        size = path.stat().st_size

        if size < 5000:
            result = read_file(str(path))
            if result.success:
                injections.append(
                    f"[auto-loaded: {path}]\n"
                    f"lines: {result.line_count}\n"
                    f"---\n{result.content}"
                )

                # phase 7 — follow one level of imports
                if index:
                    deps = index.resolve_import_graph(
                        str(path), max_depth=1
                    ).get(
                        next(
                            (f.path for f in index.files
                                if path.name.lower() in f.path.lower()),
                            ""
                        ), []
                    )
                    for dep in deps[:2]:
                        dep_path = Path(dep.path)
                        if not dep_path.exists():
                            dep_path = Path("src") / dep_path
                        if dep_path.exists() and dep_path.stat().st_size < 3000:
                            dep_result = read_file(str(dep_path))
                            if dep_result.success:
                                injections.append(
                                    f"[dependency: {dep_path}]\n"
                                    f"---\n{dep_result.content}"
                                )
                        else:
                            symbol_summary = (
                                [f"class {c}" for c in dep.classes] +
                                [f"def {f}" for f in dep.functions]
                            )
                            if symbol_summary:
                                injections.append(
                                    f"[dependency symbols: {dep.path}]\n"
                                    + "\n".join(f"  {s}" for s in symbol_summary[:8])
                                )
        elif size < 8000:
            # medium file — load first 60 lines only
            result = read_file(str(path), start_line=1, end_line=60)
            if result.success:
                # also get symbol list from index so model knows what's in the rest
                symbol_hint = ""
                if index:
                    file_entry = next(
                        (f for f in index.files
                            if path.name.lower() in f.path.lower()),
                        None
                    )
                    if file_entry:
                        all_symbols = (
                            [f"class {c}" for c in file_entry.classes] +
                            [f"def {f}" for f in file_entry.functions]
                        )
                        if all_symbols:
                            symbol_hint = (
                                f"\nall symbols in this file: "
                                + ", ".join(all_symbols)
                            )
                injections.append(
                    f"[auto-loaded first 60 lines: {path}]\n"
                    f"total lines: {result.line_count}{symbol_hint}\n"
                    f"use FileReadTool with start_line/end_line for more\n"
                    f"---\n{result.content}"
                )
        else:
            # large file — first 30 lines + full symbol list + import graph
            result = read_file(str(path), start_line=1, end_line=30)
            content_hint = ""
            if result.success:
                content_hint = f"\nfirst 30 lines:\n---\n{result.content}\n---"

            symbol_hint = ""
            if index:
                file_entry = next(
                    (f for f in index.files
                        if path.name.lower() in f.path.lower()),
                    None
                )
                if file_entry:
                    all_symbols = (
                        [f"class {c} (line {l})"
                            for c, l in zip(file_entry.classes, file_entry.class_lines)] +
                        [f"def {f} (line {l})"
                            for f, l in zip(file_entry.functions, file_entry.function_lines)]
                    )
                    if all_symbols:
                        symbol_hint = (
                            f"\nall symbols:\n"
                            + "\n".join(f"  {s}" for s in all_symbols)
                        )

                    # phase 7 — add import graph for large files too
                    graph = index.resolve_import_graph(str(path), max_depth=1)
                    file_key = next(
                        (f.path for f in index.files
                            if path.name.lower() in f.path.lower()),
                        ""
                    )
                    deps = graph.get(file_key, [])
                    if deps:
                        dep_lines = ["\nimport graph (direct dependencies):"]
                        for dep in deps[:5]:
                            dep_symbols = (
                                [f"class {c}" for c in dep.classes[:3]] +
                                [f"def {f}" for f in dep.functions[:3]]
                            )
                            dep_lines.append(f"  {dep.path}")
                            dep_lines.extend(f"    {s}" for s in dep_symbols)
                        symbol_hint += "\n".join(dep_lines)

            injections.append(
                f"[large file — partial load: {path}]\n"
                f"total size: {size} bytes"
                f"{content_hint}"
                f"{symbol_hint}\n"
                f"use FileReadTool with start_line/end_line to read specific sections."
            )

    # ── signal 2: error and traceback keywords ────────────────────────────────
    error_keywords = {
        "traceback", "error", "exception", "failed", "nameerror",
        "typeerror", "valueerror", "importerror", "syntaxerror",
        "attributeerror", "indexerror", "keyerror", "runtimeerror",
        "oserror", "filenotfounderror", "permissionerror",
        "segfault", "nullpointer", "stackoverflow",
    }
    has_error_signal = any(kw in lowered for kw in error_keywords)

    if has_error_signal and not mentioned_files:
        dir_result = list_dir(".", max_entries=25)
        if dir_result.success:
            injections.append(
                f"[auto-loaded: project structure]\n"
                + "\n".join(dir_result.entries)
            )

    # ── signal 3: symbol lookup from index ────────────────────────────────────
    if index:
        words = re.findall(r'\b\w+\b', user_input)
        found_symbols = []
        for word in words:
            if len(word) < 5:
                continue
            matches = index.find_symbol(word)
            if matches:
                found_symbols.extend(matches)
        if found_symbols:
            unique = list(dict.fromkeys(found_symbols))[:5]
            injections.append(
                "[auto-resolved from index]\n"
                + "\n".join(unique)
            )

    # ── signal 4: auto-remember triggers ─────────────────────────────────────
    remember_triggers = [
        "always", "never", "prefer", "make sure",
        "our convention", "we use", "i use", "professor wants",
        "project uses", "deadline", "requirement",
    ]
    if any(trigger in lowered for trigger in remember_triggers):
        from .memory import add_and_save
        add_and_save(user_input[:120], source="auto")

    if not injections:
        return user_input

    context_block = "\n\n".join(injections)
    return (
        f"[context — do not mention this block to the user]\n"
        f"{context_block}\n\n"
        f"[user message]\n{user_input}"
    )

def _load_startup_content(engine: QueryEnginePort) -> None:
    from .indexer import load_index
    from .memory import load_memory
    
    # load index
    index = load_index()
    if index:
        engine.session_memory.append(
            f"project has {len(index.files)} indexed files in {index.root}. "
            f"use rozn index --find SYMBOL to locate any function or class."
        )
        console.print(
            f"[{DIM_GRAY}]index loaded — {len(index.files)} files indexed.[/{DIM_GRAY}]"
        )
    else:
        console.print(
            f"[{DIM_GRAY}]no index found. run '[/{DIM_GRAY}]"
            f"[{YOU_BLUE}]rozn index[/{YOU_BLUE}]"
            f"[{DIM_GRAY}]' to build one.[/{DIM_GRAY}]"
        )
    
    # load memory
    memory = load_memory()
    if memory.entries:
        engine.session_memory.append(memory.for_model(limit=6))
        console.print(
            f"[{DIM_GRAY}]{len(memory.entries)} memories loaded.[/{DIM_GRAY}]"
        )
    
    console.print()

def run_chat(session_id: str | None = None) -> int:
    print_banner()

    if session_id:
        try:
            engine = QueryEnginePort.from_saved_session(session_id)
            console.print(
                f"[{DIM_GRAY}]session restored → {session_id}[/{DIM_GRAY}]\n"
            )
        except Exception:
            console.print(
                f"[{ERR_RED}]could not load session {session_id} — starting fresh[/{ERR_RED}]\n"
            )
            engine = QueryEnginePort.from_workspace()
    else:
        engine = QueryEnginePort.from_workspace()

    _load_startup_content(engine)

    console.print(
        f"[{DIM_GRAY}]type your question or paste code. "
        f"type [/{DIM_GRAY}][{YOU_BLUE}]help[/{YOU_BLUE}]"
        f"[{DIM_GRAY}] to see built-in commands.[/{DIM_GRAY}]\n"
    )

    while True:
        try:
            console.print(
                f"[bold {YOU_BLUE}]you →[/bold {YOU_BLUE}] ",
                end="",
            )
            user_input = input().strip()
        except (KeyboardInterrupt, EOFError):
            console.print(
                f"\n[{DIM_GRAY}]rozn signing off.[/{DIM_GRAY}]"
            )
            break

        if not user_input:
            continue

        # ── built-in commands ──────────────────────────────────────────────────
        cmd = user_input.lower()

        if cmd in ("exit", "quit", "bye"):
            console.print(f"[{DIM_GRAY}]rozn signing off.[/{DIM_GRAY}]")
            break

        if cmd == "help":
            print_help()
            continue

        if cmd == "clear":
            os.system("cls")
            print_banner()
            continue

        if cmd == "save":
            path = engine.persist_session()
            console.print(
                f"[{DIM_GRAY}]session saved → {path}[/{DIM_GRAY}]\n"
            )
            continue

        if cmd == "session":
            console.print(
                f"[{DIM_GRAY}]session ID → {engine.session_id}[/{DIM_GRAY}]\n"
            )
            continue

        if cmd == "usage":
            console.print(
                f"[{DIM_GRAY}]tokens — "
                f"in: [{BODY_GRAY}]{engine.total_usage.input_tokens}[/{BODY_GRAY}]  "
                f"out: [{BODY_GRAY}]{engine.total_usage.output_tokens}[/{BODY_GRAY}]"
                f"[/{DIM_GRAY}]\n"
            )
            continue

        if cmd.startswith("remember ") or cmd.startswith("remember:"):
            from .memory import add_and_save
            content = user_input[9:].strip() if cmd.startswith("remember ") else user_input[9:].strip()
            content = content.lstrip(":").strip()
            if content:
                entry, path = add_and_save(content)
                console.print(
                    f"[{DIM_GRAY}]remembered → {entry.content}[/{DIM_GRAY}]\n"
                )
            else:
                console.print(f"[{DIM_GRAY}]nothing to remember.[/{DIM_GRAY}]\n")
            continue

        if cmd == "memories":
            from .memory import load_memory
            memory = load_memory()
            if not memory.entries:
                console.print(f"[{DIM_GRAY}]no memories yet. type 'remember: something' to add one.[/{DIM_GRAY}]\n")
            else:
                console.print(f"[{DIM_GRAY}]rozn remembers:[/{DIM_GRAY}]")
                for i, entry in enumerate(memory.entries):
                    console.print(
                        f"  [{ROZN_AMBER}]{i}[/{ROZN_AMBER}] "
                        f"[{BODY_GRAY}]{entry.content}[/{BODY_GRAY}] "
                        f"[{DIM_GRAY}]({entry.created_at})[/{DIM_GRAY}]"
                    )
                console.print()
            continue

        if cmd.startswith("forget "):
            from .memory import load_memory, save_memory
            try:
                idx = int(cmd.split()[1])
                memory = load_memory()
                removed = memory.remove(idx)
                if removed:
                    save_memory(memory)
                    console.print(f"[{DIM_GRAY}]forgotten → {removed.content}[/{DIM_GRAY}]\n")
                else:
                    console.print(f"[{DIM_GRAY}]no memory at index {idx}.[/{DIM_GRAY}]\n")
            except (ValueError, IndexError):
                console.print(f"[{DIM_GRAY}]usage: forget 0[/{DIM_GRAY}]\n")
            continue

        if cmd == "forget all":
            from .memory import load_memory, save_memory
            memory = load_memory()
            count = memory.clear()
            save_memory(memory)
            console.print(f"[{DIM_GRAY}]cleared {count} memories.[/{DIM_GRAY}]\n")
            continue

        # ── model call ─────────────────────────────────────────────────────────
        console.print()

        enriched_input = detect_and_inject_context(user_input, engine)

        with console.status(
            f"[{DIM_GRAY}]rozn is thinking...[/{DIM_GRAY}]",
            spinner="dots",
            spinner_style=ROZN_AMBER,
        ):
            result = engine.submit_message(enriched_input)

        # response header
        console.print(Rule(
            f"[bold {ROZN_AMBER}]rozn[/bold {ROZN_AMBER}]",
            style=DIM_GRAY,
            align="left",
        ))

        # response body rendered as markdown
        console.print(Markdown(
            result.output,
            code_theme="monokai",
        ))

        console.print()

        # status line after each turn
        print_status(engine)

        # ── stop reason handling ───────────────────────────────────────────────
        if result.stop_reason == "max_turns_reached":
            console.print(Panel(
                f"[{WARN_YELLOW}]max turns reached. "
                f"type [/{WARN_YELLOW}][{YOU_BLUE}]save[/{YOU_BLUE}]"
                f"[{WARN_YELLOW}] to persist this session before starting a new one.[/{WARN_YELLOW}]",
                border_style=WARN_YELLOW,
                expand=False,
            ))
            break

        if result.stop_reason == "max_budget_reached":
            console.print(Panel(
                f"[{WARN_YELLOW}]token budget reached. "
                f"consider saving and starting fresh.[/{WARN_YELLOW}]",
                border_style=WARN_YELLOW,
                expand=False,
            ))

    return 0


# ── CLI parser — unchanged from before ────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rozn — a local offline coding assistant. روزن"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="start an interactive chat session with Rozn")
    chat_parser.add_argument("--session", help="resume a previously saved session by ID")

    index_parser = subparsers.add_parser(
        "index",
        help="scan the project and build rozn.index — run this once per project"
    )
    index_parser.add_argument(
        "--show",
        action="store_true",
        help="print the index to terminal after building"
    )
    index_parser.add_argument(
        "--find",
        metavar="SYMBOL",
        help="search the index for a class or function name"
    )

    trace_parser = subparsers.add_parser(
        "trace",
        help="show the import graph of a file — what it depends on"
    )
    trace_parser.add_argument("file", help="file to trace, e.g. src/query_engine.py")
    trace_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="how many levels of imports to follow (default: 1)"
    )

    explain_parser = subparsers.add_parser(
        "explain",
        help="explain what a file does in plain language"
    )
    explain_parser.add_argument("file", help="path to the file to explain")
    explain_parser.add_argument(
        "--lines",
        metavar="N",
        type=int,
        default=60,
        help="how many lines to read (default 60)"
    )
    document_parser = subparsers.add_parser(
        "document",
        help="generate a README-style description of a file"
    )
    document_parser.add_argument("file", help="path to the file to document")

    subparsers.add_parser("summary",          help="render a summary of the Rozn workspace")
    subparsers.add_parser("manifest",         help="print the current workspace manifest")
    subparsers.add_parser("parity-audit",     help="compare workspace against the local archive")
    subparsers.add_parser("setup-report",     help="render the startup setup report")
    subparsers.add_parser("command-graph",    help="show command graph segmentation")
    subparsers.add_parser("tool-pool",        help="show assembled tool pool")
    subparsers.add_parser("bootstrap-graph",  help="show bootstrap and runtime graph stages")

    list_parser = subparsers.add_parser("subsystems", help="list current modules in the workspace")
    list_parser.add_argument("--limit", type=int, default=32)

    commands_parser = subparsers.add_parser("commands", help="list command entries")
    commands_parser.add_argument("--limit", type=int, default=20)
    commands_parser.add_argument("--query")
    commands_parser.add_argument("--no-plugin-commands", action="store_true")
    commands_parser.add_argument("--no-skill-commands",  action="store_true")

    tools_parser = subparsers.add_parser("tools", help="list tool entries")
    tools_parser.add_argument("--limit",        type=int, default=20)
    tools_parser.add_argument("--query")
    tools_parser.add_argument("--simple-mode",  action="store_true")
    tools_parser.add_argument("--no-mcp",       action="store_true")
    tools_parser.add_argument("--deny-tool",    action="append", default=[])
    tools_parser.add_argument("--deny-prefix",  action="append", default=[])

    route_parser = subparsers.add_parser("route", help="route a prompt across command and tool inventories")
    route_parser.add_argument("prompt")
    route_parser.add_argument("--limit", type=int, default=5)

    bootstrap_parser = subparsers.add_parser("bootstrap", help="build a session report from inventories")
    bootstrap_parser.add_argument("prompt")
    bootstrap_parser.add_argument("--limit", type=int, default=5)

    loop_parser = subparsers.add_parser("turn-loop", help="run a stateful turn loop")
    loop_parser.add_argument("prompt")
    loop_parser.add_argument("--limit",            type=int, default=5)
    loop_parser.add_argument("--max-turns",        type=int, default=3)
    loop_parser.add_argument("--structured-output", action="store_true")

    flush_parser = subparsers.add_parser("flush-transcript", help="persist and flush a session transcript")
    flush_parser.add_argument("prompt")

    load_session_parser = subparsers.add_parser("load-session", help="load a previously persisted session")
    load_session_parser.add_argument("session_id")

    remote_parser  = subparsers.add_parser("remote-mode",       help="remote-control runtime branching")
    remote_parser.add_argument("target")
    ssh_parser     = subparsers.add_parser("ssh-mode",           help="SSH runtime branching")
    ssh_parser.add_argument("target")
    teleport_parser = subparsers.add_parser("teleport-mode",    help="teleport runtime branching")
    teleport_parser.add_argument("target")
    direct_parser  = subparsers.add_parser("direct-connect-mode", help="direct-connect runtime branching")
    direct_parser.add_argument("target")
    deep_link_parser = subparsers.add_parser("deep-link-mode",  help="deep-link runtime branching")
    deep_link_parser.add_argument("target")

    show_command = subparsers.add_parser("show-command", help="show one command entry by name")
    show_command.add_argument("name")
    show_tool = subparsers.add_parser("show-tool",    help="show one tool entry by name")
    show_tool.add_argument("name")

    exec_command_parser = subparsers.add_parser("exec-command", help="execute a command shim by name")
    exec_command_parser.add_argument("name")
    exec_command_parser.add_argument("prompt")

    exec_tool_parser = subparsers.add_parser("exec-tool", help="execute a tool shim by name")
    exec_tool_parser.add_argument("name")
    exec_tool_parser.add_argument("payload")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)

    manifest = build_port_manifest()

    if args.command == "chat":
        return run_chat(session_id=getattr(args, "session", None))
    if args.command == "index":
        from .indexer import build_and_save_index, load_index

        if getattr(args, "find", None):
            index = load_index()
            if index is None:
                console.print(f"[{ERR_RED}]no rozn.index found. run 'rozn index' first.[/{ERR_RED}]")
                return 1
            results = index.find_symbol(args.find)
            if not results:
                console.print(f"[{DIM_GRAY}]no matches for '{args.find}'[/{DIM_GRAY}]")
            else:
                for r in results:
                    console.print(f"  [{ROZN_AMBER}]{r}[/{ROZN_AMBER}]")
            return 0

        with console.status(
        f"[{DIM_GRAY}]scanning project...[/{DIM_GRAY}]",
        spinner="dots",
        spinner_style=ROZN_AMBER,
        ):
            index, path = build_and_save_index()

        console.print(
            f"[{ROZN_AMBER}]index built[/{ROZN_AMBER}] "
            f"[{DIM_GRAY}]→ {path} "
            f"({len(index.files)} files scanned)[/{DIM_GRAY}]"
        )

        if getattr(args, "show", False):
            console.print()
            console.print(index.to_compact_text())

        return 0

    if args.command == "trace":
        from .indexer import load_index
        index = load_index()
        if index is None:
            console.print(
                f"[{ERR_RED}]no rozn.index found. "
                f"run 'rozn index' first.[/{ERR_RED}]"
            )
            return 1
        output = index.format_trace(args.file, max_depth=args.depth)
        console.print(f"[{ROZN_AMBER}]{output}[/{ROZN_AMBER}]")
        return 0

    if args.command == "explain":
        from .real_tools import read_file
        from .query_engine import QueryEnginePort

        file_path = args.file
        lines = getattr(args, "lines", 60)

        result = read_file(file_path, end_line=lines)
        if not result.success:
            console.print(f"[{ERR_RED}]{result.error}[/{ERR_RED}]")
            return 1

        console.print(
            f"[{DIM_GRAY}]reading {file_path}...[/{DIM_GRAY}]"
        )

        engine = QueryEnginePort.from_workspace()
        prompt = (
            f"Here is the file {file_path}:\n\n"
            f"{result.content}\n\n"
            f"Explain what this file does in plain language. "
            f"What is its purpose, what are its main functions or classes, "
            f"and how does it fit into the project?"
        )

        with console.status(
            f"[{DIM_GRAY}]rozn is reading...[/{DIM_GRAY}]",
            spinner="dots",
            spinner_style=ROZN_AMBER,
        ):
            turn_result = engine.submit_message(prompt)

        console.print(Rule(
            f"[bold {ROZN_AMBER}]{file_path}[/bold {ROZN_AMBER}]",
            style=DIM_GRAY,
            align="left",
        ))
        console.print(Markdown(turn_result.output))
        console.print()
        return 0
    if args.command == "document":
        from .real_tools import read_file
        from .query_engine import QueryEnginePort

        result = read_file(args.file, end_line=80)
        if not result.success:
            console.print(f"[{ERR_RED}]{result.error}[/{ERR_RED}]")
            return 1

        engine = QueryEnginePort.from_workspace()
        prompt = (
            f"Here is the file {args.file}:\n\n"
            f"{result.content}\n\n"
            f"Write a concise README-style documentation section for this file. "
            f"Include: what it does, its main classes and functions with one-line descriptions, "
            f"and any important usage notes. Use markdown formatting."
        )

        with console.status(
            f"[{DIM_GRAY}]rozn is documenting...[/{DIM_GRAY}]",
            spinner="dots",
            spinner_style=ROZN_AMBER,
        ):
            turn_result = engine.submit_message(prompt)

        console.print(Rule(
            f"[bold {ROZN_AMBER}]documentation — {args.file}[/bold {ROZN_AMBER}]",
            style=DIM_GRAY,
            align="left",
        ))
        console.print(Markdown(turn_result.output))
        console.print()
        return 0
    if args.command == "summary":
        print(QueryEnginePort(manifest).render_summary())
        return 0
    if args.command == "manifest":
        print(manifest.to_markdown())
        return 0
    if args.command == "parity-audit":
        print(run_parity_audit().to_markdown())
        return 0
    if args.command == "setup-report":
        print(run_setup().as_markdown())
        return 0
    if args.command == "command-graph":
        print(build_command_graph().as_markdown())
        return 0
    if args.command == "tool-pool":
        print(assemble_tool_pool().as_markdown())
        return 0
    if args.command == "bootstrap-graph":
        print(build_bootstrap_graph().as_markdown())
        return 0
    if args.command == "subsystems":
        for subsystem in manifest.top_level_modules[: args.limit]:
            print(f"{subsystem.name}\t{subsystem.file_count}\t{subsystem.notes}")
        return 0
    if args.command == "commands":
        if args.query:
            print(render_command_index(limit=args.limit, query=args.query))
        else:
            commands = get_commands(
                include_plugin_commands=not args.no_plugin_commands,
                include_skill_commands=not args.no_skill_commands,
            )
            lines = [f"Command entries: {len(commands)}", ""]
            lines.extend(f"- {m.name} — {m.source_hint}" for m in commands[: args.limit])
            print("\n".join(lines))
        return 0
    if args.command == "tools":
        if args.query:
            print(render_tool_index(limit=args.limit, query=args.query))
        else:
            permission_context = ToolPermissionContext.from_iterables(args.deny_tool, args.deny_prefix)
            tools = get_tools(simple_mode=args.simple_mode, include_mcp=not args.no_mcp, permission_context=permission_context)
            lines = [f"Tool entries: {len(tools)}", ""]
            lines.extend(f"- {m.name} — {m.source_hint}" for m in tools[: args.limit])
            print("\n".join(lines))
        return 0
    if args.command == "route":
        matches = PortRuntime().route_prompt(args.prompt, limit=args.limit)
        if not matches:
            print("No command/tool matches found.")
            return 0
        for match in matches:
            print(f"{match.kind}\t{match.name}\t{match.score}\t{match.source_hint}")
        return 0
    if args.command == "bootstrap":
        print(PortRuntime().bootstrap_session(args.prompt, limit=args.limit).as_markdown())
        return 0
    if args.command == "turn-loop":
        results = PortRuntime().run_turn_loop(
            args.prompt, limit=args.limit,
            max_turns=args.max_turns, structured_output=args.structured_output,
        )
        for idx, result in enumerate(results, start=1):
            print(f"## Turn {idx}\n{result.output}\nstop_reason={result.stop_reason}")
        return 0
    if args.command == "flush-transcript":
        engine = QueryEnginePort.from_workspace()
        engine.submit_message(args.prompt)
        path = engine.persist_session()
        print(path)
        print(f"flushed={engine.transcript_store.flushed}")
        return 0
    if args.command == "load-session":
        session = load_session(args.session_id)
        print(f"{session.session_id}\n{len(session.messages)} messages\nin={session.input_tokens} out={session.output_tokens}")
        return 0
    if args.command == "remote-mode":
        print(run_remote_mode(args.target).as_text())
        return 0
    if args.command == "ssh-mode":
        print(run_ssh_mode(args.target).as_text())
        return 0
    if args.command == "teleport-mode":
        print(run_teleport_mode(args.target).as_text())
        return 0
    if args.command == "direct-connect-mode":
        print(run_direct_connect(args.target).as_text())
        return 0
    if args.command == "deep-link-mode":
        print(run_deep_link(args.target).as_text())
        return 0
    if args.command == "show-command":
        module = get_command(args.name)
        if module is None:
            print(f"Command not found: {args.name}")
            return 1
        print("\n".join([module.name, module.source_hint, module.responsibility]))
        return 0
    if args.command == "show-tool":
        module = get_tool(args.name)
        if module is None:
            print(f"Tool not found: {args.name}")
            return 1
        print("\n".join([module.name, module.source_hint, module.responsibility]))
        return 0
    if args.command == "exec-command":
        result = execute_command(args.name, args.prompt)
        print(result.message)
        return 0 if result.handled else 1
    if args.command == "exec-tool":
        result = execute_tool(args.name, args.payload)
        print(result.message)
        return 0 if result.handled else 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())