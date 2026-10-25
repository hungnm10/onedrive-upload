#!/usr/bin/env python3
"""Upload one local file to a OneDrive folder and print a public download link."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BLOCKED_NAMES = {".env", "rclone.conf", "onedrive-token.json"}


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def validate_folder(folder: str) -> str:
    folder = folder.strip().strip("/")
    if not folder:
        die("folder is required, for example: any_bot")
    if ":" in folder or "\\" in folder or folder.startswith("/"):
        die(f"invalid folder {folder!r}")
    parts = folder.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        die(f"invalid folder {folder!r}")
    return folder


def validate_name(name: str) -> str:
    name = name.strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        die(f"invalid remote filename {name!r}")
    if name in BLOCKED_NAMES:
        die(f"refusing credential file: {name}")
    return name


def validate_file(path: Path) -> Path:
    if not path.exists():
        die(f"file not found: {path}")
    if path.is_dir():
        die(f"not a file: {path}")
    if not path.is_file():
        die(f"not a file: {path}")
    if path.name in BLOCKED_NAMES:
        die(f"refusing credential file: {path.name}")
    return path


def list_remotes() -> list[str]:
    result = subprocess.run(
        ["rclone", "listremotes"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        die(err or "rclone listremotes failed")
    return [line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()]


def share_url(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("https://") or line.startswith("http://"):
            return line
    die(f"no URL from rclone link: {stdout!r} {stderr!r}")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload one file to OneDrive and print a public download link"
    )
    parser.add_argument("--file", required=True, help="Local file to upload")
    parser.add_argument(
        "--folder",
        required=True,
        help="Folder under the OneDrive root, for example any_bot or any_bot/notes",
    )
    parser.add_argument("--remote", default="onedrive", help="rclone remote name")
    parser.add_argument("--name", help="Filename to use on OneDrive")
    parser.add_argument("--expire", help="Link expiry passed to rclone link, for example 7d")
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        die("rclone not found. Install with: brew install rclone")

    remote = args.remote.strip().rstrip(":")
    if not remote or any(char in remote for char in ":/\\"):
        die(f"invalid remote {args.remote!r}")

    folder = validate_folder(args.folder)
    source = validate_file(Path(args.file).expanduser().resolve())
    filename = validate_name(args.name or source.name)
    dest = f"{remote}:{folder}/{filename}"

    remotes = list_remotes()
    if remote not in remotes:
        listed = ", ".join(remotes) or "(none)"
        die(
            f"Remote '{remote}' is not configured.\n"
            f"Run: rclone config\n"
            f"Create a Microsoft OneDrive remote named {remote}.\n"
            f"Existing remotes: {listed}",
            code=2,
        )

    mkdir = subprocess.run(
        ["rclone", "mkdir", f"{remote}:{folder}"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if mkdir.returncode != 0:
        err = (mkdir.stderr or mkdir.stdout or "").strip()
        die(f"rclone mkdir failed: {err}")

    copy = subprocess.run(
        [
            "rclone",
            "copyto",
            str(source),
            dest,
            "--retries",
            "5",
            "--low-level-retries",
            "10",
        ],
        stderr=sys.stderr,
    )
    if copy.returncode != 0:
        die(f"rclone copyto failed ({copy.returncode})")

    link_cmd = ["rclone", "link", dest]
    if args.expire:
        link_cmd.extend(["--expire", args.expire])
    link = subprocess.run(link_cmd, capture_output=True, text=True, timeout=180)
    if link.returncode != 0:
        err = (link.stderr or link.stdout or "").strip()
        die(f"rclone link failed: {err}")

    payload = {
        "remote": dest,
        "bytes": source.stat().st_size,
        "link": share_url(link.stdout, link.stderr),
    }
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
