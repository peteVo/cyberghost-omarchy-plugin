import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "cg_bridge_updates", Path(__file__).parents[1] / "cg_bridge.py"
)
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


API = "https://api.github.com/repos/peteVo/cyberghost-omarchy-plugin/releases?per_page=5"
CURL = ["/usr/bin/curl", "--disable", "--proto", "=https", "--silent", "--show-error", "--fail",
        "--connect-timeout", "3", "--max-time", "8", "--max-filesize", "100000", API]


def release(tag="v0.8.0", *, draft=False, prerelease=False, **extra):
    return {"draft": draft, "prerelease": prerelease, "tag_name": tag,
            "html_url": "https://github.com/peteVo/cyberghost-omarchy-plugin/releases/tag/" + tag,
            **extra}


class UpdatesTests(unittest.TestCase):
    def test_returns_only_valid_release_metadata_and_ignores_assets(self):
        payload = [release(assets=[{"browser_download_url": "https://evil.invalid/payload"}],
                           body="ignore me", zipball_url="https://evil.invalid/source")]
        with patch.object(b, "run", return_value=json.dumps(payload)) as run:
            result = b.updates()
        run.assert_called_once_with(CURL, timeout=10)
        self.assertEqual(result, {"release": {"tag": "v0.8.0", "url":
                         "https://github.com/peteVo/cyberghost-omarchy-plugin/releases/tag/v0.8.0",
                         "prerelease": False}})

    def test_accepts_beta_and_skips_drafts(self):
        payload = [release("v99.0.0", draft=True), release("v0.8.0-beta.12", prerelease=True)]
        with patch.object(b, "run", return_value=json.dumps(payload)):
            self.assertEqual(b.updates()["release"], {
                "tag": "v0.8.0-beta.12",
                "url": "https://github.com/peteVo/cyberghost-omarchy-plugin/releases/tag/v0.8.0-beta.12",
                "prerelease": True,
            })

    def test_no_published_releases_returns_null(self):
        with patch.object(b, "run", return_value=json.dumps([release("v1.0.0", draft=True)])):
            self.assertEqual(b.updates(), {"release": None})

    def test_malformed_or_untrusted_release_data_is_rejected(self):
        invalid = [
            "{}",
            "[1]",
            json.dumps([{"draft": False, "prerelease": False}]),
            json.dumps([release("v1.2.3;curl evil")]),
            json.dumps([release("https://evil.invalid")]),
            json.dumps([release(html_url="https://evil.invalid/redirect")]),
            json.dumps([release(prerelease="false")]),
            "not json",
        ]
        for output in invalid:
            with self.subTest(output=output), patch.object(b, "run", return_value=output):
                with self.assertRaises(b.BridgeError) as raised:
                    b.updates()
                self.assertEqual(raised.exception.code, "invalid_response")
                self.assertNotIn("evil", str(raised.exception))
                self.assertNotIn(output[:20], str(raised.exception))

    def test_timeout_and_network_errors_are_sanitized_by_command_runner(self):
        failures = [
            subprocess.TimeoutExpired(CURL, 10),
            OSError("socket failure at /private/account"),
        ]
        for error in failures:
            with self.subTest(error=type(error).__name__), \
                 patch.object(b.subprocess, "run", side_effect=error) as subprocess_run:
                with self.assertRaises(b.BridgeError) as raised:
                    b.updates()
                self.assertIn(raised.exception.code, ("timeout", "dependency"))
                self.assertNotIn("private", str(raised.exception))
                called = subprocess_run.call_args
                self.assertEqual(called.args[0], CURL)
                self.assertEqual(called.kwargs["timeout"], 10)

    def test_dispatch_routes_updates_before_profile_validation(self):
        args = SimpleNamespace(action="updates", backend="invalid", profile="invalid\nprofile")
        expected = {"release": None}
        with patch.object(b, "updates", return_value=expected) as updates, \
             patch.object(b, "validate_profile", side_effect=AssertionError("profile validated")), \
             patch.object(b, "status", side_effect=AssertionError("status read")):
            result = b.dispatch(args)
        updates.assert_called_once_with()
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
