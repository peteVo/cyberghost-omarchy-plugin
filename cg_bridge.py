#!/usr/bin/env python3
"""Short-lived, unprivileged VPN bridge. Credentials stay with NM/the vendor CLI."""
import argparse
from contextlib import contextmanager
import fcntl
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

PROFILE = "cyberghost"
BACKENDS = ("manual-profile", "official-cli")
PROTOCOLS = ("auto", "wireguard", "openvpn")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
CODE_RE = re.compile(r"[A-Z]{2}")
SERVER_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
NAME_RE = re.compile(r"[^\W\d_][\w .()'’-]{0,63}", re.UNICODE)
COUNTRY_RE = re.compile(r"\s*(?:\d+[.)]?\s+)?([A-Za-z][A-Za-z .()&'-]{1,60}?)\s+([A-Z]{2})\s*")
CITY_RE = re.compile(r"\s*\d+[.)]?\s+([^\W\d_][\w .()'’-]{0,63})\s*", re.UNICODE)


class BridgeError(RuntimeError):
    def __init__(self, message, code="operation_failed"):
        super().__init__(message)
        self.code = code


def run(argv, timeout=25):
    try:
        cp = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, errors="replace", timeout=timeout, check=False,
                            env={**os.environ, "LC_ALL": "C", "NO_COLOR": "1"})
    except subprocess.TimeoutExpired as exc:
        raise BridgeError("VPN command timed out. Refresh status before retrying; a privileged operation may still be finishing.", "timeout") from exc
    except OSError as exc:
        raise BridgeError(f"Cannot run {Path(argv[0]).name}; check that it is installed.", "dependency") from exc
    if cp.returncode:
        if argv[0] == "/usr/bin/pkexec" and cp.returncode in (75, 124):
            raise BridgeError("Another privileged VPN operation is running; refresh before retrying." if cp.returncode == 75
                              else "The privileged VPN operation timed out; refresh status before retrying.",
                              "busy" if cp.returncode == 75 else "timeout")
        # Classify locally; never expose raw vendor output or account details.
        reply = (cp.stdout + cp.stderr).lower()
        if any(term in reply for term in ("authentication failed", "auth_failed", "invalid credentials", "login required", "not logged in",
                                         "no valid vpn secrets", "secrets were required", "no agents were available", "no secrets were provided")):
            raise BridgeError("Authentication failed. Sign in using the official client or your NetworkManager secret agent in a local terminal.", "authentication")
        if "config file" in reply and "does not exist" in reply:
            raise BridgeError("CyberGhost setup is incomplete. Run its official setup in a local terminal; never enter account credentials in this panel.", "authentication")
        if argv[0] == "/usr/bin/pkexec" and cp.returncode in (126, 127):
            raise BridgeError("Authorization was cancelled or denied. Retry when you can approve the system prompt.", "authorization")
        raise BridgeError(f"{Path(argv[0]).name} failed (exit {cp.returncode}). Check local client logs, then refresh status.")
    if len(cp.stdout) > 100_000:
        raise BridgeError("The client returned an unexpectedly large response.", "invalid_response")
    return cp.stdout


def safe_system_binary(candidate):
    # Resolve symlinks, but trust neither a writable target nor its parents.
    try:
        source = Path(candidate)
        path = source.resolve(strict=True)
        if path.name != source.name or not path.is_file() or not os.access(path, os.X_OK):
            return None
        for part in (source, *source.parents, path, *path.parents):
            info = part.stat()
            if info.st_uid != 0 or info.st_mode & 0o022 or os.access(part, os.W_OK):
                return None
        return str(path)
    except (OSError, RuntimeError):
        return None


def safe_vendor_binary():
    # Ignore PATH: only conventional system installations may receive privilege.
    return (safe_system_binary("/usr/bin/cyberghostvpn")
            or safe_system_binary("/usr/local/bin/cyberghostvpn"))


def privileged_command(vendor):
    launcher = safe_system_binary("/usr/local/cyberghost/omarchy-bridge")
    if vendor != "/usr/local/cyberghost/cyberghostvpn" or not launcher:
        raise BridgeError("GUI authorization requires the reviewed CyberGhost compatibility package. Use the existing OpenVPN profile meanwhile.", "dependency")
    return ["/usr/bin/pkexec", launcher]


def vendor_binary():
    path = safe_vendor_binary()
    if not path:
        raise BridgeError("A trusted system CyberGhost CLI is not installed. Use the existing OpenVPN profile.", "dependency")
    return path


def parse_countries(output):
    found = {}
    for row in output.splitlines():
        match = COUNTRY_RE.fullmatch(row.replace("|", " "))
        if match:
            name, code = match.groups()
            found[code] = name.strip()
    return [{"code": code, "name": name} for code, name in sorted(found.items(), key=lambda item: item[1])]


def location_rows(output):
    for row in output.splitlines():
        parts = [part.strip() for part in row.strip().strip("|").split("|")]
        if len(parts) == 4 and parts[0].isascii() and parts[0].isdigit():
            yield parts


def parse_cities(output):
    found = {parts[1] for parts in location_rows(output) if NAME_RE.fullmatch(parts[1]) and parts[2].isdigit()}
    # Older CLI lists have no table columns; keep the existing strict format.
    for row in output.splitlines():
        match = CITY_RE.fullmatch(row.strip())
        if match:
            found.add(match[1].strip())
    return sorted(found)


def parse_servers(output):
    found = {}
    for _, city, name, load in location_rows(output):
        if not NAME_RE.fullmatch(city) or not SERVER_RE.fullmatch(name):
            continue
        percent = int(load[:-1]) if re.fullmatch(r"[0-9]{1,3}%", load) else None
        found[name] = {"name": name, "city": city, "load": percent if percent is not None and percent <= 100 else None}
    return [found[name] for name in sorted(found)]


def validate_code(value):
    if not CODE_RE.fullmatch(value):
        raise ValueError("Country must be a two-letter uppercase code")
    return value


def validate_name(value):
    if not NAME_RE.fullmatch(value):
        raise ValueError("City must be a name of at most 64 characters")
    return value


def validate_profile(value):
    if not value or len(value) > 128 or value.startswith("-") or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Profile must be a nonempty name of at most 128 characters, without control characters")
    return value


def nm_rows(output):
    rows = []
    for line in output.splitlines():
        fields, value, escaped = [], "", False
        for char in line:
            if escaped:
                value += char
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == ":":
                fields.append(value)
                value = ""
            else:
                value += char
        if escaped:
            raise BridgeError("NetworkManager returned an invalid escaped field.", "invalid_response")
        rows.append(fields + [value])
    return rows


def profile_info(profile):
    validate_profile(profile)
    rows = nm_rows(run(["/usr/bin/nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"], timeout=8))
    matches = [row for row in rows if len(row) == 3 and row[0] == profile and row[2] == "vpn"]
    if len(matches) != 1:
        raise BridgeError("The profile is missing or its name is ambiguous. Select one existing OpenVPN profile.", "profile")
    _, uuid, kind = matches[0]
    if kind != "vpn" or not UUID_RE.fullmatch(uuid):
        raise BridgeError("The selected profile is not a VPN. Wi-Fi and other connections cannot be controlled here.", "profile")
    service = run(["/usr/bin/nmcli", "-g", "vpn.service-type", "connection", "show", "uuid", uuid], timeout=8).strip()
    if service != "org.freedesktop.NetworkManager.openvpn":
        raise BridgeError("The fallback requires an existing NetworkManager OpenVPN profile.", "profile")
    return uuid


def active_connections():
    rows = nm_rows(run(["/usr/bin/nmcli", "-t", "-f", "UUID,STATE,TYPE,DEVICE", "connection", "show", "--active"], timeout=8))
    if any(len(row) != 4 or not UUID_RE.fullmatch(row[0]) for row in rows):
        raise BridgeError("NetworkManager returned an unrecognized active connection list.", "invalid_response")
    return rows


def external_connection(uuid):
    path = run(["/usr/bin/nmcli", "-g", "GENERAL.DBUS-PATH", "connection", "show", "--active", "uuid", uuid], timeout=8).strip()
    if not re.fullmatch(r"/org/freedesktop/NetworkManager/ActiveConnection/[0-9]+", path):
        raise BridgeError("Cannot identify the active WireGuard connection.", "invalid_response")
    value = run(["/usr/bin/busctl", "get-property", "org.freedesktop.NetworkManager", path,
                 "org.freedesktop.NetworkManager.Connection.Active", "StateFlags"], timeout=8).strip()
    match = re.fullmatch(r"u ([0-9]+)", value)
    if not match:
        raise BridgeError("Cannot identify the WireGuard connection origin.", "invalid_response")
    # NM_ACTIVATION_STATE_FLAG_EXTERNAL, from the installed libnm API.
    return bool(int(match[1]) & 0x80)


def kernel_tunnel_status(protocol):
    try:
        links = json.loads(run(["/usr/bin/ip", "-j", "-d", "link", "show"], timeout=8))
        if not isinstance(links, list) or any(not isinstance(item, dict) for item in links):
            raise ValueError
        kinds = ("wireguard",) if protocol == "WireGuard" else ("tun", "ovpn")
        tunnels = [item for item in links if item.get("linkinfo", {}).get("info_kind") in kinds
                   and (protocol != "WireGuard" or item.get("ifname") == "cyberghost")]
        if not tunnels:
            return None
        if any(not isinstance(item.get("flags", []), list) for item in tunnels):
            raise ValueError
        routes = json.loads(run(["/usr/bin/ip", "-j", "route", "get", "1.1.1.1"], timeout=8))
        if not isinstance(routes, list) or any(not isinstance(item, dict) for item in routes):
            raise ValueError
    except (ValueError, AttributeError, TypeError) as exc:
        raise BridgeError("The kernel returned an unrecognized tunnel or route response.", "invalid_response") from exc
    routed = next((item for item in tunnels if "UP" in item.get("flags", [])
                   and any(route.get("dev") == item.get("ifname") for route in routes)), None)
    tunnel = routed or tunnels[0]
    return {"state": "connected" if routed else "unknown", "protocol": protocol,
            "device": tunnel.get("ifname", ""), "interface_index": tunnel.get("ifindex"),
            "can_connect": False, "can_disconnect": True, "verified": False,
            "evidence": "Tunnel interface and IPv4 route" if routed else "Tunnel exists without the expected IPv4 route",
            **({} if routed else {"error": "The tunnel exists, but its internet route is not active. Disconnect or refresh."})}


def wireguard_status():
    # The tested vendor 1.5.0 --status does not detect its own WireGuard tunnel.
    return kernel_tunnel_status("WireGuard")


def state_file():
    root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "petevo-cyberghost"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise BridgeError("Connection details require a private user-owned state directory.", "state")
    return root / "connection.json"


def saved_details(snapshot):
    try:
        path = state_file()
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 4096:
            return {}
        saved = json.loads(path.read_text())
        if not isinstance(saved, dict): return {}
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if (snapshot.get("state") != "connected" or saved.get("boot_id") != boot
                or not snapshot.get("interface_index") or saved.get("interface_index") != snapshot["interface_index"]
                or saved.get("device") != snapshot.get("device") or saved.get("protocol") != snapshot.get("protocol")):
            return {}
        started = saved.get("started")
        if not isinstance(started, (int, float)) or not math.isfinite(started) or not 0 <= started <= time.monotonic():
            return {}
        validate_code(saved["country"])
        if saved.get("city"): validate_name(saved["city"])
        server = saved.get("server", "")
        if server and not SERVER_RE.fullmatch(server): return {}
        return {"country": saved["country"], "city": saved.get("city", ""),
                "location": saved["country"] + (" · " + saved["city"] if saved.get("city") else ""),
                "location_source": "requested", "server": server, "server_source": saved.get("server_source", "requested"),
                "duration": max(0, int(time.monotonic() - float(saved["started"])))}
    except (OSError, ValueError, KeyError, TypeError, BridgeError):
        return {}


def save_details(snapshot, country, city, server, output, known_servers=()):
    candidates = set(re.findall(r"\b[a-z][a-z0-9-]*-s[0-9]+-i[0-9]+\b", output)) & set(known_servers)
    reported = next(iter(candidates)) if len(candidates) == 1 else ""
    record = {"country": country, "city": city, "server": reported or server,
              "server_source": "client" if reported else "requested", "device": snapshot.get("device"),
              "interface_index": snapshot.get("interface_index"), "protocol": snapshot.get("protocol"),
              "started": time.monotonic(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    path = state_file()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".connection-", delete=False) as file:
            temporary = Path(file.name)
            json.dump(record, file)
        os.replace(temporary, path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)



def status(profile, backend="manual-profile"):
    result = {"backend": backend, "state": "unknown", "profile": profile,
              "location": "", "server": "", "protocol": "", "device": "",
              "verified": False, "can_connect": False, "can_disconnect": False}
    try:
        if backend == "manual-profile":
            uuid = profile_info(profile)
            active = active_connections()
            rows = [row for row in active if row[0] == uuid and row[2] == "vpn"]
            result["protocol"] = "OpenVPN"
            if rows:
                result["state"] = {"activated": "connected", "activating": "connecting", "deactivating": "disconnecting"}.get(rows[0][1], "unknown")
                result["device"] = rows[0][3]
                result["can_disconnect"] = True
            else:
                result["state"] = "disconnected"
                others = any(row[0] != uuid and row[2] in ("vpn", "wireguard") for row in active)
                result["can_connect"] = not others
                if others:
                    result.update(other_vpn_active=True, code="conflict",
                                  error="Another VPN is active. Select its backend or disconnect it before using this profile.")
        else:
            vendor = vendor_binary()
            tunnel = wireguard_status()
            if tunnel:
                rows = [row for row in active_connections() if row[2:] == ["wireguard", "cyberghost"]]
                if len(rows) != 1 or not external_connection(rows[0][0]):
                    raise BridgeError("A WireGuard device uses the CyberGhost name but is not an identified external client connection. Inspect it locally before using CLI controls.", "conflict")
                result.update(tunnel)
                result.update(saved_details(result))
                try:
                    result["ipv6_disabled"] = Path("/proc/sys/net/ipv6/conf/all/disable_ipv6").read_text().strip() == "1"
                except OSError:
                    result["ipv6_disabled"] = None
                return result
            if any(row[2] in ("vpn", "wireguard") for row in active_connections()):
                raise BridgeError("Another NetworkManager VPN is active. Select its backend or disconnect it deliberately before using CLI controls.", "conflict")
            output = run([vendor, "--status"], timeout=8).strip().lower()
            if re.search(r"\bnot connected\b|\bdisconnected\b|\bno vpn connection", output):
                result.update(state="disconnected", can_connect=True)
            elif re.search(r"\bconnecting\b", output):
                result["state"] = "connecting"
            elif re.search(r"(?m)^\s*(?:vpn )?(?:connected|connection established|connection found)[.!]?\s*$", output):
                tunnel = kernel_tunnel_status("OpenVPN")
                if not tunnel:
                    raise BridgeError("The client reports OpenVPN, but no kernel tunnel was found. Refresh before retrying.", "unconfirmed")
                result.update(tunnel)
            else:
                raise BridgeError("The CLI status was not recognized. Inspect it locally before retrying.", "invalid_response")
    except BridgeError as exc:
        result.update(error=str(exc), code=exc.code)
    if backend == "official-cli":
        result.update(saved_details(result))
    try:
        result["ipv6_disabled"] = Path("/proc/sys/net/ipv6/conf/all/disable_ipv6").read_text().strip() == "1"
    except OSError:
        result["ipv6_disabled"] = None
    return result


def locations(kind, country="", backend="manual-profile", city="", protocol="auto"):
    if backend != "official-cli":
        return {"items": [], "reason": "Locations are fixed by your imported OpenVPN profile. Dynamic switching requires a verified official CLI setup."}
    vendor = vendor_binary()
    argv = [vendor, "--traffic", "--country-code"]
    if kind in ("cities", "servers"):
        argv.append(validate_code(country))
    if kind == "servers":
        argv += ["--city", validate_name(city)]
    if protocol not in PROTOCOLS:
        raise ValueError("Select a supported VPN protocol")
    if protocol != "auto":
        argv.append("--" + protocol)
    parser = {"countries": parse_countries, "cities": parse_cities, "servers": parse_servers}[kind]
    items = parser(run(argv))
    return {"items": items, "reason": "" if items else "No locations recognized. Inspect the official CLI locally; no locations will be guessed."}


def operate(action, country, city, profile, backend="manual-profile", protocol="auto", server=""):
    if action not in ("connect", "disconnect", "switch") or protocol not in PROTOCOLS:
        raise ValueError("Unsupported VPN operation or protocol")
    if backend == "manual-profile":
        if action == "switch":
            raise ValueError("Location switching requires the official CLI backend")
        uuid = profile_info(profile)
        rows = active_connections()
        if action == "connect" and any(row[0] != uuid and row[2] in ("vpn", "wireguard") for row in rows):
            raise BridgeError("Another NetworkManager VPN is active. Disconnect it deliberately before connecting here.", "conflict")
        active = any(row[0] == uuid and row[2] == "vpn" for row in rows)
        if action == "connect" and not active:
            run(["/usr/bin/nmcli", "--wait", "55", "connection", "up", "uuid", uuid], timeout=65)
        elif action == "disconnect" and active:
            run(["/usr/bin/nmcli", "--wait", "20", "connection", "down", "uuid", uuid], timeout=30)
    else:
        rows = active_connections()
        detected = wireguard_status() if any(row[2] == "wireguard" and row[3] == "cyberghost" for row in rows) else None
        if any(row[2] == "vpn" or (row[2] == "wireguard" and not (detected and row[3] == "cyberghost" and external_connection(row[0]))) for row in rows):
            raise BridgeError("Disconnect the other NetworkManager VPN before using the official CLI. Its stop command can affect other VPNs.", "conflict")
        vendor = vendor_binary()
        launcher = privileged_command(vendor)
        output = ""
        known_servers = set()
        if action in ("connect", "switch"):
            validate_code(country)
            if country not in {item["code"] for item in locations("countries", backend=backend, protocol=protocol)["items"]}:
                raise ValueError("Select a country returned by the official CLI")
            argv = launcher + ["--traffic", "--country-code", country]
            if city:
                validate_name(city)
                if city not in locations("cities", country, backend, protocol=protocol)["items"]:
                    raise ValueError("Select a city returned by the official CLI")
                argv += ["--city", city]
                known_servers = {item["name"] for item in locations("servers", country, backend, city, protocol)["items"]}
            if server:
                if not city or not SERVER_RE.fullmatch(server):
                    raise ValueError("Select a valid server within a discovered city")
                if server not in known_servers:
                    raise ValueError("Select a server returned by the official CLI")
                argv += ["--server", server]
            if protocol != "auto": argv.append("--" + protocol)
            if action == "switch":
                current = status(profile, backend)
                if current.get("can_disconnect"):
                    run(launcher + ["--stop"], timeout=60)
                    if status(profile, backend)["state"] != "disconnected":
                        raise BridgeError("The existing tunnel did not disconnect; the new connection was not started.", "unconfirmed")
                elif current["state"] != "disconnected":
                    raise BridgeError("Cannot identify the current connection. Refresh before switching.", "unconfirmed")
            output = run(argv + ["--connect"], timeout=150)
        else:
            run(launcher + ["--stop"], timeout=60)
    result = status(profile, backend)
    expected = "disconnected" if action == "disconnect" else "connected"
    if result["state"] != expected:
        raise BridgeError("The command finished, but the requested VPN state was not confirmed. Refresh status and inspect the client locally.", "unconfirmed")
    if backend == "official-cli":
        try:
            if action == "disconnect": state_file().unlink(missing_ok=True)
            else:
                save_details(result, country, city, server, output, known_servers)
                result.update(saved_details(result))
        except (OSError, BridgeError):
            result["warning"] = "Connection changed successfully, but its display details could not be saved."
    return result


@contextmanager
def operation_lock():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    info = runtime.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise BridgeError("VPN operations require a private, user-owned XDG_RUNTIME_DIR.", "runtime")
    fd = os.open(runtime / "petevo-cyberghost.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise BridgeError("The VPN operation lock is not a private regular file.", "runtime")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BridgeError("Another VPN operation is running. Wait, then refresh status.", "busy") from exc
        yield
    finally:
        os.close(fd)


def dispatch(args):
    validate_profile(args.profile)
    if args.action == "check":
        result = status(args.profile, args.backend)
        result.update(nmcli=bool(shutil.which("nmcli")), pkexec=Path("/usr/bin/pkexec").is_file(),
                      has_vendor=bool(safe_vendor_binary()))
        return result
    if args.action == "status":
        return status(args.profile, args.backend)
    if args.action in ("countries", "cities", "servers"):
        return locations(args.action, args.country, args.backend, args.city, getattr(args, "protocol", "auto"))
    if args.action == "ip":
        before = status(args.profile, args.backend)
        if before["state"] != "connected":
            raise BridgeError("Connect first to check your public IP.", "disconnected")
        value = run(["/usr/bin/curl", "--ipv4", "--noproxy", "*", "--proto", "=https", "--silent", "--show-error", "--fail",
                     "--connect-timeout", "3", "--max-time", "6", "--max-filesize", "64", "https://api.ipify.org"], timeout=8).strip()
        try:
            parsed = ipaddress.IPv4Address(value)
            if not parsed.is_global:
                raise ValueError
            address = str(parsed)
        except ValueError as exc:
            raise BridgeError("The IP service did not return a public IPv4 address.", "invalid_response") from exc
        after = status(args.profile, args.backend)
        if after["state"] != "connected" or any(before.get(key) != after.get(key) for key in ("device", "interface_index")):
            raise BridgeError("Connection changed during the IP lookup. Refresh and retry.", "unconfirmed")
        return {"ip": address}
    with operation_lock():
        return operate(args.action, args.country, args.city, args.profile, args.backend, getattr(args, "protocol", "auto"), getattr(args, "server", ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "status", "countries", "cities", "servers", "connect", "switch", "disconnect", "ip"])
    parser.add_argument("--country", default="DE")
    parser.add_argument("--city", default="")
    parser.add_argument("--profile", default=PROFILE)
    parser.add_argument("--protocol", choices=PROTOCOLS, default="auto")
    parser.add_argument("--server", default="")
    parser.add_argument("--backend", choices=BACKENDS, default="manual-profile")
    args = parser.parse_args()
    try:
        result = dispatch(args)
    except (RuntimeError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "code": getattr(exc, "code", "invalid_input")}))
        return 1
    print(json.dumps({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
