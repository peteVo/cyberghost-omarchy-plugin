import importlib.util
from importlib.machinery import SourceFileLoader
from contextlib import nullcontext
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SOURCE = Path(__file__).parents[1] / "packaging/cyberghostvpn/omarchy-bridge"
LOADER = SourceFileLoader("omarchy_bridge_test", str(SOURCE))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
adapter = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(adapter)


class Account:
    pw_name = "alice"
    pw_dir = "/home/alice"

    @property
    def pw_passwd(self):
        raise AssertionError("adapter must never inspect a password field")


class AuthorizerTests(unittest.TestCase):
    def authorized(self, uid="1000", result=0):
        return (
            patch.object(adapter.os, "geteuid", return_value=0),
            patch.dict(adapter.os.environ, {"PKEXEC_UID": uid}, clear=True),
            patch.object(adapter.pwd, "getpwuid", return_value=Account()),
            patch.object(adapter, "root_lock", return_value=nullcontext(41)),
            patch.object(adapter, "guard_state", return_value=None),
            patch.object(adapter, "ipv6_namespace"),
            patch.object(adapter, "prepare_guard"),
            patch.object(adapter, "apply_guard"),
            patch.object(adapter, "remove_guard"),
            patch.object(adapter, "vendor", return_value=result),
        )

    def test_valid_operations_run_only_the_fixed_vendor_without_leaking_lock_fd(self):
        operations = (
            ["--traffic", "--country-code", "DE", "--connect"],
            ["--traffic", "--country-code", "CH", "--city", "Zürich", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", "Berlin", "--server",
             "berlin-s1-i2", "--wireguard", "--connect"],
            ["--traffic", "--country-code", "DE", "--wireguard", "--kill-switch", "--connect"],
            ["--traffic", "--country-code", "NL", "--openvpn", "--connect"],
            ["--stop"],
            ["--release-protection"],
        )
        for argv in operations:
            with self.subTest(argv=argv):
                (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
                 remove, vendor) = self.authorized()
                with (geteuid, environ, getpwuid as lookup, lock as root_lock, guard,
                      namespace, prepare, apply, remove, vendor as command):
                    result = adapter.main(argv)
                lookup.assert_called_once_with(1000)
                root_lock.assert_called_once_with()
                if argv == ["--release-protection"]:
                    command.assert_not_called()
                else:
                    expected = [arg for arg in argv if arg != "--kill-switch"]
                    self.assertEqual(command.call_args.args[0], expected)
                    self.assertEqual(command.call_args.args[1]["HOME"], "/home/alice")
                self.assertEqual(result, 0)

    def test_vendor_wrapper_uses_fixed_binary_and_closes_inherited_descriptors(self):
        environment = {"PATH": "/usr/bin:/bin", "HOME": "/home/alice"}
        with patch.object(adapter.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as command:
            result = adapter.vendor(["--stop"], environment)
        self.assertEqual(result, 0)
        self.assertEqual(command.call_args.args[0], [adapter.VENDOR, "--stop"])
        self.assertEqual(command.call_args.kwargs["env"], environment)
        self.assertEqual(command.call_args.kwargs["timeout"], 45)
        self.assertEqual(command.call_args.kwargs["stdin"], adapter.subprocess.DEVNULL)
        self.assertTrue(command.call_args.kwargs["close_fds"])
        self.assertNotIn("pass_fds", command.call_args.kwargs)

    def test_version_is_public_and_does_not_require_authorization(self):
        result = subprocess.run(
            [sys.executable, "-I", str(SOURCE), "--version"],
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            capture_output=True, text=True, timeout=3, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "omarchy-bridge 2\n")

    def test_guard_metadata_is_unprotected_until_nft_commit_succeeds(self):
        link = SimpleNamespace(
            returncode=0,
            stdout='[{"ifname":"cyberghost","ifindex":7,"linkinfo":{"info_kind":"wireguard"}}]',
        )
        fwmark = SimpleNamespace(returncode=0, stdout="0x2a\n")
        value = {"uid": 1000, "device": "cyberghost", "interface_index": 7,
                 "mark": 42, "kill_switch": True, "phase": "prepared"}

        failed_records = []
        with patch.object(adapter, "command", side_effect=[link, fwmark]), \
             patch.object(adapter, "guard_state", return_value=None), \
             patch.object(adapter, "guard_exists", return_value=False), \
             patch.object(adapter, "write_guard", side_effect=lambda record: failed_records.append(dict(record))), \
             patch.object(adapter.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as nft:
            with self.assertRaises(RuntimeError):
                adapter.apply_guard(1000, True)
        self.assertEqual(failed_records, [{**value, "kill_switch": False}])
        self.assertEqual(nft.call_args.args[0], ["/usr/bin/nft", "--file", "-"])

        active_records = []
        with patch.object(adapter, "command", side_effect=[link, fwmark]), \
             patch.object(adapter, "guard_state", return_value=None), \
             patch.object(adapter, "guard_exists", return_value=False), \
             patch.object(adapter, "guard_fingerprint", return_value="a" * 64), \
             patch.object(adapter, "write_guard", side_effect=lambda record: active_records.append(dict(record))), \
             patch.object(adapter.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
            adapter.apply_guard(1000, True)
        self.assertEqual(active_records, [
            {**value, "kill_switch": False},
            {**value, "phase": "active", "fingerprint": "a" * 64},
        ])

    def test_verify_protection_requires_matching_firewall_and_tunnel_state(self):
        protection = {"uid": 1000, "device": "cyberghost", "interface_index": 7,
                      "mark": 42, "kill_switch": False, "phase": "active",
                      "fingerprint": "a" * 64}
        cases = ((None, None, False),
                 ({**protection, "fingerprint": None}, "a" * 64, False),
                 (protection, "b" * 64, False),
                 (protection, "a" * 64, True))
        for state, fingerprint, tunnel_matches in cases:
            with self.subTest(state=state, fingerprint=fingerprint, tunnel=tunnel_matches):
                (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
                 remove, vendor) = self.authorized()
                output = []
                with (geteuid, environ, getpwuid, lock,
                      patch.object(adapter, "guard_state", return_value=state),
                      patch.object(adapter, "guard_fingerprint", return_value=fingerprint) as inspect,
                      patch.object(adapter, "wireguard_details",
                                   return_value=(7, 42) if tunnel_matches else (8, 42)) as tunnel,
                      patch("builtins.print", side_effect=lambda value: output.append(value))):
                    result = adapter.main(["--verify-protection"])
                self.assertEqual(result, 0)
                self.assertEqual(json.loads(output[0]), {"protection_verified": tunnel_matches})
                if state is None or not state.get("fingerprint") or fingerprint != state["fingerprint"]:
                    tunnel.assert_not_called()
                else:
                    tunnel.assert_called_once_with()
                if state is None:
                    inspect.assert_not_called()

    def test_guard_fingerprint_rejects_malformed_nft_json(self):
        malformed = ("not json", "[]", '{"nftables": []}',
                     '{"nftables": [{"table": {"name": "another_table"}}]}',
                     '{"nftables": [null]}',
                     '{"nftables": [{"table": {"name": "omarchy_cyberghost"}}, {"nonsense": true}]}',
                     '{"nftables": [{"table": {"name": "omarchy_cyberghost"}}, {"rule": []}]}')
        for payload in malformed:
            with self.subTest(payload=payload), \
                 patch.object(adapter, "command", return_value=SimpleNamespace(returncode=0, stdout=payload)):
                with self.assertRaises((ValueError, TypeError)):
                    adapter.guard_fingerprint()

    def test_only_sanitized_environment_reaches_vendor(self):
        unsafe = {"PKEXEC_UID": "1000", "PATH": "/tmp/hostile", "LD_PRELOAD": "/tmp/pwn.so",
                  "SUDO_USER": "attacker", "PASSWORD": "do-not-forward", "CYBERGHOST_PASSWORD": "secret"}
        with patch.object(adapter.os, "geteuid", return_value=0), \
             patch.dict(adapter.os.environ, unsafe, clear=True), \
             patch.object(adapter.pwd, "getpwuid", return_value=Account()), \
             patch.object(adapter, "root_lock", return_value=nullcontext(41)), \
             patch.object(adapter, "guard_state", return_value=None), \
             patch.object(adapter, "ipv6_namespace"), \
             patch.object(adapter, "vendor", return_value=0) as command, \
             patch("builtins.open", side_effect=AssertionError("must not read credentials")) as open_file:
            adapter.main(["--traffic", "--country-code", "DE", "--connect"])
        self.assertEqual(command.call_args.args[1], {
            "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
            "HOME": "/home/alice", "USER": "alice", "LOGNAME": "alice", "SUDO_USER": "alice",
        })
        self.assertNotIn("PASSWORD", command.call_args.args[1])
        open_file.assert_not_called()

    def test_rejects_unprivileged_root_uid_and_invalid_uid(self):
        for euid, uid in ((1000, "1000"), (0, "0"), (0, ""), (0, "x1000"),
                          (0, "10000000000"), (0, "4294967295"), (0, "4294967296")):
            with self.subTest(euid=euid, uid=uid), \
                 patch.object(adapter.os, "geteuid", return_value=euid), \
                 patch.dict(adapter.os.environ, {"PKEXEC_UID": uid}, clear=True), \
                 patch.object(adapter.pwd, "getpwuid") as lookup, \
                 patch.object(adapter, "root_lock") as lock, \
                 patch.object(adapter, "vendor") as command:
                with self.assertRaises(ValueError):
                    adapter.main(["--stop"])
                lookup.assert_not_called()
                lock.assert_not_called()
                command.assert_not_called()

    def test_rejects_invalid_command_grammar_before_authorizing(self):
        invalid = (
            ["--status"], ["/bin/sh", "-c", "id"], ["--setup"], ["--uninstall"],
            ["--traffic", "--country-code", "de", "--connect"],
            ["--traffic", "--country-code", "DE;id", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", ";id", "--connect"],
            ["--traffic", "--country-code", "DE", "--server", "berlin-s1-i1", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", "Berlin", "--server", "bad/server", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", "Berlin", "--server", "berlin-s1-i1",
             "--server", "berlin-s2-i2", "--connect"],
            ["--traffic", "--country-code", "DE", "--wireguard", "--openvpn", "--connect"],
            ["--traffic", "--country-code", "DE", "--openvpn", "--city", "Berlin", "--connect"],
            ["--traffic", "--country-code", "DE", "--openvpn", "--kill-switch", "--connect"],
            ["--traffic", "--country-code", "DE", "--kill-switch", "--wireguard", "--connect"],
            ["--traffic", "--country-code", "DE", "--wireguard", "--kill-switch", "--openvpn", "--connect"],
            ["--release-protection", "--stop"],
            ["--stop", "--setup"],
        )
        for argv in invalid:
            with self.subTest(argv=argv), \
                 patch.object(adapter.os, "geteuid", return_value=0), \
                 patch.dict(adapter.os.environ, {"PKEXEC_UID": "1000"}, clear=True), \
                 patch.object(adapter.pwd, "getpwuid") as lookup, \
                 patch.object(adapter, "root_lock") as lock, \
                 patch.object(adapter, "vendor") as command:
                with self.assertRaises(ValueError):
                    adapter.main(argv)
                lookup.assert_not_called()
                lock.assert_not_called()
                command.assert_not_called()

    def test_root_lock_uses_a_root_owned_private_nofollow_file(self):
        fd = 41
        opened = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0)
        with patch.object(adapter.os, "open", return_value=fd) as open_file, \
             patch.object(adapter.os, "fstat", return_value=opened), \
             patch.object(adapter.fcntl, "flock") as flock, \
             patch.object(adapter.os, "close") as close:
            with adapter.root_lock() as locked_fd:
                self.assertEqual(locked_fd, fd)
            open_file.assert_called_once_with(
                "/run/cyberghost-omarchy.lock",
                adapter.os.O_RDWR | adapter.os.O_CREAT | adapter.os.O_NOFOLLOW | adapter.os.O_CLOEXEC,
                0o600,
            )
            flock.assert_called_once_with(fd, adapter.fcntl.LOCK_EX | adapter.fcntl.LOCK_NB)
            close.assert_called_once_with(fd)

    def test_root_lock_rejects_unsafe_file_and_always_closes_fd(self):
        fd = 41
        unsafe_files = (
            SimpleNamespace(st_mode=stat.S_IFREG | 0o666, st_uid=0),
            SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=1000),
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0),
        )
        for info in unsafe_files:
            with self.subTest(info=info), \
                 patch.object(adapter.os, "open", return_value=fd), \
                 patch.object(adapter.os, "fstat", return_value=info), \
                 patch.object(adapter.fcntl, "flock") as flock, \
                 patch.object(adapter.os, "close") as close:
                with self.assertRaises(ValueError):
                    with adapter.root_lock():
                        pass
                flock.assert_not_called()
                close.assert_called_once_with(fd)

    def test_busy_lock_and_timeout_return_distinct_exit_codes(self):
        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with geteuid, environ, getpwuid, \
             patch.object(adapter, "root_lock", side_effect=BlockingIOError), \
             patch.object(adapter, "vendor") as command:
            self.assertEqual(adapter.main(["--stop"]), 75)
        command.assert_not_called()

        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply, remove,
              patch.object(adapter, "vendor", side_effect=subprocess.TimeoutExpired(adapter.VENDOR, 45)) as command):
            self.assertEqual(adapter.main(["--stop"]), 124)
        command.assert_called_once_with(["--stop"], {
            "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
            "HOME": "/home/alice", "USER": "alice", "LOGNAME": "alice", "SUDO_USER": "alice",
        })

    def test_guard_state_rejects_malformed_or_unowned_metadata(self):
        valid = {"uid": 1000, "device": "cyberghost", "interface_index": 7,
                 "mark": 42, "kill_switch": False, "phase": "active"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guard.json"
            cases = ("{", json.dumps({**valid, "mark": 0}),
                     json.dumps({**valid, "kill_switch": 1}),
                     json.dumps({**valid, "phase": "unknown"}))
            with patch.object(adapter, "GUARD", path):
                for payload in cases:
                    with self.subTest(payload=payload):
                        path.write_text(payload)
                        path.chmod(0o644)
                        owned = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0,
                                                 st_size=path.stat().st_size)
                        with patch.object(adapter.os, "fstat", return_value=owned):
                            with self.assertRaises(ValueError):
                                adapter.guard_state()

                path.write_text(json.dumps(valid))
                path.chmod(0o644)
                not_root_owned = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=1000,
                                                 st_size=path.stat().st_size)
                with patch.object(adapter.os, "fstat", return_value=not_root_owned):
                    with self.assertRaises(ValueError):
                        adapter.guard_state()

    def test_guard_owned_by_another_uid_blocks_all_vendor_work(self):
        protection = {"uid": 2000, "device": "cyberghost", "interface_index": 7,
                      "mark": 42, "kill_switch": True, "phase": "active"}
        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with (geteuid, environ, getpwuid, lock, patch.object(adapter, "guard_state", return_value=protection),
              namespace as isolate, vendor as call_vendor):
            with self.assertRaises(ValueError):
                adapter.main(["--stop"])
        isolate.assert_not_called()
        call_vendor.assert_not_called()

    def test_ipv6_namespace_isolates_only_via_mocked_mount_commands(self):
        with patch.object(adapter.os, "unshare") as unshare, \
             patch.object(adapter, "command", return_value=SimpleNamespace(returncode=0)) as command:
            adapter.ipv6_namespace()
        unshare.assert_called_once_with(adapter.os.CLONE_NEWNS)
        self.assertEqual([item.args[0] for item in command.call_args_list], [
            ["/usr/bin/mount", "--make-rprivate", "/"],
            ["/usr/bin/mount", "--bind", "/proc/sys/net/ipv6/conf", "/proc/sys/net/ipv6/conf"],
            ["/usr/bin/mount", "-o", "remount,bind,ro", "/proc/sys/net/ipv6/conf"],
        ])
        with patch.object(adapter.os, "unshare"), \
             patch.object(adapter, "command", side_effect=[
                 SimpleNamespace(returncode=0), SimpleNamespace(returncode=1),
             ]):
            with self.assertRaises(RuntimeError):
                adapter.ipv6_namespace()

    def test_kill_switch_command_is_removed_before_vendor_and_guard_is_applied(self):
        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with (geteuid, environ, getpwuid, lock, guard, namespace as isolate,
              prepare as install, apply as activate, remove,
              vendor as call_vendor):
            result = adapter.main(["--traffic", "--country-code", "DE", "--wireguard",
                                   "--kill-switch", "--connect"])
        self.assertEqual(result, 0)
        isolate.assert_called_once_with()
        install.assert_called_once_with(1000)
        activate.assert_called_once_with(1000, True)
        self.assertEqual(call_vendor.call_args.args[0],
                         ["--traffic", "--country-code", "DE", "--wireguard", "--connect"])

    def test_kill_switch_rollback_reblocks_even_if_vendor_stop_fails(self):
        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with (geteuid, environ, getpwuid, lock, guard, namespace as isolate,
              prepare as install, apply as activate, remove as release,
              patch.object(adapter, "vendor", side_effect=[1, 1]) as call_vendor):
            result = adapter.main(["--traffic", "--country-code", "DE", "--wireguard",
                                   "--kill-switch", "--connect"])
        self.assertEqual(result, 1)
        self.assertEqual(call_vendor.call_args_list[0].args[0],
                         ["--traffic", "--country-code", "DE", "--wireguard", "--connect"])
        self.assertEqual(call_vendor.call_args_list[1].args[0], ["--stop"])
        install.assert_has_calls([unittest.mock.call(1000), unittest.mock.call(1000, blocked=True)])
        activate.assert_not_called()
        release.assert_not_called()

    def test_guard_script_rejects_injected_marks_and_emits_kill_switch_policy(self):
        for mark in (0, -1, 2**32, "0x2a; accept", True):
            with self.subTest(mark=mark), self.assertRaises(ValueError):
                adapter.guard_script(mark, True)
        with self.assertRaises(ValueError):
            adapter.guard_script(None, 1)
        script = adapter.guard_script(None, True)
        self.assertIn('oifname "cyberghost" accept', script)
        self.assertIn("meta nfproto { ipv4, ipv6 } reject", script)
        self.assertNotIn("0x2a; accept", script)

    def test_stop_inspection_failure_keeps_protection_metadata(self):
        protection = {"uid": 1000, "device": "cyberghost", "interface_index": 7,
                      "mark": 42, "kill_switch": False, "phase": "active"}
        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with (geteuid, environ, getpwuid, lock,
              patch.object(adapter, "guard_state", return_value=protection),
              patch.object(adapter, "ipv6_namespace") as isolate,
              patch.object(adapter, "tunnel_absent", side_effect=RuntimeError("probe failed")) as inspect,
              patch.object(adapter, "remove_guard") as release,
              patch.object(adapter, "vendor", return_value=0) as run_vendor):
            with self.assertRaises(RuntimeError):
                adapter.main(["--stop"])
        isolate.assert_called_once_with()
        run_vendor.assert_called_once_with(["--stop"], {
            "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
            "HOME": "/home/alice", "USER": "alice", "LOGNAME": "alice", "SUDO_USER": "alice",
        })
        inspect.assert_called_once_with()
        release.assert_not_called()

    def test_rollback_inspection_failure_does_not_release_guard(self):
        (geteuid, environ, getpwuid, lock, guard, namespace, prepare, apply,
         remove, vendor) = self.authorized()
        with (geteuid, environ, getpwuid, lock, guard, namespace, prepare as install,
              apply, patch.object(adapter, "tunnel_absent", side_effect=RuntimeError("probe failed")),
              patch.object(adapter, "remove_guard") as release,
              patch.object(adapter, "vendor", side_effect=[1, 0]) as run_vendor):
            result = adapter.main(["--traffic", "--country-code", "DE", "--wireguard", "--connect"])
        self.assertEqual(result, 1)
        self.assertEqual([item.args[0] for item in run_vendor.call_args_list], [
            ["--traffic", "--country-code", "DE", "--wireguard", "--connect"], ["--stop"],
        ])
        install.assert_called_once_with(1000)
        release.assert_not_called()


if __name__ == "__main__":
    unittest.main()
