#!/usr/bin/env python3
"""play_channel.py – play a P2P TV channel from the current schedule position.

Works without FieldStation42 or the hub running.  Reads the schedule JSON
directly from data/schedules/ and launches mpv on the local files in
data/content/.

Usage
-----
    python tools/play_channel.py [channel-id] [options]

The script figures out which video is "on air" right now (based on start_ts and
duration), seeks into it at the correct offset, then chains all following items
in order — just like a real TV channel.

Examples
--------
    # Play channel-1 from the current on-air position:
    python tools/play_channel.py channel-1

    # List what would play without launching mpv:
    python tools/play_channel.py channel-1 --list

    # Play from the very start of the first video (ignore schedule time):
    python tools/play_channel.py channel-1 --from-start

    # Loop continuously – restart from the first item after the last one ends:
    python tools/play_channel.py channel-1 --loop

    # Play a specific channel on the CRT profile:
    python tools/play_channel.py channel-crt
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Seek offsets below this threshold are not applied or displayed –
# sub-second precision is not meaningful and avoids an unnecessary --start flag.
_MIN_SEEK_SECONDS: float = 1.0


# ── helpers ────────────────────────────────────────────────────────────────────

def find_data_dir() -> Path:
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "data" / "channels.json").exists():
            return candidate / "data"
    return here / "data"


def load_schedule(data_dir: Path, channel_id: str) -> list[dict]:
    """Load and sort all entries from data/schedules/<channel_id>.json."""
    path = data_dir / "schedules" / f"{channel_id}.json"
    if not path.exists():
        print(f"Error: no schedule file found at {path}", file=sys.stderr)
        print(
            "  Run  python tools/add_content.py <video>  to create one.",
            file=sys.stderr,
        )
        sys.exit(1)
    with path.open() as fh:
        entries: list[dict] = json.load(fh)
    # Normalise start_ts to UTC-aware datetimes and sort
    for e in entries:
        ts = datetime.fromisoformat(e["start_ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        e["_start"] = ts
        e["_end"] = ts + timedelta(seconds=int(e["duration_seconds"]))
    entries.sort(key=lambda e: e["_start"])
    return entries


def resolve_file(data_dir: Path, content_id: str) -> Path | None:
    """Find the local file for *content_id* in data/content/."""
    content_dir = data_dir / "content"
    if not content_dir.is_dir():
        return None
    for fname in os.listdir(content_dir):
        stem = os.path.splitext(fname)[0]
        if fname == content_id or stem == content_id:
            full = content_dir / fname
            if full.is_file():
                return full
    return None


def check_mpv() -> str:
    """Return the mpv command name, or exit with an install hint."""
    for candidate in ["mpv"]:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    print("Error: mpv is not installed or not on your PATH.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Install it:", file=sys.stderr)
    print("  Debian/Ubuntu : sudo apt install mpv", file=sys.stderr)
    print("  Fedora/RHEL   : sudo dnf install mpv", file=sys.stderr)
    print("  Arch          : sudo pacman -S mpv", file=sys.stderr)
    print("  macOS (brew)  : brew install mpv", file=sys.stderr)
    print("  Windows       : https://mpv.io/installation/", file=sys.stderr)
    sys.exit(1)


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


# ── main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Play a P2P TV channel from the current schedule position.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "channel",
        nargs="?",
        default="channel-1",
        help="Channel ID to play (default: channel-1).",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List scheduled items without launching mpv.",
    )
    parser.add_argument(
        "--from-start", "-f",
        action="store_true",
        help="Play from the first item regardless of current time (no seek offset).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop the playlist continuously after the last item.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to the data/ directory (auto-detected if omitted).",
    )

    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir) if args.data_dir else find_data_dir()
    entries = load_schedule(data_dir, args.channel)

    if not entries:
        print(f"No schedule entries found for channel '{args.channel}'.")
        print("  Add videos with:  python tools/add_content.py <video_file>")
        sys.exit(0)

    now = datetime.now(timezone.utc)

    # ── figure out which entry is on air right now ──────────────────────────

    seek_offset: float = 0.0
    start_idx: int = 0

    if not args.from_start:
        for i, entry in enumerate(entries):
            if entry["_start"] <= now < entry["_end"]:
                seek_offset = (now - entry["_start"]).total_seconds()
                start_idx = i
                break
            if entry["_start"] > now:
                # Nothing is airing yet; start from the next upcoming item
                start_idx = i
                seek_offset = 0.0
                break
        else:
            # All entries are in the past – start from the last one for a loop,
            # or from the beginning.
            if args.loop:
                start_idx = 0
                seek_offset = 0.0
            else:
                print(
                    f"All schedule entries for '{args.channel}' are in the past."
                )
                print(
                    "  Re-run with  --from-start  to play from the beginning, "
                    "or  --loop  to cycle."
                )
                sys.exit(0)

    # ── resolve local files ─────────────────────────────────────────────────

    playlist: list[tuple[dict, Path]] = []
    missing: list[str] = []

    ordered = entries[start_idx:] + (entries[:start_idx] if args.loop else [])
    for entry in ordered:
        file_path = resolve_file(data_dir, entry["content_id"])
        if file_path is None:
            missing.append(entry["content_id"])
        else:
            playlist.append((entry, file_path))

    if missing:
        print(
            f"Warning: {len(missing)} content file(s) not found in data/content/ "
            f"and will be skipped: {', '.join(missing)}",
            file=sys.stderr,
        )

    if not playlist:
        print(
            "Error: no playable files found. "
            "Copy your videos to data/content/ first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── list mode ──────────────────────────────────────────────────────────

    current_entry = entries[start_idx]
    print(f"\nChannel: {args.channel}")
    print(f"Time:    {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    for idx, (entry, fpath) in enumerate(playlist):
        is_current = idx == 0 and not args.from_start
        marker = "▶ NOW" if is_current else f"  {idx + 1:>2}."
        seek_note = f"  (seek {fmt_duration(seek_offset)} in)" if is_current and seek_offset > _MIN_SEEK_SECONDS else ""
        print(
            f"{marker}  {entry['title']}"
            f"  [{fmt_duration(entry['duration_seconds'])}]"
            f"{seek_note}"
        )
        print(f"        {fpath.name}")

    if args.loop:
        print("       … (loops)")
    print()

    if args.list:
        return

    # ── launch mpv ─────────────────────────────────────────────────────────

    mpv_cmd = check_mpv()

    cmd: list[str] = [mpv_cmd]

    # Seek into the currently-airing item (applies to the first file only)
    if seek_offset > _MIN_SEEK_SECONDS:
        cmd += [f"--start={seek_offset:.1f}"]

    # Display the title in the mpv title bar
    cmd += [f"--title=P2P TV – {args.channel}"]

    # Keep window open at the end if looping
    if args.loop:
        cmd += ["--loop-playlist=inf"]

    # Add all the file paths
    cmd += [str(fpath) for _, fpath in playlist]

    print(f"Launching mpv …")
    print(f"  {' '.join(cmd[:4])} …\n")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
