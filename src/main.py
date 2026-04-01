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

BANNER_URDU = f"[{DIM_GRAY}]  rozn— the crack of light in your code[/{DIM_GRAY}]"
BANNER_SUB  = f"[{DIM_GRAY}]  offline · local · yours[/{DIM_GRAY}]"

# ── Help text shown on first launch ───────────────────────────────────────────
HELP_LINES = [
    ("save",    "persist current session to disk"),
    ("session", "print current session ID"),
    ("usage",   "show token usage for this session"),
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

        # ── model call ─────────────────────────────────────────────────────────
        console.print()

        with console.status(
            f"[{DIM_GRAY}]rozn is thinking...[/{DIM_GRAY}]",
            spinner="dots",
            spinner_style=ROZN_AMBER,
        ):
            result = engine.submit_message(user_input)

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