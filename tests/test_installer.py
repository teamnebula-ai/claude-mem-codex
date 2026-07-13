import importlib.util
import json
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
                "hooks": {"SessionStart": [{"hooks": [{
                    "type": "command", "command": "existing-hook"
                }]}]}
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
            self.assertEqual(sum(installer.HOOK_NAME in c for c in commands), 1)

            installer.uninstall(home)
            data = json.loads(settings.read_text())
            commands = [
                hook["command"]
                for group in data["hooks"]["SessionStart"]
                for hook in group["hooks"]
            ]
            self.assertEqual(commands, ["existing-hook"])


if __name__ == "__main__":
    unittest.main()

