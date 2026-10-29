#!/usr/bin/env python3
"""Short-lived, unprivileged VPN bridge. Credentials stay with NM/the vendor CLI."""
import argparse
from contextlib import contextmanager
import fcntl
import ipaddress
import json
import math
import os
import platform
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
PROTECTION = Path("/run/cyberghost-omarchy.json")
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


def privileged_command(vendor, *, require_api=True):
    launcher = safe_system_binary("/usr/local/cyberghost/omarchy-bridge")
    if vendor != "/usr/local/cyberghost/cyberghostvpn" or not launcher:
        raise BridgeError("GUI authorization requires the reviewed CyberGhost compatibility package. Install it or select a valid OpenVPN profile in Settings.", "dependency")
    if require_api:
        try:
            if run([launcher, "--version"], timeout=3).strip() != "omarchy-bridge 4":
                raise ValueError
        except (BridgeError, ValueError) as exc:
            raise BridgeError("Install the reviewed cyberghostvpn-omarchy package with helper API 4 (legacy cyberghostvpn 1.5.0-7 also works) before changing connections.", "dependency") from exc
    return ["/usr/bin/pkexec", launcher]


def vendor_binary():
    path = safe_vendor_binary()
    if not path:
        raise BridgeError("A trusted system CyberGhost CLI is not installed. Install the reviewed package or select a valid OpenVPN profile in Settings.", "dependency")
    return path


def prerequisites(backend):
    """Local checks only: no authentication, account files or external requests."""
    checks = [{"id": "python", "label": "Python 3.12 or newer",
               "ready": sys.version_info >= (3, 12),
               "message": "Update Python through the normal Arch system update."}]
    if backend == "official-cli":
        checks.append({"id": "architecture", "label": "x86-64 Linux client",
                       "ready": sys.platform == "linux" and platform.machine() == "x86_64",
                       "message": "The reviewed vendor executable supports x86-64 Linux only."})
    tools = ["nmcli"]
    if backend == "official-cli":
        tools += ["ip", "busctl", "curl", "pkexec", "wg", "wg-quick", "nft", "mount", "resolvectl", "openvpn"]
    missing = [name for name in tools if not safe_system_binary("/usr/bin/" + name)]
    checks.append({"id": "tools", "label": "Required system tools", "ready": not missing,
                   "message": "Missing tools: " + ", ".join(missing) if missing else "Available."})
    services = ["NetworkManager"] + (["systemd-resolved"] if backend == "official-cli" else [])
    for service in services:
        try:
            active = run(["/usr/bin/systemctl", "is-active", service], timeout=4).strip() == "active"
        except BridgeError:
            active = False
        checks.append({"id": service, "label": service, "ready": active,
                       "message": "Check this service locally; the plugin does not start or change system services."})
    if backend == "official-cli":
        try:
            compat = bool(safe_system_binary("/usr/bin/resolvectl")) and (
                Path("/usr/bin/resolvconf").resolve(strict=True) == Path("/usr/bin/resolvectl").resolve(strict=True))
        except (OSError, RuntimeError):
            compat = False
        checks.append({"id": "resolvconf", "label": "systemd-resolvconf compatibility", "ready": compat,
                       "message": "Install systemd-resolvconf for WireGuard DNS. Other resolvconf implementations are not supported; review conflicts locally."})
        try:
            privileged_command(vendor_binary())
            adapter_ready, detail = True, "Reviewed adapter available. Account authentication is checked when connecting."
        except BridgeError as exc:
            adapter_ready, detail = False, str(exc)
        checks.append({"id": "adapter", "label": "Reviewed CyberGhost client and adapter",
                       "ready": adapter_ready, "message": detail})
        try:
            stub = Path("/etc/resolv.conf").resolve(strict=True) == Path("/run/systemd/resolve/stub-resolv.conf")
        except (OSError, RuntimeError):
            stub = False
        checks.append({"id": "resolver", "label": "systemd-resolved stub integration", "ready": stub,
                       "message": "Use the documented resolved setup; the plugin does not replace /etc/resolv.conf."})
    return checks


def diagnostics(backend):
    """Shareable allowlist: no vendor execution, account files or network requests."""
    if backend not in BACKENDS:
        raise ValueError("Select a supported backend")
    version = "unknown"
    try:
        value = json.loads(Path(__file__).with_name("manifest.json").read_text()).get("version")
        if isinstance(value, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", value) and len(value) <= 64:
            version = value
    except (OSError, ValueError, AttributeError):
        pass
    packages = {}
    for name in ("omarchy", "quickshell", "networkmanager", "systemd", "cyberghostvpn-omarchy", "cyberghostvpn"):
        packages[name] = None
        try:
            value = run(["/usr/bin/pacman", "-Q", name], timeout=3).strip()
        except BridgeError:
            continue
        match = re.fullmatch(re.escape(name) + r" ([0-9][A-Za-z0-9.+_:~\-]{0,63})", value)
        if match:
            packages[name] = match[1]
    return {"schema": 1, "plugin_version": version,
            "python_version": ".".join(str(n) for n in sys.version_info[:3]),
            "platform": "linux" if sys.platform == "linux" else "unsupported",
            "backend": backend, "packages": packages,
            "prerequisites": [{"id": item["id"], "ready": item["ready"]} for item in prerequisites(backend)]}


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


def traffic_protection():
    try:
        fd = os.open(PROTECTION, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        with os.fdopen(fd) as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
                    or info.st_size > 2048 or os.access(PROTECTION, os.W_OK)):
                raise ValueError
            value = json.load(file)
        if (not isinstance(value, dict) or type(value.get("uid")) is not int
                or not 0 < value["uid"] < 2**32 - 1 or value.get("device") != "cyberghost"
                or type(value.get("kill_switch")) is not bool
                or type(value.get("interface_index")) is not int or value["interface_index"] < 0
                or type(value.get("mark")) is not int or not 0 <= value["mark"] < 2**32
                or value.get("phase") not in ("prepared", "active", "blocked")
                or (value["phase"] == "active" and (value["mark"] == 0 or value["interface_index"] == 0))
                or (value["phase"] == "blocked" and not value["kill_switch"])):
            raise ValueError
        return value
    except (OSError, ValueError, TypeError) as exc:
        raise BridgeError("Traffic-protection state is not trusted. Inspect the reviewed package locally before retrying.", "protection") from exc


def uplink_ready():
    try:
        routes = json.loads(run(["/usr/bin/ip", "-j", "-4", "route", "show", "table", "main", "default"], timeout=8))
        if not isinstance(routes, list) or any(not isinstance(item, dict) for item in routes):
            raise ValueError
        return any(item.get("dev") and item["dev"] != "cyberghost"
                   and item.get("type", "unicast") == "unicast" for item in routes)
    except (ValueError, TypeError) as exc:
        raise BridgeError("The upstream route response was not recognized.", "invalid_response") from exc


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
        protection = traffic_protection()
        if protection:
            if protection["uid"] != os.getuid():
                raise BridgeError("Another user's VPN traffic protection is active.", "conflict")
            result["can_release_protection"] = True
            result["protection_phase"] = protection["phase"]
            if backend != "official-cli":
                raise BridgeError("Official CLI traffic protection is active. Select Official CLI to recover or release its traffic block in Settings.", "conflict")
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
                active = active_connections()
                rows = [row for row in active if row[2:] == ["wireguard", "cyberghost"]]
                if (len(rows) != 1 or not external_connection(rows[0][0])
                        or any(row[2] == "vpn" or (row[2] == "wireguard" and row[3] != "cyberghost") for row in active)):
                    raise BridgeError("A WireGuard device uses the CyberGhost name but is not an identified external client connection. Inspect it locally before using CLI controls.", "conflict")
                result.update(tunnel)
                result.update(saved_details(result))
                if protection:
                    if protection["phase"] == "active" and protection["interface_index"] == result.get("interface_index"):
                        result.update(ipv6_guard=True, kill_switch=protection["kill_switch"])
                        if result["state"] == "unknown":
                            result.update(state="recovery-required",
                                          error="The tunnel has no usable internet route. Disconnect and reconnect, or choose another location.")
                    else:
                        result.update(state="blocked" if protection["phase"] == "blocked" else "recovery-required",
                                      kill_switch=protection["phase"] == "blocked",
                                      ipv6_guard=protection["phase"] == "blocked",
                                      error="Traffic protection needs recovery. Disconnect or release the block in Settings.",
                                      can_connect=False, can_disconnect=True)
                if (result["state"] == "connected" or (result["state"] == "recovery-required"
                        and result.get("ipv6_guard") and protection and protection["phase"] == "active")) and not uplink_ready():
                    result.update(state="waiting-network", warning="Waiting for an upstream network. WireGuard can retry when it returns.")
                    result.pop("error", None)
                try:
                    result["ipv6_disabled"] = Path("/proc/sys/net/ipv6/conf/all/disable_ipv6").read_text().strip() == "1"
                except OSError:
                    result["ipv6_disabled"] = None
                return result
            if any(row[2] in ("vpn", "wireguard") for row in active_connections()):
                raise BridgeError("Another NetworkManager VPN is active. Select its backend or disconnect it deliberately before using CLI controls.", "conflict")
            if protection:
                result.update(state="blocked" if protection["kill_switch"] else "recovery-required",
                              kill_switch=protection["kill_switch"], can_disconnect=True,
                              error="Setup was interrupted before protection was confirmed. Restore normal networking before retrying."
                              if protection["phase"] == "prepared" else
                              "The tunnel is absent. Disconnect to release its traffic protection and restore normal networking.")
                return result
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


def operate(action, country, city, profile, backend="manual-profile", protocol="auto", server="", kill_switch=False):
    if action not in ("connect", "disconnect", "switch", "release-protection") or protocol not in PROTOCOLS:
        raise ValueError("Unsupported VPN operation or protocol")
    if kill_switch and (backend != "official-cli" or protocol != "wireguard"):
        raise ValueError("The kill switch requires the official CLI with WireGuard")
    if action in ("connect", "switch"):
        failed = next((item for item in prerequisites(backend) if not item["ready"]), None)
        if failed:
            raise BridgeError(failed["label"] + ": " + failed["message"], "setup")
    if action == "release-protection":
        if backend != "official-cli":
            raise ValueError("Select Official CLI to release its traffic protection")
        protection = traffic_protection()
        if not protection or protection["uid"] != os.getuid():
            raise BridgeError("No traffic protection owned by this user was identified.", "protection")
        # Release does not execute the vendor; it must remain usable if that
        # binary is missing while the trusted adapter and owned guard remain.
        run(privileged_command("/usr/local/cyberghost/cyberghostvpn") + ["--release-protection"], timeout=30)
        return status(profile, backend)
    if backend == "manual-profile":
        if traffic_protection():
            raise BridgeError("Release Official CLI traffic protection before using another backend.", "conflict")
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
        launcher = privileged_command(vendor, require_api=action != "disconnect")
        if action == "connect" and status(profile, backend)["state"] != "disconnected":
            raise BridgeError("A session or traffic block already exists. Use Switch location, or disconnect and refresh before connecting.", "conflict")
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
            if kill_switch: argv.append("--kill-switch")
            if action == "switch":
                current = status(profile, backend)
                if current.get("can_disconnect"):
                    run(launcher + ["--stop"], timeout=110)
                    if status(profile, backend)["state"] != "disconnected":
                        raise BridgeError("The existing tunnel did not disconnect; the new connection was not started.", "unconfirmed")
                elif current["state"] != "disconnected":
                    raise BridgeError("Cannot identify the current connection. Refresh before switching.", "unconfirmed")
            output = run(argv + ["--connect"], timeout=195)
        else:
            run(launcher + ["--stop"], timeout=110)
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
    if args.action == "diagnostics":
        return {"report": diagnostics(args.backend)}
    validate_profile(args.profile)
    if args.action == "check":
        result = status(args.profile, args.backend)
        checks = prerequisites(args.backend)
        result.update(nmcli=bool(shutil.which("nmcli")), pkexec=Path("/usr/bin/pkexec").is_file(),
                      has_vendor=bool(safe_vendor_binary()), prerequisites=checks,
                      setup_ready=all(item["ready"] for item in checks))
        result["setup_message"] = next((item["label"] + ": " + item["message"]
                                        for item in checks if not item["ready"]), "")
        if not result["setup_ready"]:
            result["can_connect"] = False
        return result
    if args.action == "status":
        return status(args.profile, args.backend)
    if args.action in ("countries", "cities", "servers"):
        return locations(args.action, args.country, args.backend, args.city, getattr(args, "protocol", "auto"))
    if args.action == "ip":
        before = status(args.profile, args.backend)
        if before["state"] != "connected":
            raise BridgeError("Connect first to check your public IP.", "disconnected")
        device = before.get("device", "")
        if not isinstance(device, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", device):
            raise BridgeError("Cannot identify the VPN interface for the IP lookup.", "unconfirmed")
        value = run(["/usr/bin/curl", "--disable", "--ipv4", "--interface", "if!" + device,
                     "--noproxy", "*", "--proto", "=https", "--silent", "--show-error", "--fail",
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
    if args.action == "verify-protection":
        if args.backend != "official-cli":
            raise ValueError("Select Official CLI to verify its traffic protection")
        with operation_lock():
            output = run(privileged_command("/usr/local/cyberghost/cyberghostvpn") + ["--verify-protection"], timeout=30)
        try:
            value = json.loads(output)
            if not isinstance(value, dict) or type(value.get("protection_verified")) is not bool:
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise BridgeError("The protection check returned an invalid response.", "invalid_response") from exc
        return value
    with operation_lock():
        return operate(args.action, args.country, args.city, args.profile, args.backend, getattr(args, "protocol", "auto"), getattr(args, "server", ""), getattr(args, "kill_switch", False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "status", "diagnostics", "countries", "cities", "servers", "connect", "switch", "disconnect", "release-protection", "verify-protection", "ip"])
    parser.add_argument("--country", default="DE")
    parser.add_argument("--city", default="")
    parser.add_argument("--profile", default=PROFILE)
    parser.add_argument("--protocol", choices=PROTOCOLS, default="auto")
    parser.add_argument("--server", default="")
    parser.add_argument("--kill-switch", action="store_true")
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
