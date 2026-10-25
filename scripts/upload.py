#!/usr/bin/env python3
"""Upload one local file to OneDrive and print a share link plus a direct byte URL."""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
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


def access_token(remote: str) -> str:
    result = subprocess.run(
        ["rclone", "config", "show", remote],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        die(err or "rclone config show failed")
    for line in result.stdout.splitlines():
        if not line.startswith("token ") or "=" not in line:
            continue
        blob = json.loads(line.split("=", 1)[1].strip())
        token = blob.get("access_token") or ""
        if token:
            return token
    die(f"rclone remote '{remote}' has no access token")
    return ""


def graph_item(share_link: str, token: str) -> dict:
    share_id = "u!" + base64.urlsafe_b64encode(share_link.encode()).decode().rstrip("=")
    encoded = urllib.parse.quote(share_id, safe="")
    api = f"https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem"
    request = urllib.request.Request(api, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        message = f"graph {err.code}"
        try:
            message = json.loads(body).get("error", {}).get("message") or message
        except json.JSONDecodeError:
            pass
        raise RuntimeError(message) from err
    if not isinstance(payload, dict):
        raise RuntimeError("graph response was not an object")
    return payload


def direct_for_link(share_link: str, remote: str) -> dict:
    link = share_link.strip()
    if not (link.startswith("https://") or link.startswith("http://")):
        die(f"link must be an http(s) URL: {share_link!r}")
    token = access_token(remote)
    try:
        item = graph_item(link, token)
    except RuntimeError as err:
        if "InvalidAuthenticationToken" not in str(err) and "token" not in str(err).lower():
            die(f"could not resolve share link: {err}")
        subprocess.run(["rclone", "about", f"{remote}:"], capture_output=True, text=True, timeout=90)
        try:
            item = graph_item(link, access_token(remote))
        except RuntimeError as retry_err:
            die(f"could not resolve share link: {retry_err}")
    if "folder" in item and "file" not in item:
        die("share link points at a folder, not a file")
    direct = item.get("@microsoft.graph.downloadUrl") or ""
    if not direct.startswith("https://"):
        die("graph did not return a direct download URL")
    file_info = item.get("file") if isinstance(item.get("file"), dict) else {}
    return {
        "name": item.get("name") or "",
        "bytes": item.get("size"),
        "mime": file_info.get("mimeType") or "",
        "link": link,
        "direct": direct,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload one file to OneDrive and print a public download link"
    )
    parser.add_argument("--file", help="Local file to upload")
    parser.add_argument(
        "--folder",
        help="Folder under the OneDrive root, for example any_bot or any_bot/notes",
    )
    parser.add_argument("--remote", default="onedrive", help="rclone remote name")
    parser.add_argument("--name", help="Filename to use on OneDrive")
    parser.add_argument("--expire", help="Link expiry passed to rclone link, for example 7d")
    parser.add_argument(
        "--link",
        help="Existing OneDrive share link to turn into a direct byte URL",
    )
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        die("rclone not found. Install with: brew install rclone")

    remote = args.remote.strip().rstrip(":")
    if not remote or any(char in remote for char in ":/\\"):
        die(f"invalid remote {args.remote!r}")

    if args.link:
        if remote not in list_remotes():
            die(f"Remote '{remote}' is not configured. Run: rclone config", code=2)
        json.dump(direct_for_link(args.link, remote), sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    if not args.file or not args.folder:
        die("pass --file and --folder, or pass --link")

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

    shared = share_url(link.stdout, link.stderr)
    resolved = direct_for_link(shared, remote)
    payload = {
        "remote": dest,
        "name": resolved["name"],
        "bytes": source.stat().st_size,
        "mime": resolved["mime"],
        "link": shared,
        "direct": resolved["direct"],
    }
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
