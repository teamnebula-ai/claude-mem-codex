#!/bin/sh
set -eu

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
  echo "claude-mem: installation not found; install thedotmack/claude-mem first" >&2
  exit 1
fi

node_bin=$(find_node || true)
if [ -z "$node_bin" ]; then
  echo "claude-mem: Node.js not found; set CLAUDE_MEM_NODE to an executable path" >&2
  exit 1
fi

export CLAUDE_MEM_CODEX_HOOK=1
exec "$node_bin" "$root/scripts/bun-runner.js" "$root/scripts/worker-service.cjs" hook codex "$event"
