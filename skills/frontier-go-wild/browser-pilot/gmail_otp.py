"""Read the latest Frontier one-time passcode from a Gmail account via OAuth.

Uses a Google OAuth2 refresh-token grant stored in the central credentials
store under [google.<namespace>], mirroring the rental-ledger gmail pattern.
Stdlib-only (urllib) so it runs headless with no Claude connector."""
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

STORE = Path(os.path.expanduser("~/.config/credentials/store.toml"))
DEFAULT_QUERY = 'subject:"Frontier Passcode" newer_than:1h'
_ANCHORED = re.compile(r"passcode is:?\s*(\d{6})", re.I)
_ANY6 = re.compile(r"\b(\d{6})\b")


class OtpError(RuntimeError):
    pass


def load_creds(namespace: str = "frontier_otp_gmail") -> dict:
    try:
        data = tomllib.loads(STORE.read_text())
        return data["google"][namespace]
    except (FileNotFoundError, KeyError) as e:
        raise OtpError(f"google.{namespace} not found in {STORE}") from e


def extract_code(text: str) -> str | None:
    if not text:
        return None
    m = _ANCHORED.search(text)
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


def whoami(namespace: str = "frontier_otp_gmail") -> str:
    at = _access_token(load_creds(namespace))
    return _gmail(at, "profile")["emailAddress"]


def latest_code(namespace: str = "frontier_otp_gmail", query: str = DEFAULT_QUERY) -> str | None:
    at = _access_token(load_creds(namespace))
    q = urllib.parse.quote(query)
    listing = _gmail(at, f"messages?q={q}&maxResults=1")
    msgs = listing.get("messages") or []
    if not msgs:
        return None
    full = _gmail(at, f"messages/{msgs[0]['id']}?format=full")
    return extract_code(message_text(full["payload"]))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--namespace", default="frontier_otp_gmail")
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
