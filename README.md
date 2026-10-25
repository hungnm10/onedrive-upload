# onedrive-upload

Hermes skill. Uploads one local file into a OneDrive folder you name and prints a public download link.

## Install

Requires [rclone](https://rclone.org/) with a remote named `onedrive` (Microsoft OneDrive).

```bash
mkdir -p ~/.hermes/skills/productivity
git clone git@github.com:hungnm10/onedrive-upload.git ~/.hermes/skills/productivity/onedrive-upload
```

Start a new Hermes session so the skill list reloads, or run `/reload-skills`.

## Use

```bash
python3 ~/.hermes/skills/productivity/onedrive-upload/scripts/upload.py \
  --file ./report.pdf \
  --folder any_bot
```

Stdout is JSON with `remote`, `bytes`, and `link`. The link is an anonymous OneDrive share (`https://1drv.ms/...`). The local file is not deleted.

`--name` renames the file on OneDrive. `--expire 7d` sets link expiry. `--folder` is required and is a path under the drive root, such as `any_bot` or `any_bot/notes`.
