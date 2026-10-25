---
name: onedrive-upload
description: Upload one local file to a OneDrive folder the user names and return a public download link. Use when the user asks to upload a file to OneDrive, put a file in a specific OneDrive folder, or create a OneDrive download or share link.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [OneDrive, Upload, Share, rclone]
---

# OneDrive upload

Upload one local file into a folder the user names on OneDrive, then return a public download link. Uses the rclone remote `onedrive`. The local file stays in place.

## When to use

The user wants a file on OneDrive, names a destination folder, or asks for a download link for that file.

## Before running

If the user did not name a folder, ask for one. The folder is a path under the OneDrive root (`any_bot`, `any_bot/notes`). Do not invent a folder and do not upload to the drive root.

Do not upload `.env`, `rclone.conf`, or `onedrive-token.json`.

Do not read `rclone.conf` or call the Microsoft Graph API. Run the script below.

## Command

```bash
python3 "${HERMES_HOME:-$HOME/.hermes}/skills/productivity/onedrive-upload/scripts/upload.py" \
  --file /absolute/path/to/file \
  --folder FOLDER
```

Optional flags:

- `--name other-name.ext` sets the filename on OneDrive
- `--expire 7d` sets when the link expires
- `--remote onedrive` selects a different rclone remote name

## Result

Stdout is one JSON object with `remote`, `bytes`, and `link`. Tell the user the remote path and the `link`. The link is an anonymous `https://1drv.ms/...` share. Anyone with it can open the file.

Exit code 2 means the rclone remote is missing. Tell the user to run `rclone config` and create a Microsoft OneDrive remote named `onedrive`.

## Check

`rclone lsf onedrive:FOLDER` lists the uploaded filename. `rclone link onedrive:FOLDER/filename` prints the same URL.
