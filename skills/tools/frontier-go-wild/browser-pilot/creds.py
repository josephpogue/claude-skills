"""Load site logins from the central credentials store.

`creds.load("frontier")` returns the `[logins.frontier]` table from
~/.config/credentials/store.toml (written by setup.sh), mirroring the
tomllib pattern gmail_otp.py uses for its OAuth namespace. Stdlib-only.

CLI (for agent-driven login steps):
    uv run python creds.py frontier --field username
    uv run python creds.py frontier --field password
"""
from __future__ import annotations
import argparse
import os
import tomllib
from pathlib import Path

STORE = Path(os.path.expanduser("~/.config/credentials/store.toml"))


class CredsError(RuntimeError):
    pass


def load(name: str) -> dict:
    try:
        data = tomllib.loads(STORE.read_text())
        return data["logins"][name]
    except (FileNotFoundError, KeyError) as e:
        raise CredsError(f"logins.{name} not found in {STORE} — run setup.sh") from e


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("name", help="login table name, e.g. frontier")
    p.add_argument("--field", required=True, help="field to print, e.g. username")
    a = p.parse_args()
    print(load(a.name)[a.field])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
