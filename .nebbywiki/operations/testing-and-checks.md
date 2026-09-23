---
type: operations
title: Testing and repo checks
description: The checks expected before a PR, what the test suite actually asserts, and the repo-wide guardrails in AGENTS.md.
tags: [testing, ci, contributing, guardrails]
timestamp: 2026-08-29
---

# Testing and repo checks

There is no CI workflow file in this repo (no `.github/workflows/`) — the checks below are
documented in `README.md`'s Development section and are expected to be run manually before a PR,
per `CONTRIBUTING.md`.

## The three checks

```bash
python3 -m json.tool plugins/claude-mem-codex/hooks/hooks.json >/dev/null
sh -n plugins/claude-mem-codex/scripts/*.sh
python3 -m unittest discover -s tests -v
```

([README.md](../README.md#development)) — validate `hooks.json` parses as JSON, syntax-check every
shell script without executing it, and run the unit tests.

## What `tests/test_installer.py` actually asserts

Single test file, four cases, all under `InstallerTest`:

- **`test_install_is_idempotent_and_uninstall_preserves_other_hooks`** — builds a fake
  `~/.claude/settings.json` with an unrelated hook and a legacy-format cross-context hook, runs
  `install()` twice, and asserts: the unrelated hook survives untouched, the legacy hook is gone,
  and the new hook command appears exactly once (not duplicated by the second install). Then
  `uninstall()` and assert only the unrelated hook remains. This is the executable spec for
  [workflows/installer.md](../workflows/installer.md).
- **`test_hook_wrappers_use_explicit_node_when_path_is_minimal`** — runs
  `claude-mem-hook.sh` and `claude-mem-cross-context.sh` against a fake `node` binary and a fake
  claude-mem install directory (via `CLAUDE_MEM_PLUGIN_ROOT` / `CLAUDE_MEM_NODE`), with `PATH`
  reduced to `/usr/bin:/bin` — proving discovery falls back to explicit env vars when `node` isn't
  on the interactive `PATH` a lifecycle hook actually runs under (the bug fixed in
  [73dbea5](https://github.com/teamnebula-ai/claude-mem-codex/commit/73dbea5) "fix(hooks): resolve
  Node outside interactive PATH"). Asserts the exact `worker-service.cjs hook codex ...` /
  `hook claude-code context` argument tail and that stdin is passed through unmodified.
- **`test_hook_wrappers_fail_open_on_empty_input_or_runner_failure`** — for both wrapper scripts,
  asserts empty stdin exits `0` with empty stdout and never invokes the runner at all, and that a
  runner which prints partial JSON and exits `7` still makes the wrapper exit `0` with empty
  stdout (the runner *was* invoked, but its broken output is discarded, per
  [workflows/hook-lifecycle.md](../workflows/hook-lifecycle.md#fail-open-contract)).
- **`test_stop_hook_sequences_summary_before_optional_hyperswarm`** — parses `hooks.json` to
  confirm `Stop` binds exactly one command, then string-searches `claude-mem-stop.sh` to assert
  `summarize` precedes `capture --runtime claude_mem_session` precedes `push`, and that
  `CODEX_NO_INTERACTIVE:-` and a backgrounded (`&\n`) block are present — the ordering guarantee
  described in
  [workflows/hook-lifecycle.md](../workflows/hook-lifecycle.md#stop-the-race-that-must-not-happen).

## Repo-wide guardrails (`AGENTS.md`)

- Keep the repo portable — never commit absolute user paths (all scripts here resolve paths at
  runtime via `$HOME`/env vars, never hardcode them).
- `~/.claude-mem/claude-mem.db` is upstream-owned state — never mutate it directly; go through the
  worker.
- Preserve `platform_source` attribution and cross-recall behavior when changing hook scripts.
- Compressor policy (added 2026-08-01, [78d9ad6](https://github.com/teamnebula-ai/claude-mem-codex/commit/78d9ad6)):
  each CLI's sessions are compressed by its own host LLM (Codex via Codex CLI, Grok via Grok CLI,
  Claude via Claude CLI, with Codex as fallback on weekly limit); local Ollama is only used for
  local/qwen. Full routing table lives in `~/.claude-mem/HOST-LLM-ROUTING.md`, which is
  machine-local and not vendored in this repo.
- Use Conventional Commits; include tests for installer changes.
- Never commit memory databases, transcripts, credentials, tokens, or generated auth state.

`SECURITY.md` asks that vulnerabilities be reported via GitHub security advisories rather than
public issues, and notes hooks execute outside the Codex sandbox after explicit user trust — review
hook script changes before trusting a new release.

## Relationships

- **verifies** [workflows/hook-lifecycle.md](../workflows/hook-lifecycle.md) and
  [workflows/installer.md](../workflows/installer.md).
