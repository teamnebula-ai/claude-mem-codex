---
type: quickstart
title: claude-mem-codex quickstart
description: Overview of the Codex plugin that bridges claude-mem memory between Claude Code and OpenAI Codex.
tags: [overview, codex, claude-mem, memory, plugin]
timestamp: 2026-08-29
---

# claude-mem-codex

A [Codex](https://github.com/openai/codex) plugin, published by Team Nebula, that lets
Claude Code and OpenAI Codex CLI share **one** local
[claude-mem](https://github.com/thedotmack/claude-mem) knowledge base
(`~/.claude-mem/claude-mem.db`) instead of each keeping its own memory silo.
([README.md](../README.md))

## Why this exists

claude-mem already gives Claude Code persistent memory across sessions. This repo does not
reimplement that — it wires Codex's own lifecycle hooks and MCP tools onto the *same* database,
and adds an optional reciprocal hook so Claude Code sessions can read Codex's memories too
("cross-recall"). Every record keeps a `platform_source` tag (`claude` or `codex`) so origin is
never lost. ([README.md](../README.md), [AGENTS.md](../AGENTS.md))

The repo is intentionally small and does not vendor claude-mem itself — at runtime it locates
whatever claude-mem install already exists (Claude Code's plugin cache or Codex's) and shells out
to it. See [architecture/overview.md](architecture/overview.md) for how that discovery works.

## What's here

- `plugins/claude-mem-codex/` — the Codex plugin: `hooks/hooks.json` (lifecycle wiring),
  `scripts/*.sh` (hook adapters), `.mcp.json` (exposes claude-mem's search/timeline tools over
  MCP), `.codex-plugin/plugin.json` (plugin manifest, v0.1.2).
- `plugins/claude-mem-codex/scripts/install-claude-cross-recall.py` — a standalone, idempotent
  installer that adds the Claude Code half of cross-recall (Codex-side wiring installs via the
  Codex plugin marketplace instead).
- `tests/test_installer.py` — the only test suite; covers the installer and the shell hook
  adapters' fail-open behavior.
- `.agents/plugins/marketplace.json` — the marketplace manifest Codex reads when a user runs
  `codex plugin marketplace add teamnebula-ai/claude-mem-codex`.

## Two install paths

1. **Codex side** (required): `codex plugin marketplace add teamnebula-ai/claude-mem-codex` then
   `codex plugin add claude-mem-codex@team-nebula-memory`. This is what wires `hooks.json` into a
   Codex session and enables the `mcp-search` MCP server.
2. **Claude Code side** (optional, for cross-recall): clone the repo and run
   `python3 plugins/claude-mem-codex/scripts/install-claude-cross-recall.py`, which patches
   `~/.claude/settings.json` to add a `SessionStart` hook. See
   [workflows/installer.md](workflows/installer.md).

## Map

- [architecture/overview.md](architecture/overview.md) — how the two hook surfaces both reach one
  claude-mem worker process, and where HyperSwarm plugs in.
- [workflows/hook-lifecycle.md](workflows/hook-lifecycle.md) — every Codex lifecycle event, the
  script and worker subcommand it triggers, and the fail-open contract each script must uphold.
- [workflows/installer.md](workflows/installer.md) — what `install-claude-cross-recall.py` does to
  `~/.claude/settings.json`, and why it's safe to run repeatedly.
- [operations/testing-and-checks.md](operations/testing-and-checks.md) — the three checks this
  repo expects before a PR, what the test suite actually verifies, and the repo-wide guardrails in
  `AGENTS.md`.

## Backlog

- No page covers `.mcp.json`'s inline `mcp-search` launcher script in detail beyond
  [architecture/overview.md](architecture/overview.md) — it duplicates the same
  `find_claude_mem`-style root discovery inline as a one-line Node `-e` script; worth a dedicated
  note if it diverges from the shell scripts' discovery logic in a future change.
- HyperSwarm itself (the optional downstream sync layer referenced in `claude-mem-stop.sh`) lives
  in a separate project; this wiki only documents the handoff contract (`hyperswarm capture` /
  `hyperswarm push`), not HyperSwarm's own behavior.
- `~/.claude-mem/HOST-LLM-ROUTING.md`, referenced by `AGENTS.md` for which LLM compresses which
  CLI's sessions, is machine-local and not vendored in this repo — out of scope for the wiki.
