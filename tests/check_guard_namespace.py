#!/usr/bin/env python3
"""Manual dual-stack guard check, isolated to fresh network namespaces.

Run as root only after reviewing the installed package. This is intentionally
not discovered by unittest; it never changes the host network namespace.
"""
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time


HELPER = "/usr/local/cyberghost/omarchy-bridge"
TABLE = "omarchy_cyberghost"
OTHER_TABLE = "cgqa_unrelated"
IFACE = "cgqa-uplink"
PEER = "cgqa-peer"
V4_LOCAL, V4_SERVER = "198.18.0.1", "198.18.0.2"
V6_LOCAL, V6_SERVER = "2001:db8:77::1", "2001:db8:77::2"
MARK = 51820
PORT = 43789
DNS_PORT = 53
RESOLVER_UID = 65534
NETNS_FLAG = getattr(os, "CLONE_NEWNET", 0x40000000)
COMMAND_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}


def run(argv, *, input_text=None, timeout=5):
    result = subprocess.run(argv, input=input_text, text=True, capture_output=True,
                           timeout=timeout, check=False, env=COMMAND_ENV)
    if result.returncode:
        detail = result.stderr.strip()[:300]
        raise RuntimeError(f"command failed ({argv[0]}): {detail}")
    return result.stdout


def load_guard_script():
    """Load guard policy only from the reviewed fixed installation path."""
    for parent in Path(HELPER).parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError("installed helper has an untrusted parent directory")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(HELPER, flags)
    with os.fdopen(fd) as file:
        info = os.fstat(file.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or not info.st_mode & 0o111 or info.st_size > 100_000):
            raise RuntimeError("installed helper is not a trusted root-owned executable")
        source = file.read()
    namespace = {"__name__": "_reviewed_guard"}
    exec(compile(source, HELPER, "exec"), namespace)
    script = namespace.get("guard_script")
    if not callable(script):
        raise RuntimeError("installed helper has no guard script")
    return script


def unshare_net():
    os.unshare(NETNS_FLAG)


def set_link(ifname, address, family):
    argv = (["/usr/sbin/ip", "addr", "add", address, "dev", ifname] if family == 4 else
            ["/usr/sbin/ip", "-6", "addr", "add", address, "dev", ifname, "nodad"])
    run(argv)


def listen_server(control):
    try:
        run(["/usr/sbin/ip", "link", "set", "lo", "up"])
        run(["/usr/sbin/ip", "link", "set", PEER, "up"])
        set_link(PEER, f"{V4_SERVER}/30", 4)
        set_link(PEER, f"{V6_SERVER}/64", 6)
        servers = []
        for family, address, port in ((socket.AF_INET, V4_SERVER, PORT),
                                      (socket.AF_INET6, V6_SERVER, PORT),
                                      (socket.AF_INET6, V6_SERVER, DNS_PORT)):
            server = socket.socket(family, socket.SOCK_STREAM)
            if family == socket.AF_INET6:
                server.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((address, port))
            server.listen(16)
            server.settimeout(0.2)
            servers.append(server)
        control.sendall(b"ready\n")
        while True:
            for server in servers:
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    return
                conn.close()
    except Exception as exc:
        try:
            control.sendall(("error " + str(exc)[:200] + "\n").encode())
        except OSError:
            pass


def probe(family, address, marked=False, port=PORT):
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(0.7)
    try:
        if marked:
            sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_MARK", 36), MARK)
        sock.connect((address, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def probe_as_uid(uid, family, address, port):
    parent, child = socket.socketpair()
    pid = os.fork()
    if pid == 0:
        parent.close()
        try:
            os.setgroups([])
            os.setgid(uid)
            os.setuid(uid)
            child.sendall(b"1" if probe(family, address, port=port) else b"0")
        except Exception:
            try:
                child.sendall(b"e")
            except OSError:
                pass
        finally:
            child.close()
            os._exit(0)
    child.close()
    try:
        parent.settimeout(3)
        result = parent.recv(1)
    finally:
        parent.close()
        cleanup_child(pid)
    if result not in (b"0", b"1"):
        raise RuntimeError(f"unprivileged UID {uid} probe did not complete")
    return result == b"1"


def expect(label, observed, expected):
    print(f"{label}: {observed} (expected {expected})")
    if observed != expected:
        raise AssertionError(f"{label}: expected {expected}, got {observed}")


def wait_ready(control, child):
    control.settimeout(4)
    message = control.recv(256).decode(errors="replace").strip()
    if message != "isolated":
        raise RuntimeError(f"server namespace setup failed (child {child})")


def cleanup_child(child):
    try:
        os.kill(child, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            waited, _ = os.waitpid(child, os.WNOHANG)
        except ChildProcessError:
            return
        if waited:
            return
        time.sleep(0.05)
    try:
        os.kill(child, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(child, 0)
    except ChildProcessError:
        pass


def main():
    if os.geteuid() != 0:
        raise SystemExit("run this manual harness as root; it does not require host network changes")
    guard_script = load_guard_script()
    if not os.path.exists("/usr/bin/nft") or not os.path.exists("/usr/sbin/ip"):
        raise SystemExit("requires existing /usr/bin/nft and /usr/sbin/ip")

    # Enter a disposable namespace before creating links or changing nftables.
    unshare_net()
    parent_control, child_control = socket.socketpair()
    child = os.fork()
    if child == 0:
        parent_control.close()
        try:
            unshare_net()
            child_control.sendall(b"isolated\n")
            if child_control.recv(16) != b"go\n":
                raise RuntimeError("parent did not authorize server setup")
            listen_server(child_control)
        finally:
            os._exit(0)

    child_control.close()
    nft_guard = False
    nft_other = False
    try:
        wait_ready(parent_control, child)
        run(["/usr/sbin/ip", "link", "add", IFACE, "type", "veth", "peer", "name", PEER])
        set_link(IFACE, f"{V4_LOCAL}/30", 4)
        set_link(IFACE, f"{V6_LOCAL}/64", 6)
        run(["/usr/sbin/ip", "link", "set", IFACE, "up"])
        run(["/usr/sbin/ip", "link", "set", PEER, "netns", str(child)])
        parent_control.sendall(b"go\n")
        parent_control.settimeout(4)
        ready = parent_control.recv(256).decode(errors="replace").strip()
        if ready != "ready":
            raise RuntimeError(f"server setup failed: {ready}")

        expect("unguarded IPv4", probe(socket.AF_INET, V4_SERVER), True)
        expect("unguarded IPv6", probe(socket.AF_INET6, V6_SERVER), True)
        expect("unguarded IPv6 DNS TCP", probe(socket.AF_INET6, V6_SERVER, port=DNS_PORT), True)

        run(["/usr/bin/nft", "-f", "-"], input_text=f"table inet {OTHER_TABLE} {{}}\n")
        nft_other = True
        run(["/usr/bin/nft", "-f", "-"],
            input_text=guard_script(None, False, bootstrap_uid=RESOLVER_UID))
        nft_guard = True
        expect("bootstrap resolver UID IPv6 DNS TCP",
               probe_as_uid(RESOLVER_UID, socket.AF_INET6, V6_SERVER, DNS_PORT), True)
        expect("root IPv6 DNS TCP during bootstrap",
               probe(socket.AF_INET6, V6_SERVER, port=DNS_PORT), False)
        expect("bootstrap resolver UID non-DNS TCP",
               probe_as_uid(RESOLVER_UID, socket.AF_INET6, V6_SERVER, PORT), False)

        run(["/usr/bin/nft", "-f", "-"], input_text=guard_script(MARK, True, replace=True))
        expect("full guard unmarked IPv4", probe(socket.AF_INET, V4_SERVER), False)
        expect("full guard unmarked IPv6", probe(socket.AF_INET6, V6_SERVER), False)
        expect("full guard bootstrap UID IPv6 DNS TCP",
               probe_as_uid(RESOLVER_UID, socket.AF_INET6, V6_SERVER, DNS_PORT), False)
        expect("full guard marked IPv4", probe(socket.AF_INET, V4_SERVER, True), True)
        expect("full guard marked IPv6", probe(socket.AF_INET6, V6_SERVER, True), True)

        run(["/usr/bin/nft", "-f", "-"], input_text=guard_script(MARK, False, replace=True))
        expect("IPv6-only guard IPv4", probe(socket.AF_INET, V4_SERVER), True)
        expect("IPv6-only guard IPv6", probe(socket.AF_INET6, V6_SERVER), False)

        run(["/usr/bin/nft", "delete", "table", "inet", TABLE])
        nft_guard = False
        expect("guard deleted IPv4", probe(socket.AF_INET, V4_SERVER), True)
        expect("guard deleted IPv6", probe(socket.AF_INET6, V6_SERVER), True)
        run(["/usr/bin/nft", "list", "table", "inet", OTHER_TABLE])
        print("unrelated nft table preserved: yes")
    finally:
        if nft_guard:
            subprocess.run(["/usr/bin/nft", "delete", "table", "inet", TABLE],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=3, check=False, env=COMMAND_ENV)
        if nft_other:
            subprocess.run(["/usr/bin/nft", "delete", "table", "inet", OTHER_TABLE],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=3, check=False, env=COMMAND_ENV)
        parent_control.close()
        cleanup_child(child)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
