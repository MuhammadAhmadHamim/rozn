from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

import requests

from .commands import build_command_backlog
from .models import PermissionDenial, UsageSummary
from .port_manifest import PortManifest, build_port_manifest
from .session_store import StoredSession, load_session, save_session
from .tools import build_tool_backlog
from .transcript import TranscriptStore

from .real_tools import (
    dispatch_tool,
    read_file,
    run_bash,
    edit_file,
    list_dir,
    FileReadResult,
    BashResult,
    FileEditResult,
    ListDirResult,
    TOOL_LOOP_LIMIT,
)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5-coder:3b"

ROZN_SYSTEM_PROMPT = """You are Rozn — a precise, local, offline coding assistant.
Your name comes from the Urdu word روزن — a crack of light through a dark wall.
A developer buried in errors is in darkness. You are the single shaft of light
that finds exactly what is wrong — nothing more, nothing less.

════════════════════════════════════════
TOOLS
════════════════════════════════════════

You have four tools. Call a tool by responding with ONLY a single JSON object —
no text before it, no text after it, no markdown fences around it.

{"tool": "ListDirTool", "path": ".", "max_entries": 80}
{"tool": "FileReadTool", "path": "path/to/file.py"}
{"tool": "FileReadTool", "path": "path/to/file.py", "start_line": 1, "end_line": 50}
{"tool": "BashTool", "command": "python --version", "cwd": "optional/path"}
{"tool": "FileEditTool", "path": "file.py", "old_content": "exact text to find", "new_content": "replacement text"}

════════════════════════════════════════
CORE RULES
════════════════════════════════════════

- Never guess at file contents. If a file is mentioned, read it first.
- Never guess at command output. If you need to know, run it.
- Only edit files when the user explicitly asks for a change.
- Always read a file before editing it.
- For large files, read in sections using start_line and end_line.
- After every tool result, explain what you found in plain language.
- One problem, one fix. Not a list of possibilities — the answer.
- You run fully offline. That is a feature, not a limitation.

════════════════════════════════════════
WHEN ASKED ABOUT YOUR OWN CODEBASE
════════════════════════════════════════

Never answer questions about any project from memory.
Always verify by reading the relevant file.
If someone asks whether something is defined, read the file and confirm.
If someone asks whether something works, run it and confirm.
Memory is unreliable. Files are truth.

════════════════════════════════════════
WHEN YOU SEE A TRACEBACK
════════════════════════════════════════

A traceback is a map. Read it bottom to top.
The last line is the error type and message — that is your starting point.
The line above it is where it happened — that is your target.
Everything above that is how execution got there — that is context.

Do this every time:
1. Identify the error type and message precisely.
2. Identify the exact file and line number where it happened.
3. Read that file at that line before saying anything else.
4. State the cause in one sentence.
5. Give the fix — the exact change, not a suggestion.

Never say "this might be caused by" when you have the file and line number.
You have the tools to know for certain. Use them.

════════════════════════════════════════
WHEN YOU SEE A SYNTAX ERROR
════════════════════════════════════════

Python tells you the file and line. Go there immediately.
Syntax errors are almost always one of:
- missing colon after if / for / def / class
- mismatched brackets, parentheses, or quotes
- wrong indentation after a block
- f-string with nested quotes of the same type

Read the line and the two lines above it.
State what is wrong on that line specifically.
Show the corrected line, not the whole function.

════════════════════════════════════════
WHEN SOMETHING WORKS LOCALLY BUT FAILS ELSEWHERE
════════════════════════════════════════

This is almost always one of three things:
- a missing dependency that exists on one machine but not another
- an environment variable that is set locally but not in the other environment
- a relative path that resolves differently depending on working directory

Ask which environment is failing before suggesting fixes.
Run the failing command with BashTool if possible to see the actual error.
Never suggest "try reinstalling" without a specific reason.

════════════════════════════════════════
WHEN TESTS ARE FAILING
════════════════════════════════════════

1. Run the tests first with BashTool to see the actual output.
2. Read the specific test that is failing — not the whole test file.
3. Read the function being tested.
4. The failure is either in the test's assumptions or in the function's behaviour. State which one it is before suggesting a fix.
5. Never modify a test to make it pass unless the test is genuinely wrong.

════════════════════════════════════════
WHEN YOU DO NOT KNOW
════════════════════════════════════════

Say so directly. "I don't know" is better than a confident wrong answer.
If you need more information, ask for one specific thing — not a list of questions.
If the problem requires seeing a file, say which file and why.

════════════════════════════════════════
TONE
════════════════════════════════════════

Short. Direct. No filler phrases like "Great question" or "Certainly".
No bullet lists of things that might be wrong when you can find out for certain.
No apologies. No hedging. Just the answer.
When something is complex, be precise — not verbose.
You are the crack of light. Not a floodlight. Not a search engine.
One beam. Exactly where it needs to go.
"""


@dataclass(frozen=True)
class QueryEngineConfig:
    max_turns: int = 8
    max_budget_tokens: int = 2000
    compact_after_turns: int = 12
    structured_output: bool = False
    structured_retry_limit: int = 2


@dataclass(frozen=True)
class TurnResult:
    prompt: str
    output: str
    matched_commands: tuple[str, ...]
    matched_tools: tuple[str, ...]
    permission_denials: tuple[PermissionDenial, ...]
    usage: UsageSummary
    stop_reason: str


@dataclass
class QueryEnginePort:
    manifest: PortManifest
    config: QueryEngineConfig = field(default_factory=QueryEngineConfig)
    session_id: str = field(default_factory=lambda: uuid4().hex)
    mutable_messages: list[dict] = field(default_factory=list)
    session_memory: list[str] = field(default_factory=list)
    permission_denials: list[PermissionDenial] = field(default_factory=list)
    total_usage: UsageSummary = field(default_factory=UsageSummary)
    transcript_store: TranscriptStore = field(default_factory=TranscriptStore)

    @classmethod
    def from_workspace(cls) -> 'QueryEnginePort':
        return cls(manifest=build_port_manifest())

    @classmethod
    def from_saved_session(cls, session_id: str) -> 'QueryEnginePort':
        stored = load_session(session_id)
        transcript = TranscriptStore(entries=list(stored.messages), flushed=True)
        return cls(
            manifest=build_port_manifest(),
            session_id=stored.session_id,
            mutable_messages=list(stored.messages),
            total_usage=UsageSummary(stored.input_tokens, stored.output_tokens),
            transcript_store=transcript,
        )

    def _compress_turn(self, prompt: str, output: str) -> str:
        prompt_short = prompt[:50].replace("\n", " ").strip()
        output_short = output[:80].replace("\n", " ").strip()
        return f"t{len(self.session_memory)+1}: {prompt_short} → {output_short}"

    def _call_ollama(self, prompt: str) -> tuple[str, int, int]:
        import re as _re
        import json as _json

        messages = [{"role": "system", "content": ROZN_SYSTEM_PROMPT}]

        # inject compressed memory if we have any
        if self.session_memory:
            memory_block = "\n".join(self.session_memory[-2:])
            messages.append({
                "role": "user",
                "content": f"[session memory]\n{memory_block}"
            })
            messages.append({
                "role": "assistant",
                "content": "Understood."
            })

        for msg in self.mutable_messages[-2:]:
            messages.append(msg)

        messages.append({"role": "user", "content": prompt})

        total_input_tokens  = 0
        total_output_tokens = 0
        content             = ""

        for attempt in range(TOOL_LOOP_LIMIT):
            try:
                response = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=300,
                )
                response.raise_for_status()
                data    = response.json()
                content = data["message"]["content"].strip()
                total_input_tokens  += data.get("prompt_eval_count", len(prompt.split()))
                total_output_tokens += data.get("eval_count", len(content.split()))

            except requests.exceptions.ConnectionError:
                return "Rozn cannot reach Ollama. Make sure Ollama is running on port 11434.", 0, 0
            except requests.exceptions.Timeout:
                return "Rozn timed out waiting for the model. The prompt may be too long.", 0, 0
            except Exception as exc:
                return f"Rozn encountered an unexpected error: {exc}", 0, 0


            # ── tool detection ─────────────────────────────────────────────────────

            cleaned = content.strip()

            # strip markdown fences if model wrapped JSON in them
            fence_match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, _re.DOTALL)
            if fence_match:
                cleaned = fence_match.group(1).strip()

            # some models prefix with a line of text before the JSON — grab last { block
            if not cleaned.startswith("{") and "{" in cleaned:
                cleaned = cleaned[cleaned.rfind("{"):]

            if cleaned.startswith("{") and '"tool"' in cleaned:
                try:
                    tool_payload = _json.loads(cleaned)
                    tool_name    = tool_payload.pop("tool", "")
                    tool_result  = dispatch_tool(tool_name, tool_payload)

                    # feed tool result back into conversation
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"Tool result for {tool_name}:\n{tool_result}\n\nNow answer the user's original question using this information."
                    })
                    continue

                except _json.JSONDecodeError as e:
                    print(f"[debug] JSON parse failed: {e}", file=sys.stderr)

            # no tool call detected — this is the final answer
            return content, total_input_tokens, total_output_tokens

        # hit loop limit — force a final plain language answer
        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": "Please summarise what you found and answer the original question in plain language. Do not call any more tools."
        })

        try:
            response = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            final = data["message"]["content"].strip()
            total_input_tokens  += data.get("prompt_eval_count", 0)
            total_output_tokens += data.get("eval_count", 0)
            return final, total_input_tokens, total_output_tokens

        except Exception:
            return content, total_input_tokens, total_output_tokens

    def submit_message(
        self,
        prompt: str,
        matched_commands: tuple[str, ...] = (),
        matched_tools: tuple[str, ...] = (),
        denied_tools: tuple[PermissionDenial, ...] = (),
    ) -> TurnResult:
        if len(self.mutable_messages) >= self.config.max_turns * 2:
            output = f"Max turns reached before processing prompt: {prompt}"
            return TurnResult(
                prompt=prompt,
                output=output,
                matched_commands=matched_commands,
                matched_tools=matched_tools,
                permission_denials=denied_tools,
                usage=self.total_usage,
                stop_reason="max_turns_reached",
            )

        output, input_tokens, output_tokens = self._call_ollama(prompt)
        
        self.session_memory.append(self._compress_turn(prompt, output))
        self.mutable_messages.append({"role": "user", "content": prompt})
        self.mutable_messages.append({"role": "assistant", "content": output})
        self.transcript_store.append(prompt)
        self.permission_denials.extend(denied_tools)

        self.total_usage = UsageSummary(
            input_tokens=self.total_usage.input_tokens + input_tokens,
            output_tokens=self.total_usage.output_tokens + output_tokens,
        )

        stop_reason = "completed"
        if self.total_usage.input_tokens + self.total_usage.output_tokens > self.config.max_budget_tokens:
            stop_reason = "max_budget_reached"

        self.compact_messages_if_needed()

        return TurnResult(
            prompt=prompt,
            output=output,
            matched_commands=matched_commands,
            matched_tools=matched_tools,
            permission_denials=denied_tools,
            usage=self.total_usage,
            stop_reason=stop_reason,
        )

    def stream_submit_message(
        self,
        prompt: str,
        matched_commands: tuple[str, ...] = (),
        matched_tools: tuple[str, ...] = (),
        denied_tools: tuple[PermissionDenial, ...] = (),
    ):
        yield {"type": "message_start", "session_id": self.session_id, "prompt": prompt}
        if matched_commands:
            yield {"type": "command_match", "commands": matched_commands}
        if matched_tools:
            yield {"type": "tool_match", "tools": matched_tools}
        if denied_tools:
            yield {"type": "permission_denial", "denials": [d.tool_name for d in denied_tools]}

        try:
            messages = [{"role": "system", "content": ROZN_SYSTEM_PROMPT}]
            for msg in self.mutable_messages[-2:]:
                messages.append(msg)
            messages.append({"role": "user", "content": prompt})

            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": True,
                },
                stream=True,
                timeout=300,
            )
            response.raise_for_status()

            full_output = []
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_output.append(token)
                        yield {"type": "message_delta", "text": token}
                    if chunk.get("done"):
                        input_tokens = chunk.get("prompt_eval_count", 0)
                        output_tokens = chunk.get("eval_count", 0)
                        assembled = "".join(full_output)
                        self.mutable_messages.append({"role": "user", "content": prompt})
                        self.mutable_messages.append({"role": "assistant", "content": assembled})
                        self.transcript_store.append(prompt)
                        self.total_usage = UsageSummary(
                            input_tokens=self.total_usage.input_tokens + input_tokens,
                            output_tokens=self.total_usage.output_tokens + output_tokens,
                        )
                        self.compact_messages_if_needed()
                        yield {
                            "type": "message_stop",
                            "usage": {
                                "input_tokens": self.total_usage.input_tokens,
                                "output_tokens": self.total_usage.output_tokens,
                            },
                            "stop_reason": "completed",
                            "transcript_size": len(self.transcript_store.entries),
                        }

        except Exception as exc:
            yield {"type": "error", "message": str(exc)}

    def compact_messages_if_needed(self) -> None:
        max_stored = self.config.compact_after_turns * 2
        if len(self.mutable_messages) > max_stored:
            self.mutable_messages[:] = self.mutable_messages[-max_stored:]
        self.transcript_store.compact(self.config.compact_after_turns)

    def replay_user_messages(self) -> tuple[str, ...]:
        return self.transcript_store.replay()

    def flush_transcript(self) -> None:
        self.transcript_store.flush()

    def persist_session(self) -> str:
        self.flush_transcript()
        path = save_session(
            StoredSession(
                session_id=self.session_id,
                messages=tuple(
                    m["content"] for m in self.mutable_messages
                    if m.get("role") == "user"
                ),
                input_tokens=self.total_usage.input_tokens,
                output_tokens=self.total_usage.output_tokens,
            )
        )
        return str(path)

    def _format_output(self, summary_lines: list[str]) -> str:
        if self.config.structured_output:
            payload = {
                "summary": summary_lines,
                "session_id": self.session_id,
            }
            return self._render_structured_output(payload)
        return "\n".join(summary_lines)

    def _render_structured_output(self, payload: dict[str, object]) -> str:
        last_error: Exception | None = None
        for _ in range(self.config.structured_retry_limit):
            try:
                return json.dumps(payload, indent=2)
            except (TypeError, ValueError) as exc:
                last_error = exc
                payload = {"summary": ["structured output retry"], "session_id": self.session_id}
        raise RuntimeError("structured output rendering failed") from last_error

    def render_summary(self) -> str:
        command_backlog = build_command_backlog()
        tool_backlog = build_tool_backlog()
        sections = [
            "# Rozn — Local Coding Assistant",
            "",
            self.manifest.to_markdown(),
            "",
            f"Command surface: {len(command_backlog.modules)} entries",
            *command_backlog.summary_lines()[:10],
            "",
            f"Tool surface: {len(tool_backlog.modules)} entries",
            *tool_backlog.summary_lines()[:10],
            "",
            f"Session id: {self.session_id}",
            f"Conversation turns stored: {len(self.mutable_messages) // 2}",
            f"Permission denials tracked: {len(self.permission_denials)}",
            f"Usage totals: in={self.total_usage.input_tokens} out={self.total_usage.output_tokens}",
            f"Max turns: {self.config.max_turns}",
            f"Max budget tokens: {self.config.max_budget_tokens}",
            f"Transcript flushed: {self.transcript_store.flushed}",
        ]
        return "\n".join(sections)