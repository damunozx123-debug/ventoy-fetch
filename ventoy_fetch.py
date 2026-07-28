
#!/usr/bin/env python3
"""
Ventoy multi-boot USB — ISO fetcher for Termux (Android)  v7.0  "Touch-Friendly"

One-time setup (in Termux):
    pkg install curl -y
    termux-setup-storage
    # optional: pkg install aria2 pyyaml gnupg termux-api dialog

Run:
    python3 ventoy_fetch.py                # all auto‑fetchable ISOs (or use roles)
    python3 ventoy_fetch.py --gui          # interactive checklist (GUI)
    python3 ventoy_fetch.py --role pentest # only pentest‑related ISOs
    python3 ventoy_fetch.py --list         # show all sources & configured roles
    python3 ventoy_fetch.py --dry-run      # resolve URLs/sizes, download nothing
    python3 ventoy_fetch.py --verify-only  # re-check hashes of files already on disk

Extra flags (all optional, all have sane defaults):
    --output-dir PATH        where to save ISOs (default: ~/storage/shared/Ventoy)
    --force                  re-download even if a valid file already exists
    --jobs N                 concurrent downloads (default: 3; lower = gentler on
                              mobile data/battery)
    --downloader {auto,curl,aria2}
    --no-wake-lock           don't request termux-wake-lock during the run
    --no-notify              don't send a termux-notification when finished

Optional companion packages (all auto‑detected):
    termux-api   -> also install the "Termux:API" app itself.
    gnupg        -> best‑effort verification of downloaded .sig/.asc files.
    aria2        -> multi‑connection downloads instead of plain curl.
    pyyaml       -> lets you use config.yaml instead of config.json.
    dialog       -> prettier TUI for --gui; otherwise a built‑in text selector is used.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "7.0"
UA = f"Mozilla/5.0 (compatible; ventoy-fetch/{VERSION})"
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE_JSON = SCRIPT_DIR / "config.json"
CONFIG_FILE_YAML = SCRIPT_DIR / "config.yaml"
MANIFEST_FILENAME = "ventoy_fetch_manifest.json"

APPROX_SIZES_MB = {
    "Kali Linux": 4500, "Parrot OS": 4000, "Arch Linux": 1200,
    "Ubuntu Desktop LTS": 5400, "SystemRescue": 1400, "Clonezilla": 500,
    "GParted Live": 700, "Hiren's BootCD PE": 3500, "CAINE": 4000,
    "Boot-Repair-Disk": 1000, "Rescatux": 700, "Super Grub2 Disk": 20,
    "Ultimate Boot CD": 1000, "DBAN": 20, "ShredOS": 30,
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_config() -> dict:
    if CONFIG_FILE_YAML.exists():
        try:
            import yaml
            with open(CONFIG_FILE_YAML) as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            print("YAML config found but pyyaml not installed; falling back to JSON.")
    if CONFIG_FILE_JSON.exists():
        with open(CONFIG_FILE_JSON) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def http_get_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def get_remote_size(url: str, timeout: int = 10) -> int | None:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            length = resp.headers.get("Content-Length")
            return int(length) if length else None
    except Exception:
        return None


def human_size(n) -> str:
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def sha256_of(path: Path) -> str:
    return _hash_file(path, hashlib.sha256())


def sha512_of(path: Path) -> str:
    return _hash_file(path, hashlib.sha512())


def blake2b_of(path: Path) -> str:
    return _hash_file(path, hashlib.blake2b())


HASH_FUNCS = {"sha256": sha256_of, "sha512": sha512_of, "blake2b": blake2b_of}


def _hash_file(path: Path, hasher) -> str:
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def looks_bogus(path: Path, min_bytes: int) -> bool:
    size = path.stat().st_size
    if size < min_bytes:
        return True
    with open(path, "rb") as f:
        head = f.read(512).lower()
        if head.strip().startswith((b"<html", b"<!doctype", b"<?xml")):
            return True
        if size >= 0x8800:
            f.seek(0x8001)
            if f.read(5) != b"CD001":
                return True
        else:
            return True
    return False


def detect_checksum_algorithm(sums_text: str, filename: str) -> tuple[str | None, str | None, bool]:
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and filename in parts[-1]:
            h = parts[0]
            algo = _guess_algo(line, h)
            return h, algo, True
    candidates = [l.split() for l in sums_text.splitlines() if ".iso" in l]
    if len(candidates) == 1 and len(candidates[0]) >= 2:
        h = candidates[0][0]
        algo = _guess_algo("", h)
        return h, algo, False
    return None, None, False


def _guess_algo(line: str, hash_str: str) -> str | None:
    line_lower = line.lower()
    if "sha256" in line_lower:
        return "sha256"
    if "sha512" in line_lower:
        return "sha512"
    if "blake2" in line_lower:
        return "blake2b"
    l = len(hash_str)
    if l == 64:
        return "sha256"
    if l == 128:
        return "sha512"
    return None


def resolve_sourceforge_rss(project: str) -> str | None:
    rss_url = f"https://sourceforge.net/projects/{project}/rss?limit=20"
    try:
        data = http_get_text(rss_url, timeout=15)
        root = ET.fromstring(data)
        ns = {"media": "http://search.yahoo.com/mrss/"}
        for item in root.iter("item"):
            for mc in item.findall("media:content", ns):
                url = mc.get("url")
                if url and url.lower().endswith(".iso"):
                    return url
            link = item.find("link")
            if link is not None and link.text and link.text.lower().endswith(".iso"):
                return link.text
    except Exception:
        pass
    return None


def verify_signature(sig_path: Path, data_path: Path) -> str:
    if shutil.which("gpg") is None:
        return "signature saved (install gnupg to auto-verify)"
    try:
        result = subprocess.run(
            ["gpg", "--verify", str(sig_path), str(data_path)],
            capture_output=True, text=True, timeout=30,
        )
        output = (result.stdout + result.stderr).lower()
        if result.returncode == 0 and "good signature" in output:
            return "GOOD signature"
        if "no public key" in output:
            return "signature saved, but public key missing"
        return "signature verification FAILED"
    except Exception:
        return "signature verification attempt errored"


# ---------------------------------------------------------------------------
# Termux API helpers
# ---------------------------------------------------------------------------
def termux_wake_lock():
    if shutil.which("termux-wake-lock"):
        try:
            subprocess.run(["termux-wake-lock"], timeout=10, check=False)
            return True
        except Exception:
            pass
    return False


def termux_wake_unlock():
    if shutil.which("termux-wake-unlock"):
        try:
            subprocess.run(["termux-wake-unlock"], timeout=10, check=False)
        except Exception:
            pass


def termux_notify(title: str, content: str):
    if shutil.which("termux-notification"):
        try:
            subprocess.run(["termux-notification", "--title", title, "--content", content],
                           timeout=10, check=False)
        except Exception:
            pass


def termux_open_url(url: str):
    if shutil.which("termux-open-url"):
        try:
            subprocess.run(["termux-open-url", url], timeout=10, check=False)
        except Exception:
            pass


def termux_battery_ok() -> tuple[bool, str]:
    if not shutil.which("termux-battery-status"):
        return True, ""
    try:
        out = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=10)
        info = json.loads(out.stdout)
        pct = info.get("percentage")
        charging = info.get("plugged") not in (None, "UNPLUGGED")
        if isinstance(pct, (int, float)) and pct < 20 and not charging:
            return False, f"battery at {pct}% and not charging"
    except Exception:
        pass
    return True, ""


# ---------------------------------------------------------------------------
# Downloaders
# ---------------------------------------------------------------------------
def _run_with_cancel(cmd, cancel_event, poll_interval=0.5):
    try:
        proc = subprocess.Popen(cmd)
    except FileNotFoundError:
        return False
    while True:
        try:
            return proc.wait(timeout=poll_interval) == 0
        except subprocess.TimeoutExpired:
            if cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return False


def curl_download(url, dest, cancel_event):
    delay = 5
    for _ in range(5):
        if cancel_event.is_set():
            return False
        cmd = ["curl", "-L", "-C", "-", "-A", UA,
               "--retry", "2", "--retry-delay", "2",
               "--connect-timeout", "15", "--max-time", "0", "-sS",
               "-o", str(dest), url]
        if _run_with_cancel(cmd, cancel_event):
            return True
        if cancel_event.wait(delay):
            return False
        delay *= 2
    return False


def aria2_download(url, dest, cancel_event):
    delay = 5
    for _ in range(5):
        if cancel_event.is_set():
            return False
        cmd = ["aria2c", "--max-connection-per-server=4", "--split=4",
               "--continue=true", "--retry-wait=2", "--max-tries=3",
               "--timeout=15", "--connect-timeout=15",
               "--console-log-level=error", "--summary-interval=0",
               "--file-allocation=none", f"--user-agent={UA}",
               "-o", dest.name, "-d", str(dest.parent), url]
        if _run_with_cancel(cmd, cancel_event):
            return True
        if cancel_event.wait(delay):
            return False
        delay *= 2
    return False


def download_file(url, dest, prefer, cancel_event):
    if prefer == "auto":
        use_aria2 = shutil.which("aria2c") is not None
    else:
        use_aria2 = (prefer == "aria2")
    return aria2_download(url, dest, cancel_event) if use_aria2 else curl_download(url, dest, cancel_event)


# ---------------------------------------------------------------------------
# Progress & threading
# ---------------------------------------------------------------------------
progress_lock = threading.Lock()
progress = {}
DONE_SIGNAL = False
manifest_lock = threading.Lock()
cancel_event = threading.Event()


def update_progress(name, status):
    with progress_lock:
        progress[name] = status


def progress_reporter():
    while not DONE_SIGNAL:
        with progress_lock:
            active = {k: v for k, v in progress.items() if v != "done"}
            if active:
                line = " | ".join(f"{k}: {v}" for k, v in active.items())
                print(f"\r[Progress] {line:<120}", end="", flush=True)
            else:
                print("\r[Progress] All tasks completed.            ", end="", flush=True)
        time.sleep(1)


def poll_progress(name, part, total_bytes, stop, interval=1.0):
    last_size = part.stat().st_size if part.exists() else 0
    last_time = time.time()
    while not stop.wait(interval):
        try:
            size = part.stat().st_size
        except FileNotFoundError:
            continue
        now = time.time()
        elapsed = max(now - last_time, 0.001)
        speed = max((size - last_size) / elapsed, 0)
        last_size, last_time = size, now
        if total_bytes:
            pct = min(size / total_bytes * 100, 100.0)
            eta_s = max(total_bytes - size, 0) / speed if speed > 0 else 0
            mins, secs = divmod(int(eta_s), 60)
            eta = f", eta {mins}m{secs:02d}s" if eta_s < 6 * 3600 else ""
            update_progress(name, f"{pct:5.1f}% ({human_size(speed)}/s{eta})")
        else:
            update_progress(name, f"{human_size(size)} @ {human_size(speed)}/s")


def record_failure(manifest, name, reason):
    with manifest_lock:
        manifest.setdefault("failures", {})[name] = {
            "reason": reason,
            "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    print(f"\n [FAIL] {name}: {reason}")


# ---------------------------------------------------------------------------
# Source infrastructure
# ---------------------------------------------------------------------------
@dataclass
class SourceInfo:
    url: str
    filename: str
    checksum_url: str | None = None
    sig_url: str | None = None
    direct_hash: str | None = None
    direct_algo: str | None = None


class BaseSource:
    name = ""
    category = ""
    min_size_mb = 50
    tags: list[str] = []
    # If set, this source cannot be auto-fetched (login wall, CAPTCHA, no stable
    # direct-download host, etc). fetch() records it in the manifest and returns
    # immediately instead of calling discover().
    manual_url: str | None = None

    def discover(self) -> SourceInfo | None:
        raise NotImplementedError

    def verify(self, dest, expected_hash, algo, exact):
        if algo in HASH_FUNCS:
            local_hash, hash_algo = HASH_FUNCS[algo](dest), algo
        else:
            local_hash, hash_algo = sha256_of(dest), "sha256"
        status = "unverified — no upstream checksum available"
        if expected_hash:
            if local_hash.lower() == expected_hash.lower():
                status = "verified" if exact else "verified (best-effort match)"
            else:
                status = "CHECKSUM MISMATCH"
        return local_hash, hash_algo, status

    def fetch(self, dest_dir, manifest, force, downloader):
        if cancel_event.is_set():
            update_progress(self.name, "cancelled")
            return

        if self.manual_url:
            with manifest_lock:
                manifest.setdefault("manual", {})[self.name] = {
                    "url": self.manual_url,
                    "note": "manual download - cannot auto-fetch",
                }
            update_progress(self.name, "manual (see manifest)")
            print(f"\n [MANUAL] {self.name}: download yourself from {self.manual_url}")
            return

        update_progress(self.name, "discovering")
        try:
            info = self.discover()
        except Exception as e:
            record_failure(manifest, self.name, f"discover(): {e}")
            update_progress(self.name, "failed")
            return
        if not info:
            record_failure(manifest, self.name, "could not resolve download URL")
            update_progress(self.name, "failed")
            return
        if cancel_event.is_set():
            update_progress(self.name, "cancelled")
            return

        dest = dest_dir / info.filename
        min_bytes = self.min_size_mb * 1024 * 1024
        need = force or not dest.exists() or looks_bogus(dest, min_bytes)

        if not need:
            update_progress(self.name, "skipped")
        else:
            part = dest.with_name(dest.name + ".part")
            if force and part.exists():
                part.unlink()
            total_bytes = get_remote_size(info.url) or (APPROX_SIZES_MB.get(self.name, 0) * 1024 * 1024) or None
            update_progress(self.name, "downloading   0%")
            stop_poll = threading.Event()
            poller = threading.Thread(target=poll_progress, args=(self.name, part, total_bytes, stop_poll), daemon=True)
            poller.start()
            ok = download_file(info.url, part, downloader, cancel_event)
            stop_poll.set()
            poller.join(timeout=2)
            if not ok:
                if cancel_event.is_set():
                    update_progress(self.name, "cancelled")
                else:
                    record_failure(manifest, self.name, "download failed after retries")
                    update_progress(self.name, "failed")
                return
            if looks_bogus(part, min_bytes):
                part.unlink(missing_ok=True)
                record_failure(manifest, self.name, "downloaded file failed sanity check")
                update_progress(self.name, "failed")
                return
            try:
                part.replace(dest)
            except OSError:
                shutil.move(str(part), str(dest))

        gpg_path = None
        gpg_status = None
        if info.sig_url:
            sig_dest = dest.with_suffix(dest.suffix + ".sig")
            try:
                if not sig_dest.exists() or force:
                    urllib.request.urlretrieve(info.sig_url, sig_dest)
                if sig_dest.exists():
                    gpg_path = str(sig_dest)
                    gpg_status = verify_signature(sig_dest, dest)
            except Exception:
                pass

        expected_hash, algo, exact = info.direct_hash, info.direct_algo, bool(info.direct_hash)
        if not expected_hash and info.checksum_url:
            try:
                sums_text = http_get_text(info.checksum_url)
                expected_hash, algo, exact = detect_checksum_algorithm(sums_text, info.filename)
            except Exception:
                pass

        update_progress(self.name, "verifying")
        local_hash, hash_algo, status = self.verify(dest, expected_hash, algo, exact)
        entry = {
            "file": info.filename,
            "path": str(dest),
            "hash": local_hash,
            "hash_algo": hash_algo,
            "size_mb": round(dest.stat().st_size / (1024 * 1024), 1),
            "downloaded": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
        }
        if gpg_path:
            entry["gpg_signature"] = gpg_path
        if gpg_status:
            entry["gpg_verify"] = gpg_status

        with manifest_lock:
            manifest.setdefault("isos", {})[self.name] = entry
            manifest["failures"].pop(self.name, None)
        print(f"\n [OK] {self.name}: {status}")
        update_progress(self.name, "done")


# ---------------------------------------------------------------------------
# Concrete sources
# ---------------------------------------------------------------------------
class KaliSource(BaseSource):
    name = "Kali Linux"
    category = "distros"
    tags = ["pentest"]

    def discover(self):
        index_url = "https://cdimage.kali.org/current/"
        try:
            html = http_get_text(index_url)
        except Exception:
            return None
        for pat in [r'kali-linux-[\d.]+-live-amd64\.iso\b', r'kali-linux-[\d.]+-installer-amd64\.iso\b']:
            m = re.search(pat, html)
            if m:
                filename = m.group(0)
                url = index_url + filename
                return SourceInfo(url=url, filename=filename,
                                  checksum_url=index_url + "SHA256SUMS",
                                  sig_url=url + ".asc")
        return None


class ParrotSource(BaseSource):
    name = "Parrot OS"
    category = "distros"
    tags = ["pentest"]

    def discover(self):
        # NOTE: v6 pointed at .../iso/stable/, which no longer exists on
        # download.parrot.sh — the live index only has version-numbered dirs
        # (e.g. 7.3/) plus caine/ and latest/. latest/ is the stable pointer.
        base = "https://download.parrot.sh/parrot/iso/latest/"
        try:
            html = http_get_text(base)
        except Exception:
            return None
        m = re.search(r'Parrot-[Ss]ecurity-[\w.\-]+?_amd64\.iso', html)
        if not m:
            m = re.search(r'Parrot-\w+-[\w.\-]+?_amd64\.iso', html)
        if not m:
            return None
        filename = m.group(0)
        return SourceInfo(url=base + filename, filename=filename)


class ArchSource(BaseSource):
    name = "Arch Linux"
    category = "distros"

    def discover(self):
        base = "https://geo.mirror.pkgbuild.com/iso/latest/"
        try:
            html = http_get_text(base)
        except Exception:
            return None
        m = re.search(r'archlinux-[\d.]+-x86_64\.iso\b', html)
        if not m:
            return None
        filename = m.group(0)
        return SourceInfo(url=base + filename, filename=filename,
                          checksum_url=base + "sha256sums.txt",
                          sig_url=base + filename + ".sig")


class UbuntuSource(BaseSource):
    name = "Ubuntu Desktop LTS"
    category = "distros"

    def discover(self):
        base = "https://releases.ubuntu.com/"
        try:
            html = http_get_text(base)
        except Exception:
            return None
        # LTS releases are the .04 versions in even years (20.04, 22.04, 24.04, 26.04, ...)
        year_strs = set(re.findall(r'(\d\d)\.04/', html))
        lts_years = sorted((int(y) for y in year_strs if int(y) % 2 == 0), reverse=True)
        if not lts_years:
            return None
        latest = f"{lts_years[0]:02d}.04"
        rel_url = f"{base}{latest}/"
        try:
            rel_html = http_get_text(rel_url)
        except Exception:
            return None
        m = re.search(rf'ubuntu-{re.escape(latest)}[\d.]*-desktop-amd64\.iso', rel_html)
        if not m:
            return None
        filename = m.group(0)
        return SourceInfo(url=rel_url + filename, filename=filename,
                          checksum_url=rel_url + "SHA256SUMS")


class SystemRescueSource(BaseSource):
    name = "SystemRescue"
    category = "recovery"

    def discover(self):
        url = resolve_sourceforge_rss("systemrescuecd")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class ClonezillaSource(BaseSource):
    name = "Clonezilla"
    category = "recovery"
    tags = ["backup"]

    def discover(self):
        url = resolve_sourceforge_rss("clonezilla")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class GPartedSource(BaseSource):
    name = "GParted Live"
    category = "recovery"
    tags = ["partitioning"]

    def discover(self):
        url = resolve_sourceforge_rss("gparted")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class HirensSource(BaseSource):
    name = "Hiren's BootCD PE"
    category = "recovery"
    tags = ["windows-repair"]
    # No clean, single official direct-download URL exists (the official site
    # hasn't published a stable direct link in years; third-party mirrors bundle
    # ads/other installers). Safer to send the user there manually.
    manual_url = "https://www.hirensbootcd.org/download/"


class CAINESource(BaseSource):
    name = "CAINE"
    category = "distros"
    tags = ["pentest", "forensics"]

    def discover(self):
        page_url = "https://www.caine-live.net/page5/page5.html"
        try:
            html = http_get_text(page_url)
        except Exception:
            return None
        # exclude "nbcaine..." (the netbook edition) via negative lookbehind
        versions = re.findall(r'(?<!nb)caine(\d+\.\d+)\.iso', html, re.IGNORECASE)
        if not versions:
            return None
        best = max(set(versions), key=lambda v: tuple(int(p) for p in v.split(".")))
        filename = f"caine{best}.iso"
        return SourceInfo(
            url=f"https://www.caine-live.net/Downloads/{filename}",
            filename=filename,
            checksum_url=f"https://www.caine-live.net/page5/{filename}.sha256.txt",
        )


class BootRepairDiskSource(BaseSource):
    name = "Boot-Repair-Disk"
    category = "recovery"
    tags = ["boot-repair"]

    def discover(self):
        # SourceForge project slug is "boot-repair-cd", NOT "boot-repair-disk"
        url = resolve_sourceforge_rss("boot-repair-cd")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class RescatuxSource(BaseSource):
    name = "Rescatux"
    category = "recovery"
    tags = ["boot-repair"]

    def discover(self):
        url = resolve_sourceforge_rss("rescatux")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class SuperGrub2Source(BaseSource):
    name = "Super Grub2 Disk"
    category = "recovery"
    tags = ["boot-repair"]
    min_size_mb = 5  # real image is ~20MB — well under the 50MB default floor

    def discover(self):
        url = resolve_sourceforge_rss("supergrub2")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class UBCDSource(BaseSource):
    name = "Ultimate Boot CD"
    category = "recovery"
    tags = ["diagnostics"]

    def discover(self):
        # SourceForge project slug is "ubcd", NOT "ultimatebootcd"
        url = resolve_sourceforge_rss("ubcd")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class DBANSource(BaseSource):
    name = "DBAN"
    category = "wipe"
    tags = ["data-destruction"]
    min_size_mb = 5  # real image is ~17-20MB

    def discover(self):
        url = resolve_sourceforge_rss("dban")
        if not url:
            return None
        return SourceInfo(url=url, filename=url.rsplit("/", 1)[-1])


class ShredOSSource(BaseSource):
    name = "ShredOS"
    category = "wipe"
    tags = ["data-destruction"]
    min_size_mb = 5  # real image is ~30MB

    def discover(self):
        api_url = "https://api.github.com/repos/PartialVolume/shredos.x86_64/releases/latest"
        try:
            data = json.loads(http_get_text(api_url))
        except Exception:
            return None
        assets = data.get("assets", [])
        # Prefer a non-"lite" 64-bit .iso; fall back to any .iso asset.
        best = None
        for asset in assets:
            n = asset.get("name", "")
            if n.lower().endswith(".iso") and "lite" not in n.lower() and (
                "x86-64" in n or "x86_64" in n or "64" in n
            ):
                best = asset
                break
        if best is None:
            for asset in assets:
                if asset.get("name", "").lower().endswith(".iso"):
                    best = asset
                    break
        if best is None:
            return None
        return SourceInfo(url=best["browser_download_url"], filename=best["name"])


ALL_SOURCES: list[BaseSource] = [
    KaliSource(), ParrotSource(), ArchSource(), UbuntuSource(),
    SystemRescueSource(), ClonezillaSource(), GPartedSource(), HirensSource(),
    CAINESource(), BootRepairDiskSource(), RescatuxSource(), SuperGrub2Source(),
    UBCDSource(), DBANSource(), ShredOSSource(),
]


# ---------------------------------------------------------------------------
# Manifest persistence
# ---------------------------------------------------------------------------
def load_manifest(dest_dir: Path) -> dict:
    path = dest_dir / MANIFEST_FILENAME
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
                data.setdefault("isos", {})
                data.setdefault("failures", {})
                data.setdefault("manual", {})
                return data
        except Exception:
            pass
    return {"isos": {}, "failures": {}, "manual": {}}


def save_manifest(dest_dir: Path, manifest: dict):
    path = dest_dir / MANIFEST_FILENAME
    try:
        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"\nWarning: could not save manifest: {e}")


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
def sources_for_role(all_sources: list[BaseSource], role: str) -> list[BaseSource]:
    role = role.lower()
    return [s for s in all_sources
            if role == s.category.lower() or role in (t.lower() for t in s.tags)]


def all_role_names(all_sources: list[BaseSource]) -> list[str]:
    roles = {s.category for s in all_sources} | {t for s in all_sources for t in s.tags}
    return sorted(roles)


# ---------------------------------------------------------------------------
# --list / --dry-run / --verify-only
# ---------------------------------------------------------------------------
def list_sources(all_sources: list[BaseSource]):
    print(f"ventoy_fetch.py v{VERSION} — configured sources:\n")
    by_cat: dict[str, list[BaseSource]] = {}
    for s in all_sources:
        by_cat.setdefault(s.category, []).append(s)
    for cat in sorted(by_cat):
        print(f"[{cat}]")
        for s in by_cat[cat]:
            tags = f"  tags={','.join(s.tags)}" if s.tags else ""
            manual = "  ** manual download – cannot auto-fetch **" if s.manual_url else ""
            size = APPROX_SIZES_MB.get(s.name)
            size_str = f"~{size}MB" if size else "size unknown"
            print(f"  - {s.name:<22} {size_str}{tags}{manual}")
        print()
    print("Available --role values:", ", ".join(all_role_names(all_sources)))


def dry_run(sources: list[BaseSource]):
    print("Dry run — resolving URLs only, nothing will be downloaded.\n")
    for s in sources:
        if s.manual_url:
            print(f"  {s.name:<22} MANUAL   -> {s.manual_url}")
            continue
        try:
            info = s.discover()
        except Exception as e:
            print(f"  {s.name:<22} FAILED   ({e})")
            continue
        if not info:
            print(f"  {s.name:<22} FAILED   (could not resolve URL)")
            continue
        size = get_remote_size(info.url)
        print(f"  {s.name:<22} {info.filename}  ({human_size(size)})")


def verify_only(sources: list[BaseSource], dest_dir: Path):
    print(f"Verifying existing files in {dest_dir} ...\n")
    for s in sources:
        if s.manual_url:
            continue
        try:
            info = s.discover()
        except Exception:
            info = None
        dest = dest_dir / info.filename if info else None
        if not dest or not dest.exists():
            print(f"  {s.name:<22} not on disk")
            continue
        expected_hash, algo, exact = None, None, False
        if info.checksum_url:
            try:
                sums_text = http_get_text(info.checksum_url)
                expected_hash, algo, exact = detect_checksum_algorithm(sums_text, info.filename)
            except Exception:
                pass
        local_hash, hash_algo, status = s.verify(dest, expected_hash, algo, exact)
        print(f"  {s.name:<22} {status}  ({hash_algo}: {local_hash[:16]}...)")


# ---------------------------------------------------------------------------
# --gui  (dialog checklist, falling back to a plain numbered multi-select)
# ---------------------------------------------------------------------------
def gui_dialog_checklist(sources: list[BaseSource]) -> list[str] | None:
    """Try the `dialog` command for a real checkbox UI. Returns a list of
    selected source names, or None if `dialog` isn't installed / failed,
    so the caller can fall back to the text-based selector."""
    if shutil.which("dialog") is None:
        return None
    args = ["dialog", "--backtitle", f"ventoy_fetch v{VERSION}",
            "--separate-output", "--checklist",
            "Select ISOs to fetch (space = toggle, enter = confirm)",
            "22", "78", "14"]
    for src in sources:
        item = src.category + (f" [{'/'.join(src.tags)}]" if src.tags else "")
        if src.manual_url:
            item += " (manual download - cannot auto-fetch)"
        status = "off" if src.manual_url else "on"
        args += [src.name, item, status]
    try:
        result = subprocess.run(args, stderr=subprocess.PIPE, text=True, timeout=180)
    except Exception:
        return None
    finally:
        print("\033[2J\033[H", end="")  # clear the screen dialog drew over
    if result.returncode != 0:
        return []  # user cancelled
    return [line for line in result.stderr.strip().split("\n") if line]


def gui_text_fallback(sources: list[BaseSource]) -> list[str]:
    """Built-in multi-select for environments without `dialog` (e.g. a bare
    Termux install, which doesn't ship it by default)."""
    print(f"\nventoy_fetch v{VERSION} — no `dialog` found, using text checklist:\n")
    for i, s in enumerate(sources, start=1):
        tags = f" [{', '.join(s.tags)}]" if s.tags else ""
        manual = "  (manual download - cannot auto-fetch)" if s.manual_url else ""
        size = APPROX_SIZES_MB.get(s.name)
        size_str = f"~{size}MB" if size else "size unknown"
        print(f"  {i:2d}) {s.name:<22} {s.category}{tags}  {size_str}{manual}")
    print("\nEnter numbers separated by spaces/commas, 'all', or blank to cancel:")
    try:
        raw = input("> ").strip()
    except EOFError:
        return []
    if not raw:
        return []
    if raw.lower() == "all":
        return [s.name for s in sources]
    picked = []
    for tok in re.split(r"[,\s]+", raw):
        if tok.isdigit():
            idx = int(tok)
            if 1 <= idx <= len(sources):
                picked.append(sources[idx - 1].name)
    return picked


def run_gui(sources: list[BaseSource]) -> list[BaseSource]:
    selected_names = gui_dialog_checklist(sources)
    if selected_names is None:
        selected_names = gui_text_fallback(sources)
    return [s for s in sources if s.name in selected_names]


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------
def default_output_dir() -> Path:
    shared = Path.home() / "storage" / "shared" / "Ventoy"
    if (Path.home() / "storage").exists():
        return shared
    return SCRIPT_DIR / "Ventoy-ISOs"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ventoy_fetch.py",
        description=f"Ventoy multi-boot USB ISO fetcher v{VERSION} (Termux-friendly)",
    )
    p.add_argument("--gui", action="store_true",
                    help="interactive checklist to choose ISOs")
    p.add_argument("--role",
                    help="only fetch sources matching this role (e.g. pentest, distros, "
                         "recovery, wipe) — see --list for all values")
    p.add_argument("--list", action="store_true",
                    help="show all sources & configured roles, then exit")
    p.add_argument("--dry-run", action="store_true",
                    help="resolve URLs/sizes, download nothing")
    p.add_argument("--verify-only", action="store_true",
                    help="re-check hashes of files already on disk")
    p.add_argument("--output-dir",
                    help="where to save ISOs (default: config.json, else "
                         "~/storage/shared/Ventoy)")
    p.add_argument("--force", action="store_true",
                    help="re-download even if a valid file already exists")
    p.add_argument("--jobs", type=int,
                    help="concurrent downloads (default: config.json, else 3)")
    p.add_argument("--downloader", choices=["auto", "curl", "aria2"],
                    help="which downloader to use (default: auto-detect aria2c)")
    p.add_argument("--no-wake-lock", action="store_true",
                    help="don't request termux-wake-lock during the run")
    p.add_argument("--no-notify", action="store_true",
                    help="don't send a termux-notification when finished")
    return p


def main():
    args = build_arg_parser().parse_args()
    config = load_config()

    if args.list:
        list_sources(ALL_SOURCES)
        return

    if args.output_dir:
        dest_dir = Path(args.output_dir).expanduser()
    elif config.get("output_dir"):
        dest_dir = Path(config["output_dir"]).expanduser()
    else:
        dest_dir = default_output_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    if args.role:
        sources = sources_for_role(ALL_SOURCES, args.role)
        if not sources:
            print(f"No sources match role '{args.role}'.")
            print("Available roles:", ", ".join(all_role_names(ALL_SOURCES)))
            return
    else:
        sources = list(ALL_SOURCES)

    if args.gui:
        sources = run_gui(sources)
        if not sources:
            print("Nothing selected, exiting.")
            return

    if args.dry_run:
        dry_run(sources)
        return

    if args.verify_only:
        verify_only(sources, dest_dir)
        return

    manual_sources = [s for s in sources if s.manual_url]
    auto_sources = [s for s in sources if not s.manual_url]

    jobs = args.jobs or config.get("jobs", 3)
    downloader = args.downloader or config.get("downloader", "auto")
    use_wake_lock = not args.no_wake_lock and config.get("wake_lock", True)
    use_notify = not args.no_notify and config.get("notify", True)

    ok, reason = termux_battery_ok()
    if not ok:
        print(f"Warning: {reason}. Plug in your device — a long fetch may get interrupted.")

    manifest = load_manifest(dest_dir)

    def handle_sigint(signum, frame):
        print("\nCancelling... (finishing in-flight requests, press Ctrl+C again to force)")
        if cancel_event.is_set():
            raise KeyboardInterrupt
        cancel_event.set()
    old_handler = signal.signal(signal.SIGINT, handle_sigint)

    if use_wake_lock:
        termux_wake_lock()

    global DONE_SIGNAL
    DONE_SIGNAL = False
    reporter = threading.Thread(target=progress_reporter, daemon=True)
    reporter.start()

    try:
        if auto_sources:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
                futures = [pool.submit(s.fetch, dest_dir, manifest, args.force, downloader)
                           for s in auto_sources]
                for fut in concurrent.futures.as_completed(futures):
                    fut.result()  # re-raise any unexpected exception
    finally:
        DONE_SIGNAL = True
        reporter.join(timeout=2)
        if use_wake_lock:
            termux_wake_unlock()
        signal.signal(signal.SIGINT, old_handler)

    for s in manual_sources:
        manifest.setdefault("manual", {})[s.name] = {
            "url": s.manual_url,
            "note": "manual download - cannot auto-fetch",
        }
        print(f"\n [MANUAL] {s.name}: please download yourself from {s.manual_url}")

    save_manifest(dest_dir, manifest)

    n_ok = len(manifest.get("isos", {}))
    n_fail = len(manifest.get("failures", {}))
    n_manual = len(manual_sources)
    summary = f"{n_ok} fetched, {n_fail} failed, {n_manual} manual — see {MANIFEST_FILENAME}"
    print(f"\n\nDone. {summary}")
    if use_notify:
        termux_notify("Ventoy fetch complete", summary)


if __name__ == "__main__":
    main()
