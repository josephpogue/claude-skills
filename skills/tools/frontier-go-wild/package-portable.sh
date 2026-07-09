#!/usr/bin/env bash
# Build a portable hand-off bundle for the frontier-go-wild skill.
# Gathers the LIVE versions of every dependency into one tarball:
#   skill/           this skill folder (SKILL.md, network/blackout data, renderer, setup docs)
#   browser-pilot/   the browser toolkit (code + recipes; NO session state, NO secrets)
#   agents/          the browser-pilot agent definition workers are cast from
#   bin/runlog       optional heartbeat helper
#   setup.sh         the installer to run on the new machine
#
# Usage: bash package-portable.sh [output.tar.gz]
set -euo pipefail

OUT="${1:-$HOME/Desktop/frontier-go-wild-portable.tar.gz}"
SKILL_DIR="$HOME/.claude/skills/frontier-go-wild"
PILOT_DIR="$HOME/Documents/GitHub/My-Life/automations/browser-pilot"
AGENT_MD="$HOME/.claude/agents/browser-pilot.md"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
B="$STAGE/frontier-go-wild-portable"
mkdir -p "$B/agents" "$B/bin"

rsync -a --exclude '__pycache__' "$SKILL_DIR/" "$B/skill/"
rsync -a --exclude '__pycache__' --exclude 'state' --exclude 'signals' \
      --exclude '.venv' --exclude 'recon-notes-*' \
      "$PILOT_DIR/" "$B/browser-pilot/"
cp "$AGENT_MD" "$B/agents/browser-pilot.md"
[ -f "$HOME/.local/bin/runlog" ] && cp "$HOME/.local/bin/runlog" "$B/bin/runlog"

# Vendor the shared browser module (lives in the sibling flight-search
# automation at home; the bundle must be self-contained). control.py's own
# directory is on sys.path, so a shared/ subpackage resolves the
# `from shared.browser import ...` in session.py. Profiles dir is patched to
# live under the pilot root instead of a repo-relative walk-up.
mkdir -p "$B/browser-pilot/shared"
touch "$B/browser-pilot/shared/__init__.py"
sed 's|^REPO_ROOT = .*|REPO_ROOT = Path(__file__).resolve().parents[1]  # pilot root (vendored)|' \
  "$PILOT_DIR/../flight-search/shared/browser.py" > "$B/browser-pilot/shared/browser.py"

# Minimal standalone python project so `uv run` works without the My-Life repo.
cat > "$B/browser-pilot/pyproject.toml" <<'EOF'
[project]
name = "browser-pilot"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["patchright>=1.49.0"]

[tool.uv]
package = false
EOF

cp "$SKILL_DIR/setup.sh" "$B/setup.sh"
chmod +x "$B/setup.sh"

tar -czf "$OUT" -C "$STAGE" "frontier-go-wild-portable"
echo "bundle: $OUT ($(du -h "$OUT" | cut -f1 | tr -d ' '))"
echo "hand-off: copy the tarball, then on the new machine:"
echo "  tar -xzf $(basename "$OUT") && bash frontier-go-wild-portable/setup.sh"
