"""Read a one-time passcode out of a Gmail account via OAuth.

Uses a Google OAuth2 refresh-token grant stored in the central credentials
store under [google.<namespace>], mirroring the rental-ledger gmail pattern.
Stdlib-only (urllib) so it runs headless with no Claude connector.

Written for Frontier, whose wording the defaults still describe. Two senders now
use it, so a caller that phrases things differently passes its own `anchor`
rather than relying on the six-digit fallback: Marcus writes "Your code is
[401203]" in an HTML-only message that opens with inline CSS, and the first
six-digit run in that markup is a coincidence waiting to happen.

`newer_than_ms` is the other half of that. Gmail's `newer_than:1h` is the
tightest window its query language offers, and an hour is long enough to hold a
code from an earlier attempt. A caller that stamps the moment it asked for a
code can insist on a message that arrived after it, which is the only thing
separating this run's code from the last one's."""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import sys
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

# otp_mail lives in My-Life's automations/_shared and is not part of the
# published skill copy, so its absence must not stop a login. Without it a
# spent code just stays in the mailbox.
_SHARED = Path(__file__).resolve().parents[1] / "_shared"
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
try:
    import otp_mail  # noqa: E402  (path is set immediately above)
except ImportError:
    otp_mail = None

STORE = Path(os.path.expanduser("~/.config/credentials/store.toml"))
DEFAULT_QUERY = 'subject:"Frontier Passcode" newer_than:1h'
_ANCHORED = re.compile(r"passcode is:?\s*(\d{6})", re.I)
_ANY6 = re.compile(r"\b(\d{6})\b")


class OtpError(RuntimeError):
    pass


def load_creds(namespace: str = "josephpogue22_gmail") -> dict:
    try:
        data = tomllib.loads(STORE.read_text())
        return data["google"][namespace]
    except (FileNotFoundError, KeyError) as e:
        raise OtpError(f"google.{namespace} not found in {STORE}") from e


def extract_code(text: str, anchor: re.Pattern | None = None) -> str | None:
    """The six digits, preferring a caller's own wording over the fallback.

    The fallback takes the first six-digit run in the message, which is right
    for a plain-text mail and a gamble on an HTML one: markup and inline CSS
    carry numbers of their own. A sender whose wording is known should be given
    an `anchor` so the fallback is never reached.
    """
    if not text:
        return None
    for pattern in (anchor, _ANCHORED):
        if pattern is None:
            continue
        m = pattern.search(text)
        if m:
            return m.group(1)
    m = _ANY6.search(text)
    return m.group(1) if m else None


def message_text(payload: dict) -> str:
    out = ""
    if payload.get("mimeType", "").startswith("text/"):
        data = payload.get("body", {}).get("data")
        if data:
            out += base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
    for part in payload.get("parts", []) or []:
        out += message_text(part)
    return out


def _access_token(creds: dict) -> str:
    data = urllib.parse.urlencode({
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data) as r:
        return json.load(r)["access_token"]


def _gmail(access_token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"https://gmail.googleapis.com/gmail/v1/users/me/{path}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def whoami(namespace: str = "josephpogue22_gmail") -> str:
    at = _access_token(load_creds(namespace))
    return _gmail(at, "profile")["emailAddress"]


def latest_code(namespace: str = "josephpogue22_gmail", query: str = DEFAULT_QUERY,
                anchor: re.Pattern | None = None,
                newer_than_ms: int | None = None,
                max_results: int = 5) -> str | None:
    """The newest code matching `query`, and arriving after `newer_than_ms`.

    Several messages are fetched rather than one, because the newest match for a
    query is not always the one being waited for: a resent code, or a second
    message from the same sender, can sit on top of it. Each is judged in turn
    and the first that is both fresh enough and carries digits wins.
    """
    at = _access_token(load_creds(namespace))
    q = urllib.parse.quote(query)
    listing = _gmail(at, f"messages?q={q}&maxResults={max_results}")
    for msg in listing.get("messages") or []:
        full = _gmail(at, f"messages/{msg['id']}?format=full")
        if newer_than_ms is not None:
            # Gmail states internalDate in milliseconds as a string. A message
            # without one is not given the benefit of the doubt: an unknown
            # arrival time cannot be proved to be this run's.
            try:
                arrived = int(full.get("internalDate", ""))
            except (TypeError, ValueError):
                continue
            if arrived <= newer_than_ms:
                continue
        code = extract_code(message_text(full["payload"]), anchor)
        if code:
            # This module's own grant is gmail.readonly and cannot modify a
            # message, so the cleanup goes out through `gog`, whose login
            # already has write access. Frontier is why this line exists: it
            # put 41 passcode emails in the inbox between May and August.
            if otp_mail is not None:
                otp_mail.trash(msg.get("id"), label="passcode email")
            return code
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--namespace", default="josephpogue22_gmail")
    p.add_argument("--query", default=DEFAULT_QUERY)
    p.add_argument("--whoami", action="store_true")
    a = p.parse_args()
    if a.whoami:
        print(whoami(a.namespace))
        return 0
    code = latest_code(a.namespace, a.query)
    if code:
        print(code)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
