"""Optional, isolated smoke tests for a locally built Arch package."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


PACKAGE = os.environ.get("CG_TEST_PACKAGE")
# Hash of the unmodified binary in the PKGBUILD's SHA-pinned vendor archive.
VENDOR_SHA256 = "038c202a969cf790081af9a7382025c5150b7495b76c63d08a765324e898164a"


class RecipeTests(unittest.TestCase):
    def test_checked_in_recipe_and_text_source_checksums_agree(self):
        root = Path(__file__).parents[1] / "packaging/cyberghostvpn"
        recipe = (root / "PKGBUILD").read_text()
        metadata = (root / ".SRCINFO").read_text()
        sources = re.findall(r"^\s*source = (.+)$", metadata, re.MULTILINE)
        checksums = re.findall(r"^\s*sha256sums = ([0-9a-f]{64})$", metadata, re.MULTILINE)
        self.assertEqual(len(sources), 4)
        self.assertEqual(len(sources), len(checksums))
        self.assertEqual(re.findall(r"'([0-9a-f]{64})'", recipe), checksums)
        self.assertTrue(sources[0].startswith("https://download.cyberghostvpn.com/linux/"))
        for source, expected in zip(sources[1:], checksums[1:]):
            self.assertEqual(Path(source).name, source)
            self.assertEqual(hashlib.sha256((root / source).read_bytes()).hexdigest(), expected)
        for name in ("pkgname", "pkgver", "pkgrel"):
            value = re.search(r"^" + name + r"=([A-Za-z0-9.-]+)$", recipe, re.MULTILINE)
            self.assertIsNotNone(value)
            self.assertRegex(metadata, r"(?m)^\s*" + name + " = " + re.escape(value[1]) + "$" )


@unittest.skipUnless(PACKAGE, "set CG_TEST_PACKAGE to a locally built CyberGhost package")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() == 0:
            raise RuntimeError("Refusing package integration tests as root")
        if not shutil.which("bsdtar"):
            raise RuntimeError("bsdtar is required for package inspection")
        cls.package = Path(PACKAGE).resolve(strict=True)
        cls.members = subprocess.run(["bsdtar", "-tf", str(cls.package)], check=True,
                                     capture_output=True, text=True).stdout.splitlines()
        listing = subprocess.run(["bsdtar", "-tvf", str(cls.package)], check=True,
                                 capture_output=True, text=True).stdout
        if any(Path(name.removeprefix("./")).name == ".INSTALL" for name in cls.members):
            raise AssertionError("package must not contain an .INSTALL scriptlet")
        key = next((line for line in listing.splitlines() if line.endswith("openvpn/client.key")), "")
        if not re.match(r"^-rw-------\s+\d+\s+root\s+root\s+\d+\s", key):
            raise AssertionError("client.key archive metadata must be root:root mode 0600")

        helper_member = "usr/local/cyberghost/update-systemd-resolved"
        if helper_member not in {name.removeprefix("./") for name in cls.members}:
            raise AssertionError("resolver helper is missing from package")
        cls.temp = tempfile.TemporaryDirectory(prefix="cg-package-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.helper = cls.root / "update-systemd-resolved"
        with cls.helper.open("wb") as output:
            subprocess.run(["bsdtar", "-xOf", str(cls.package), helper_member],
                           check=True, stdout=output)
        cls.script = cls.helper.read_text()
        guard = "refusing to rewrite resolv.conf"
        if guard not in cls.script or cls.script.index(guard) > cls.script.index('cp "${resolvConfFile}"'):
            raise AssertionError("patched early resolver guard is required before execution")
        subprocess.run(["/bin/bash", "-n", str(cls.helper)], check=True)

        cls.fakebin = cls.root / "bin"
        cls.fakebin.mkdir()
        cls.log = cls.root / "resolvectl.log"
        cls._mock("systemctl", '[ "${RESOLVED_ACTIVE:-0}" = 1 ] && exit 0\nexit 3\n')
        cls._mock("resolvectl", 'printf "%s\\n" "$@" >> "$CALL_LOG"\n'
                  '[ "${FAIL_COMMAND:-}" = "${1:-}" ] && exit 1\nexit 0\n')

    @classmethod
    def _mock(cls, name, body):
        path = cls.fakebin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o700)

    def run_hook(self, action, *, active=True, dns=True, fail_command=""):
        self.log.unlink(missing_ok=True)
        env = {"PATH": str(self.fakebin), "CALL_LOG": str(self.log),
               "RESOLVED_ACTIVE": "1" if active else "0",
               "FAIL_COMMAND": fail_command, "script_type": action}
        if dns:
            env["foreign_option_1"] = "dhcp-option DNS 10.8.0.1"
        return subprocess.run(["/bin/bash", str(self.helper), "tun0"],
                              env=env, capture_output=True, text=True, check=False)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_package_binary_hash_matches_vendor_without_writing_or_execution(self):
        binary = "usr/local/cyberghost/cyberghostvpn"
        self.assertIn(binary, {name.removeprefix("./") for name in self.members})
        contents = subprocess.run(["bsdtar", "-xOf", str(self.package), binary],
                                  check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(contents).hexdigest(), VENDOR_SHA256)

    def test_adapter_metadata_and_content_match_reviewed_source(self):
        member = "usr/local/cyberghost/omarchy-bridge"
        self.assertIn(member, {name.removeprefix("./") for name in self.members})
        listing = subprocess.run(["bsdtar", "-tvf", str(self.package)], check=True,
                                 capture_output=True, text=True).stdout
        entry = next(line for line in listing.splitlines() if line.endswith("omarchy-bridge"))
        self.assertRegex(entry, r"^-rwxr-xr-x\s+\d+\s+root\s+root\s+\d+\s")
        packaged = subprocess.run(["bsdtar", "-xOf", str(self.package), member],
                                  check=True, capture_output=True).stdout
        source = Path(__file__).parents[1] / "packaging/cyberghostvpn/omarchy-bridge"
        self.assertEqual(hashlib.sha256(packaged).digest(), hashlib.sha256(source.read_bytes()).digest())

    def test_polkit_policy_is_root_owned_auth_only_and_targets_the_helper(self):
        member = "usr/share/polkit-1/actions/org.petevo.cyberghost.policy"
        members = {name.removeprefix("./") for name in self.members}
        self.assertIn(member, members)

        listing = subprocess.run(["bsdtar", "-tvf", str(self.package)], check=True,
                                 capture_output=True, text=True).stdout
        entry = next(line for line in listing.splitlines() if line.endswith(member))
        self.assertRegex(entry, r"^-rw-r--r--\s+\d+\s+root\s+root\s+\d+\s")

        packaged = subprocess.run(["bsdtar", "-xOf", str(self.package), member],
                                  check=True, capture_output=True).stdout
        source = Path(__file__).parents[1] / "packaging/cyberghostvpn/org.petevo.cyberghost.policy"
        self.assertEqual(packaged, source.read_bytes())
        text = packaged.decode("utf-8")
        policy = ET.fromstring(text)
        actions = policy.findall("action")
        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action.get("id"), "org.petevo.cyberghost.manage")
        defaults = action.find("defaults")
        self.assertIsNotNone(defaults)
        self.assertEqual(defaults.findtext("allow_any"), "auth_admin")
        self.assertEqual(defaults.findtext("allow_inactive"), "auth_admin")
        self.assertEqual(defaults.findtext("allow_active"), "auth_admin_keep")
        annotate = action.find("annotate[@key='org.freedesktop.policykit.exec.path']")
        self.assertIsNotNone(annotate)
        self.assertEqual(annotate.text, "/usr/local/cyberghost/omarchy-bridge")
        self.assertNotRegex(text, r"<allow_(?:any|inactive|active)>\s*yes\s*</")
        self.assertFalse(any("polkit-1/rules.d/" in name for name in members))

    def test_active_resolved_up_sets_dns_then_default_domain(self):
        result = self.run_hook("up")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertLess(calls.index("dns"), calls.index("domain"))
        self.assertIn("10.8.0.1", calls)
        self.assertIn("~.", calls)
        self.assertEqual(calls[calls.index("default-route"):],
                         ["default-route", "--", "tun0", "true"])

    def test_down_reverts_tunnel_dns(self):
        result = self.run_hook("down")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["revert", "--", "tun0"])

    def test_inactive_resolved_fails_without_resolvectl(self):
        result = self.run_hook("up", active=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_missing_vpn_dns_fails_without_default_domain(self):
        result = self.run_hook("up", dns=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("domain", self.calls())

    def test_dns_failure_does_not_install_default_domain(self):
        result = self.run_hook("up", fail_command="dns")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), ["dns", "--", "tun0", "10.8.0.1"])

    def test_default_route_failure_is_reported(self):
        result = self.run_hook("up", fail_command="default-route")
        self.assertNotEqual(result.returncode, 0)
        calls = self.calls()
        self.assertIn("domain", calls)
        self.assertEqual(calls[calls.index("default-route"):],
                         ["default-route", "--", "tun0", "true"])


if __name__ == "__main__":
    unittest.main()
