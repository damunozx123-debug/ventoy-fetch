# ventoy_fetch.py

A Termux (Android) script that fetches ISOs for a [Ventoy](https://www.ventoy.net/) multi-boot USB drive: pentest/security distros, general Linux distros, system-recovery tools, and disk-wipe utilities. Runs entirely from your phone — no laptop required.

v7.0 "Touch-Friendly" adds an interactive checklist (`--gui`) on top of everything from earlier versions: concurrent downloads, resume support, checksum/GPG verification, retry with backoff, a JSON manifest, and Termux API integration (wake-lock, notifications, battery check).

## Setup

```sh
pkg install curl -y
termux-setup-storage
python3 ventoy_fetch.py --list
```

Optional, all auto-detected if present:

| Package | Adds |
|---|---|
| `aria2` | multi-connection downloads (faster than plain curl) |
| `gnupg` | verifies `.sig`/`.asc` signatures where available |
| `pyyaml` | lets you use `config.yaml` instead of `config.json` |
| `dialog` | a real checkbox UI for `--gui` (bare Termux doesn't ship it — without it you get a built-in numbered text selector, which works the same) |
| `termux-api` package + **Termux:API** app | wake-lock during long fetches, a notification when done, and a low-battery warning |

## Usage

```sh
python3 ventoy_fetch.py                # everything that can be auto-fetched
python3 ventoy_fetch.py --gui          # interactive checklist
python3 ventoy_fetch.py --role pentest # only pentest-tagged sources
python3 ventoy_fetch.py --list         # show all sources & available --role values
python3 ventoy_fetch.py --dry-run      # resolve URLs/sizes, download nothing
python3 ventoy_fetch.py --verify-only  # re-check hashes of files already on disk
```

Other flags:

| Flag | Effect |
|---|---|
| `--output-dir PATH` | where ISOs go (default: `config.json`, else `~/storage/shared/Ventoy`) |
| `--force` | re-download even if a valid file is already there |
| `--jobs N` | concurrent downloads (default 3 — lower it if you're on mobile data or want to save battery) |
| `--downloader {auto,curl,aria2}` | pick the transfer tool explicitly |
| `--no-wake-lock` / `--no-notify` | skip the Termux:API calls |

## Sources

| Name | Role/category | ~Size |
|---|---|---|
| Kali Linux | distros, pentest | 4.5 GB |
| Parrot OS (Security edition) | distros, pentest | 4.0 GB |
| CAINE | distros, pentest, forensics | 4.0 GB |
| Arch Linux | distros | 1.2 GB |
| Ubuntu Desktop (latest LTS) | distros | 5.4 GB |
| SystemRescue | recovery | 1.4 GB |
| Clonezilla | recovery, backup | 500 MB |
| GParted Live | recovery, partitioning | 700 MB |
| Boot-Repair-Disk | recovery, boot-repair | 1.0 GB |
| Rescatux | recovery, boot-repair | 700 MB |
| Super Grub2 Disk | recovery, boot-repair | 20 MB |
| Ultimate Boot CD | recovery, diagnostics | 1.0 GB |
| DBAN | wipe, data-destruction | 20 MB |
| ShredOS | wipe, data-destruction | 30 MB |
| Hiren's BootCD PE | recovery, windows-repair | **manual** |

Run `--list` any time — it's generated from the same source list this file describes, so it's always current. Everything above is resolved dynamically (latest Kali build, current Ubuntu LTS, latest SourceForge/GitHub release, etc.) rather than pinned to a version, so the script keeps working as upstream projects release new builds.

**Hiren's BootCD PE** is the one exception: there's no single stable, official direct-download link to scrape — third-party mirrors bundle ads or other installers, so `--gui` and a normal run both just point you at the official page instead of guessing at a mirror.

## Config file

Drop a `config.json` (or `config.yaml` with `pyyaml` installed) next to the script to set defaults — any matching CLI flag overrides it. See `config.example.json`:

```json
{
  "output_dir": "/sdcard/Ventoy",
  "jobs": 3,
  "downloader": "auto",
  "wake_lock": true,
  "notify": true
}
```

## Manifest & verification

Every run reads/writes `ventoy_fetch_manifest.json` in the output directory: which files were fetched and their hash/status, which failed and why, and which are manual-only. Files are checked against upstream SHA256/SHA512 sums where a project publishes them, and against GPG signatures where `gnupg` is installed and a `.sig`/`.asc` is available; otherwise they're marked `unverified — no upstream checksum available` rather than silently treated as good. `--verify-only` re-runs this check without downloading anything, so you can confirm your Ventoy drive's contents any time.

## Putting ISOs on Ventoy

Once files are in your output directory, copy them onto the Ventoy-formatted drive (Termux can read/write it directly if it's exposed as shared storage, or via a USB-OTG connection) — no re-flashing needed, Ventoy just boots whatever `.iso` files it finds on the drive.
