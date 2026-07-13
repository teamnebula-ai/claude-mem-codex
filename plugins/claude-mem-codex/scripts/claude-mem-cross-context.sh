#!/bin/sh
set -eu

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

root=$(find_claude_mem || true)
if [ -z "$root" ]; then
  echo "claude-mem: installation not found; install thedotmack/claude-mem first" >&2
  exit 1
fi

# Running the opposite adapter selects the other platform_source. Each CLI's
# native hook still loads its own source, producing symmetric cross-recall.
export CLAUDE_MEM_CODEX_HOOK=1
exec node "$root/scripts/bun-runner.js" "$root/scripts/worker-service.cjs" hook "$platform" context
