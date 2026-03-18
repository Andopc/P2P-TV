#!/usr/bin/env python3
"""add_content.py – register a local video file with a P2P TV channel schedule.

Usage
-----
    python tools/add_content.py <video_file> [options]

The script:
  1. Checks the file exists and is readable.
  2. Computes the SHA-256 digest and file size automatically.
  3. Optionally detects duration via ffprobe (falls back to --duration if unavailable).
  4. Appends a new schedule entry to data/schedules/<channel_id>.json.
  5. Prints a curl command to verify the file is reachable once the hub is running.

Examples
--------
    # Minimal – start now, duration auto-detected (or asks interactively):
    python tools/add_content.py data/content/my-show-ep1.mkv

    # Full:
    python tools/add_content.py data/content/my-show-ep1.mkv \\
        --channel channel-1 \\
        --title "My Show – Episode 1" \\
        --start "2026-03-20T20:00:00+00:00" \\
        --duration 1800 \\
        --magnet "magnet:?xt=urn:btih:..."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────────

def sha256_of_file(path: str) -> str:
    """Return the hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: str) -> int | None:
    """Try to get video duration in whole seconds via ffprobe.  Returns None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()))
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def find_data_dir() -> Path:
    """Return the repo-root data/ directory.

    Searches upward from the current working directory so the script works when
    called from any subdirectory of the repo.
    """
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "data" / "channels.json").exists():
            return candidate / "data"
    # Fallback: assume ./data relative to cwd
    return here / "data"


def load_channels(data_dir: Path) -> list[str]:
    channels_file = data_dir / "channels.json"
    if not channels_file.exists():
        return []
    with channels_file.open() as fh:
        return [ch["id"] for ch in json.load(fh)]


def parse_start_ts(raw: str) -> datetime:
    """Parse an ISO-8601 string, defaulting to UTC if no timezone is given."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Register a local video file with a P2P TV channel schedule.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("video_file", help="Path to the video file to register.")
    parser.add_argument(
        "--channel", "-c",
        default="channel-1",
        help="Channel ID to add the entry to (default: channel-1).",
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        help="Programme title.  Defaults to the filename stem.",
    )
    parser.add_argument(
        "--start", "-s",
        default=None,
        help=(
            "Start time as ISO-8601 string (e.g. '2026-03-20T20:00:00+00:00'). "
            "Defaults to now (UTC)."
        ),
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=None,
        help=(
            "Duration in seconds.  Auto-detected via ffprobe if omitted. "
            "Prompted interactively if ffprobe is unavailable."
        ),
    )
    parser.add_argument(
        "--magnet", "-m",
        default="",
        help="Optional BitTorrent magnet URI for this content.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to the data/ directory (auto-detected if omitted).",
    )

    args = parser.parse_args(argv)

    # ── resolve paths ────────────────────────────────────────────────────────

    video_path = os.path.abspath(args.video_file)
    if not os.path.isfile(video_path):
        print(f"Error: file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(args.data_dir) if args.data_dir else find_data_dir()
    schedules_dir = data_dir / "schedules"
    schedules_dir.mkdir(parents=True, exist_ok=True)

    # ── channel validation ───────────────────────────────────────────────────

    known_channels = load_channels(data_dir)
    if known_channels and args.channel not in known_channels:
        print(
            f"Warning: channel '{args.channel}' is not in channels.json "
            f"(known: {', '.join(known_channels)}).  Continuing anyway.",
            file=sys.stderr,
        )

    # ── content_id ──────────────────────────────────────────────────────────

    stem = Path(video_path).stem
    content_id = stem

    # ── title ───────────────────────────────────────────────────────────────

    title = args.title if args.title else stem.replace("-", " ").replace("_", " ")

    # ── start_ts ────────────────────────────────────────────────────────────

    if args.start:
        try:
            start_ts = parse_start_ts(args.start)
        except ValueError as exc:
            print(f"Error: invalid --start value: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        start_ts = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    # ── duration ────────────────────────────────────────────────────────────

    duration_seconds = args.duration
    if duration_seconds is None:
        print("Detecting duration via ffprobe …", end=" ", flush=True)
        duration_seconds = probe_duration(video_path)
        if duration_seconds is not None:
            print(f"{duration_seconds}s")
        else:
            print("ffprobe not found or failed.")
            try:
                raw = input("Enter duration in seconds: ").strip()
                duration_seconds = int(raw)
            except (ValueError, EOFError):
                print("Error: could not determine duration.  Use --duration.", file=sys.stderr)
                sys.exit(1)

    if duration_seconds <= 0:
        print("Error: duration must be greater than 0.", file=sys.stderr)
        sys.exit(1)

    # ── sha256 + size ────────────────────────────────────────────────────────

    print(f"Computing SHA-256 of {os.path.basename(video_path)} …", end=" ", flush=True)
    digest = sha256_of_file(video_path)
    size_bytes = os.path.getsize(video_path)
    print("done.")

    # ── build entry ─────────────────────────────────────────────────────────

    entry: dict = {
        "start_ts": start_ts.isoformat(),
        "duration_seconds": duration_seconds,
        "title": title,
        "content_id": content_id,
        "variant": "handheld",
        "magnet": args.magnet,
        "sha256": digest,
        "size_bytes": size_bytes,
        "http_url": "",  # filled in dynamically by the hub at query time
    }

    # ── load, append, save ────────────────────────────────────────────────────

    schedule_file = schedules_dir / f"{args.channel}.json"
    if schedule_file.exists():
        with schedule_file.open() as fh:
            schedule: list[dict] = json.load(fh)
    else:
        schedule = []

    # Deduplicate by content_id: replace existing entry if found
    existing_idx = next(
        (i for i, e in enumerate(schedule) if e.get("content_id") == content_id),
        None,
    )
    if existing_idx is not None:
        print(
            f"Replacing existing schedule entry for content_id='{content_id}'."
        )
        schedule[existing_idx] = entry
    else:
        schedule.append(entry)

    # Sort by start_ts
    schedule.sort(key=lambda e: e["start_ts"])

    with schedule_file.open("w") as fh:
        json.dump(schedule, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ── also copy the file to data/content/ if it's not already there ────────

    content_dir = data_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    target = content_dir / os.path.basename(video_path)
    if not target.exists():
        dest = str(target)
        print(f"Copying {os.path.basename(video_path)} → data/content/ …", end=" ", flush=True)
        shutil.copy2(video_path, dest)
        print("done.")
    elif os.path.abspath(str(target)) == video_path:
        pass  # file is already in data/content/
    else:
        print(
            f"Note: {os.path.basename(video_path)} already exists in data/content/. "
            "Not overwriting."
        )

    # ── success summary ──────────────────────────────────────────────────────

    print()
    print("✓ Schedule entry added:")
    print(f"  channel      : {args.channel}")
    print(f"  content_id   : {content_id}")
    print(f"  title        : {title}")
    print(f"  start_ts     : {start_ts.isoformat()}")
    print(f"  duration     : {duration_seconds}s ({duration_seconds // 60}m {duration_seconds % 60}s)")
    print(f"  sha256       : {digest}")
    print(f"  size_bytes   : {size_bytes:,}")
    print()
    print("Make sure the hub is running, then fetch the file with:")

    # Try to read the API key from .env if present
    api_key = "<your-P2PTV_API_KEY>"
    env_path = data_dir.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("P2PTV_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break

    print(
        f"  curl -H \"Authorization: Bearer {api_key}\" "
        f"http://localhost:8000/api/v1/content/{content_id}/file -o /dev/null -w '%{{http_code}}\\n'"
    )
    print()
    print("Or play directly with mpv:")
    print(
        f"  mpv --http-header-fields=\"Authorization: Bearer {api_key}\" "
        f"http://localhost:8000/api/v1/content/{content_id}/file"
    )


if __name__ == "__main__":
    main()
