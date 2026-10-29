import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "cg_bridge_preflight", Path(__file__).parents[1] / "cg_bridge.py"
)
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class PrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.tools = patch.object(b, "safe_system_binary", side_effect=lambda path: path)
        self.tools.start()
        self.addCleanup(self.tools.stop)
        self.run = patch.object(b, "run", return_value="active\n")
        self.run.start()
        self.addCleanup(self.run.stop)

    def ready_official(self):
        def resolve(path, strict=False):
            return {
                "/usr/bin/resolvconf": Path("/usr/bin/resolvectl"),
                "/usr/bin/resolvectl": Path("/usr/bin/resolvectl"),
                "/etc/resolv.conf": Path("/run/systemd/resolve/stub-resolv.conf"),
            }[str(path)]

        return (patch.object(b.sys, "version_info", (3, 12, 0)),
                patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"),
                patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/mock/adapter"]),
                patch.object(Path, "resolve", autospec=True, side_effect=resolve))

    def test_complete_official_cli_prerequisites_are_ready(self):
        patches = self.ready_official()
        with patches[0], patches[1], patches[2], patches[3]:
            checks = b.prerequisites("official-cli")
        self.assertTrue(all(item["ready"] for item in checks), checks)
        self.assertEqual({item["id"] for item in checks},
                         {"python", "architecture", "tools", "NetworkManager", "systemd-resolved", "resolvconf", "adapter", "resolver"})

    def test_unsupported_vendor_architecture_blocks_before_network_operations(self):
        patches = self.ready_official()
        with patches[0], patches[1], patches[2], patches[3], \
             patch.object(b.platform, "machine", return_value="aarch64"), \
             patch.object(b, "active_connections") as active:
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("connect", "DE", "", "cyberghost", "official-cli", "wireguard")
        self.assertEqual(caught.exception.code, "setup")
        self.assertIn("x86-64", str(caught.exception))
        active.assert_not_called()

    def test_missing_adapter_version_is_a_failed_prerequisite(self):
        with patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "safe_system_binary", return_value="/usr/local/cyberghost/omarchy-bridge"), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "run", return_value="omarchy-bridge 2\n"), \
             patch.object(Path, "resolve", autospec=True, side_effect=lambda path, strict=False: {
                 "/usr/bin/resolvconf": Path("/usr/bin/resolvectl"),
                 "/usr/bin/resolvectl": Path("/usr/bin/resolvectl"),
                 "/etc/resolv.conf": Path("/run/systemd/resolve/stub-resolv.conf"),
             }[str(path)]):
            adapter = next(item for item in b.prerequisites("official-cli") if item["id"] == "adapter")
        self.assertFalse(adapter["ready"])
        self.assertIn("1.5.0-7", adapter["message"])

    def test_service_command_failure_marks_service_unready(self):
        def service_result(argv, timeout):
            if argv[-1] == "systemd-resolved":
                raise b.BridgeError("not active")
            return "active\n"

        with patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/mock/adapter"]), \
             patch.object(b, "run", side_effect=service_result), \
             patch.object(Path, "resolve", autospec=True, side_effect=lambda path, strict=False: {
                 "/usr/bin/resolvconf": Path("/usr/bin/resolvectl"),
                 "/usr/bin/resolvectl": Path("/usr/bin/resolvectl"),
                 "/etc/resolv.conf": Path("/run/systemd/resolve/stub-resolv.conf"),
             }[str(path)]):
            checks = b.prerequisites("official-cli")
        resolved = next(item for item in checks if item["id"] == "systemd-resolved")
        self.assertFalse(resolved["ready"])

    def test_missing_required_tool_is_reported(self):
        def safe_binary(path):
            return None if path.endswith("/wg-quick") else path

        with patch.object(b, "safe_system_binary", side_effect=safe_binary), \
             patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/mock/adapter"]), \
             patch.object(Path, "resolve", return_value=Path("/run/systemd/resolve/stub-resolv.conf")):
            tools = next(item for item in b.prerequisites("official-cli") if item["id"] == "tools")
        self.assertFalse(tools["ready"])
        self.assertIn("wg-quick", tools["message"])

    def test_wrong_resolver_stub_is_unready(self):
        with patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/mock/adapter"]), \
             patch.object(Path, "resolve", autospec=True, side_effect=lambda path, strict=False: {
                 "/usr/bin/resolvconf": Path("/usr/bin/resolvconf"),
                 "/usr/bin/resolvectl": Path("/usr/bin/resolvectl"),
                 "/etc/resolv.conf": Path("/run/resolv.conf"),
             }[str(path)]):
            resolver = next(item for item in b.prerequisites("official-cli") if item["id"] == "resolver")
        self.assertFalse(resolver["ready"])

    def test_missing_resolvconf_alias_is_unready(self):
        with patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/mock/adapter"]), \
             patch.object(Path, "resolve", autospec=True, side_effect=lambda path, strict=False: {
                 "/usr/bin/resolvconf": (_ for _ in ()).throw(FileNotFoundError()),
                 "/usr/bin/resolvectl": Path("/usr/bin/resolvectl"),
                 "/etc/resolv.conf": Path("/run/systemd/resolve/stub-resolv.conf"),
             }[str(path)]):
            compat = next(item for item in b.prerequisites("official-cli") if item["id"] == "resolvconf")
        self.assertFalse(compat["ready"])

    def test_openvpn_is_a_required_official_cli_tool(self):
        with patch.object(b, "safe_system_binary", side_effect=lambda path: None if path.endswith("/openvpn") else path), \
             patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/mock/adapter"]), \
             patch.object(Path, "resolve", autospec=True, side_effect=lambda path, strict=False: {
                 "/usr/bin/resolvconf": Path("/usr/bin/resolvectl"),
                 "/usr/bin/resolvectl": Path("/usr/bin/resolvectl"),
                 "/etc/resolv.conf": Path("/run/systemd/resolve/stub-resolv.conf"),
             }[str(path)]):
            tools = next(item for item in b.prerequisites("official-cli") if item["id"] == "tools")
        self.assertFalse(tools["ready"])
        self.assertIn("openvpn", tools["message"])

    def test_manual_profile_needs_no_wireguard_adapter_or_resolved_stub(self):
        with patch.object(b.sys, "version_info", (3, 12, 0)), \
             patch.object(b, "vendor_binary") as vendor, \
             patch.object(b, "privileged_command") as adapter:
            checks = b.prerequisites("manual-profile")
        self.assertTrue(all(item["ready"] for item in checks), checks)
        self.assertEqual({item["id"] for item in checks}, {"python", "tools", "NetworkManager"})
        vendor.assert_not_called()
        adapter.assert_not_called()

    def test_connect_preflight_failure_precedes_network_and_client_operations(self):
        failed = [{"id": "adapter", "label": "Reviewed adapter", "ready": False,
                   "message": "not installed"}]
        with patch.object(b, "prerequisites", return_value=failed), \
             patch.object(b, "active_connections") as active, \
             patch.object(b, "vendor_binary") as vendor, \
             patch.object(b, "locations") as locations, \
             patch.object(b, "run") as run:
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("connect", "DE", "", "cyberghost", "official-cli", "wireguard")
        self.assertEqual(caught.exception.code, "setup")
        active.assert_not_called()
        vendor.assert_not_called()
        locations.assert_not_called()
        run.assert_not_called()

    def test_check_disables_connect_when_prerequisites_fail(self):
        from types import SimpleNamespace
        failed = [{"id": "adapter", "label": "Reviewed adapter", "ready": False,
                   "message": "Update the compatibility package."}]
        with patch.object(b, "prerequisites", return_value=failed), \
             patch.object(b, "status", return_value={"state": "disconnected", "can_connect": True}), \
             patch.object(b, "safe_vendor_binary", return_value="/trusted/vendor"):
            result = b.dispatch(SimpleNamespace(action="check", profile="cyberghost", backend="official-cli"))
        self.assertFalse(result["setup_ready"])
        self.assertFalse(result["can_connect"])
        self.assertIn("compatibility package", result["setup_message"])


if __name__ == "__main__":
    unittest.main()
