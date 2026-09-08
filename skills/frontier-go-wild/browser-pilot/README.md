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

The toolkit is a single file: `control.py` in this directory (the "pilot
root" - installed machines can resolve it from
`~/.claude/data/frontier-go-wild/pilot-root`). Run every command below from
this directory so `uv` finds the `.venv`.
Every command targets a named `--profile` (one profile = one isolated browser context).

### Start the daemon

```bash
uv run python control.py serve --profile <site> [--headed]
```

`--headed` opens a visible window (required for CAPTCHA handoffs, optional otherwise).
Run in the background (`&`) before issuing any other commands.

### Commands

| Command | Purpose |
|---|---|
| `open --profile <site> --url <URL>` | Navigate to a URL |
| `snapshot --profile <site>` | Returns JSON: title, visible text, interactive controls |
| `tree --profile <site>` | Returns every **visible** control, one section per frame, each with an id and a selector |
| `act --profile <site> --id <0-12> --method <click\|fill\|press\|select\|wait> [--value <text>]` | Drive a control by the id `tree` printed |
| `click --profile <site> --selector <sel>` | Click an element |
| `type --profile <site> --selector <sel> --value <text>` | Type into a field |
| `press --profile <site> --selector <sel> --key <key>` | Press a keyboard key (e.g. `Enter`) on an element |
| `wait --profile <site> --selector <sel>` | Wait for an element to appear |
| `screenshot --profile <site> --path <png>` | Save a screenshot; use `Read` to view it |
| `stop --profile <site>` | Shut down the daemon for this profile |

Use `snapshot` to read page content and `tree` whenever something has to be
clicked or typed. `tree` lists only what is actually visible, so a hidden
duplicate of a button cannot be picked by mistake, and it reaches inside
iframes, which `snapshot` cannot see at all.

```
=== Frame 0 (Main) ===
  [0-0] textbox: Email address
  [0-1] password: Password
  [0-2] button: Log in to your account
=== Frame 1 (Verification) ===
  [1-0] textbox: One-time code
  [1-1] button: Verify
```

`click`, `type`, `keyboard_type`, `press`, `wait`, `select` and `select_native`
also take `--intent`, `--selector-key` and `--site`; see **Self-healing**.

### Example session

```bash
# Start daemon (background)
uv run python control.py serve --profile frontier &

# Navigate and inspect
uv run python control.py open --profile frontier --url https://www.flyfrontier.com
uv run python control.py snapshot --profile frontier

# Screenshot to verify
uv run python control.py screenshot --profile frontier --path /tmp/frontier.png
# Then Read /tmp/frontier.png in the agent

# Stop when done
uv run python control.py stop --profile frontier
```

---

## Recipe schema

Recipes live at `recipes/<site>.json` under the pilot root.
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

    uv run python gmail_otp.py --query 'subject:"Frontier Passcode" newer_than:5m'   # prints the 6-digit code
    uv run python gmail_otp.py --whoami                                              # confirms the account

---

## CAPTCHA / headed handoff

If the agent hits an unbeatable CAPTCHA or anti-bot challenge:

1. It restarts the daemon with `--headed` so the browser window is visible.
2. It asks the user to complete the challenge once.
3. It resumes from there and records `needs_human: true` in the recipe.

---

## Self-healing

When a site moves a button, the run repairs itself instead of ending.

```bash
uv run python control.py type --profile frontier \
  --selector '#email-input' --value "$EMAIL" \
  --intent 'the box where the email address is typed' \
  --selector-key email_box --site frontier
```

If the selector still works, nothing changes. If it does not, the page is read
with `tree`, the failure is classified, the control that now does what the step
meant is identified, that control has to be visible on the live page before it
is used, the step runs, and the new selector is written into
`recipes/<site>.json` with a dated note in `gotchas`.

**Never repaired:** a CAPTCHA or bot challenge, a locked or suspended account, a
rejected password. Those stop and ask for a person. A site that is down or rate
limiting is retried, not rewritten. Anything the classifier does not recognise
goes to a person too.

A recipe can say what its steps mean, which lets a scraper that only passes a
selector repair itself with no change to its code:

```jsonc
{
  "selectors": { "email_box": "#email-input" },
  "intents":   { "email_box": "the box where the email address is typed" }
}
```

Set `BROWSER_PILOT_RUN_ID` (and optionally `BROWSER_PILOT_SIGNALS_DIR` and
`BROWSER_PILOT_SCREENSHOT_DIR`) so heals are attributed to the run.

---

## Signals

`signals.py` emits structured outcome signals after each run (login success, selector
fallbacks used, human handoff required). These are kept on disk so
weak spots get targeted for improvement.
