---
name: onedrive-upload
description: Upload one local file to a OneDrive folder the user names and return a public share link plus a direct URL an agent can GET for the raw file bytes. Use when the user asks to upload a file to OneDrive, create a download link, or turn a OneDrive share link into a direct file URL such as PNG bytes.
version: 0.2.0
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

Do not read `rclone.conf` or print tokens. Run the script below. It calls Graph and prints only the file URL.

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
- `--link https://1drv.ms/...` turns an existing share link into a fresh direct URL

## Result

Stdout is one JSON object with `remote`, `name`, `bytes`, `mime`, `link`, and `direct`.

`link` is the durable anonymous `https://1drv.ms/...` share page. `direct` is a temporary URL. An agent GETs `direct` with no login and receives the raw file bytes. A PNG comes back as `image/png` and starts with the PNG signature. Fetch `direct` immediately. When it expires, run the script again with `--link`.

Tell the user both URLs. Do not print the rclone token.

Exit code 2 means the rclone remote is missing. Tell the user to run `rclone config` and create a Microsoft OneDrive remote named `onedrive`.

## Check

`rclone lsf onedrive:FOLDER` lists the uploaded filename. `rclone link onedrive:FOLDER/filename` prints the same URL.
