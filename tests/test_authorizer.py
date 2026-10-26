import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
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
    def authorized(self, uid="1000"):
        return (
            patch.object(adapter.os, "geteuid", return_value=0),
            patch.dict(adapter.os.environ, {"PKEXEC_UID": uid}, clear=True),
            patch.object(adapter.pwd, "getpwuid", return_value=Account()),
            patch.object(adapter.os, "execve"),
        )

    def test_valid_connect_city_and_stop_exec_only_vendor(self):
        operations = (
            ["--traffic", "--country-code", "DE", "--connect"],
            ["--traffic", "--country-code", "CH", "--city", "Zürich", "--connect"],
            ["--stop"],
        )
        for argv in operations:
            with self.subTest(argv=argv):
                geteuid, environ, getpwuid, execve = self.authorized()
                with geteuid, environ, getpwuid as lookup, execve as execute:
                    adapter.main(argv)
                lookup.assert_called_once_with(1000)
                self.assertEqual(execute.call_args.args[:2],
                                 (adapter.VENDOR, [adapter.VENDOR, *argv]))

    def test_only_sanitized_environment_reaches_vendor_and_no_password_is_read(self):
        unsafe = {"PKEXEC_UID": "1000", "PATH": "/tmp/hostile", "LD_PRELOAD": "/tmp/pwn.so",
                  "SUDO_USER": "attacker", "PASSWORD": "do-not-forward", "CYBERGHOST_PASSWORD": "secret"}
        with patch.object(adapter.os, "geteuid", return_value=0), \
             patch.dict(adapter.os.environ, unsafe, clear=True), \
             patch.object(adapter.pwd, "getpwuid", return_value=Account()), \
             patch.object(adapter.os, "execve") as execute, \
             patch("builtins.open", side_effect=AssertionError("must not read credentials")) as open_file:
            adapter.main(["--traffic", "--country-code", "DE", "--connect"])
        environment = execute.call_args.args[2]
        self.assertEqual(environment, {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                                       "HOME": "/home/alice", "USER": "alice", "LOGNAME": "alice",
                                       "SUDO_USER": "alice"})
        self.assertNotIn("PASSWORD", environment)
        open_file.assert_not_called()

    def test_rejects_unprivileged_root_uid_and_invalid_uid(self):
        for euid, uid in ((1000, "1000"), (0, "0"), (0, ""), (0, "x1000"),
                          (0, "10000000000"), (0, "4294967295"), (0, "4294967296")):
            with self.subTest(euid=euid, uid=uid), \
                 patch.object(adapter.os, "geteuid", return_value=euid), \
                 patch.dict(adapter.os.environ, {"PKEXEC_UID": uid}, clear=True), \
                 patch.object(adapter.pwd, "getpwuid") as lookup, \
                 patch.object(adapter.os, "execve") as execute:
                with self.assertRaises(ValueError):
                    adapter.main(["--stop"])
                lookup.assert_not_called()
                execute.assert_not_called()

    def test_rejects_arbitrary_commands_flags_and_invalid_locations(self):
        invalid = (
            ["--status"], ["/bin/sh", "-c", "id"], ["--setup"], ["--uninstall"],
            ["--traffic", "--country-code", "de", "--connect"],
            ["--traffic", "--country-code", "DE;id", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", "--connect"],
            ["--traffic", "--country-code", "DE", "--city", ";id", "--connect"],
            ["--traffic", "--country-code", "DE", "--config", "/tmp/x", "--connect"],
            ["--stop", "--setup"],
        )
        for argv in invalid:
            with self.subTest(argv=argv), \
                 patch.object(adapter.os, "geteuid", return_value=0), \
                 patch.dict(adapter.os.environ, {"PKEXEC_UID": "1000"}, clear=True), \
                 patch.object(adapter.pwd, "getpwuid") as lookup, \
                 patch.object(adapter.os, "execve") as execute:
                with self.assertRaises(ValueError):
                    adapter.main(argv)
                lookup.assert_not_called()
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
