import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import call, patch


SPEC = importlib.util.spec_from_file_location(
    "cg_bridge", Path(__file__).parents[1] / "cg_bridge.py"
)
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)

_test_state_home = None
_test_runtime_dir = None
_test_environment = None
_protection_patch = None
_prerequisite_patch = None
_real_traffic_protection = b.traffic_protection


def setUpModule():
    global _test_state_home, _test_runtime_dir, _test_environment, _protection_patch, _prerequisite_patch
    _test_state_home = tempfile.TemporaryDirectory(prefix="cg-test-state-")
    _test_runtime_dir = tempfile.TemporaryDirectory(prefix="cg-test-runtime-")
    _test_environment = patch.dict(os.environ, {
        "XDG_STATE_HOME": _test_state_home.name,
        "XDG_RUNTIME_DIR": _test_runtime_dir.name,
    })
    _test_environment.start()
    _protection_patch = patch.object(b, "traffic_protection", return_value=None)
    _protection_patch.start()
    _prerequisite_patch = patch.object(b, "prerequisites", return_value=[{
        "id": "fixture", "label": "Test prerequisites", "ready": True, "message": "Available."
    }])
    _prerequisite_patch.start()


def tearDownModule():
    _prerequisite_patch.stop()
    _protection_patch.stop()
    _test_environment.stop()
    _test_runtime_dir.cleanup()
    _test_state_home.cleanup()


UUID = "01234567-89ab-cdef-0123-456789abcdef"
ACTIVE = [[UUID, "activated", "vpn", "tun0"]]


def args(action, **overrides):
    values = dict(action=action, profile="openvpn", backend="manual-profile",
                  country="DE", city="")
    values.update(overrides)
    return SimpleNamespace(**values)


class InputAndParserTests(unittest.TestCase):
    def test_valid_country_codes(self):
        self.assertEqual(b.validate_code("DE"), "DE")
        for value in ("de", "D;E", "DE\n", "USA", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                b.validate_code(value)

    def test_validated_city_names(self):
        for value in ("Frankfurt", "São Paulo", "St. John's"):
            self.assertEqual(b.validate_name(value), value)
        for value in ("", "--help", "Frankfurt\n", "; rm -rf", "a" * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                b.validate_name(value)

    def test_profile_names_allow_nm_delimiters_but_reject_controls_and_flags(self):
        for value in ("openvpn", "Travel: Home", r"VPN\Backup"):
            self.assertEqual(b.validate_profile(value), value)
        for value in ("", "-f", "bad\nname", "a" * 129):
            with self.subTest(value=value), self.assertRaises(ValueError):
                b.validate_profile(value)

    def test_actual_country_table_excerpt(self):
        table = """+-----+----------------------+--------------+
| No. |     Country Name     | Country Code |
+-----+----------------------+--------------+
|  2  | United Arab Emirates |      AE      |
| 24  |       Germany        |      DE      |
+-----+----------------------+--------------+
"""
        self.assertEqual(b.parse_countries(table),
                         [{"code": "DE", "name": "Germany"},
                          {"code": "AE", "name": "United Arab Emirates"}])
        self.assertEqual(b.parse_countries("1 Germany DE\n2 | Netherlands | NL\nunknown\n"),
                         [{"code": "DE", "name": "Germany"},
                          {"code": "NL", "name": "Netherlands"}])

    def test_actual_four_column_city_table_and_unicode(self):
        table = """+-----+------------+----------+------+
| No. |    City    | Instance | Load |
+-----+------------+----------+------+
|  1  |   Berlin   |   110    | 63%  |
|  2  | Dusseldorf |    26    | 95%  |
|  3  | Frankfurt  |   993    | 63%  |
|  4  |   Zürich   |    12    | 48%  |
|  5  | Partial    |   12    |
+-----+------------+----------+------+
"""
        self.assertEqual(b.parse_cities(table), ["Berlin", "Dusseldorf", "Frankfurt", "Zürich"])
        self.assertEqual(b.parse_cities("1 Frankfurt\n2 São Paulo\n3 Frankfurt\n"),
                         ["Frankfurt", "São Paulo"])
        self.assertEqual(b.parse_cities("Choose a city\n"), [])

    def test_actual_server_table_filters_invalid_ids_and_load(self):
        table = """+-----+-----------+--------------------+------+
| No. |    City   |      Instance      | Load |
+-----+-----------+--------------------+------+
|  1  | Frankfurt | frankfurt-s415-i01 | 72%  |
|  2  | Frankfurt | frankfurt-s415-i02 | 72%  |
|  3  | Frankfurt | frankfurt-s415-i03 | 65%  |
|  4  | Frankfurt | invalid/server-id  | 50%  |
|  5  | Frankfurt | frankfurt-s415-i04 | ??   |
|  6  | Frankfurt | frankfurt-s415-i01 | 72%  |
|  7  | Incomplete | frankfurt-s415-i05 |
+-----+-----------+--------------------+------+
"""
        self.assertEqual(b.parse_servers(table), [
            {"name": "frankfurt-s415-i01", "city": "Frankfurt", "load": 72},
            {"name": "frankfurt-s415-i02", "city": "Frankfurt", "load": 72},
            {"name": "frankfurt-s415-i03", "city": "Frankfurt", "load": 65},
            {"name": "frankfurt-s415-i04", "city": "Frankfurt", "load": None},
        ])

    def test_servers_action_is_read_only_and_uses_selected_country_and_city(self):
        table = "| 1 | Frankfurt | frankfurt-s415-i01 | 72% |\n"
        vendor = "/usr/local/cyberghost/cyberghostvpn"
        with patch.object(b, "vendor_binary", return_value=vendor), patch.object(b, "run", return_value=table) as run:
            result = b.locations("servers", "DE", "official-cli", "Frankfurt")
        self.assertEqual(run.call_args.args[0], [vendor, "--traffic", "--country-code", "DE", "--city", "Frankfurt"])
        self.assertEqual(result["items"][0]["name"], "frankfurt-s415-i01")
        self.assertNotIn("pkexec", run.call_args.args[0])
        for country, city in (("de", "Frankfurt"), ("DE", "--help"), ("DE", "")):
            with self.subTest(country=country, city=city), \
                 patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
                 patch.object(b, "run") as run:
                with self.assertRaises(ValueError):
                    b.locations("servers", country, "official-cli", city)
                run.assert_not_called()

    def test_nm_rows_unescapes_colons_and_backslashes(self):
        self.assertEqual(b.nm_rows(r"Travel\: Home\\Desk:uuid:vpn" + "\n"),
                         [["Travel: Home\\Desk", "uuid", "vpn"]])
        with self.assertRaises(b.BridgeError) as caught:
            b.nm_rows("name:uuid:vpn\\")
        self.assertEqual(caught.exception.code, "invalid_response")


class VendorPathTests(unittest.TestCase):
    def _path_mocks(self, *, bad_path=None, bad_mode=0o022, missing=False, access=None):
        first = Path("/usr/bin/cyberghostvpn")
        second = Path("/usr/local/bin/cyberghostvpn")
        targets = {
            str(first): Path("/opt/cyberghostvpn"),
            str(second): Path("/opt/cyberghostvpn"),
        }

        def resolve(path, strict=False):
            if missing:
                raise FileNotFoundError(str(path))
            return targets[str(path)]

        def info(path):
            mode = stat.S_IFREG | 0o755
            if str(path) == bad_path:
                mode |= bad_mode
            return SimpleNamespace(st_uid=0, st_mode=mode)

        return (
            patch.object(Path, "resolve", autospec=True, side_effect=resolve),
            patch.object(Path, "stat", autospec=True, side_effect=info),
            patch.object(Path, "is_file", autospec=True, return_value=True),
            patch.object(b.os, "access", side_effect=access or (lambda _path, mode: mode == os.X_OK)),
        )

    def test_accepts_symlink_to_root_owned_system_target(self):
        mocks = self._path_mocks()
        for mocked in mocks:
            mocked.start()
        self.addCleanup(patch.stopall)
        self.assertEqual(b.safe_vendor_binary(), "/opt/cyberghostvpn")

    def test_rejects_writable_target_or_parent(self):
        for unsafe in ("/opt/cyberghostvpn", "/opt"):
            with self.subTest(path=unsafe):
                mocks = self._path_mocks(bad_path=unsafe)
                for mocked in mocks:
                    mocked.start()
                self.assertIsNone(b.safe_vendor_binary())
                patch.stopall()

    def test_rejects_writable_system_symlink_parent(self):
        mocks = self._path_mocks(bad_path="/usr")
        for mocked in mocks:
            mocked.start()
        self.addCleanup(patch.stopall)
        self.assertIsNone(b.safe_vendor_binary())

    def test_rejects_component_with_effective_write_access(self):
        access = lambda path, mode: mode == os.X_OK or (mode == os.W_OK and str(path) == "/opt")
        mocks = self._path_mocks(access=access)
        for mocked in mocks:
            mocked.start()
        self.addCleanup(patch.stopall)
        self.assertIsNone(b.safe_system_binary("/usr/bin/cyberghostvpn"))

    def test_missing_binary_returns_none_without_trusting_path(self):
        mocks = self._path_mocks(missing=True)
        for mocked in mocks:
            mocked.start()
        self.addCleanup(patch.stopall)
        with patch.object(b.shutil, "which", return_value="/tmp/fake-cyberghostvpn"):
            self.assertIsNone(b.safe_vendor_binary())

    def test_privileged_command_requires_reviewed_vendor_and_adapter(self):
        adapter = "/usr/local/cyberghost/omarchy-bridge"
        with patch.object(b, "safe_system_binary", return_value=adapter), \
             patch.object(b, "run", return_value="omarchy-bridge 4\n") as run:
            self.assertEqual(b.privileged_command("/usr/local/cyberghost/cyberghostvpn"),
                             ["/usr/bin/pkexec", adapter])
        self.assertEqual(run.call_args, call([adapter, "--version"], timeout=3))
        with patch.object(b, "safe_system_binary", return_value=adapter), \
             patch.object(b, "run", return_value="omarchy-bridge 1\n") as run:
            with self.assertRaises(b.BridgeError) as caught:
                b.privileged_command("/usr/local/cyberghost/cyberghostvpn")
        self.assertEqual(caught.exception.code, "dependency")
        self.assertIn("1.5.0-7", str(caught.exception))
        run.assert_called_once_with([adapter, "--version"], timeout=3)

    def test_old_reviewed_helper_is_allowed_for_stop_but_not_connect(self):
        adapter = "/usr/local/cyberghost/omarchy-bridge"
        vendor = "/usr/local/cyberghost/cyberghostvpn"
        with patch.object(b, "safe_system_binary", return_value=adapter), \
             patch.object(b, "run") as run:
            self.assertEqual(b.privileged_command(vendor, require_api=False),
                             ["/usr/bin/pkexec", adapter])
        run.assert_not_called()

        with patch.object(b, "safe_system_binary", return_value=adapter), \
             patch.object(b, "run", return_value="omarchy-bridge 1\n") as run:
            with self.assertRaises(b.BridgeError) as caught:
                b.privileged_command(vendor)
        self.assertEqual(caught.exception.code, "dependency")
        run.assert_called_once_with([adapter, "--version"], timeout=3)
        with patch.object(b, "safe_system_binary", return_value=None):
            with self.assertRaises(b.BridgeError) as caught:
                b.privileged_command("/usr/local/cyberghost/cyberghostvpn")
        self.assertEqual(caught.exception.code, "dependency")
        with patch.object(b, "safe_system_binary", return_value=adapter) as safe:
            with self.assertRaises(b.BridgeError):
                b.privileged_command("/tmp/cyberghostvpn")
        safe.assert_called_once_with("/usr/local/cyberghost/omarchy-bridge")


class NetworkManagerTests(unittest.TestCase):
    def test_profile_info_decodes_escaped_name_and_returns_uuid(self):
        with patch.object(b, "run", side_effect=[r"Travel\: Home:" + UUID + ":vpn\n",
                                                   "org.freedesktop.NetworkManager.openvpn\n"]) as run:
            self.assertEqual(b.profile_info("Travel: Home"), UUID)
        self.assertEqual(run.call_args_list[1].args[0],
                         ["/usr/bin/nmcli", "-g", "vpn.service-type", "connection", "show", "uuid", UUID])

    def test_profile_info_rejects_missing_or_ambiguous_name(self):
        other_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        for output in ("", f"other:{UUID}:vpn\n",
                       f"openvpn:{UUID}:vpn\nopenvpn:{other_uuid}:vpn\n"):
            with self.subTest(output=output), patch.object(b, "run", return_value=output):
                with self.assertRaises(b.BridgeError) as caught:
                    b.profile_info("openvpn")
                self.assertEqual(caught.exception.code, "profile")

    def test_profile_info_rejects_non_vpn_and_invalid_uuid(self):
        for row in ("openvpn:" + UUID + ":802-3-ethernet\n", "openvpn:not-a-uuid:vpn\n"):
            with self.subTest(row=row), patch.object(b, "run", return_value=row):
                with self.assertRaises(b.BridgeError):
                    b.profile_info("openvpn")

    def test_profile_info_requires_openvpn_service(self):
        with patch.object(b, "run", side_effect=[f"openvpn:{UUID}:vpn\n", "org.freedesktop.NetworkManager.wireguard\n"]):
            with self.assertRaises(b.BridgeError) as caught:
                b.profile_info("openvpn")
        self.assertEqual(caught.exception.code, "profile")

    def test_profile_info_selects_openvpn_when_wireguard_shares_name(self):
        wg_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        with patch.object(b, "run", side_effect=[
            f"cyberghost:{wg_uuid}:wireguard\ncyberghost:{UUID}:vpn\n",
            "org.freedesktop.NetworkManager.openvpn\n",
        ]):
            self.assertEqual(b.profile_info("cyberghost"), UUID)

    def test_connect_uses_profile_uuid_and_wait_options(self):
        with patch.object(b, "profile_info", return_value=UUID), \
             patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "run") as run, \
             patch.object(b, "status", return_value={"state": "connected"}):
            self.assertEqual(b.operate("connect", "DE", "", "openvpn")["state"], "connected")
        self.assertEqual(run.call_args, call(["/usr/bin/nmcli", "--wait", "55", "connection", "up", "uuid", UUID], timeout=65))

    def test_disconnect_uses_active_profile_uuid(self):
        with patch.object(b, "profile_info", return_value=UUID), \
             patch.object(b, "active_connections", return_value=ACTIVE), \
             patch.object(b, "run") as run, \
             patch.object(b, "status", return_value={"state": "disconnected"}):
            b.operate("disconnect", "DE", "", "openvpn")
        self.assertEqual(run.call_args, call(["/usr/bin/nmcli", "--wait", "20", "connection", "down", "uuid", UUID], timeout=30))

    def test_connect_and_disconnect_are_idempotent(self):
        for action, active, result in (("connect", ACTIVE, "connected"),
                                       ("disconnect", [], "disconnected")):
            with self.subTest(action=action), \
                 patch.object(b, "profile_info", return_value=UUID), \
                 patch.object(b, "active_connections", return_value=active), \
                 patch.object(b, "run") as run, \
                 patch.object(b, "status", return_value={"state": result}):
                b.operate(action, "DE", "", "openvpn")
                run.assert_not_called()

    def test_manual_connect_refuses_other_active_vpn_but_not_wifi(self):
        for kind in ("vpn", "wireguard"):
            row = ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", kind, "tun1"]
            with self.subTest(kind=kind), \
                 patch.object(b, "profile_info", return_value=UUID), \
                 patch.object(b, "active_connections", return_value=[row]), \
                 patch.object(b, "run") as run:
                with self.assertRaises(b.BridgeError) as caught:
                    b.operate("connect", "DE", "", "openvpn")
                self.assertEqual(caught.exception.code, "conflict")
                run.assert_not_called()
        with patch.object(b, "profile_info", return_value=UUID), \
             patch.object(b, "active_connections", return_value=[["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "802-3-ethernet", "eth0"]]), \
             patch.object(b, "run") as run, \
             patch.object(b, "status", return_value={"state": "connected"}):
            b.operate("connect", "DE", "", "openvpn")
        run.assert_called_once()

    def test_post_operation_state_mismatch_is_unconfirmed(self):
        with patch.object(b, "profile_info", return_value=UUID), \
             patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "run"), \
             patch.object(b, "status", return_value={"state": "disconnected"}):
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("connect", "DE", "", "openvpn")
        self.assertEqual(caught.exception.code, "unconfirmed")

    def test_manual_status_maps_active_states_conservatively(self):
        for row, state in (([UUID, "activated", "vpn", "tun0"], "connected"),
                           ([UUID, "activating", "vpn", "tun0"], "connecting"),
                           ([UUID, "deactivating", "vpn", "tun0"], "disconnecting"),
                           (None, "disconnected")):
            rows = [row] if row else []
            with self.subTest(state=state), \
                 patch.object(b, "profile_info", return_value=UUID), \
                 patch.object(b, "active_connections", return_value=rows):
                result = b.status("openvpn")
            self.assertEqual(result["state"], state)
        for output in ("bad:activated:vpn:tun0\n", f"{UUID}:activated:vpn:tun0:extra\n"):
            with self.subTest(output=output), \
                 patch.object(b, "profile_info", return_value=UUID), \
                 patch.object(b, "run", return_value=output):
                result = b.status("openvpn")
                self.assertEqual((result["state"], result["code"]), ("unknown", "invalid_response"))
        with patch.object(b, "profile_info", side_effect=b.BridgeError("failed")):
            result = b.status("openvpn")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["code"], "operation_failed")
        with patch.object(b, "vendor_binary", side_effect=b.BridgeError("missing", "dependency")):
            official = b.status("openvpn", "official-cli")
        self.assertEqual((official["state"], official["code"]), ("unknown", "dependency"))

    def test_manual_status_blocks_connect_when_another_vpn_is_active_but_allows_wifi(self):
        other_wireguard = ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "wireguard", "wg0"]
        wifi = ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff", "activated", "802-11-wireless", "wlan0"]
        for row, can_connect, other_active in ((other_wireguard, False, True), (wifi, True, False)):
            with self.subTest(kind=row[2]), \
                 patch.object(b, "profile_info", return_value=UUID), \
                 patch.object(b, "active_connections", return_value=[row]), \
                 patch.object(b, "run") as run:
                result = b.status("openvpn")
            self.assertEqual(result["state"], "disconnected")
            self.assertEqual(result["can_connect"], can_connect)
            self.assertEqual(result.get("other_vpn_active", False), other_active)
            if other_active:
                self.assertEqual(result["code"], "conflict")
                self.assertIn("Another VPN is active", result["error"])
            run.assert_not_called()


class WireGuardStatusTests(unittest.TestCase):
    def test_recognizes_only_up_wireguard_with_default_ipv4_route(self):
        tunnel = {"ifname": "cyberghost", "flags": ["UP"],
                  "linkinfo": {"info_kind": "wireguard"}}
        other = {"ifname": "cyberghost", "flags": ["UP"],
                 "linkinfo": {"info_kind": "tun"}}
        cases = (
            ([], None, None),
            ([other], None, None),
            ([tunnel], [{"dst": "1.1.1.1", "dev": "cyberghost"}], "connected"),
            ([{**tunnel, "flags": ["LOWER_UP"]}], [{"dev": "cyberghost"}], "unknown"),
            ([tunnel], [{"dev": "eth0"}], "unknown"),
        )
        for links, routes, expected in cases:
            replies = [json.dumps(links)] + ([json.dumps(routes)] if routes is not None else [])
            with self.subTest(expected=expected, links=links), patch.object(b, "run", side_effect=replies) as run:
                result = b.wireguard_status()
            if expected is None:
                self.assertIsNone(result)
                run.assert_called_once()
            else:
                self.assertEqual(result["state"], expected)
                self.assertEqual(result["protocol"], "WireGuard")
                self.assertEqual(result["device"], "cyberghost")
                self.assertTrue(result["can_disconnect"])
                self.assertFalse(result["verified"])

    def test_malformed_kernel_json_and_probe_errors_are_reported(self):
        for output in ("not-json", json.dumps({"ifname": "cyberghost"}),
                       json.dumps([{"ifname": "cyberghost", "linkinfo": "wireguard"}]),
                       json.dumps([{"ifname": "cyberghost", "flags": "UP",
                                    "linkinfo": {"info_kind": "wireguard"}}])):
            with self.subTest(output=output), patch.object(b, "run", return_value=output):
                with self.assertRaises(b.BridgeError) as caught:
                    b.wireguard_status()
                self.assertEqual(caught.exception.code, "invalid_response")
        tunnel = [{"ifname": "cyberghost", "flags": ["UP"],
                   "linkinfo": {"info_kind": "wireguard"}}]
        with patch.object(b, "run", side_effect=[json.dumps(tunnel), "not-json"]):
            with self.assertRaises(b.BridgeError) as caught:
                b.wireguard_status()
        self.assertEqual(caught.exception.code, "invalid_response")
        with patch.object(b, "run", side_effect=b.BridgeError("ip unavailable", "dependency")):
            with self.assertRaises(b.BridgeError) as caught:
                b.wireguard_status()
        self.assertEqual(caught.exception.code, "dependency")

        active_path = "/org/freedesktop/NetworkManager/ActiveConnection/42"
        for value, expected in (("u 128", True), ("u 0", False)):
            with self.subTest(flags=value), patch.object(b, "run", side_effect=[active_path, value]) as run:
                self.assertEqual(b.external_connection(UUID), expected)
            self.assertEqual(run.call_args_list[0].args[0],
                             ["/usr/bin/nmcli", "-g", "GENERAL.DBUS-PATH", "connection", "show", "--active", "uuid", UUID])
            self.assertEqual(run.call_args_list[1].args[0],
                             ["/usr/bin/busctl", "get-property", "org.freedesktop.NetworkManager", active_path,
                              "org.freedesktop.NetworkManager.Connection.Active", "StateFlags"])
        for path, value in (("/tmp/not-an-active-connection", "u 128"),
                            (active_path, "private bus response")):
            replies = [path] if path != active_path else [path, value]
            with self.subTest(path=path, value=value), patch.object(b, "run", side_effect=replies):
                with self.assertRaises(b.BridgeError) as caught:
                    b.external_connection(UUID)
                self.assertEqual(caught.exception.code, "invalid_response")
                self.assertNotIn("private bus response", str(caught.exception))

    def test_provider_wireguard_overrides_vendor_negative_without_status_call(self):
        tunnel = [{"ifname": "cyberghost", "flags": ["UP"],
                   "linkinfo": {"info_kind": "wireguard"}}]
        routes = [{"dev": "cyberghost", "dst": "1.1.1.1"}]
        active = [["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "wireguard", "cyberghost"]]
        path = "/org/freedesktop/NetworkManager/ActiveConnection/42"
        with patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "active_connections", return_value=active), \
             patch.object(b, "uplink_ready", return_value=True), \
             patch.object(b, "run", side_effect=[json.dumps(tunnel), json.dumps(routes), path, "u 128"]) as run:
            result = b.status("cyberghost", "official-cli")
        self.assertEqual(result["state"], "connected")
        self.assertEqual(result["protocol"], "WireGuard")
        self.assertEqual(result["device"], "cyberghost")
        self.assertEqual(run.call_args_list[2].args[0],
                         ["/usr/bin/nmcli", "-g", "GENERAL.DBUS-PATH", "connection", "show", "--active", "uuid", active[0][0]])
        self.assertEqual(run.call_count, 4)
        self.assertFalse(any("--status" in c.args[0] for c in run.call_args_list))

        for rows, flags in (([], None), (active, "u 0")):
            replies = [json.dumps(tunnel), json.dumps(routes)]
            if flags is not None:
                replies += [path, flags]
            with self.subTest(rows=rows, flags=flags), \
                 patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
                 patch.object(b, "active_connections", return_value=rows), \
                 patch.object(b, "uplink_ready", return_value=True), \
                 patch.object(b, "run", side_effect=replies) as run:
                result = b.status("cyberghost", "official-cli")
            self.assertEqual((result["state"], result["code"]), ("unknown", "conflict"))
            self.assertFalse(any("--status" in c.args[0] for c in run.call_args_list))


class TrafficProtectionTests(unittest.TestCase):
    def protection(self, **overrides):
        return {"uid": os.getuid(), "device": "cyberghost", "interface_index": 7,
                "mark": 42, "kill_switch": False, "phase": "active", **overrides}

    def test_trusted_protection_metadata_requires_root_owner_and_safe_permissions(self):
        value = self.protection()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protection.json"
            path.write_text(json.dumps(value))
            path.chmod(0o644)
            info = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0,
                                   st_size=path.stat().st_size)
            original_open = os.open
            with patch.object(b, "PROTECTION", path), \
                 patch.object(b.os, "fstat", return_value=info), \
                 patch.object(b.os, "access", return_value=False), \
                 patch.object(b.os, "open", wraps=original_open) as open_file:
                self.assertEqual(_real_traffic_protection(), value)
            self.assertTrue(open_file.call_args.args[1] & os.O_NOFOLLOW)

    def test_malformed_acl_or_unowned_protection_metadata_is_rejected(self):
        value = self.protection()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protection.json"
            with patch.object(b, "PROTECTION", path):
                cases = (
                    ("not json", 0, 0o644, False),
                    (json.dumps(value), 1000, 0o644, False),
                    (json.dumps(value), 0, 0o664, False),
                    (json.dumps(value), 0, 0o644, True),
                )
                for payload, uid, mode, writable in cases:
                    with self.subTest(uid=uid, mode=oct(mode), writable=writable):
                        path.write_text(payload)
                        info = SimpleNamespace(st_mode=stat.S_IFREG | mode, st_uid=uid,
                                               st_size=path.stat().st_size)
                        with patch.object(b.os, "fstat", return_value=info), \
                             patch.object(b.os, "access", return_value=writable):
                            with self.assertRaises(b.BridgeError) as caught:
                                _real_traffic_protection()
                        self.assertEqual(caught.exception.code, "protection")

    def test_absent_protected_tunnel_requires_disconnect_or_release(self):
        for phase, kill_switch, expected in (("blocked", True, "blocked"),
                                             ("prepared", False, "recovery-required")):
            protection = self.protection(phase=phase, kill_switch=kill_switch,
                                         interface_index=0, mark=0)
            with self.subTest(phase=phase), \
                 patch.object(b, "traffic_protection", return_value=protection), \
                 patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
                 patch.object(b, "wireguard_status", return_value=None), \
                 patch.object(b, "active_connections", return_value=[]), \
                 patch.object(b, "saved_details", return_value={}), \
                 patch.object(b, "run") as run:
                result = b.status("cyberghost", "official-cli")
            self.assertEqual(result["state"], expected)
            self.assertTrue(result["can_disconnect"])
            self.assertFalse(result["can_connect"])
            self.assertTrue(result["can_release_protection"])
            run.assert_not_called()

    def test_other_nm_vpn_blocks_cli_but_keeps_owned_release_available(self):
        protection = self.protection(kill_switch=True)
        other = [["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "vpn", "tun1"]]
        with patch.object(b, "traffic_protection", return_value=protection), \
             patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
             patch.object(b, "wireguard_status", return_value=None), \
             patch.object(b, "active_connections", return_value=other), \
             patch.object(b, "saved_details", return_value={}), \
             patch.object(b, "run") as run:
            result = b.status("cyberghost", "official-cli")
        self.assertEqual((result["state"], result["code"]), ("unknown", "conflict"))
        self.assertTrue(result["can_release_protection"])
        self.assertFalse(result["can_connect"])
        run.assert_not_called()

    def test_release_action_requires_owned_protection_and_does_not_remove_profile(self):
        protection = self.protection(kill_switch=True)
        launcher = ["/usr/bin/pkexec", "/adapter"]
        with patch.object(b, "traffic_protection", return_value=protection), \
             patch.object(b.os, "getuid", return_value=protection["uid"]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", return_value="") as run, \
             patch.object(b, "status", return_value={"state": "blocked"}) as status, \
             patch.object(b, "state_file") as state_file:
            result = b.operate("release-protection", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(result["state"], "blocked")
        run.assert_called_once_with(launcher + ["--release-protection"], timeout=30)
        status.assert_called_once_with("cyberghost", "official-cli")
        state_file.assert_not_called()

        for unowned in (None, self.protection(uid=protection["uid"] + 1)):
            with self.subTest(unowned=unowned), \
                 patch.object(b, "traffic_protection", return_value=unowned), \
                 patch.object(b.os, "getuid", return_value=protection["uid"]), \
                 patch.object(b, "vendor_binary") as vendor, patch.object(b, "run") as run:
                with self.assertRaises(b.BridgeError) as caught:
                    b.operate("release-protection", "DE", "", "cyberghost", "official-cli")
            self.assertEqual(caught.exception.code, "protection")
            vendor.assert_not_called()
            run.assert_not_called()

    def test_connected_wireguard_without_upstream_route_waits_for_network(self):
        tunnel = {"state": "connected", "protocol": "WireGuard", "device": "cyberghost",
                  "interface_index": 7, "can_connect": False, "can_disconnect": True,
                  "verified": False}
        active = [["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "wireguard", "cyberghost"]]
        with patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
             patch.object(b, "wireguard_status", return_value=tunnel), \
             patch.object(b, "active_connections", return_value=active), \
             patch.object(b, "external_connection", return_value=True), \
             patch.object(b, "saved_details", return_value={}), \
             patch.object(b, "uplink_ready", return_value=False), \
             patch.object(Path, "read_text", autospec=True, return_value="0"):
            result = b.status("cyberghost", "official-cli")
        self.assertEqual(result["state"], "waiting-network")
        self.assertTrue(result["can_disconnect"])
        self.assertFalse(result["can_connect"])
        self.assertIn("upstream network", result["warning"])

    def test_protection_metadata_for_different_ifindex_is_not_claimed_active(self):
        protection = self.protection(interface_index=8, kill_switch=True)
        tunnel = {"state": "connected", "protocol": "WireGuard", "device": "cyberghost",
                  "interface_index": 7, "can_connect": False, "can_disconnect": True,
                  "verified": False}
        active = [["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "wireguard", "cyberghost"]]
        with patch.object(b, "traffic_protection", return_value=protection), \
             patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
             patch.object(b, "wireguard_status", return_value=tunnel), \
             patch.object(b, "active_connections", return_value=active), \
             patch.object(b, "external_connection", return_value=True), \
             patch.object(b, "saved_details", return_value={}), \
             patch.object(b, "uplink_ready") as uplink, \
             patch.object(Path, "read_text", autospec=True, return_value="0"):
            result = b.status("cyberghost", "official-cli")
        self.assertEqual(result["state"], "recovery-required")
        self.assertTrue(result["can_disconnect"])
        self.assertTrue(result["can_release_protection"])
        self.assertFalse(result["ipv6_guard"])
        self.assertFalse(result["kill_switch"])
        uplink.assert_not_called()

    def test_prepared_guard_reports_unconfirmed_setup_without_claiming_kill_switch(self):
        protection = self.protection(phase="prepared", interface_index=0, mark=0, kill_switch=False)
        with patch.object(b, "traffic_protection", return_value=protection), \
             patch.object(b, "vendor_binary", return_value="/trusted/vendor"), \
             patch.object(b, "wireguard_status", return_value=None), \
             patch.object(b, "active_connections", return_value=[]), \
             patch.object(Path, "read_text", return_value="0"):
            result = b.status("cyberghost", "official-cli")
        self.assertEqual(result["state"], "recovery-required")
        self.assertEqual(result["protection_phase"], "prepared")
        self.assertFalse(result["kill_switch"])
        self.assertIn("before protection was confirmed", result["error"])

    def test_release_needs_only_trusted_adapter_when_vendor_is_missing(self):
        with patch.object(b, "traffic_protection", return_value=self.protection(uid=1000)), \
             patch.object(b.os, "getuid", return_value=1000), \
             patch.object(b, "vendor_binary", side_effect=b.BridgeError("missing vendor")) as vendor, \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/adapter"]), \
             patch.object(b, "run", return_value="") as run, \
             patch.object(b, "status", return_value={"state": "disconnected"}):
            result = b.operate("release-protection", "DE", "", "cyberghost", "official-cli")
        vendor.assert_not_called()
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pkexec", "/adapter", "--release-protection"])
        self.assertEqual(result["state"], "disconnected")


class OfficialCliTests(unittest.TestCase):
    def test_cli_parses_switch_protocol_and_server_options(self):
        argv = ["cg_bridge.py", "switch", "--backend", "official-cli", "--country", "DE",
                "--city", "Frankfurt", "--protocol", "wireguard", "--server", "frankfurt-s415-i01"]
        output = StringIO()
        with patch.object(b.sys, "argv", argv), patch.object(b, "dispatch", return_value={}) as dispatch, \
             redirect_stdout(output):
            self.assertEqual(b.main(), 0)
        self.assertEqual(output.getvalue(), '{"ok": true}\n')
        parsed = dispatch.call_args.args[0]
        self.assertEqual((parsed.action, parsed.protocol, parsed.server),
                         ("switch", "wireguard", "frankfurt-s415-i01"))

    def test_country_is_discovered_before_pkexec_connect(self):
        listed = "1 Germany DE\n"
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]), \
             patch.object(b, "run", side_effect=[listed, ""]) as run, \
             patch.object(b, "status", side_effect=[{"state": "disconnected"}, {"state": "connected"}]) as status, \
             patch.object(b, "save_details"), patch.object(b, "saved_details", return_value={}):
            b.operate("connect", "DE", "", "openvpn", "official-cli")
        self.assertEqual(status.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/local/cyberghost/cyberghostvpn", "--traffic", "--country-code"])
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge", "--traffic", "--country-code", "DE", "--connect"])

    def test_city_is_discovered_before_pkexec_connect(self):
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]), \
             patch.object(b, "run", side_effect=["Germany DE\n", "1 Frankfurt\n",
                                                  "| 1 | Frankfurt | frankfurt-s415-i01 | 72% |\n", ""]) as run, \
             patch.object(b, "status", side_effect=[{"state": "disconnected"}, {"state": "connected"}]) as status, \
             patch.object(b, "save_details"), patch.object(b, "saved_details", return_value={}):
            b.operate("connect", "DE", "Frankfurt", "openvpn", "official-cli")
        self.assertEqual(status.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/local/cyberghost/cyberghostvpn", "--traffic", "--country-code", "DE"])
        self.assertEqual(run.call_args_list[2].args[0], ["/usr/local/cyberghost/cyberghostvpn", "--traffic",
                                                        "--country-code", "DE", "--city", "Frankfurt"])
        self.assertEqual(run.call_args_list[3].args[0][-3:], ["--city", "Frankfurt", "--connect"])

    def test_undiscovered_country_never_reaches_pkexec(self):
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/adapter"]), \
             patch.object(b, "run", return_value="Germany DE\n") as run, \
             patch.object(b, "status", return_value={"state": "disconnected"}) as status:
            with self.assertRaises(ValueError):
                b.operate("connect", "NL", "", "openvpn", "official-cli")
        status.assert_called_once_with("openvpn", "official-cli")
        self.assertFalse(any(c.args[0][0] == "/usr/bin/pkexec" for c in run.call_args_list))

    def test_undiscovered_city_never_reaches_pkexec(self):
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]), \
             patch.object(b, "run", side_effect=["Germany DE\n", "1 Berlin\n"]) as run, \
             patch.object(b, "status", return_value={"state": "disconnected"}) as status:
            with self.assertRaises(ValueError):
                b.operate("connect", "DE", "Frankfurt", "openvpn", "official-cli")
        status.assert_called_once_with("openvpn", "official-cli")
        self.assertFalse(any(c.args[0][0] == "/usr/bin/pkexec" for c in run.call_args_list))

    def test_protocol_is_used_for_discovery_and_connect(self):
        vendor = "/usr/local/cyberghost/cyberghostvpn"
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        with patch.object(b, "vendor_binary", return_value=vendor), \
             patch.object(b, "run", return_value="1 Germany DE\n") as run:
            b.locations("countries", backend="official-cli", protocol="wireguard")
        self.assertEqual(run.call_args.args[0], [vendor, "--traffic", "--country-code", "--wireguard"])

        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value=vendor), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", side_effect=["1 Germany DE\n", "connected"]) as run, \
             patch.object(b, "status", side_effect=[{"state": "disconnected"}, {"state": "connected"}]), \
             patch.object(b, "save_details"), patch.object(b, "saved_details", return_value={}):
            b.operate("connect", "DE", "", "cyberghost", "official-cli", "wireguard")
        self.assertEqual(run.call_args_list[-1].args[0],
                         launcher + ["--traffic", "--country-code", "DE", "--wireguard", "--connect"])

    def test_undiscovered_server_never_reaches_privilege_or_stops_current_tunnel(self):
        table = "| 1 | Frankfurt | frankfurt-s415-i01 | 72% |\n"
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", side_effect=["1 Germany DE\n", "1 Frankfurt\n", table]) as run:
            with self.assertRaises(ValueError):
                b.operate("switch", "DE", "Frankfurt", "cyberghost", "official-cli",
                          server="frankfurt-s415-i99")
        self.assertFalse(any(command.args[0][0] == "/usr/bin/pkexec"
                             for command in run.call_args_list))

    def test_empty_server_catalog_prevents_switch_stop_and_connect(self):
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/adapter"]), \
             patch.object(b, "run", side_effect=["Germany DE\n", "1 Frankfurt\n", ""]) as run, \
             patch.object(b, "status") as status:
            with self.assertRaises(ValueError):
                b.operate("switch", "DE", "Frankfurt", "cyberghost", "official-cli",
                          server="frankfurt-s415-i01")
        status.assert_not_called()
        self.assertFalse(any(command.args[0][0] == "/usr/bin/pkexec"
                             for command in run.call_args_list))

    def test_interrupted_switch_stop_never_starts_the_new_connection(self):
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", side_effect=["Germany DE\n", b.BridgeError("timed out", "timeout")]) as run, \
             patch.object(b, "status", return_value={"state": "connected", "can_disconnect": True}):
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("switch", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(caught.exception.code, "timeout")
        privileged = [command.args[0] for command in run.call_args_list
                      if command.args[0][0] == "/usr/bin/pkexec"]
        self.assertEqual(privileged, [launcher + ["--stop"]])

    def test_cancelled_connect_is_not_retried_or_reported_as_connected(self):
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", side_effect=["Germany DE\n", b.BridgeError("cancelled", "authorization")]) as run, \
             patch.object(b, "status", return_value={"state": "disconnected"}) as status:
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("connect", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(caught.exception.code, "authorization")
        status.assert_called_once_with("cyberghost", "official-cli")
        privileged = [command.args[0] for command in run.call_args_list
                      if command.args[0][0] == "/usr/bin/pkexec"]
        self.assertEqual(privileged, [launcher + ["--traffic", "--country-code", "DE", "--connect"]])

    def test_connect_requires_a_confirmed_disconnected_preflight(self):
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        for state in ("connected", "unknown", "blocked", "recovery-required"):
            with self.subTest(state=state), \
                 patch.object(b, "active_connections", return_value=[]), \
                 patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
                 patch.object(b, "privileged_command", return_value=launcher), \
                 patch.object(b, "run", return_value="Germany DE\n") as run, \
                 patch.object(b, "status", return_value={"state": state}) as status:
                with self.assertRaises(b.BridgeError) as caught:
                    b.operate("connect", "DE", "", "cyberghost", "official-cli")
            self.assertEqual(caught.exception.code, "conflict")
            status.assert_called_once_with("cyberghost", "official-cli")
            self.assertFalse(any(command.args[0][0] == "/usr/bin/pkexec"
                                 for command in run.call_args_list))

    def test_kill_switch_flag_is_forwarded_only_for_wireguard(self):
        vendor = "/usr/local/cyberghost/cyberghostvpn"
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value=vendor), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", side_effect=["1 Germany DE\n", ""]) as run, \
             patch.object(b, "status", side_effect=[{"state": "disconnected"}, {"state": "connected"}]), \
             patch.object(b, "save_details"), patch.object(b, "saved_details", return_value={}):
            b.operate("connect", "DE", "", "cyberghost", "official-cli", "wireguard", kill_switch=True)
        self.assertEqual(run.call_args_list[-1].args[0],
                         launcher + ["--traffic", "--country-code", "DE", "--wireguard",
                                     "--kill-switch", "--connect"])

        with self.assertRaises(ValueError):
            b.operate("connect", "DE", "", "cyberghost", "official-cli", "openvpn", kill_switch=True)
        with self.assertRaises(ValueError):
            b.operate("connect", "DE", "", "openvpn", "manual-profile", "wireguard", kill_switch=True)

    def test_switch_stops_but_never_connects_when_disconnect_is_unconfirmed(self):
        launcher = ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=launcher), \
             patch.object(b, "run", side_effect=["1 Germany DE\n", ""]) as run, \
             patch.object(b, "status", side_effect=[
                 {"state": "connected", "can_disconnect": True},
                 {"state": "connected"},
             ]):
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("switch", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(caught.exception.code, "unconfirmed")
        privileged = [command.args[0] for command in run.call_args_list
                      if command.args[0][0] == "/usr/bin/pkexec"]
        self.assertEqual(privileged, [launcher + ["--stop"]])


    def test_official_connect_and_disconnect_refuse_any_active_vpn(self):
        for action in ("connect", "disconnect"):
            for kind in ("vpn", "wireguard"):
                active = [["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", kind, "tun1"]]
                with self.subTest(action=action, kind=kind), \
                     patch.object(b, "active_connections", return_value=active), \
                     patch.object(b, "vendor_binary") as vendor, \
                     patch.object(b, "run") as run:
                    with self.assertRaises(b.BridgeError) as caught:
                        b.operate(action, "DE", "", "openvpn", "official-cli")
                    self.assertEqual(caught.exception.code, "conflict")
                    vendor.assert_not_called()
                    run.assert_not_called()

    def test_official_stop_allows_owned_wireguard_but_refuses_other_vpn(self):
        owned = [["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "activated", "wireguard", "cyberghost"]]
        confirmed = {"state": "connected", "protocol": "WireGuard", "device": "cyberghost"}
        with patch.object(b, "active_connections", return_value=owned), \
             patch.object(b, "wireguard_status", return_value=confirmed), \
             patch.object(b, "external_connection", return_value=True) as external, \
             patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
             patch.object(b, "privileged_command", return_value=["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge"]), \
             patch.object(b, "run") as run, \
             patch.object(b, "status", return_value={"state": "disconnected"}):
            b.operate("disconnect", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pkexec", "/usr/local/cyberghost/omarchy-bridge", "--stop"])
        external.assert_called_once_with(owned[0][0])

        with patch.object(b, "active_connections", return_value=owned), \
             patch.object(b, "wireguard_status", return_value=confirmed), \
             patch.object(b, "external_connection", return_value=False), \
             patch.object(b, "vendor_binary") as vendor, \
             patch.object(b, "run") as run:
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("disconnect", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(caught.exception.code, "conflict")
        vendor.assert_not_called()
        run.assert_not_called()

        other_vpn = owned + [["bbbbbbbb-cccc-dddd-eeee-ffffffffffff", "activated", "vpn", "tun1"]]
        with patch.object(b, "active_connections", return_value=other_vpn), \
             patch.object(b, "wireguard_status", return_value=confirmed), \
             patch.object(b, "external_connection", return_value=True), \
             patch.object(b, "vendor_binary") as vendor, \
             patch.object(b, "run") as run:
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("disconnect", "DE", "", "cyberghost", "official-cli")
        self.assertEqual(caught.exception.code, "conflict")
        vendor.assert_not_called()
        run.assert_not_called()

    def test_official_missing_binary_is_dependency_error(self):
        with patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "vendor_binary", side_effect=b.BridgeError("missing", "dependency")), \
             patch.object(b, "run") as run:
            with self.assertRaises(b.BridgeError) as caught:
                b.operate("disconnect", "DE", "", "openvpn", "official-cli")
        self.assertEqual(caught.exception.code, "dependency")
        run.assert_not_called()

    def test_official_status_parser_anchors_connected_state(self):
        cases = (("Connected.", "connected"), ("Connection established", "connected"),
                 ("Disconnected", "disconnected"), ("Connecting", "connecting"),
                 ("not sure whether connected", "unknown"))
        for output, expected in cases:
            with self.subTest(output=output), \
                 patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
                 patch.object(b, "wireguard_status", return_value=None), \
                 patch.object(b, "active_connections", return_value=[]), \
                 patch.object(b, "kernel_tunnel_status", return_value={"state": "connected"}), \
                 patch.object(b, "saved_details", return_value={}), \
                 patch.object(b, "run", return_value=output):
                result = b.status("openvpn", "official-cli")
            self.assertEqual(result["state"], expected)

    def test_openvpn_connection_found_requires_kernel_tunnel_evidence(self):
        for kind in ("tun", "ovpn"):
            tunnel = [{"ifname": "tun0", "ifindex": 11, "flags": ["UP"],
                       "linkinfo": {"info_kind": kind}}]
            routes = [{"dst": "1.1.1.1", "dev": "tun0"}]
            with self.subTest(kind=kind), \
                 patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
                 patch.object(b, "wireguard_status", return_value=None), \
                 patch.object(b, "active_connections", return_value=[]), \
                 patch.object(b, "saved_details", return_value={}), \
                 patch.object(b, "run", side_effect=["VPN connection found.", json.dumps(tunnel), json.dumps(routes)]):
                result = b.status("cyberghost", "official-cli")
            self.assertEqual((result["state"], result["protocol"], result["device"], result["interface_index"]),
                             ("connected", "OpenVPN", "tun0", 11))
            self.assertFalse(result["verified"])

        with patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
             patch.object(b, "wireguard_status", return_value=None), \
             patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "saved_details", return_value={}), \
             patch.object(b, "run", side_effect=["VPN connection found.", "[]"]):
            result = b.status("cyberghost", "official-cli")
        self.assertEqual(result["code"], "unconfirmed")
        self.assertNotEqual(result["state"], "connected")

    def test_official_openvpn_status_rejects_other_nm_vpn_or_wireguard(self):
        other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        for kind in ("vpn", "wireguard"):
            rows = [[other, "activated", kind, "tun1"]]
            with self.subTest(kind=kind), \
                 patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
                 patch.object(b, "wireguard_status", return_value=None), \
                 patch.object(b, "active_connections", return_value=rows), \
                 patch.object(b, "kernel_tunnel_status") as kernel, \
                 patch.object(b, "saved_details", return_value={}), \
                 patch.object(b, "run", return_value="Disconnected") as run:
                result = b.status("cyberghost", "official-cli")
            self.assertEqual((result["state"], result["code"]), ("unknown", "conflict"))
            self.assertFalse(result["can_connect"])
            self.assertFalse(result["can_disconnect"])
            run.assert_not_called()
            kernel.assert_not_called()

    def test_malformed_official_status_is_unknown_and_does_not_expose_output(self):
        with patch.object(b, "vendor_binary", return_value="/opt/cyberghostvpn"), \
             patch.object(b, "wireguard_status", return_value=None), \
             patch.object(b, "active_connections", return_value=[]), \
             patch.object(b, "saved_details", return_value={}), \
             patch.object(b, "run", return_value="CONNECTED alice@example.test"):
            result = b.status("cyberghost", "official-cli")
        self.assertEqual((result["state"], result["code"]), ("unknown", "invalid_response"))
        self.assertFalse(result["can_connect"])
        self.assertFalse(result["can_disconnect"])
        self.assertNotIn("alice@example.test", result["error"])

    def test_manual_profile_has_no_fake_dynamic_locations(self):
        result = b.locations("countries")
        self.assertEqual(result["items"], [])
        self.assertIn("fixed", result["reason"])

class CommandSafetyTests(unittest.TestCase):
    def test_authentication_failure_is_classified_without_raw_output(self):
        cp = SimpleNamespace(returncode=1, stdout="login required secret-token", stderr="account@example.test")
        with patch.object(b.subprocess, "run", return_value=cp):
            with self.assertRaises(b.BridgeError) as caught:
                b.run(["cyberghostvpn", "--status"])
        self.assertEqual(caught.exception.code, "authentication")
        self.assertNotIn("secret-token", str(caught.exception))
        self.assertNotIn("account@example.test", str(caught.exception))

        for phrase in ("no valid vpn secrets", "secrets were required",
                       "no agents were available", "no secrets were provided"):
            details = "alice@example.test vpn_secret=fixture-value"
            cp = SimpleNamespace(returncode=4, stdout=f"{phrase}: {details}", stderr="")
            with self.subTest(phrase=phrase), patch.object(b.subprocess, "run", return_value=cp):
                with self.assertRaises(b.BridgeError) as caught:
                    b.run(["/usr/bin/nmcli", "connection", "up", "uuid", UUID])
            self.assertEqual(caught.exception.code, "authentication")
            self.assertNotIn("alice@example.test", str(caught.exception))
            self.assertNotIn("fixture-value", str(caught.exception))

    def test_generic_failure_does_not_return_raw_stderr(self):
        cp = SimpleNamespace(returncode=2, stdout="", stderr="password=secret-value")
        with patch.object(b.subprocess, "run", return_value=cp):
            with self.assertRaises(b.BridgeError) as caught:
                b.run(["/usr/bin/nmcli", "connection", "up"])
        self.assertNotIn("secret-value", str(caught.exception))

    def test_polkit_denial_is_classified(self):
        cp = SimpleNamespace(returncode=126, stdout="", stderr="")
        with patch.object(b.subprocess, "run", return_value=cp):
            with self.assertRaises(b.BridgeError) as caught:
                b.run(["/usr/bin/pkexec", "/opt/cyberghostvpn"])
        self.assertEqual(caught.exception.code, "authorization")

    def test_missing_dependency_and_timeout_are_classified(self):
        with patch.object(b.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(b.BridgeError) as caught:
                b.run(["/usr/bin/nmcli"])
        self.assertEqual(caught.exception.code, "dependency")
        with patch.object(b.subprocess, "run", side_effect=subprocess.TimeoutExpired("nmcli", 1)):
            with self.assertRaises(b.BridgeError) as caught:
                b.run(["/usr/bin/nmcli"])
        self.assertEqual(caught.exception.code, "timeout")

    def test_oversized_command_output_is_rejected(self):
        cp = SimpleNamespace(returncode=0, stdout="x" * 100_001, stderr="")
        with patch.object(b.subprocess, "run", return_value=cp):
            with self.assertRaises(b.BridgeError) as caught:
                b.run(["/usr/bin/cyberghostvpn"])
        self.assertEqual(caught.exception.code, "invalid_response")


class PublicIpTests(unittest.TestCase):
    def test_status_does_not_make_public_ip_request(self):
        with patch.object(b, "status", return_value={"state": "disconnected"}), \
             patch.object(b, "run") as run:
            b.dispatch(args("status"))
        run.assert_not_called()

    def test_ip_lookup_is_opt_in_and_validates_address(self):
        snapshot = {"state": "connected", "device": "tun0", "interface_index": 5}
        with patch.object(b, "status", side_effect=[snapshot, dict(snapshot)]), \
             patch.object(b, "run", return_value="1.1.1.1\n") as run:
            self.assertEqual(b.dispatch(args("ip")), {"ip": "1.1.1.1"})
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/curl")
        self.assertIn("--noproxy", run.call_args.args[0])
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("--interface") + 1], "if!tun0")

    def test_ip_lookup_never_resolves_an_invalid_interface_as_a_hostname(self):
        for device in (None, "", "if!attacker", "a" * 16):
            with self.subTest(device=device), \
                 patch.object(b, "status", return_value={"state": "connected", "device": device}), \
                 patch.object(b, "run") as run:
                with self.assertRaises(b.BridgeError) as caught:
                    b.dispatch(args("ip"))
                self.assertEqual(caught.exception.code, "unconfirmed")
                run.assert_not_called()

    def test_invalid_or_non_global_ip_response_is_sanitized(self):
        for value in ("not-an-ip", "192.168.1.2", "203.0.113.10"):
            with self.subTest(value=value), \
                 patch.object(b, "status", return_value={"state": "connected", "device": "tun0"}), \
                 patch.object(b, "run", return_value=value):
                with self.assertRaises(b.BridgeError) as caught:
                    b.dispatch(args("ip"))
            self.assertEqual(caught.exception.code, "invalid_response")
            self.assertNotIn(value, str(caught.exception))

    def test_disconnected_or_changed_status_blocks_ip_result(self):
        with patch.object(b, "status", return_value={"state": "disconnected"}), patch.object(b, "run") as run:
            with self.assertRaises(b.BridgeError):
                b.dispatch(args("ip"))
            run.assert_not_called()
        with patch.object(b, "status", side_effect=[{"state": "connected", "device": "tun0"}, {"state": "disconnected"}]), \
             patch.object(b, "run", return_value="1.1.1.1"):
            with self.assertRaises(b.BridgeError) as caught:
                b.dispatch(args("ip"))
        self.assertEqual(caught.exception.code, "unconfirmed")

        before = {"state": "connected", "device": "tun0", "interface_index": 5}
        changed = (
            {"state": "connected", "device": "tun1", "interface_index": 5},
            {"state": "connected", "device": "tun0", "interface_index": 6},
        )
        for after in changed:
            with self.subTest(after=after), \
                 patch.object(b, "status", side_effect=[before, after]), \
                 patch.object(b, "run", return_value="1.1.1.1") as run:
                with self.assertRaises(b.BridgeError) as caught:
                    b.dispatch(args("ip"))
            self.assertEqual(caught.exception.code, "unconfirmed")
            run.assert_called_once()


class ProtectionVerificationTests(unittest.TestCase):
    def test_explicit_verification_accepts_only_boolean_results(self):
        launcher = ["/usr/bin/pkexec", "/adapter"]
        for value in (True, False):
            with self.subTest(value=value), \
                 patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
                 patch.object(b, "privileged_command", return_value=launcher), \
                 patch.object(b, "run", return_value=json.dumps({"protection_verified": value})) as run:
                self.assertEqual(b.dispatch(args("verify-protection", backend="official-cli")),
                                 {"protection_verified": value})
            run.assert_called_once_with(launcher + ["--verify-protection"], timeout=30)

        for output in ('{"protection_verified": 1}', '{"protection_verified": "true"}',
                       '[]', 'null', 'not json'):
            with self.subTest(output=output), \
                 patch.object(b, "vendor_binary", return_value="/usr/local/cyberghost/cyberghostvpn"), \
                 patch.object(b, "privileged_command", return_value=launcher), \
                 patch.object(b, "run", return_value=output):
                with self.assertRaises(b.BridgeError) as caught:
                    b.dispatch(args("verify-protection", backend="official-cli"))
            self.assertEqual(caught.exception.code, "invalid_response")
            self.assertNotIn(output, str(caught.exception))

    def test_verification_requires_official_cli_backend(self):
        with patch.object(b, "run") as run:
            with self.assertRaises(ValueError):
                b.dispatch(args("verify-protection", backend="manual-profile"))
        run.assert_not_called()


class ConnectionDetailsTests(unittest.TestCase):
    snapshot = {"state": "connected", "protocol": "OpenVPN", "device": "tun0",
                "interface_index": 7}
    boot_path = "/proc/sys/kernel/random/boot_id"

    def _boot_id(self, value="boot-a"):
        original = Path.read_text

        def read_text(path, *args, **kwargs):
            if str(path) == self.boot_path:
                return value + "\n"
            return original(path, *args, **kwargs)

        return patch.object(Path, "read_text", autospec=True, side_effect=read_text)

    def test_saved_details_are_atomic_private_and_bound_to_tunnel(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"XDG_STATE_HOME": directory}), \
             self._boot_id(), patch.object(b.time, "monotonic", return_value=100.0):
            path = b.state_file()
            observed = []
            replace = os.replace

            def inspect_then_replace(source, destination):
                source, destination = Path(source), Path(destination)
                observed.append((source.parent, destination, stat.S_IMODE(source.stat().st_mode),
                                destination.exists()))
                replace(source, destination)

            with patch.object(b.os, "replace", side_effect=inspect_then_replace):
                b.save_details(self.snapshot, "DE", "Frankfurt", "", "Connected frankfurt-s415-i01",
                               known_servers=("frankfurt-s415-i01",))

            self.assertEqual(len(observed), 1)
            temp_parent, destination, temp_mode, target_existed = observed[0]
            self.assertEqual(temp_parent, path.parent)
            self.assertEqual(destination, path)
            self.assertEqual(temp_mode, 0o600)
            self.assertFalse(target_existed)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(list(path.parent.glob(".connection-*")), [])

            record = json.loads(path.read_text())
            self.assertEqual(record["boot_id"], "boot-a")
            self.assertEqual(record["device"], "tun0")
            self.assertEqual(record["interface_index"], 7)
            self.assertEqual(record["server"], "frankfurt-s415-i01")
            self.assertEqual(record["server_source"], "client")
            with patch.object(b.time, "monotonic", return_value=130.0):
                details = b.saved_details(self.snapshot)
            self.assertEqual(details["location"], "DE · Frankfurt")
            self.assertEqual(details["location_source"], "requested")
            self.assertEqual(details["server_source"], "client")
            self.assertEqual(details["duration"], 30)

    def test_stale_and_malformed_metadata_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"XDG_STATE_HOME": directory}), self._boot_id():
            path = b.state_file()
            record = {"country": "DE", "city": "Frankfurt", "server": "frankfurt-s415-i01",
                      "server_source": "client", "device": "tun0", "interface_index": 7,
                      "protocol": "OpenVPN", "started": 10.0, "boot_id": "boot-a"}
            for changed in ({"interface_index": 8}, {"boot_id": "boot-b"}):
                with self.subTest(changed=changed):
                    path.write_text(json.dumps({**record, **changed}))
                    os.chmod(path, 0o600)
                    self.assertEqual(b.saved_details(self.snapshot), {})

            for malformed in ("not json", "[]", "null", '{"country": []}'):
                with self.subTest(malformed=malformed):
                    path.write_text(malformed)
                    os.chmod(path, 0o600)
                    self.assertEqual(b.saved_details(self.snapshot), {})

    def test_server_in_client_output_must_match_fresh_known_catalog(self):
        with patch.object(b.time, "monotonic", return_value=100.0), self._boot_id():
            path = b.state_file()
            b.save_details(self.snapshot, "DE", "Frankfurt", "", "Connected account-s415-i01",
                           known_servers=("frankfurt-s415-i01",))
            record = json.loads(path.read_text())
        self.assertEqual(record["server"], "")
        self.assertEqual(record["server_source"], "requested")


class OperationLockTests(unittest.TestCase):
    def _runtime(self, path):
        return patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(path)})

    def test_lock_is_acquired_and_released_in_private_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            with self._runtime(directory):
                with b.operation_lock():
                    lock = Path(directory) / "petevo-cyberghost.lock"
                    self.assertTrue(lock.is_file())
                    self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
                with b.operation_lock():
                    pass

    def test_lock_contention_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            with self._runtime(directory), b.operation_lock():
                with self.assertRaises(b.BridgeError) as caught:
                    with b.operation_lock():
                        pass
            self.assertEqual(caught.exception.code, "busy")

    def test_rejects_runtime_directory_with_unsafe_mode_or_symlink(self):
        with tempfile.TemporaryDirectory() as parent:
            actual = Path(parent) / "runtime"
            actual.mkdir(mode=0o700)
            with self.subTest(case="mode"):
                os.chmod(actual, 0o755)
                with self._runtime(actual), self.assertRaises(b.BridgeError):
                    with b.operation_lock():
                        pass
                os.chmod(actual, 0o700)
            link = Path(parent) / "runtime-link"
            link.symlink_to(actual)
            with self.subTest(case="symlink"), self._runtime(link), self.assertRaises(b.BridgeError):
                with b.operation_lock():
                    pass

    def test_rejects_unsafe_or_symlink_lock_file(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            lock = Path(directory) / "petevo-cyberghost.lock"
            lock.touch(mode=0o644)
            os.chmod(lock, 0o644)
            with self.subTest(case="mode"), self._runtime(directory), self.assertRaises(b.BridgeError):
                with b.operation_lock():
                    pass
            lock.unlink()
            target = Path(directory) / "target"
            target.touch(mode=0o600)
            lock.symlink_to(target)
            with self.subTest(case="symlink"), self._runtime(directory), self.assertRaises(OSError):
                with b.operation_lock():
                    pass


if __name__ == "__main__":
    unittest.main()
