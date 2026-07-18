import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/claude-mem-codex/scripts/install-claude-cross-recall.py"
SPEC = importlib.util.spec_from_file_location("installer", SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(installer)


class InstallerTest(unittest.TestCase):
    def test_install_is_idempotent_and_uninstall_preserves_other_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            settings = home / ".claude/settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({
                "hooks": {"SessionStart": [
                    {"hooks": [{"type": "command", "command": "existing-hook"}]},
                    {"hooks": [{
                        "type": "command",
                        "command": "/old/plugin/claude-mem-cross-context.sh codex",
                    }]},
                ]}
            }))

            source = ROOT / "plugins/claude-mem-codex/scripts/claude-mem-cross-context.sh"
            installer.install(home, source)
            installer.install(home, source)
            data = json.loads(settings.read_text())
            commands = [
                hook["command"]
                for group in data["hooks"]["SessionStart"]
                for hook in group["hooks"]
            ]
            self.assertEqual(commands.count("existing-hook"), 1)
            self.assertNotIn("/old/plugin/claude-mem-cross-context.sh codex", commands)
            self.assertEqual(sum(installer.HOOK_NAME in c for c in commands), 1)

            installer.uninstall(home)
            data = json.loads(settings.read_text())
            commands = [
                hook["command"]
                for group in data["hooks"]["SessionStart"]
                for hook in group["hooks"]
            ]
            self.assertEqual(commands, ["existing-hook"])

    def test_hook_wrappers_use_explicit_node_when_path_is_minimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_mem = root / "claude-mem"
            scripts = claude_mem / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "worker-service.cjs").write_text("// fixture\n")
            (scripts / "bun-runner.js").write_text("// fixture\n")

            args_file = root / "args.txt"
            stdin_file = root / "stdin.json"
            node = root / "node"
            node.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" > \"$FAKE_NODE_ARGS\"\n"
                "cat > \"$FAKE_NODE_STDIN\"\n"
                "printf '%s\\n' '{\"continue\":true}'\n"
            )
            node.chmod(0o755)

            env = {
                "HOME": str(root),
                "PATH": "/usr/bin:/bin",
                "CLAUDE_MEM_PLUGIN_ROOT": str(claude_mem),
                "CLAUDE_MEM_NODE": str(node),
                "FAKE_NODE_ARGS": str(args_file),
                "FAKE_NODE_STDIN": str(stdin_file),
            }
            payload = '{"hook_event_name":"UserPromptSubmit"}'
            wrappers = [
                ("claude-mem-hook.sh", ["session-init"], "hook codex session-init"),
                ("claude-mem-cross-context.sh", ["claude-code"], "hook claude-code context"),
            ]
            for script_name, arguments, expected_tail in wrappers:
                completed = subprocess.run(
                    [str(ROOT / "plugins/claude-mem-codex/scripts" / script_name), *arguments],
                    input=payload,
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout), {"continue": True})
                self.assertTrue(args_file.read_text().strip().endswith(expected_tail))
                self.assertEqual(stdin_file.read_text(), payload)

    def test_hook_wrappers_fail_open_on_empty_input_or_runner_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_mem = root / "claude-mem"
            scripts = claude_mem / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "worker-service.cjs").write_text("// fixture\n")
            (scripts / "bun-runner.js").write_text("// fixture\n")

            calls = root / "calls.txt"
            node = root / "node"
            node.write_text(
                "#!/bin/sh\n"
                "printf 'called\\n' >> \"$FAKE_NODE_CALLS\"\n"
                "printf '%s' '{partial-json'\n"
                "exit 7\n"
            )
            node.chmod(0o755)
            env = {
                "HOME": str(root),
                "PATH": "/usr/bin:/bin",
                "CLAUDE_MEM_PLUGIN_ROOT": str(claude_mem),
                "CLAUDE_MEM_NODE": str(node),
                "FAKE_NODE_CALLS": str(calls),
            }
            wrappers = [
                ("claude-mem-hook.sh", ["context"]),
                ("claude-mem-cross-context.sh", ["claude-code"]),
            ]
            for script_name, arguments in wrappers:
                script = ROOT / "plugins/claude-mem-codex/scripts" / script_name
                empty = subprocess.run(
                    [str(script), *arguments],
                    input="",
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                )
                self.assertEqual(empty.returncode, 0, empty.stderr)
                self.assertEqual(empty.stdout, "")
                self.assertFalse(calls.exists())

                failed = subprocess.run(
                    [str(script), *arguments],
                    input='{"hook_event_name":"SessionStart"}',
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                )
                self.assertEqual(failed.returncode, 0, failed.stderr)
                self.assertEqual(failed.stdout, "")
                self.assertTrue(calls.exists())
                calls.unlink()

    def test_stop_hook_sequences_summary_before_optional_hyperswarm(self):
        hooks = json.loads(
            (ROOT / "plugins/claude-mem-codex/hooks/hooks.json").read_text()
        )
        stop_commands = [
            hook["command"]
            for group in hooks["hooks"]["Stop"]
            for hook in group["hooks"]
        ]
        self.assertEqual(
            stop_commands,
            ['"$PLUGIN_ROOT/scripts/claude-mem-stop.sh"'],
        )

        script = (
            ROOT / "plugins/claude-mem-codex/scripts/claude-mem-stop.sh"
        ).read_text()
        summary_pos = script.index('claude-mem-hook.sh" summarize')
        capture_pos = script.index("capture --runtime claude_mem_session")
        push_pos = script.index('"$hs" push')
        self.assertLess(summary_pos, capture_pos)
        self.assertLess(capture_pos, push_pos)
        self.assertIn('CODEX_NO_INTERACTIVE:-', script)
        self.assertIn("&\n", script)


if __name__ == "__main__":
    unittest.main()
