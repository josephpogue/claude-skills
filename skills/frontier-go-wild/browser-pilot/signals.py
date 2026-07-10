"""Append-only run signals consumed by Agent Evolution to target proposals."""
from __future__ import annotations
import json
from pathlib import Path


def emit(run_id: str, event: str, signals_dir, **fields) -> None:
    d = Path(signals_dir)
    d.mkdir(parents=True, exist_ok=True)
    rec = {"run_id": run_id, "event": event, **fields}
    with open(d / f"{run_id}.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")


def read(run_id: str, signals_dir) -> list[dict]:
    p = Path(signals_dir) / f"{run_id}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
