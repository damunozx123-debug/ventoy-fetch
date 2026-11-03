# Ventoy Fetch

**Build a recovery or multiboot ISO collection directly from Termux.**

A Python utility for discovering, selecting, downloading and verifying operating-system and recovery ISOs for [Ventoy](https://www.ventoy.net/) USB drives. Designed for Android + Termux, including situations where a desktop computer is unavailable.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white) ![Platform](https://img.shields.io/badge/Platform-Android%20%2F%20Termux-2d8a68) ![Version](https://img.shields.io/badge/Version-7.0-84d7ff) ![Status](https://img.shields.io/badge/Status-source%20available-75879a)

## At a glance

| Capability | What you get |
| --- | --- |
| **Touch-friendly selection** | `--gui` opens a checkbox interface when `dialog` is available, with built-in text selection as a fallback |
| **Resumable downloads** | Optional `aria2`, concurrent jobs, retry with backoff and resume support |
| **Integrity reporting** | SHA-256/SHA-512 and GPG verification where upstream checksums/signatures are published |
| **Flexible collections** | Filter by role such as `pentest`, `recovery` or `distros` |
| **Phone-aware operation** | Optional Termux wake-lock, notifications and battery checks |
| **Audit trail** | JSON manifest recording downloads, hashes and whether verification was possible |

> **Safety and transparency:** A download without a trustworthy upstream checksum is marked **unverified**, not silently treated as safe. This tool downloads ISOs; it does **not** partition or flash drives automatically.

## Quick start

In Termux, from the cloned repository:

```sh
pkg install python curl -y
termux-setup-storage
python3 ventoy_fetch.py --list
python3 ventoy_fetch.py --gui
```

For a no-download inspection first:

```sh
python3 ventoy_fetch.py --dry-run
```

## Main commands

```sh
python3 ventoy_fetch.py                 # fetch all supported automatic sources
python3 ventoy_fetch.py --gui           # choose images interactively
python3 ventoy_fetch.py --role pentest  # limit selection to one role
python3 ventoy_fetch.py --list          # show sources and available roles
python3 ventoy_fetch.py --dry-run       # resolve metadata; do not download
python3 ventoy_fetch.py --verify-only   # verify already downloaded files
```

Useful options:

| Option | Behaviour |
| --- | --- |
| `--output-dir PATH` | Destination folder (default via config or `~/storage/shared/Ventoy`) |
| `--jobs N` | Concurrent download count, default **3** |
| `--downloader {auto,curl,aria2}` | Choose the download backend |
| `--force` | Re-fetch when you explicitly want to |
| `--no-wake-lock` | Do not request a Termux wake-lock |
| `--no-notify` | Do not use Termux notifications |

## Optional packages

| Package | Additional functionality |
| --- | --- |
| `aria2` | Parallel/multiconnection downloads |
| `gnupg` | Best-effort verification of published `.asc` / `.sig` signatures |
| `pyyaml` | Support for `config.yaml` |
| `dialog` | Terminal checklist interface |
| `termux-api` and the Termux:API app | Wake-lock, notifications and battery checks |

The tool detects optional packages. Their absence should not prevent the built-in basic CLI workflow.

## ISO catalog

Available sources are resolved at runtime where possible; published sizes below are **approximate** and may change.

| Source | Role / purpose | Approximate size |
| --- | --- | ---: |
| Kali Linux | Security and pentesting | 4.5 GB |
| Parrot OS (Security) | Security and pentesting | 4 GB |
| CAINE | Forensics | 4 GB |
| Arch Linux | General Linux | 1.2 GB |
| Ubuntu Desktop LTS | General Linux | 5.4 GB |
| SystemRescue | Recovery | 1.4 GB |
| Clonezilla | Backups / recovery | 500 MB |
| GParted Live | Partitioning | 700 MB |
| Boot-Repair-Disk | Boot repair | 1 GB |
| Rescatux | Boot repair | 700 MB |
| Super Grub2 Disk | Boot repair | 20 MB |
| Ultimate Boot CD | Diagnostics | 1 GB |
| DBAN | Drive wiping | 20 MB |
| ShredOS | Drive wiping | 30 MB |
| Hiren's BootCD PE | Windows recovery | Manual download |

**Hiren's BootCD PE** is manual-only because the project does not rely on third-party mirrors to guess at an installer URL. For the live list, run `--list`.

## Configuration

Place a `config.json` (or `config.yaml` when PyYAML is installed) beside the script. See [config.example.json](config.example.json). Command-line flags override the corresponding config defaults.

```json
{
  "output_dir": "/sdcard/Ventoy",
  "jobs": 3,
  "downloader": "auto",
  "wake_lock": true,
  "notify": true
}
```

## Verification and manifest

Each run maintains `ventoy_fetch_manifest.json` in the output directory. It records which files completed or failed, their associated status and available hashes/signatures. `--verify-only` rechecks local files without downloading new images.

Verification depends on what publishers actually provide. A file may be explicitly labelled **unverified** if no upstream checksum or signature is available. Always prefer official publisher download channels.

## Copy to Ventoy

After downloading and checking images, copy the finished `.iso` files to the filesystem on a correctly prepared Ventoy USB drive. Ventoy can boot supported images found on that drive without needing to flash each ISO individually.

This tool does **not** create a Ventoy partition layout, bypass device permissions or erase disks. Double-check the destination, particularly for drive-wiping ISO images.

## Contributing and project files

- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Python project metadata](pyproject.toml)
- [Tests](tests/)
- [Configuration example](config.example.json)

Maintained by [Daniel Munoz](https://github.com/damunozx123-debug). The readme describes source functionality, not a claim that every upstream download endpoint has recently been tested.


## Behind the project

<img src="assets/creator-avatar.svg" width="112" alt="Relaxed penguin engineer mascot" align="right"/>

I'm Dan, an independent developer experimenting with Linux, Android/Termux, automation and practical modifications. I like building tools that make complicated tasks easier. The penguin is my creator mascot, not a claim of project certification or endorsement.

