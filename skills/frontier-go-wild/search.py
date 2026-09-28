#!/usr/bin/env python3
"""frontier-go-wild: read a list of (origin, destination, date) on Frontier Go Wild, top to bottom.

    echo '{"reads": [...], "filters": {...}}' | uv run python search.py [--saved-only]

Input, output columns and the run itself are shared by the three linear search
skills: flight-search/flights/linear/.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The published skill ships the code beside this file; in the source repo it is
# automations/flight-search, three folders up.
CODE = HERE / "flight-search"
if not CODE.is_dir():
    CODE = HERE.parents[2] / "automations" / "flight-search"
sys.path.insert(0, str(CODE))

from flights.linear.gowild import GoWildAdapter          # noqa: E402
from flights.linear.runner import main    # noqa: E402

if __name__ == "__main__":
    sys.exit(main(GoWildAdapter))
