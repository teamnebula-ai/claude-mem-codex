# Repository Guidance

- Keep this repository portable; never commit absolute user paths.
- Treat `~/.claude-mem/claude-mem.db` as upstream-owned state. Do not mutate it directly.
- Preserve `platform_source` attribution and cross-recall behavior.
- **Compressor policy (Mac, 2026-08-01):** host LLM routing. Codex sessions
  compress via Codex CLI; Grok via Grok CLI; Claude via Claude CLI (Codex
  fallback on weekly limit). Local Ollama only for local/qwen. Machine detail:
  `~/.claude-mem/HOST-LLM-ROUTING.md` (not vendored in this repo).
- Use Conventional Commits and include tests for installer changes.
- Never commit memory databases, transcripts, credentials, tokens, or generated auth state.
