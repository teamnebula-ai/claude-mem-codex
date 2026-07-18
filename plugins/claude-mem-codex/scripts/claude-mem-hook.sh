#!/bin/sh
set -u

event=${1:?usage: claude-mem-hook.sh EVENT}

find_claude_mem() {
  if [ -n "${CLAUDE_MEM_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_MEM_PLUGIN_ROOT/scripts/worker-service.cjs" ]; then
    printf '%s\n' "${CLAUDE_MEM_PLUGIN_ROOT%/}"
    return 0
  fi
  for base in \
    "$HOME/.claude/plugins/cache/thedotmack/claude-mem" \
    "$HOME/.codex/plugins/cache/thedotmack/claude-mem"
  do
    candidate=$(ls -dt "$base"/[0-9]*/ 2>/dev/null | head -n 1 || true)
    candidate=${candidate%/}
    if [ -n "$candidate" ] && [ -f "$candidate/scripts/worker-service.cjs" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  candidate="$HOME/.claude/plugins/marketplaces/thedotmack/plugin"
  if [ -f "$candidate/scripts/worker-service.cjs" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

find_node() {
  if [ -n "${CLAUDE_MEM_NODE:-}" ] && [ -x "$CLAUDE_MEM_NODE" ]; then
    printf '%s\n' "$CLAUDE_MEM_NODE"
    return 0
  fi
  if command -v node >/dev/null 2>&1; then
    command -v node
    return 0
  fi
  for candidate in \
    /opt/homebrew/bin/node \
    /usr/local/bin/node \
    /usr/bin/node \
    "$HOME/.local/bin/node"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  candidate=$(ls -dt "$HOME/.nvm/versions/node"/*/bin/node 2>/dev/null | head -n 1 || true)
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

root=$(find_claude_mem || true)
if [ -z "$root" ]; then
  exit 0
fi

node_bin=$(find_node || true)
if [ -z "$node_bin" ]; then
  exit 0
fi

# Hooks are optional context infrastructure. Buffer stdin and stdout so an empty
# Codex payload, runner crash, or partial JSON response can never fail or corrupt
# the lifecycle event that invoked this adapter.
payload=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-input.XXXXXX") || exit 0
output=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-output.XXXXXX") || {
  rm -f "$payload"
  exit 0
}
trap 'rm -f "$payload" "$output"' EXIT HUP INT TERM
cat >"$payload" 2>/dev/null || exit 0
[ -s "$payload" ] || exit 0

export CLAUDE_MEM_CODEX_HOOK=1
if "$node_bin" "$root/scripts/bun-runner.js" \
    "$root/scripts/worker-service.cjs" hook codex "$event" \
    <"$payload" >"$output" 2>/dev/null; then
  cat "$output"
fi
exit 0
