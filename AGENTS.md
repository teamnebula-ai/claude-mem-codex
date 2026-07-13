# Repository Guidance

- Keep this repository portable; never commit absolute user paths.
- Treat `~/.claude-mem/claude-mem.db` as upstream-owned state. Do not mutate it directly.
- Preserve `platform_source` attribution and cross-recall behavior.
- Use Conventional Commits and include tests for installer changes.
- Never commit memory databases, transcripts, credentials, tokens, or generated auth state.
