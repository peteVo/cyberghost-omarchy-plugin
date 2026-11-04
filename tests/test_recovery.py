"""Guarded retries use no credentials or real networking in these checks."""
from contextlib import nullcontext
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cg_bridge as b

source = Path(__file__).parents[1] / 'packaging/cyberghostvpn/omarchy-bridge'
loader = SourceFileLoader('recovery_adapter', str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
a = importlib.util.module_from_spec(spec)
loader.exec_module(a)
ARGV = ['--traffic', '--country-code', 'DE', '--wireguard', '--recover']


class GuardedRecoveryTests(unittest.TestCase):
    def guard(self, **changes):
        return {'uid': os.getuid(), 'device': 'cyberghost', 'interface_index': 7,
                'mark': 42, 'kill_switch': False, 'phase': 'active', 'fingerprint': 'a' * 64, **changes}

    def test_root_recovery_requires_owned_matching_active_ipv6_guard_and_absence(self):
        guard = self.guard()
        for state, fingerprint, absent in (
            (None, 'a' * 64, True), ({**guard, 'uid': guard['uid'] + 1}, 'a' * 64, True),
            ({**guard, 'kill_switch': True}, 'a' * 64, True),
            ({**guard, 'phase': 'prepared'}, 'a' * 64, True),
            (guard, 'b' * 64, True), (guard, 'a' * 64, False),
        ):
            with self.subTest(state=state, absent=absent), \
                 patch.object(a.os, 'geteuid', return_value=0), \
                 patch.dict(a.os.environ, {'PKEXEC_UID': str(guard['uid'])}, clear=True), \
                 patch.object(a.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir='/home/test', pw_name='test')), \
                 patch.object(a, 'root_lock', return_value=nullcontext()), \
                 patch.object(a, 'guard_state', return_value=state), \
                 patch.object(a, 'guard_fingerprint', return_value=fingerprint), \
                 patch.object(a, 'tunnel_absent', return_value=absent), \
                 patch.object(a, 'ipv6_namespace') as namespace, patch.object(a, 'vendor') as vendor:
                with self.assertRaises((ValueError, RuntimeError)):
                    a.main(ARGV)
                namespace.assert_not_called()
                vendor.assert_not_called()

    def test_root_recovery_connects_once_without_preemptive_stop_or_guard_removal(self):
        guard = self.guard()
        with patch.object(a.os, 'geteuid', return_value=0), \
             patch.dict(a.os.environ, {'PKEXEC_UID': str(guard['uid'])}, clear=True), \
             patch.object(a.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir='/home/test', pw_name='test')), \
             patch.object(a, 'root_lock', return_value=nullcontext()), \
             patch.object(a, 'guard_state', return_value=guard), \
             patch.object(a, 'guard_fingerprint', return_value='a' * 64), \
             patch.object(a, 'tunnel_absent', return_value=True), \
             patch.object(a, 'ipv6_namespace'), patch.object(a, 'prepare_guard') as stage, \
             patch.object(a, 'apply_guard') as apply, patch.object(a, 'remove_guard') as remove, \
             patch.object(a, 'vendor', return_value=0) as vendor:
            self.assertEqual(a.main(ARGV), 0)
        stage.assert_called_once_with(guard['uid'])
        vendor.assert_called_once()
        self.assertEqual(vendor.call_args.args[0], ARGV[:-1] + ['--connect'])
        apply.assert_called_once_with(guard['uid'], False)
        remove.assert_not_called()

    def test_recovery_staging_failure_does_not_stop_vendor_and_connect_failure_retains_guard(self):
        guard = self.guard()
        for stage_fails in (True, False):
            with self.subTest(stage_fails=stage_fails), patch.object(a.os, 'geteuid', return_value=0), \
                 patch.dict(a.os.environ, {'PKEXEC_UID': str(guard['uid'])}, clear=True), \
                 patch.object(a.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir='/home/test', pw_name='test')), \
                 patch.object(a, 'root_lock', return_value=nullcontext()), \
                 patch.object(a, 'guard_state', return_value=guard), \
                 patch.object(a, 'guard_fingerprint', return_value='a' * 64), \
                 patch.object(a, 'tunnel_absent', return_value=True), \
                 patch.object(a, 'ipv6_namespace'), \
                 patch.object(a, 'prepare_guard', side_effect=RuntimeError() if stage_fails else None), \
                 patch.object(a, 'retain_recovery_guard') as retain, \
                 patch.object(a, 'remove_guard') as remove, \
                 patch.object(a, 'vendor', return_value=1) as vendor:
                if stage_fails:
                    with self.assertRaises(RuntimeError):
                        a.main(ARGV)
                    vendor.assert_not_called()
                else:
                    self.assertEqual(a.main(ARGV), 1)
                    self.assertEqual([c.args[0] for c in vendor.call_args_list], [ARGV[:-1] + ['--connect'], ['--stop']])
                retain.assert_called_once_with(guard['uid'])
                remove.assert_not_called()

    def test_recovery_grammar_never_accepts_full_kill_switch_or_other_protocol(self):
        a.validate(ARGV)
        for options in ([], ['--openvpn'], ['--wireguard', '--kill-switch']):
            with self.subTest(options=options), self.assertRaises(ValueError):
                a.validate(ARGV[:3] + options + ['--recover'])

    def test_failed_recovery_retains_guard_without_resolver_bootstrap_exception(self):
        with patch.object(a, 'vendor', side_effect=RuntimeError('failed teardown')), \
             patch.object(a, 'remove_guard') as remove, patch.object(a, 'install_guard') as install:
            a.rollback(1000, False, {}, retain_guard=True)
        remove.assert_not_called()
        self.assertEqual(install.call_args.args[1:], (None, False, 'prepared'))
        self.assertNotIn('bootstrap_uid', install.call_args.kwargs)

    def test_retry_validates_confirmed_target_without_catalog_dns_or_guessing(self):
        guard = self.guard()
        current = dict(state='recovery-required', can_recover=True, uplink_ready=True)
        connected = dict(state='connected', protocol='WireGuard', device='cyberghost', interface_index=9)
        target = dict(country='DE', city='Frankfurt', server='frankfurt-s1-i01')
        with patch.object(b, 'prerequisites', return_value=[]), \
             patch.object(b, 'active_connections', return_value=[]), \
             patch.object(b, 'vendor_binary', return_value='/usr/local/cyberghost/cyberghostvpn'), \
             patch.object(b, 'privileged_command', return_value=['/usr/bin/pkexec', '/adapter']) as privileged, \
             patch.object(b, 'traffic_protection', return_value=guard), \
             patch.object(b, 'status', side_effect=[current, connected]), \
             patch.object(b, 'saved_details', side_effect=[target, {}]), \
             patch.object(b, 'save_details'), patch.object(b, 'locations') as catalogs, \
             patch.object(b, 'run', return_value='') as run:
            result = b.operate('recover', 'DE', 'Frankfurt', 'cyberghost', 'official-cli', 'wireguard', target['server'])
        self.assertEqual(result['state'], 'connected')
        catalogs.assert_not_called()
        self.assertEqual(run.call_args.args[0], ['/usr/bin/pkexec', '/adapter', '--traffic', '--country-code', 'DE',
                                                '--city', 'Frankfurt', '--server', target['server'], '--wireguard', '--recover'])
        self.assertEqual(privileged.call_args.kwargs, {'min_api': 6})

    def test_retry_refuses_a_different_or_missing_confirmed_target_before_mutation(self):
        guard = self.guard()
        for target in ({}, dict(country='NL', city='', server='')):
            with self.subTest(target=target), patch.object(b, 'prerequisites', return_value=[]), \
                 patch.object(b, 'active_connections', return_value=[]), \
                 patch.object(b, 'vendor_binary', return_value='/usr/local/cyberghost/cyberghostvpn'), \
                 patch.object(b, 'privileged_command', return_value=['/usr/bin/pkexec', '/adapter']), \
                 patch.object(b, 'traffic_protection', return_value=guard), \
                 patch.object(b, 'status', return_value=dict(state='recovery-required', can_recover=True, uplink_ready=True)), \
                 patch.object(b, 'saved_details', return_value=target), patch.object(b, 'run') as run:
                with self.assertRaises(b.BridgeError) as caught:
                    b.operate('recover', 'DE', '', 'cyberghost', 'official-cli', 'wireguard')
                self.assertEqual(caught.exception.code, 'unconfirmed')
                run.assert_not_called()

    def test_status_offers_guarded_retry_only_for_api6_active_nonkill_guard(self):
        for api, phase, kill, expected in ((6, 'active', False, True), (5, 'active', False, False),
                                           (6, 'prepared', False, False), (6, 'active', True, False)):
            guard = {**self.guard(), 'phase': phase, 'kill_switch': kill}
            with self.subTest(api=api, phase=phase, kill=kill), \
                 patch.object(b, 'traffic_protection', return_value=guard), \
                 patch.object(b, 'vendor_binary', return_value='/usr/local/cyberghost/cyberghostvpn'), \
                 patch.object(b, 'wireguard_status', return_value=None), \
                 patch.object(b, 'active_connections', return_value=[]), \
                 patch.object(b, 'helper_api', return_value=api), patch.object(b, 'uplink_ready', return_value=True):
                result = b.status('cyberghost', 'official-cli')
            self.assertEqual(result['can_recover'], expected)
            self.assertFalse(result['can_connect'])

    def test_private_retry_target_keeps_auto_selection_separate_from_reported_server(self):
        snapshot = dict(state='connected', protocol='WireGuard', device='cyberghost', interface_index=7)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_STATE_HOME': directory}):
            b.save_details(snapshot, 'DE', 'Frankfurt', '', 'Connected frankfurt-s1-i01',
                           known_servers=('frankfurt-s1-i01',))
            self.assertEqual(b.saved_details(snapshot)['server'], 'frankfurt-s1-i01')
            self.assertEqual(b.saved_details(snapshot, target_only=True),
                             dict(country='DE', city='Frankfurt', server=''))
            self.assertEqual(b.saved_details({**snapshot, 'interface_index': 8}, target_only=True), {})

    def test_old_helper_rejects_guarded_retry(self):
        with patch.object(b, 'safe_system_binary', return_value='/usr/local/cyberghost/omarchy-bridge'), \
             patch.object(b, 'run', return_value='omarchy-bridge 5\n'):
            with self.assertRaises(b.BridgeError) as caught:
                b.privileged_command('/usr/local/cyberghost/cyberghostvpn', min_api=6)
        self.assertEqual(caught.exception.code, 'dependency')
