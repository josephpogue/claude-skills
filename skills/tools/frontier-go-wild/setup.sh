#!/usr/bin/env bash
# Onboard the frontier-go-wild skill: install its vendored browser toolkit +
# agent. No credentials needed — Go Wild availability reads off the public
# booking page logged out. Idempotent — re-running skips anything already in
# place. This file ships beside SKILL.md, so $HERE is the installed skill folder
# itself. Run: bash setup.sh
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)   # the installed skill folder

# ── install roots ────────────────────────────────────────────────────────────
# If a live My-Life browser-pilot is already present, reuse it (keeps its warm
# session); otherwise install the vendored toolkit under ~/.claude/tools.
if [ -d "$HOME/Documents/GitHub/My-Life/automations/browser-pilot" ]; then
  PILOT="$HOME/Documents/GitHub/My-Life/automations/browser-pilot"
else
  PILOT="$HOME/.claude/tools/browser-pilot"
fi

# runlog: the skill's run-logging heartbeat helper. Vendored; only installed
# when the machine doesn't already have one (keeps a live My-Life symlink).
if [ ! -e "$HOME/.local/bin/runlog" ]; then
  echo "→ runlog → ~/.local/bin/runlog"
  mkdir -p "$HOME/.local/bin"
  cp "$HERE/bin/runlog" "$HOME/.local/bin/runlog"
  chmod +x "$HOME/.local/bin/runlog"
else
  echo "✓ runlog already present"
fi

echo "→ agent  → ~/.claude/agents/browser-pilot.md"
mkdir -p "$HOME/.claude/agents"
cp "$HERE/agent/browser-pilot.md" "$HOME/.claude/agents/browser-pilot.md"

echo "→ pilot  → $PILOT"
mkdir -p "$PILOT"
rsync -a --ignore-existing "$HERE/browser-pilot/" "$PILOT/"   # never clobber a live install
mkdir -p "$PILOT/state" "$PILOT/signals"

# Record where the toolkit lives so SKILL.md can resolve it on any machine.
mkdir -p "$HOME/.claude/data/frontier-go-wild"
echo "$PILOT" > "$HOME/.claude/data/frontier-go-wild/pilot-root"

# ── python runtime ───────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  echo "→ installing uv (python package runner)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "→ python deps + chromium (first time takes a few minutes)…"
( cd "$PILOT" && uv sync --quiet && uv run patchright install chromium )

# No credentials needed: Go Wild availability reads off the public booking page
# for logged-out visitors (verified 2026-07-09), so there is no Frontier login
# and no Gmail OTP reader to collect.

# ── smoke test ───────────────────────────────────────────────────────────────
echo
echo "→ smoke test: headless browser round-trip…"
(
  cd "$PILOT"
  nohup uv run python control.py serve --profile setup-smoke --headless >/dev/null 2>&1 &
  sleep 6
  uv run python control.py open --profile setup-smoke --url https://example.com >/dev/null
  SNAP=$(uv run python control.py snapshot --profile setup-smoke 2>/dev/null | head -c 300)
  case "$SNAP" in
    *Example*) echo "  ✓ browser toolkit works" ;;
    *)         echo "  ✗ snapshot didn't return the expected page - check chromium install"; exit 1 ;;
  esac
  pkill -f "control.py serve --profile setup-smoke" 2>/dev/null || true
)

echo
echo "✓ setup complete. No login needed - the first run just works."
echo "  Try: claude, then ask for 'frontier go wild ATL to Boston next weekend'."
