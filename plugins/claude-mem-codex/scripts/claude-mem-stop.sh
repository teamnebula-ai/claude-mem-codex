#!/bin/sh
set -u

# Codex launches matching Stop hooks concurrently. Finish the claude-mem summary
# first, then detach optional HyperSwarm work so network/model latency cannot
# turn an otherwise successful Codex turn into a Stop-hook timeout.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
payload=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-stop.XXXXXX") || exit 0
trap 'rm -f "$payload"' EXIT HUP INT TERM
cat >"$payload" 2>/dev/null || exit 0
[ -s "$payload" ] || exit 0

"$script_dir/claude-mem-hook.sh" summarize <"$payload" || true

# HyperSwarm's significance gate may itself use `codex exec`. That child gets
# CODEX_NO_INTERACTIVE=1; do not recursively feed its housekeeping session back
# into HyperSwarm.
if [ "${CODEX_NO_INTERACTIVE:-}" = "1" ]; then
  exit 0
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
  hs_payload=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-hyperswarm.XXXXXX") || exit 0
  if cp "$payload" "$hs_payload" 2>/dev/null; then
    (
      trap 'rm -f "$hs_payload"' EXIT HUP INT TERM
      "$hs" capture --runtime claude_mem_session <"$hs_payload" >/dev/null 2>&1 || true
      "$hs" push >/dev/null 2>&1 || true
    ) </dev/null >/dev/null 2>&1 &
  else
    rm -f "$hs_payload"
  fi
fi

exit 0
