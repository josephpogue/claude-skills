#!/usr/bin/env bash
# One-time setup for the frontier-go-wild skill. Idempotent: re-running it
# skips anything already in place. No login and no credentials: Go Wild
# availability reads off Frontier's public booking page.
#   bash setup.sh
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)   # the installed skill folder
cd "$HERE"

if ! command -v uv >/dev/null 2>&1; then
  echo "-> installing uv (Python package runner)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "-> Python dependencies"
uv sync --quiet

echo "-> Chromium for the browser (the first time takes a few minutes)"
if [ "$(uname -s)" = "Linux" ]; then
  uv run patchright install --with-deps chromium
else
  uv run patchright install chromium
fi

echo "-> check: the skill loads (a business-class read opens no browser)"
OUT=$(echo '{"reads":[{"origin":"ATL","destination":"DEN","date":"2030-01-15"}],"filters":{"cabin":"business"}}' \
  | uv run python search.py 2>/dev/null)
case "$OUT" in
  *'"not_applicable"'*) echo "   ok" ;;
  *) echo "   the skill did not load; output was:"; echo "$OUT"; exit 1 ;;
esac

echo "-> check: the headless browser opens a page"
PROFILE=setup-check
DATA="$HOME/.claude/data/frontier-go-wild/browser-profiles/$PROFILE"
uv run python browser-pilot/control.py serve --profile "$PROFILE" >/dev/null
uv run python browser-pilot/control.py open --profile "$PROFILE" --url https://example.com >/dev/null
SNAP=$(uv run python browser-pilot/control.py snapshot --profile "$PROFILE" 2>/dev/null | head -c 400 || true)
uv run python browser-pilot/control.py stop --profile "$PROFILE" >/dev/null 2>&1 || true
rm -rf "$DATA"
case "$SNAP" in
  *Example*) echo "   ok" ;;
  *) echo "   the browser did not return the page; re-run setup.sh (usually the Chromium install)"; exit 1 ;;
esac

echo
echo "Setup complete. Try: echo '{\"reads\":[{\"origin\":\"ATL\",\"destination\":\"DEN\",\"date\":\"YYYY-MM-DD\"}]}' | uv run python search.py"
