import unittest
import json
from unittest.mock import patch
import cg_bridge as bridge
from cg_bridge import traffic_totals


class TrafficTests(unittest.TestCase):
    def test_kernel_counters_include_real_zero_and_prefer_64bit(self):
        self.assertEqual(traffic_totals({"stats64": {"rx": {"bytes": 0}, "tx": {"bytes": 2048}},
                                        "stats": {"rx": {"bytes": 4}, "tx": {"bytes": 5}}}),
                         {"download_bytes": 0, "upload_bytes": 2048})

    def test_missing_malformed_and_unsafe_counters_stay_unknown(self):
        for stats in (None, [], {}, {"rx": None}, {"rx": {"bytes": True}, "tx": {"bytes": 2}},
                      {"rx": {"bytes": -1}, "tx": {"bytes": 2}},
                      {"rx": {"bytes": 2**53}, "tx": {"bytes": 2}},
                      {"rx": {"bytes": "4"}, "tx": {"bytes": 2}}):
            with self.subTest(stats=stats):
                self.assertEqual(traffic_totals({"stats64": stats}),
                                 {"download_bytes": None, "upload_bytes": None})

    def test_legacy_counter_format_is_supported(self):
        self.assertEqual(traffic_totals({"stats": {"rx": {"bytes": 1024}, "tx": {"bytes": 2}}}),
                         {"download_bytes": 1024, "upload_bytes": 2})


    def test_status_uses_only_the_selected_tunnel_counters(self):
        links = [{"ifname": "other", "linkinfo": {"info_kind": "wireguard"}, "flags": ["UP"],
                  "stats64": {"rx": {"bytes": 999}, "tx": {"bytes": 888}}},
                 {"ifname": "cyberghost", "ifindex": 7, "linkinfo": {"info_kind": "wireguard"},
                  "flags": ["UP"], "stats64": {"rx": {"bytes": 12}, "tx": {"bytes": 34}}}]
        with patch.object(bridge, "run", side_effect=[json.dumps(links), '[{"dev":"cyberghost"}]']) as run:
            result = bridge.kernel_tunnel_status("WireGuard")
        self.assertEqual(result["state"], "connected")
        self.assertEqual((result["download_bytes"], result["upload_bytes"]), (12, 34))
        self.assertIn("-s", run.call_args_list[0].args[0])
