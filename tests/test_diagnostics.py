import importlib.util
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "cg_bridge_diagnostics", Path(__file__).parents[1] / "cg_bridge.py"
)
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


PACKAGES = ("omarchy", "quickshell", "networkmanager", "systemd",
            "cyberghostvpn-omarchy", "cyberghostvpn")


class DiagnosticsTests(unittest.TestCase):
    def test_report_has_fixed_schema_and_sanitized_prerequisites(self):
        checks = [{"id": "python", "ready": True, "label": "secret label", "message": "/private/raw error"}]

        def package(argv, timeout):
            name = argv[-1]
            return name + " 1.2.3-1\n"

        with patch.object(b, "run", side_effect=package), \
             patch.object(b, "prerequisites", return_value=checks), \
             patch.object(Path, "read_text", return_value='{"version":"2.3.4-beta1"}'):
            report = b.diagnostics("manual-profile")

        self.assertEqual(set(report), {"schema", "plugin_version", "python_version", "platform", "backend", "packages", "prerequisites"})
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["plugin_version"], "2.3.4-beta1")
        self.assertEqual(report["backend"], "manual-profile")
        self.assertEqual(set(report["packages"]), set(PACKAGES))
        self.assertEqual(report["prerequisites"], [{"id": "python", "ready": True}])
        serialized = json.dumps(report)
        for forbidden in ("secret label", "raw error", "/private", "vendor", "status", "ip", "private-profile-name", "account", "uid"):
            self.assertNotIn(forbidden, serialized.lower())

    def test_unexpected_package_versions_are_discarded_and_missing_pacman_is_null(self):
        def package(argv, timeout):
            name = argv[-1]
            if name == "omarchy":
                return "omarchy 1.2.3\nextra private output\n"
            if name == "quickshell":
                return "quickshell 1.2.3;echo-leak\n"
            raise b.BridgeError("pacman failed with raw path /private/account")

        with patch.object(b, "run", side_effect=package), \
             patch.object(b, "prerequisites", return_value=[]), \
             patch.object(Path, "read_text", side_effect=OSError):
            report = b.diagnostics("manual-profile")
        self.assertEqual(report["plugin_version"], "unknown")
        self.assertIsNone(report["packages"]["omarchy"])
        self.assertIsNone(report["packages"]["quickshell"])
        self.assertTrue(all(report["packages"][name] is None for name in PACKAGES[2:]))

    def test_manual_report_needs_no_vendor_and_only_queries_fixed_package_names(self):
        calls = []

        def package(argv, timeout):
            calls.append(argv)
            raise b.BridgeError("not installed")

        with patch.object(b, "run", side_effect=package), \
             patch.object(b, "prerequisites", return_value=[]), \
             patch.object(b, "vendor_binary", side_effect=AssertionError("vendor lookup")), \
             patch.object(b, "status", side_effect=AssertionError("status lookup")):
            report = b.diagnostics("manual-profile")
        self.assertEqual([call[-1] for call in calls], list(PACKAGES))
        self.assertTrue(all(call[:2] == ["/usr/bin/pacman", "-Q"] for call in calls))
        self.assertEqual(report["backend"], "manual-profile")

    def test_official_report_uses_only_local_probes_and_helper_version(self):
        calls = []

        def local_command(argv, timeout):
            calls.append(argv)
            if argv[0] == "/usr/bin/systemctl":
                return "active\n"
            if argv[-1] == "--version":
                return "omarchy-bridge 4\n"
            raise b.BridgeError("package is absent")

        def resolve(path, strict=False):
            targets = {
                "/usr/bin/resolvconf": "/usr/bin/resolvectl",
                "/usr/bin/resolvectl": "/usr/bin/resolvectl",
                "/etc/resolv.conf": "/run/systemd/resolve/stub-resolv.conf",
            }
            return Path(targets[str(path)])

        with patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "safe_system_binary", side_effect=lambda path: path), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "run", side_effect=local_command), \
             patch.object(Path, "resolve", autospec=True, side_effect=resolve), \
             patch.object(Path, "read_text", return_value='{"version":"2.3.4"}'):
            report = b.diagnostics("official-cli")

        helper_checks = [argv for argv in calls if argv[-1:] == ["--version"]]
        self.assertEqual(helper_checks, [["/usr/local/cyberghost/omarchy-bridge", "--version"]])
        self.assertEqual([argv[-1] for argv in calls if argv[0] == "/usr/bin/pacman"], list(PACKAGES))
        self.assertTrue(all(argv[0] not in ("curl", "/usr/bin/curl") for argv in calls))
        self.assertTrue(all(argv[0] != "/usr/local/cyberghost/cyberghostvpn" for argv in calls))
        self.assertEqual(report["backend"], "official-cli")

    def test_dispatch_routes_diagnostics_without_validating_or_resolving_profile(self):
        args = SimpleNamespace(action="diagnostics", backend="manual-profile", profile="invalid\nprofile")
        expected = {"schema": 1}
        with patch.object(b, "diagnostics", return_value=expected) as diagnostics, \
             patch.object(b, "validate_profile", side_effect=AssertionError("profile validated")), \
             patch.object(b, "status", side_effect=AssertionError("status read")):
            result = b.dispatch(args)
        diagnostics.assert_called_once_with("manual-profile")
        self.assertEqual(result, {"report": expected})


if __name__ == "__main__":
    unittest.main()
