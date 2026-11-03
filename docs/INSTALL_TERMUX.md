# Install Ventoy Fetch on Android / Termux

This is a **Python CLI**, not an Android APK. It downloads ISO files to storage; it does not install Ventoy onto a USB stick.

## 1. Install and authorise storage

Install Termux from its official F-Droid/GitHub distribution (avoid outdated Play Store builds). In Termux:

```sh
pkg update && pkg upgrade -y
pkg install python git curl -y
termux-setup-storage
```

Accept the Android storage permission. If you decline, use a directory inside Termux instead of shared storage.

## 2. Get the app

```sh
git clone https://github.com/damunozx123-debug/ventoy-fetch.git
cd ventoy-fetch
python3 ventoy_fetch.py --help
python3 ventoy_fetch.py --list
```

For a menu:

```sh
pkg install dialog -y
python3 ventoy_fetch.py --gui
```

The numbered selector works without `dialog`.

## 3. Check before downloading

```sh
python3 ventoy_fetch.py --dry-run
```

The dry run can contact official upstream sources to resolve current downloads. Only proceed if you have free storage, appropriate network/data allowance and trusted destinations. ISO files can be several gigabytes.

To select by role, for example:

```sh
python3 ventoy_fetch.py --role recovery --jobs 1
```

## 4. Confirm integrity

```sh
python3 ventoy_fetch.py --verify-only
```

Review `ventoy_fetch_manifest.json`: `unverified` means there was no authoritative upstream signature/checksum available, **not** that the download was verified.

## 5. Ventoy USB

Prepare Ventoy on a separate USB device using official Ventoy instructions. Copy verified `.iso` files to its data partition; this tool does not repartition or flash a drive.

## Optional installation as CLI command

The repository contains a `pyproject.toml`. Installing `pip install .` should expose `ventoy-fetch`; until a CI install smoke test passes, prefer the directly tested `python3 ventoy_fetch.py` command.

## Screenshots

See [SCREENSHOTS.md](SCREENSHOTS.md) for a repeatable CLI screenshot capture. A captured CLI screen is not a claim that Android or physical USB boot was tested.
