#!/usr/bin/env python3
"""Conservative CyberGhost official-CLI / NetworkManager bridge. No provider API or secrets."""
import argparse
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

PROFILE = "openvpn"
COUNTRY_RE = re.compile(r"^\s*(?:\d+[.)]?\s+)?(?P<name>[A-Za-z][A-Za-z .()&-]{1,60}?)\s+(?P<code>[A-Z]{2})\s*$")
CITY_RE = re.compile(r"^\s*(?:\d+[.)]?\s+)?(?P<city>[A-Za-z][A-Za-z .()&-]{1,64})\s*$")
CODE_RE = re.compile(r"^[A-Z]{2}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .-]{0,63}$")


def run(argv, timeout=25):
    try:
        cp = subprocess.run(
            argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            errors="replace", timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Command unavailable or timed out: {argv[0]}") from exc
    if cp.returncode:
        # Never return raw stderr: vendor output might include account details.
        raise RuntimeError(f"Operation failed (exit {cp.returncode}); check official CLI or NetworkManager logs locally")
    return cp.stdout[:100_000]


def safe_vendor_binary():
    candidate = shutil.which("cyberghostvpn")
    if not candidate:
        return None
    path = Path(candidate)
    if path.is_symlink() or not path.is_absolute():
        return None
    # A user-writable binary or parent must never be passed to pkexec.
    try:
        for part in (path, *path.parents):
            info = part.stat()
            if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                return None
    except OSError:
        return None
    return str(path)


def parse_countries(output):
    found = {}
    for row in output.splitlines():
        match = COUNTRY_RE.fullmatch(row.replace("|", " "))
        if match:
            found[match["code"]] = match["name"].strip()
    return [{"code": code, "name": name} for code, name in sorted(found.items(), key=lambda t: t[1])]


def parse_cities(output):
    cities = set()
    for row in output.splitlines():
        if not re.match(r"^\s*\d+[.)]?\s+", row):
            continue
        match = CITY_RE.fullmatch(row.replace("|", " "))
        if match:
            city = match["city"].strip()
            if not city.isupper() and len(city) >= 2:
                cities.add(city)
    return sorted(cities)


def validate_code(value):
    if not CODE_RE.fullmatch(value):
        raise ValueError("Country must be a two-letter code")
    return value


def validate_name(value):
    if not NAME_RE.fullmatch(value):
        raise ValueError("Name must contain letters, spaces, dots or hyphens (max 64 characters)")
    return value


def backend():
    return "official-cli" if safe_vendor_binary() else "manual-profile"


def active_profiles():
    output = run(["/usr/bin/nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"], timeout=8)
    return {line[:-4] for line in output.splitlines() if line.endswith(":vpn")}


def status(profile):
    nm_available = bool(shutil.which("nmcli"))
    active = active_profiles() if nm_available else set()
    if backend() == "manual-profile":
        state = "unknown" if not nm_available else ("connected" if profile in active else "disconnected")
        return {"backend": "manual-profile", "state": state, "profile": profile,
                "location": "", "server": "", "verified": False}
    try:
        output = run([safe_vendor_binary(), "--status"], timeout=8).lower()
    except RuntimeError:
        state = "unknown"
    else:
        if re.search(r"\bnot connected\b|\bdisconnected\b|\bno vpn connection", output):
            state = "disconnected"
        elif re.search(r"\bconnected\b|\bconnection established\b", output):
            state = "connected"
        else:
            state = "unknown"
    return {"backend": "official-cli", "state": state, "profile": profile,
            "location": "", "server": "", "verified": False}


def locations(kind, country=""):
    vendor = safe_vendor_binary()
    if not vendor:
        return {"items": [], "reason": "Dynamic discovery requires the official CyberGhost Linux CLI, unsupported on Arch/Omarchy."}
    if kind == "countries":
        items = parse_countries(run([vendor, "--traffic", "--country-code"]))
        return {"items": items, "reason": "" if items else "The CLI's country list was not recognized."}
    validate_code(country)
    items = parse_cities(run([vendor, "--traffic", "--country-code", country]))
    return {"items": items, "reason": "" if items else "No city list recognized; city may be entered manually if supported by CLI."}


def operate(action, country, city, profile):
    vendor = safe_vendor_binary()
    if vendor and action == "connect":
        validate_code(country)
        argv = ["/usr/bin/pkexec", vendor, "--traffic", "--country-code", country]
        if city:
            argv += ["--city", validate_name(city)]
        run(argv + ["--connect"], timeout=120)
    elif vendor and action == "disconnect":
        run(["/usr/bin/pkexec", vendor, "--stop"], timeout=60)
    else:
        validate_name(profile)
        if action == "connect":
            run(["/usr/bin/nmcli", "connection", "up", "id", profile], timeout=60)
        elif profile in active_profiles():
            run(["/usr/bin/nmcli", "connection", "down", "id", profile], timeout=45)
    return status(profile)


def dispatch(args):
    validate_name(args.profile)
    if args.action == "check":
        available = bool(shutil.which("nmcli"))
        return {"backend": backend(), "nmcli": available,
                "pkexec": bool(shutil.which("pkexec")), "has_vendor": bool(safe_vendor_binary()),
                "has_profile": args.profile in run(["/usr/bin/nmcli", "-g", "NAME", "connection", "show"], timeout=8).splitlines() if available else False}
    if args.action == "status":
        return status(args.profile)
    if args.action in ("countries", "cities"):
        return locations(args.action, args.country)
    if args.action == "ip":
        if status(args.profile)["state"] != "connected":
            raise RuntimeError("Connect first to check your public IP")
        value = run(["/usr/bin/curl", "--ipv4", "--silent", "--show-error", "--fail",
                     "--connect-timeout", "3", "--max-time", "6", "https://api.ipify.org"], timeout=8).strip()
        import ipaddress
        return {"ip": str(ipaddress.IPv4Address(value))}
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    if not runtime.is_dir() or runtime.stat().st_uid != os.getuid():
        raise RuntimeError("A private XDG_RUNTIME_DIR is required for VPN operations")
    fd = os.open(runtime / "petevo-cyberghost.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError("Another VPN operation is already running") from exc
    try:
        return operate(args.action, args.country, args.city, args.profile)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["check", "status", "countries", "cities", "connect", "disconnect", "ip"])
    parser.add_argument("--country", default="DE")
    parser.add_argument("--city", default="")
    parser.add_argument("--profile", default=PROFILE)
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, **dispatch(args)}))
    except (RuntimeError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
