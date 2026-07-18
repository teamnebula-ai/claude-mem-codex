#!/bin/sh
set -u

platform=${1:?usage: claude-mem-cross-context.sh PLATFORM}
case "$platform" in
  codex|claude-code) ;;
  *) echo "unsupported platform: $platform" >&2; exit 2 ;;
esac

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

# Fail open for the same reason as claude-mem-hook.sh: memory recall must never
# make a Codex SessionStart fail when stdin is empty or upstream is unavailable.
payload=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-cross-input.XXXXXX") || exit 0
output=$(mktemp "${TMPDIR:-/tmp}/claude-mem-codex-cross-output.XXXXXX") || {
  rm -f "$payload"
  exit 0
}
trap 'rm -f "$payload" "$output"' EXIT HUP INT TERM
cat >"$payload" 2>/dev/null || exit 0
[ -s "$payload" ] || exit 0

# Running the opposite adapter selects the other platform_source. Each CLI's
# native hook still loads its own source, producing symmetric cross-recall.
export CLAUDE_MEM_CODEX_HOOK=1
if "$node_bin" "$root/scripts/bun-runner.js" \
    "$root/scripts/worker-service.cjs" hook "$platform" context \
    <"$payload" >"$output" 2>/dev/null; then
  cat "$output"
fi
exit 0
