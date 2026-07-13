#!/usr/bin/env python3
"""Install or remove the Claude Code half of bidirectional recall."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from pathlib import Path


HOOK_NAME = "claude-mem-codex-cross-context.sh"


def install(home: Path, source: Path) -> tuple[Path, Path]:
    claude_dir = home / ".claude"
    settings_path = claude_dir / "settings.json"
    hook_path = claude_dir / "hooks" / HOOK_NAME
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, hook_path)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        backup = settings_path.with_suffix(".json.claude-mem-codex.bak")
        if not backup.exists():
            shutil.copy2(settings_path, backup)
    else:
        settings = {}
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    command = f'"{hook_path}" codex'
    groups = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
    for group in groups:
        group["hooks"] = [
            hook for hook in group.get("hooks", [])
            if not (
                "claude-mem-cross-context.sh" in str(hook.get("command", ""))
                and str(hook.get("command", "")).strip().endswith(" codex")
                and hook.get("command") != command
            )
        ]
    groups[:] = [group for group in groups if group.get("hooks")]
    present = any(
        command == hook.get("command")
        for group in groups
        for hook in group.get("hooks", [])
        if isinstance(hook, dict)
    )
    if not present:
        groups.append({
            "hooks": [{
                "type": "command",
                "command": command,
                "timeout": 60,
                "statusMessage": "Loading Codex memory",
            }]
        })

    temp = settings_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, settings_path)
    return settings_path, hook_path


def uninstall(home: Path) -> tuple[Path, Path]:
    settings_path = home / ".claude" / "settings.json"
    hook_path = home / ".claude" / "hooks" / HOOK_NAME
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        groups = settings.get("hooks", {}).get("SessionStart", [])
        for group in groups:
            group["hooks"] = [
                hook for hook in group.get("hooks", [])
                if HOOK_NAME not in str(hook.get("command", ""))
            ]
        settings["hooks"]["SessionStart"] = [g for g in groups if g.get("hooks")]
        temp = settings_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, settings_path)
    hook_path.unlink(missing_ok=True)
    return settings_path, hook_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = Path(__file__).with_name("claude-mem-cross-context.sh")
    settings, hook = uninstall(args.home) if args.uninstall else install(args.home, source)
    action = "Removed" if args.uninstall else "Installed"
    print(f"{action} Claude cross-recall hook: {hook}")
    print(f"Updated settings: {settings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
