#!/usr/bin/env python3
"""refresh_sample_schedules.py – roll sample schedule dates to today (UTC).

Rewrites every JSON file under data/schedules/ so that the first entry starts
at midnight UTC *today*.  Subsequent entries follow at their original intervals.
This is run automatically by setup_linux.sh to ensure the sample schedule is
always current when the hub is first started.

Usage:
    python tools/refresh_sample_schedules.py [--data-dir ./data]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def find_data_dir() -> Path:
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "data" / "channels.json").exists():
            return candidate / "data"
    return here / "data"


def refresh(schedule_file: Path) -> int:
    """Return the number of entries updated."""
    with schedule_file.open() as fh:
        entries: list[dict] = json.load(fh)

    if not entries:
        return 0

    # Anchor: midnight UTC today
    today_midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Work out the inter-entry offsets from the original data
    orig_starts = []
    for entry in entries:
        ts = datetime.fromisoformat(entry["start_ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        orig_starts.append(ts)

    # Shift every entry so the first one lands on today_midnight
    delta = today_midnight - orig_starts[0]
    updated = []
    for entry, orig_start in zip(entries, orig_starts):
        new_start = orig_start + delta
        updated.append({**entry, "start_ts": new_start.isoformat(), "http_url": ""})

    with schedule_file.open("w") as fh:
        json.dump(updated, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return len(updated)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir) if args.data_dir else find_data_dir()
    schedules_dir = data_dir / "schedules"

    if not schedules_dir.is_dir():
        print(f"No schedules directory found at {schedules_dir}", file=sys.stderr)
        sys.exit(1)

    schedule_files = list(schedules_dir.glob("*.json"))
    if not schedule_files:
        print("No schedule files found.")
        return

    for sf in sorted(schedule_files):
        count = refresh(sf)
        print(f"  {sf.name}: {count} entries anchored to today (UTC midnight).")


if __name__ == "__main__":
    main()
