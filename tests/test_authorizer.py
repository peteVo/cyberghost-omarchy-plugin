import importlib.util
from importlib.machinery import SourceFileLoader
from contextlib import nullcontext
from pathlib import Path
import stat
import subprocess
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
            patch.object(adapter.subprocess, "run", return_value=SimpleNamespace(returncode=result)),
        )

    def test_valid_operations_run_only_the_fixed_vendor_without_leaking_lock_fd(self):
        operations = (
            ["--traffic", "--country-code", "DE", "--connect"],
            ["--traffic", "--country-code", "CH", "--city", "Zürich", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", "Berlin", "--server",
             "berlin-s1-i2", "--wireguard", "--connect"],
            ["--traffic", "--country-code", "NL", "--openvpn", "--connect"],
            ["--stop"],
        )
        for argv in operations:
            with self.subTest(argv=argv):
                geteuid, environ, getpwuid, lock, run = self.authorized()
                with geteuid, environ, getpwuid as lookup, lock as root_lock, run as command:
                    result = adapter.main(argv)
                lookup.assert_called_once_with(1000)
                root_lock.assert_called_once_with()
                self.assertEqual(command.call_args.args[0], [adapter.VENDOR, *argv])
                self.assertTrue(command.call_args.kwargs["close_fds"])
                self.assertNotIn("pass_fds", command.call_args.kwargs)
                self.assertEqual(command.call_args.kwargs["stdin"], adapter.subprocess.DEVNULL)
                self.assertEqual(result, 0)

    def test_only_sanitized_environment_reaches_vendor(self):
        unsafe = {"PKEXEC_UID": "1000", "PATH": "/tmp/hostile", "LD_PRELOAD": "/tmp/pwn.so",
                  "SUDO_USER": "attacker", "PASSWORD": "do-not-forward", "CYBERGHOST_PASSWORD": "secret"}
        with patch.object(adapter.os, "geteuid", return_value=0), \
             patch.dict(adapter.os.environ, unsafe, clear=True), \
             patch.object(adapter.pwd, "getpwuid", return_value=Account()), \
             patch.object(adapter, "root_lock", return_value=nullcontext(41)), \
             patch.object(adapter.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as command, \
             patch("builtins.open", side_effect=AssertionError("must not read credentials")) as open_file:
            adapter.main(["--traffic", "--country-code", "DE", "--connect"])
        self.assertEqual(command.call_args.kwargs["env"], {
            "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
            "HOME": "/home/alice", "USER": "alice", "LOGNAME": "alice", "SUDO_USER": "alice",
        })
        self.assertNotIn("PASSWORD", command.call_args.kwargs["env"])
        open_file.assert_not_called()

    def test_rejects_unprivileged_root_uid_and_invalid_uid(self):
        for euid, uid in ((1000, "1000"), (0, "0"), (0, ""), (0, "x1000"),
                          (0, "10000000000"), (0, "4294967295"), (0, "4294967296")):
            with self.subTest(euid=euid, uid=uid), \
                 patch.object(adapter.os, "geteuid", return_value=euid), \
                 patch.dict(adapter.os.environ, {"PKEXEC_UID": uid}, clear=True), \
                 patch.object(adapter.pwd, "getpwuid") as lookup, \
                 patch.object(adapter, "root_lock") as lock, \
                 patch.object(adapter.subprocess, "run") as command:
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
            ["--stop", "--setup"],
        )
        for argv in invalid:
            with self.subTest(argv=argv), \
                 patch.object(adapter.os, "geteuid", return_value=0), \
                 patch.dict(adapter.os.environ, {"PKEXEC_UID": "1000"}, clear=True), \
                 patch.object(adapter.pwd, "getpwuid") as lookup, \
                 patch.object(adapter, "root_lock") as lock, \
                 patch.object(adapter.subprocess, "run") as command:
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
        geteuid, environ, getpwuid, lock, run = self.authorized()
        with geteuid, environ, getpwuid, \
             patch.object(adapter, "root_lock", side_effect=BlockingIOError), \
             patch.object(adapter.subprocess, "run") as command:
            self.assertEqual(adapter.main(["--stop"]), 75)
        command.assert_not_called()

        geteuid, environ, getpwuid, lock, run = self.authorized()
        with geteuid, environ, getpwuid, lock, \
             patch.object(adapter.subprocess, "run", side_effect=subprocess.TimeoutExpired(adapter.VENDOR, 45)) as command:
            self.assertEqual(adapter.main(["--stop"]), 124)
        self.assertEqual(command.call_args.kwargs["timeout"], 45)


if __name__ == "__main__":
    unittest.main()
