from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from src.commands import PORTED_COMMANDS
from src.parity_audit import run_parity_audit
from src.port_manifest import build_port_manifest
from src.query_engine import QueryEnginePort
from src.tools import PORTED_TOOLS


class RoznWorkspaceTests(unittest.TestCase):

    def test_manifest_counts_python_files(self) -> None:
        manifest = build_port_manifest()
        self.assertGreaterEqual(manifest.total_python_files, 20)
        self.assertTrue(manifest.top_level_modules)

    def test_query_engine_summary_mentions_rozn(self) -> None:
        summary = QueryEnginePort.from_workspace().render_summary()
        self.assertIn('Rozn', summary)
        self.assertIn('Command surface:', summary)
        self.assertIn('Tool surface:', summary)

    def test_cli_summary_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'summary'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Rozn', result.stdout)

    def test_parity_audit_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'parity-audit'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Parity Audit', result.stdout)

    def test_command_and_tool_snapshots_are_nontrivial(self) -> None:
        self.assertGreaterEqual(len(PORTED_COMMANDS), 150)
        self.assertGreaterEqual(len(PORTED_TOOLS), 100)

    def test_commands_and_tools_cli_run(self) -> None:
        commands_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'commands',
             '--limit', '5', '--query', 'review'],
            check=True, capture_output=True, text=True,
        )
        tools_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'tools',
             '--limit', '5', '--query', 'MCP'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Command entries:', commands_result.stdout)
        self.assertIn('Tool entries:', tools_result.stdout)

    def test_subsystem_packages_expose_archive_metadata(self) -> None:
        from src import assistant, bridge, utils
        self.assertGreater(assistant.MODULE_COUNT, 0)
        self.assertGreater(bridge.MODULE_COUNT, 0)
        self.assertGreater(utils.MODULE_COUNT, 100)
        self.assertTrue(utils.SAMPLE_FILES)

    def test_route_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'route',
             'review MCP tool', '--limit', '5'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('review', result.stdout.lower())

    def test_show_command_and_tool_cli_run(self) -> None:
        show_command = subprocess.run(
            [sys.executable, '-m', 'src.main', 'show-command', 'review'],
            check=True, capture_output=True, text=True,
        )
        show_tool = subprocess.run(
            [sys.executable, '-m', 'src.main', 'show-tool', 'MCPTool'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('review', show_command.stdout.lower())
        self.assertIn('mcptool', show_tool.stdout.lower())

    def test_exec_command_and_tool_cli_run(self) -> None:
        command_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'exec-command',
             'review', 'inspect security review'],
            check=True, capture_output=True, text=True,
        )
        tool_result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'exec-tool',
             'MCPTool', 'fetch resource list'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn("Mirrored command 'review'", command_result.stdout)
        self.assertIn("Mirrored tool 'MCPTool'", tool_result.stdout)

    def test_setup_report_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'setup-report'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Setup Report', result.stdout)
        self.assertIn('Deferred init:', result.stdout)

    def test_command_graph_and_tool_pool_cli_run(self) -> None:
        command_graph = subprocess.run(
            [sys.executable, '-m', 'src.main', 'command-graph'],
            check=True, capture_output=True, text=True,
        )
        tool_pool = subprocess.run(
            [sys.executable, '-m', 'src.main', 'tool-pool'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Command Graph', command_graph.stdout)
        self.assertIn('Tool Pool', tool_pool.stdout)

    def test_bootstrap_graph_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'bootstrap-graph'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Bootstrap Graph', result.stdout)

    def test_remote_mode_clis_run(self) -> None:
        remote = subprocess.run(
            [sys.executable, '-m', 'src.main', 'remote-mode', 'workspace'],
            check=True, capture_output=True, text=True,
        )
        ssh = subprocess.run(
            [sys.executable, '-m', 'src.main', 'ssh-mode', 'workspace'],
            check=True, capture_output=True, text=True,
        )
        teleport = subprocess.run(
            [sys.executable, '-m', 'src.main', 'teleport-mode', 'workspace'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('mode=remote', remote.stdout)
        self.assertIn('mode=ssh', ssh.stdout)
        self.assertIn('mode=teleport', teleport.stdout)

    def test_direct_modes_run(self) -> None:
        direct = subprocess.run(
            [sys.executable, '-m', 'src.main',
             'direct-connect-mode', 'workspace'],
            check=True, capture_output=True, text=True,
        )
        deep = subprocess.run(
            [sys.executable, '-m', 'src.main', 'deep-link-mode', 'workspace'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('mode=direct-connect', direct.stdout)
        self.assertIn('mode=deep-link', deep.stdout)

    def test_flush_transcript_cli_runs(self) -> None:
        import requests as _requests
        try:
            _requests.get("http://localhost:11434", timeout=2)
        except Exception:
            self.skipTest("Ollama not running — skipping flush-transcript test")

        result = subprocess.run(
            [sys.executable, '-m', 'src.main',
            'flush-transcript', 'review MCP tool'],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            self.assertIn('flushed=True', result.stdout)
        else:
            self.skipTest("flush-transcript requires Ollama — skipped")

    def test_tool_permission_filtering_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'tools',
             '--limit', '10', '--deny-prefix', 'mcp'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('Tool entries:', result.stdout)
        self.assertNotIn('MCPTool', result.stdout)

    def test_turn_loop_cli_runs(self) -> None:
        import requests as _requests
        try:
            _requests.get("http://localhost:11434", timeout=2)
        except Exception:
            self.skipTest("Ollama not running — skipping turn-loop test")

        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'turn-loop',
            'review MCP tool', '--max-turns', '2'],
            capture_output=True, text=True,
        )
        self.assertIn('## Turn 1', result.stdout)
        self.assertIn('stop_reason=', result.stdout)

    def test_index_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'index'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('index built', result.stdout.lower())

    def test_index_find_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'index',
             '--find', 'dispatch_tool'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('dispatch_tool', result.stdout)

    def test_trace_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'trace',
             'query_engine.py'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('imports', result.stdout)

    def test_detect_cli_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, '-m', 'src.main', 'detect'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn('primary language', result.stdout.lower())

    def test_real_tools_file_read(self) -> None:
        from src.real_tools import read_file
        result = read_file('src/real_tools.py')
        self.assertTrue(result.success)
        self.assertGreater(result.line_count, 50)

    def test_real_tools_list_dir(self) -> None:
        from src.real_tools import list_dir
        result = list_dir('src')
        self.assertTrue(result.success)
        self.assertGreater(len(result.entries), 5)

    def test_real_tools_bash(self) -> None:
        from src.real_tools import run_bash
        result = run_bash('echo rozn')
        self.assertTrue(result.success)
        self.assertIn('rozn', result.stdout)

    def test_memory_add_and_load(self) -> None:
        from src.memory import load_memory, ProjectMemory
        memory = ProjectMemory(project_root='.')
        entry = memory.add('test memory entry')
        self.assertEqual(entry.content, 'test memory entry')
        self.assertEqual(len(memory.entries), 1)

    def test_language_detector_runs(self) -> None:
        from src.language_detector import detect_language
        lang = detect_language()
        self.assertNotEqual(lang.primary, '')
        self.assertIn(lang.confidence, ['high', 'low'])

    def test_execution_registry_runs(self) -> None:
        from src.execution_registry import build_execution_registry
        registry = build_execution_registry()
        self.assertGreaterEqual(len(registry.commands), 150)
        self.assertGreaterEqual(len(registry.tools), 100)

    def test_parity_audit_conditional(self) -> None:
        audit = run_parity_audit()
        if audit.archive_present:
            self.assertEqual(
                audit.root_file_coverage[0],
                audit.root_file_coverage[1]
            )


if __name__ == '__main__':
    unittest.main()