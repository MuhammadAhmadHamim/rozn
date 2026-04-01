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

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5-coder:3b"

ROZN_SYSTEM_PROMPT = """You are Rozn — a precise, local, offline coding assistant.
Your name comes from the Urdu word روزن — a crack of light through a dark wall.
A developer buried in errors is in darkness. You are the single shaft of light.

You have access to four tools. Use them by responding with ONLY a single JSON
object on one line — no explanation before or after the JSON when calling a tool.

{"tool": "FileReadTool", "path": "path/to/file.py"}
{"tool": "BashTool", "command": "python --version", "cwd": "optional/path"}
{"tool": "FileEditTool", "path": "file.py", "old_content": "exact text to find", "new_content": "replacement text"}
{"tool": "ListDirTool", "path": ".", "max_entries": 80}

Rules:
- If the user mentions a file by name, read it before answering. Never guess at contents.
- If you need to explore the project structure, use ListDirTool first.
- Use BashTool to run, test, or diagnose — never guess what a command will output.
- Only edit files when the user explicitly asks for changes.
- Always read a file before editing it.
- After a tool returns results, explain what you found in plain language.
- Be precise. One problem, one fix. Not ten possibilities.
- You run fully offline on the developer's machine. That is a feature, not a limitation.
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

    def _call_ollama(self, prompt: str) -> tuple[str, int, int]:
        messages = [{"role": "system", "content": ROZN_SYSTEM_PROMPT}]

        for msg in self.mutable_messages[-6:]:
            messages.append(msg)

        messages.append({"role": "user", "content": prompt})

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            content = data["message"]["content"]
            input_tokens = data.get("prompt_eval_count", len(prompt.split()))
            output_tokens = data.get("eval_count", len(content.split()))
            return content, input_tokens, output_tokens

        except requests.exceptions.ConnectionError:
            return (
                "Rozn cannot reach Ollama. Make sure Ollama is running on port 11434.",
                0, 0,
            )
        except requests.exceptions.Timeout:
            return (
                "Rozn timed out waiting for the model. The prompt may be too long.",
                0, 0,
            )
        except Exception as exc:
            return f"Rozn encountered an unexpected error: {exc}", 0, 0

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
            for msg in self.mutable_messages[-6:]:
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
                timeout=120,
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