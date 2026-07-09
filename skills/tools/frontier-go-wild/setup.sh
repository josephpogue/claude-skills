#!/usr/bin/env bash
# Install the frontier-go-wild portable bundle on a fresh machine.
# Idempotent: re-running skips anything already in place.
# Run from inside the unpacked bundle: bash setup.sh
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)

# ── install roots ────────────────────────────────────────────────────────────
# Keep the canonical My-Life path when that repo exists (Joseph's own machine);
# otherwise install the toolkit under ~/.claude/tools.
if [ -d "$HOME/Documents/GitHub/My-Life/automations" ]; then
  PILOT="$HOME/Documents/GitHub/My-Life/automations/browser-pilot"
else
  PILOT="$HOME/.claude/tools/browser-pilot"
fi

echo "→ skill  → ~/.claude/skills/frontier-go-wild"
mkdir -p "$HOME/.claude/skills"
rsync -a "$HERE/skill/" "$HOME/.claude/skills/frontier-go-wild/"

echo "→ agent  → ~/.claude/agents/browser-pilot.md"
mkdir -p "$HOME/.claude/agents"
cp "$HERE/agents/browser-pilot.md" "$HOME/.claude/agents/browser-pilot.md"

echo "→ pilot  → $PILOT"
mkdir -p "$PILOT"
rsync -a --ignore-existing "$HERE/browser-pilot/" "$PILOT/"   # never clobber a live install
mkdir -p "$PILOT/state" "$PILOT/signals"

# Record where the toolkit lives so SKILL.md can resolve it on any machine.
mkdir -p "$HOME/.claude/data/frontier-go-wild"
echo "$PILOT" > "$HOME/.claude/data/frontier-go-wild/pilot-root"

if [ -f "$HERE/bin/runlog" ] && [ ! -f "$HOME/.local/bin/runlog" ]; then
  echo "→ runlog → ~/.local/bin/runlog (heartbeat helper, optional)"
  mkdir -p "$HOME/.local/bin"
  cp "$HERE/bin/runlog" "$HOME/.local/bin/runlog"
  chmod +x "$HOME/.local/bin/runlog"
fi

# ── python runtime ───────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  echo "→ installing uv (python package runner)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "→ python deps + chromium (first time takes a few minutes)…"
( cd "$PILOT" && uv sync --quiet && uv run patchright install chromium )

# ── secrets (the only manual inputs) ─────────────────────────────────────────
STORE="$HOME/.config/credentials/store.toml"
mkdir -p "$HOME/.config/credentials"
touch "$STORE"; chmod 600 "$STORE"

if ! grep -q '^\[logins.frontier\]' "$STORE"; then
  echo
  echo "Frontier account login (stored locally in $STORE):"
  read -rp  "  username (email): " F_USER
  read -rsp "  password: " F_PASS; echo
  printf '\n[logins.frontier]\nusername = "%s"\npassword = "%s"\n' "$F_USER" "$F_PASS" >> "$STORE"
  echo "  ✓ [logins.frontier] written"
else
  echo "✓ [logins.frontier] already present"
fi

cat <<'MSG'

Gmail OTP reader: Frontier emails a 6-digit code at login; the skill reads it
via the Gmail API. It needs a Google OAuth client with gmail.readonly scope
and a refresh token for the inbox that receives Frontier codes.
(Google Cloud Console → OAuth client, then mint a refresh token, e.g. via
https://developers.google.com/oauthplayground with scope
https://www.googleapis.com/auth/gmail.readonly)
MSG
read -rp "  gmail address: " G_EMAIL
# Namespace the store block by the account's local-part, so it is per-user and
# not hardcoded to any one inbox. The OTP reader is invoked with this namespace.
NS="$(printf '%s' "${G_EMAIL%%@*}" | tr -cs 'A-Za-z0-9' '_')_gmail"
if ! grep -q "^\[google.$NS\]" "$STORE"; then
  read -rp "  client_id: " G_ID
  read -rp "  client_secret: " G_SECRET
  read -rp "  refresh_token: " G_REFRESH
  printf '\n[google.%s]\nclient_id = "%s"\nclient_secret = "%s"\nrefresh_token = "%s"\nemail = "%s"\nscope = "https://www.googleapis.com/auth/gmail.readonly"\n' \
    "$NS" "$G_ID" "$G_SECRET" "$G_REFRESH" "$G_EMAIL" >> "$STORE"
  echo "  ✓ [google.$NS] written"
else
  echo "✓ [google.$NS] already present"
fi

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
echo "✓ setup complete. First real run warms the Frontier session (one OTP email)."
echo "  Try: claude, then ask for 'frontier go wild ATL to Boston next weekend'."
