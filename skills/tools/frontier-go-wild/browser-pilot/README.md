# browser-pilot

Vision-equipped browser-automation agent. Drives a persistent Patchright browser to navigate arbitrary sites and complete logins (including OTP and CAPTCHA handoffs), then records what it learned in per-site recipes so deterministic scrapers can run the steady state.

The agent definition lives at `~/.claude/agents/browser-pilot.md`.

---

## First-run setup

Install the Chromium binary Patchright needs:

```bash
uv run patchright install chromium
```

Run this once per machine. The browser profile is persisted under
`~/.patchright/profiles/<site>/` so session cookies survive across runs.

---

## Daemon / client usage

The toolkit is a single file: `automations/browser-pilot/control.py`.
Every command targets a named `--profile` (one profile = one isolated browser context).

### Start the daemon

```bash
uv run python automations/browser-pilot/control.py serve --profile <site> [--headed]
```

`--headed` opens a visible window (required for CAPTCHA handoffs, optional otherwise).
Run in the background (`&`) before issuing any other commands.

### Commands

| Command | Purpose |
|---|---|
| `open --profile <site> --url <URL>` | Navigate to a URL |
| `snapshot --profile <site>` | Returns JSON: title, visible text, interactive controls |
| `click --profile <site> --selector <sel>` | Click an element |
| `type --profile <site> --selector <sel> --value <text>` | Type into a field |
| `press --profile <site> --selector <sel> --key <key>` | Press a keyboard key (e.g. `Enter`) on an element |
| `wait --profile <site> --selector <sel>` | Wait for an element to appear |
| `screenshot --profile <site> --path <png>` | Save a screenshot; use `Read` to view it |
| `stop --profile <site>` | Shut down the daemon for this profile |

### Example session

```bash
# Start daemon (background)
uv run python automations/browser-pilot/control.py serve --profile frontier &

# Navigate and inspect
uv run python automations/browser-pilot/control.py open --profile frontier --url https://www.flyfrontier.com
uv run python automations/browser-pilot/control.py snapshot --profile frontier

# Screenshot to verify
uv run python automations/browser-pilot/control.py screenshot --profile frontier --path /tmp/frontier.png
# Then Read /tmp/frontier.png in the agent

# Stop when done
uv run python automations/browser-pilot/control.py stop --profile frontier
```

---

## Recipe schema

Recipes live at `automations/browser-pilot/recipes/<site>.json`.
Schema is enforced by `recipes.py`. Key fields:

```jsonc
{
  "site": "frontier",
  "login_url": "https://www.flyfrontier.com/login",
  "last_verified": "2026-06-26",
  "needs_human": false,
  "steps": [
    { "action": "click", "selector": "#email-input" },
    { "action": "type", "selector": "#email-input", "value": "{{EMAIL}}" },
    { "action": "click", "selector": "#submit-btn" }
  ],
  "signals": {
    "go_wild_available": ".go-wild-badge"
  },
  "gotchas": []
}
```

The agent reads the recipe at the start of every run and updates it at the end
(bumping `last_verified`, recording new selectors, setting `needs_human` if needed).

---

## OTP handling

When a site sends a one-time code by email, the agent reads it automatically by
running `gmail_otp.py`, which fetches the newest code from the OTP inbox
via a stored Google OAuth refresh token (`[google.frontier_otp_gmail]` in the
central credentials store). This is pure OAuth+HTTP, so it works headless — it does
NOT use the Claude Gmail connector (that connector is authenticated to a different
account and cannot read this inbox). No manual code entry required.

    uv run python automations/browser-pilot/gmail_otp.py --query 'subject:"Frontier Passcode" newer_than:5m'   # prints the 6-digit code
    uv run python automations/browser-pilot/gmail_otp.py --whoami                                              # confirms the account

---

## CAPTCHA / headed handoff

If the agent hits an unbeatable CAPTCHA or anti-bot challenge:

1. It restarts the daemon with `--headed` so the browser window is visible.
2. It asks the user to complete the challenge once.
3. It resumes from there and records `needs_human: true` in the recipe.

---

## Signals

`signals.py` emits structured outcome signals after each run (login success, selector
fallbacks used, human handoff required). These feed the Agent Evolution system so
weak spots get targeted for improvement.

---

## Tests

```bash
uv run pytest automations/browser-pilot/tests -v
```

`test_agent_def.py` is a structural smoke test that asserts the agent definition
exists at `~/.claude/agents/browser-pilot.md` with correct frontmatter and all
protocol tokens present.
