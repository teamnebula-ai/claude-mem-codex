# Claude Mem for Codex

Use one local [claude-mem](https://github.com/thedotmack/claude-mem) knowledge base from both Claude Code and OpenAI Codex.

This Team Nebula plugin connects Codex lifecycle hooks and MCP memory search to the existing `~/.claude-mem/claude-mem.db`. It preserves source attribution while adding symmetric cross-recall: Codex can load Claude Code observations, and Claude Code can load Codex observations.

## What it does

- Captures Codex prompts, tool activity, and session summaries through native Codex hooks.
- Exposes claude-mem search, timeline, and observation tools through MCP.
- Loads both Codex and Claude Code context when a Codex session starts.
- Optionally adds the reciprocal Claude Code hook so Claude sessions load Codex context.
- Dynamically follows installed claude-mem versions instead of pinning a cache path.
- Resolves Node.js outside the interactive shell `PATH` used by lifecycle hooks.
- Keeps one database; it does not copy, migrate, or rewrite memory records.

## Requirements

- macOS or Linux
- Node.js
- Codex with plugin and hook support
- Claude Code with [claude-mem](https://github.com/thedotmack/claude-mem) installed and working

## Install in Codex

```bash
codex plugin marketplace add teamnebula-ai/claude-mem-codex
codex plugin add claude-mem-codex@team-nebula-memory
```

Start a new Codex session, review the hook definitions, and trust them. Run `codex mcp list` to confirm `mcp-search` is enabled.

## Enable Claude Code → Codex cross-recall

Clone the repository and run the idempotent installer:

```bash
git clone https://github.com/teamnebula-ai/claude-mem-codex.git
python3 claude-mem-codex/plugins/claude-mem-codex/scripts/install-claude-cross-recall.py
```

The installer:

1. copies a stable hook into `~/.claude/hooks/`;
2. backs up an existing `~/.claude/settings.json` once;
3. appends one `SessionStart` hook without replacing other hooks;
4. migrates an older direct-path cross-recall hook without duplication;
5. remains safe to run repeatedly.

Remove only this integration with:

```bash
python3 plugins/claude-mem-codex/scripts/install-claude-cross-recall.py --uninstall
```

## Architecture

```text
Claude Code hooks ─┐
                   ├─> claude-mem worker ─> ~/.claude-mem/claude-mem.db
Codex hooks ───────┘                         │
      │                                      ├─ platform_source=claude
      └─ mcp-search                          └─ platform_source=codex

SessionStart in either CLI loads its native source plus the other source.
```

Claude-mem generates distilled observations asynchronously. Prompt capture is immediate; newly distilled summaries appear after the worker processes its queue.

If HyperSwarm is installed, the Codex `Stop` adapter runs the two layers in a
strict sequence: claude-mem summarizes the turn first, then HyperSwarm reads
that session summary, applies its significance gate, and pushes any qualifying
entry through the configured sync. HyperSwarm remains optional; its absence or
an unavailable sync target never prevents claude-mem from saving context.

## Security and privacy

All memory remains in the user's existing local claude-mem store. The plugin does not add telemetry or a remote service. Hooks run outside the Codex sandbox after explicit user trust, so review the scripts before enabling them.

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Development

```bash
python3 -m json.tool plugins/claude-mem-codex/hooks/hooks.json >/dev/null
sh -n plugins/claude-mem-codex/scripts/*.sh
python3 -m unittest discover -s tests -v
```

This project is an independent integration and is not affiliated with or endorsed by the claude-mem maintainers, Anthropic, or OpenAI.
