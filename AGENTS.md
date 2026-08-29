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

<!-- nebby:start -->
## Codebase wiki (nebby)

This repository uses **nebby** to keep a generated, source-grounded wiki in `.nebbywiki/`.
A maintainer added it deliberately — it is part of this repo's tooling, not something that
appeared on its own. Source: https://github.com/teamnebula-ai/teamwiki

**Read it first.** Start at `.nebbywiki/quickstart.md` before grepping source or answering
architecture questions. It maps the architecture, APIs, data models, and workflows, and links to
each section. It is compiled from this codebase and cites real files, so it is a faster way in
than scanning — but it is generated text: verify against source before acting on anything
load-bearing, and trust the code over the wiki when they disagree.

**Do not hand-edit it.** Every page under `.nebbywiki/` is rewritten on the next build and your
edits will be lost. To correct the wiki, fix the code and run `nebby build`.

**The other files are nebby's, and are expected:** `config.json` holds its settings,
`nebby.db` is a local run log (gitignored), and a `post-commit` git hook rebuilds the wiki in
the background after a commit. Run `nebby doctor` if the wiki looks out of date.

Full explanation: `.nebbywiki/README.md`. To remove nebby from this repo: `nebby uninstall`.
<!-- nebby:end -->
