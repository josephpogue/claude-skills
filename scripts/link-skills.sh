#!/usr/bin/env bash
set -euo pipefail
# Symlink every skill in this repo into ~/.claude/skills so your live agent uses
# the repo copies directly. A `git pull` then keeps installed skills current.
# Re-run after adding, removing, or renaming a skill.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/.claude/skills"
mkdir -p "$DEST"

while IFS= read -r -d '' skill_md; do
  src="$(dirname "$skill_md")"
  name="$(basename "$src")"
  target="$DEST/$name"
  # Replace a real dir with a symlink; leave existing correct symlinks alone.
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    rm -rf "$target"
  fi
  ln -sfn "$src" "$target"
  echo "linked $name -> $src"
done < <(find "$REPO/skills" -name SKILL.md -not -path '*/node_modules/*' -print0)
