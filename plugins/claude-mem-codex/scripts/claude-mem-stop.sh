#!/bin/sh
set -u

# Codex launches matching Stop hooks concurrently. Keep claude-mem summary and
# optional HyperSwarm distillation in one handler so HyperSwarm never races the
# summary it is meant to read.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
payload=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-stop.XXXXXX") || exit 1
trap 'rm -f "$payload"' EXIT HUP INT TERM
cat >"$payload"

summary_rc=0
"$script_dir/claude-mem-hook.sh" summarize <"$payload" || summary_rc=$?

# HyperSwarm's significance gate may itself use `codex exec`. That child gets
# CODEX_NO_INTERACTIVE=1; do not recursively feed its housekeeping session back
# into HyperSwarm.
if [ "${CODEX_NO_INTERACTIVE:-}" = "1" ]; then
  exit "$summary_rc"
fi

# HyperSwarm is an optional downstream layer. If installed and configured, it
# reads the just-written session summary, emits at most one significance-gated
# entry, and pushes the staging store to its configured canonical host. Memory
# capture must continue to work normally when HyperSwarm is absent or offline.
hs=""
if command -v hyperswarm >/dev/null 2>&1; then
  hs=$(command -v hyperswarm)
elif [ -x "$HOME/.local/bin/hyperswarm" ]; then
  hs="$HOME/.local/bin/hyperswarm"
fi

if [ -n "$hs" ]; then
  "$hs" capture --runtime claude_mem_session <"$payload" >/dev/null 2>&1 || true
  "$hs" push >/dev/null 2>&1 || true
fi

exit "$summary_rc"
