---
name: setup-frontier-go-wild
description: One-time onboarding for the frontier-go-wild skill — installs the browser toolkit and collects the two credentials it needs (Frontier login + Gmail OTP reader). Run this once after installing frontier-go-wild.
disable-model-invocation: true
---

# setup-frontier-go-wild

`frontier-go-wild` is not a pure-prompt skill: it drives a real headless browser
into frontier.com, and Frontier requires a login plus a one-time passcode (OTP)
on every fresh session. Installing the skill folder copies the instructions, not
the engine. This skill bootstraps the engine and the credentials **once**, so
the first real search just works.

Run it after `frontier-go-wild` is installed. It is safe to re-run; every step
is idempotent and skips anything already in place.

## What this sets up

1. **The browser toolkit** (`browser-pilot`): the `control.py` daemon, the
   Frontier recipe, and a Chromium runtime, installed under `$PILOT_ROOT` and
   recorded in `~/.claude/data/frontier-go-wild/pilot-root` so the skill can
   find it on any machine.
2. **Two credentials**, written only to the local, `chmod 600`
   `~/.config/credentials/store.toml` (never committed, never leaves the
   machine):
   - **Frontier login** — the account whose Go Wild pass you are searching.
   - **Gmail OTP reader** — a Google OAuth client with `gmail.readonly` scope
     and a refresh token for the inbox that receives Frontier's login codes.

## Steps

1. **Locate the bundled installer.** It ships with the skill at
   `<this-repo>/skills/tools/frontier-go-wild/setup.sh`, alongside
   `package-portable.sh`. If the skill was installed via `npx skills add`, the
   folder is at `~/.claude/skills/frontier-go-wild/`.

2. **Run the installer** and follow its prompts:
   ```bash
   bash ~/.claude/skills/frontier-go-wild/setup.sh
   ```
   It installs `uv`, the browser toolkit, and Chromium; drops the
   `browser-pilot` agent definition; then prompts for the two credentials below.
   It finishes with a headless smoke test.

3. **Frontier login** — when prompted, enter the account email and password.
   These go into `[logins.frontier]` in the local store.

4. **Gmail OTP reader** — this is the fiddly step, and it is required because
   Frontier emails a fresh 6-digit code at every login. You need, for the inbox
   that receives those codes:
   - a Google Cloud project with the **Gmail API enabled**,
   - an **OAuth client** (client id + secret),
   - a **refresh token** minted with scope
     `https://www.googleapis.com/auth/gmail.readonly` (e.g. via the
     [OAuth Playground](https://developers.google.com/oauthplayground)).

   Paste the client id, client secret, refresh token, and Gmail address when
   prompted. They go into a `[google.<account>]` block in the local store.
   **The OTP reader is Gmail-only today** — if your Frontier codes arrive at a
   non-Gmail address, this path will not work without adapting the reader.

5. **Confirm the smoke test passed** ("browser toolkit works"). If it fails,
   the most common cause is the Chromium install; re-run the installer.

## Done

The first real search warms the session with one OTP email (about 1-2 minutes),
then caches the login. From then on runs reuse the warm session and only
re-authenticate every ~20-25 minutes. Try it:

> frontier go wild ATL to Boston next weekend

If a run ever reports it needs a one-time headed re-login, run a single
interactive login once and it will re-cache.
