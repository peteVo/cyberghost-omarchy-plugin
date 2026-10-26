import importlib.util
import pathlib
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "cg_bridge", pathlib.Path(__file__).parents[1] / "cg_bridge.py"
)
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class BridgeTests(unittest.TestCase):
    def test_validated_inputs(self):
        self.assertEqual(b.validate_code("DE"), "DE")
        self.assertEqual(b.validate_name("Frankfurt"), "Frankfurt")
        for bad in ["D;E", "de", "DE\n"]:
            with self.assertRaises(ValueError):
                b.validate_code(bad)
        for bad in ["; rm -rf", "Frankfurt\n", "--help", ""]:
            with self.assertRaises(ValueError):
                b.validate_name(bad)

    def test_countries_parser(self):
        self.assertEqual(
            b.parse_countries("1 Germany DE\n2 Netherlands NL\n"),
            [{"code": "DE", "name": "Germany"}, {"code": "NL", "name": "Netherlands"}]
        )
        self.assertEqual(b.parse_countries("unexpected response"), [])

    def test_cities_parser_no_guesses(self):
        self.assertEqual(
            b.parse_cities("1 Frankfurt\n2 Berlin\n"), ["Berlin", "Frankfurt"]
        )
        self.assertEqual(b.parse_cities("Please choose a city"), [])

    @patch.object(b.shutil, "which", return_value="/usr/bin/nmcli")
    @patch.object(b, "safe_vendor_binary", return_value=None)
    @patch.object(b, "run")
    def test_manual_connect(self, command, vendor, which):
        command.side_effect = ["", "openvpn:vpn\n"]
        result = b.operate("connect", "DE", "", "openvpn")
        self.assertEqual(result["state"], "connected")
        self.assertEqual(
            command.call_args_list[0].args[0],
            ["/usr/bin/nmcli", "connection", "up", "id", "openvpn"]
        )

    @patch.object(b, "safe_vendor_binary", return_value="/usr/bin/cyberghostvpn")
    @patch.object(b, "run")
    def test_official_cli_command(self, command, vendor):
        command.side_effect = ["", "Connected"]
        result = b.operate("connect", "DE", "Frankfurt", "openvpn")
        self.assertEqual(result["state"], "connected")
        self.assertEqual(
            command.call_args_list[0].args[0],
            ["/usr/bin/pkexec", "/usr/bin/cyberghostvpn", "--traffic",
             "--country-code", "DE", "--city", "Frankfurt", "--connect"]
        )

    @patch.object(b, "safe_vendor_binary", return_value="/usr/bin/cyberghostvpn")
    @patch.object(b, "run", return_value="Unexpected reply")
    def test_unknown_cli_status_not_connected(self, command, vendor):
        self.assertEqual(b.status("openvpn")["state"], "unknown")

    @patch.object(b.shutil, "which", return_value=None)
    @patch.object(b, "safe_vendor_binary", return_value=None)
    def test_missing_nmcli_is_unknown(self, vendor, which):
        self.assertEqual(b.status("openvpn")["state"], "unknown")

    @patch.object(b, "safe_vendor_binary", return_value=None)
    def test_no_fake_locations_without_authorized_client(self, vendor):
        result = b.locations("countries")
        self.assertEqual(result["items"], [])
        self.assertIn("official", result["reason"])


if __name__ == "__main__":
    unittest.main()
