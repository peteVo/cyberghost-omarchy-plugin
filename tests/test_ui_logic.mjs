import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const qml = readFileSync(new URL('../BarWidget.qml', import.meta.url), 'utf8');

function functionSource(name) {
  const match = qml.match(new RegExp(`^  function ${name}\\([^\\n]*\\) \\{[\\s\\S]*?^  \\}`, 'm'));
  assert.ok(match, `BarWidget.qml is missing ${name}()`);
  return match[0];
}

function widget() {
  const calls = { invoke: [], notify: [], persist: [], later: [] };
  let context;
  let peers;
  context = {
    now: 100_000,
    Date: { now: () => context.now },
    runner: '/plugin/cg_bridge.py', profileName: 'cyberghost',
    Quickshell: { execDetached: args => calls.notify.push(args) },
    Qt: { callLater: fn => calls.later.push(fn) },
    settings: {}, moduleName: 'test', bar: { moduleWidgets: () => peers },
    snapshot: { state: 'disconnected', can_connect: true },
    backendMode: 'official-cli', dynamicMode: true, setupReady: true,
    working: false, protocolRefresh: false, selectedProtocol: 'wireguard',
    selectedCountry: '', selectedCity: '', selectedServer: '', selectionRevision: 0,
    pendingCountry: '', pendingCity: '', quickConnecting: false,
    favoriteToApply: null, quickTarget: null, quickTargetKey: '', favorites: [],
    awaiting: false, pending: '', pendingRevision: 0, helperExit: 0,
    process: { running: false }, output: { text: '' },
    setupChecks: [], setupMessage: '',
    panelLoader: { item: null },
    notifications: true, observedState: '', statusFailed: false,
    opened: false,
    recoveryEnabled: false, recoveryArmed: false, recoveryInFlight: false,
    recoveryTarget: null, recoveryAttempts: 0, recoveryRevision: 0, recoveryIndex: 0,
    recoveryKillSwitch: false, recoveryNextAt: 0, recoveryLastClock: 0,
    recoveryMessage: 'Off', statusStale: false, uplink_ready: true,
    lastStatusAt: 0, verificationAt: 0, publicIpAt: 0,
    protectionCheck: '', publicIp: '', clockNow: 100_000, message: '',
    discovery: { items: [], reason: '' }, cities: { items: [], reason: '' },
    servers: { items: [], reason: '' }, killSwitch: false,
    invoke(task) {
      calls.invoke.push(task);
      context.pending = task;
      context.pendingCountry = context.selectedCountry;
      context.pendingCity = context.selectedCity;
      context.pendingRevision = context.selectionRevision;
    },
    resetLocations() { context.cities = { items: [], reason: '' }; context.servers = { items: [], reason: '' }; context.selectedCity = ''; context.selectedServer = ''; },
    persistSettings(values) { calls.persist.push(values); },
    refresh() {},
    calls,
  };
  context.root = context;
  peers = [context];
  for (const name of ['validTarget', 'favoriteKey', 'startSavedTarget', 'quickConnect', 'completeSavedTarget', 'selectServer', 'cancelSavedTarget', 'cancelQuickConnect', 'notify', 'observeState', 'observeRecovery', 'recoverableState', 'setRecovery', 'stopRecovery', 'clearHealth', 'noteStateFailure', 'selectBackend', 'selectProfile', 'selectCountry', 'arrayFrom', 'finish']) {
    vm.runInNewContext(functionSource(name), context);
  }
  return context;
}

function finish(w, task, data) {
  w.pending = task;
  w.awaiting = true;
  w.helperExit = 0;
  w.output.text = JSON.stringify({ ok: true, ...data });
  w.finish();
}

function fail(w, task, error, code) {
  w.pending = task;
  w.awaiting = true;
  w.helperExit = 1;
  w.output.text = JSON.stringify({ ok: false, error, ...(code ? { code } : {}) });
  w.finish();
}

const plain = value => JSON.parse(JSON.stringify(value));

test('saved targets reject malformed identities while accepting Any city', () => {
  const w = widget();
  assert.equal(w.validTarget({ country: 'DE', city: '', protocol: 'wireguard', server: '' }), true);
  for (const target of [null, [], { country: 'de', protocol: 'wireguard' },
    { country: 'DE', protocol: 'bogus' }, { country: 'DE', city: 3, protocol: 'auto' },
    { country: 'DE', city: '', protocol: 'wireguard', server: 'bad server' }])
    assert.equal(!!w.validTarget(target), false);
});

test('Quick Connect honors a selected favorite key and falls back only when no key is selected', () => {
  const binding = qml.match(/^  readonly property var quickTarget: ([\s\S]*?)\n  property string publicIp/m)?.[1];
  assert.ok(binding, 'BarWidget.qml is missing quickTarget binding');
  const w = widget();
  const last = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  const selected = { country: 'NL', city: 'Amsterdam', protocol: 'wireguard', server: '' };
  w.lastSuccessful = last;
  w.favorites = [selected];

  w.quickTargetKey = JSON.stringify(['BE', '', 'wireguard', '']);
  assert.equal(vm.runInNewContext(binding, w), null);
  w.quickTargetKey = w.favoriteKey(selected);
  assert.equal(vm.runInNewContext(binding, w), selected);
  w.quickTargetKey = '';
  assert.equal(vm.runInNewContext(binding, w), last);
});

test('Quick Connect starts fresh discovery for its saved target, then defers connect', () => {
  const w = widget();
  const target = { country: 'NL', city: '', protocol: 'wireguard', server: '' };
  w.quickTarget = target;
  w.quickConnect();
  assert.deepEqual(w.calls.invoke, ['countries']);
  assert.equal(w.favoriteToApply.country, 'NL');
  assert.equal(w.quickConnecting, true);
  assert.deepEqual(plain(w.calls.persist), [{ protocol: 'wireguard' }]);

  w.completeSavedTarget();
  assert.deepEqual(w.calls.invoke, ['countries']);
  assert.equal(w.quickConnecting, false);
  assert.equal(w.calls.later.length, 1);
  w.calls.later[0]();
  assert.deepEqual(w.calls.invoke, ['countries', 'connect']);
});

test('Quick Connect validates fresh country, city, and server lists before connecting', () => {
  const w = widget();
  w.quickTarget = { country: 'NL', city: 'Amsterdam', protocol: 'wireguard', server: 'nl-ams-001' };
  w.quickConnect();
  finish(w, 'countries', { items: [{ code: 'NL', name: 'Netherlands' }] });
  assert.equal(w.calls.later.length, 1);
  w.calls.later.shift()();
  assert.deepEqual(w.calls.invoke, ['countries', 'cities']);
  finish(w, 'cities', { items: ['Amsterdam'] });
  assert.deepEqual(w.calls.invoke, ['countries', 'cities', 'servers']);
  finish(w, 'servers', { items: [{ name: 'nl-ams-001' }] });
  assert.equal(w.calls.later.length, 1);
  w.calls.later.shift()();
  assert.deepEqual(w.calls.invoke, ['countries', 'cities', 'servers', 'connect']);
  assert.equal(w.selectedServer, 'nl-ams-001');
});

test('Quick Connect aborts unavailable country, city, or server without substituting', () => {
  for (const [task, data] of [
    ['countries', { items: [{ code: 'DE', name: 'Germany' }] }],
    ['cities', { items: ['Berlin'] }],
    ['servers', { items: [{ name: 'nl-ams-002' }] }],
  ]) {
    const w = widget();
    w.quickTarget = { country: 'NL', city: 'Amsterdam', protocol: 'wireguard', server: 'nl-ams-001' };
    w.quickConnect();
    if (task !== 'countries') {
      finish(w, 'countries', { items: [{ code: 'NL', name: 'Netherlands' }] });
      w.calls.later.shift()();
    }
    if (task === 'servers') finish(w, 'cities', { items: ['Amsterdam'] });
    finish(w, task, data);
    assert.equal(w.favoriteToApply, null);
    assert.equal(w.quickConnecting, false);
    assert.equal(w.calls.invoke.includes('connect'), false);
    assert.equal(w.selectedCountry, 'NL');
    assert.equal(w.selectedCity, task === 'servers' ? 'Amsterdam' : '');
    assert.equal(w.selectedServer, '');
    assert.equal(w.calls.later.length, 0);
  }
});

test('Quick Connect is gated by fresh setup, disconnected state, and kill-switch protocol', () => {
  const w = widget();
  w.quickTarget = { country: 'DE', city: '', protocol: 'openvpn', server: '' };
  w.setupReady = false;
  w.quickConnect();
  assert.deepEqual(w.calls.invoke, []);
  w.setupReady = true;
  w.killSwitch = true;
  w.quickConnect();
  assert.deepEqual(w.calls.invoke, []);
  assert.match(w.message, /WireGuard/);
  w.killSwitch = false;
  w.snapshot.state = 'connected';
  w.quickConnect();
  assert.deepEqual(w.calls.invoke, []);
});

test('cancellation and stale state prevent the deferred connection', () => {
  const w = widget();
  w.quickTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  w.quickConnect();
  w.completeSavedTarget();
  w.cancelQuickConnect();
  w.calls.later[0]();
  assert.deepEqual(w.calls.invoke, ['countries']);
  assert.match(w.message, /cancelled/i);

  const w2 = widget();
  w2.quickTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  w2.quickConnect();
  w2.completeSavedTarget();
  w2.snapshot.state = 'connected';
  w2.calls.later[0]();
  assert.deepEqual(w2.calls.invoke, ['countries']);

  const w3 = widget();
  w3.quickTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  w3.quickConnect();
  w3.completeSavedTarget();
  w3.selectServer('another-discovered-server');
  w3.calls.later[0]();
  assert.deepEqual(w3.calls.invoke, ['countries']);
});

test('only a confirmed dynamic connect or switch remembers a valid target', () => {
  const w = widget();
  w.pendingCountry = 'NL'; w.pendingCity = ''; w.selectedProtocol = 'wireguard'; w.selectedServer = '';
  w.observeState({ state: 'connecting' }, 'connect');
  assert.deepEqual(w.calls.persist, []);
  w.observeState({ state: 'connected' }, 'connect');
  assert.deepEqual(plain(w.calls.persist), [{ lastSuccessful: { country: 'NL', city: '', protocol: 'wireguard', server: '' } }]);
  w.dynamicMode = false;
  w.observeState({ state: 'connected' }, 'switch');
  assert.equal(w.calls.persist.length, 1);
});

test('failed connection does not replace the last successful target', () => {
  const w = widget();
  w.lastSuccessful = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  w.pendingCountry = 'NL';
  w.selectedProtocol = 'openvpn';
  fail(w, 'connect', 'backend unavailable');
  assert.equal(w.lastSuccessful.country, 'DE');
  assert.deepEqual(w.calls.persist, []);
});

test('initial observations stay quiet; repeated states are quiet and notices are generic', () => {
  const w = widget();
  w.observeState({ state: 'disconnected' }, 'status');
  assert.deepEqual(w.calls.notify, []);
  w.observeState({ state: 'disconnected' }, 'status');
  assert.deepEqual(w.calls.notify, []);
  w.observeState({ state: 'connected', device: 'sensitive' }, 'connect');
  assert.equal(w.calls.notify.length, 1);
  assert.deepEqual(plain(w.calls.notify[0]), ['/usr/bin/omarchy', 'notification', 'send', '--app-name', 'CyberGhost for Omarchy', 'VPN connected', 'Connection reported. Check Details for routing and protection observations.']);
  assert.equal(w.calls.notify[0].includes('sensitive'), false);
});

test('notification opt-out and monitor dedup suppress passive notices but allow operations', () => {
  const w = widget();
  w.notifications = false;
  w.notify('VPN connected', 'generic', true);
  assert.deepEqual(w.calls.notify, []);

  w.notifications = true;
  w.bar.moduleWidgets = () => [{}, w];
  w.notify('VPN needs attention', 'generic');
  assert.deepEqual(w.calls.notify, []);
  w.notify('VPN connected', 'generic', true);
  assert.equal(w.calls.notify.length, 1);
  assert.deepEqual(plain(w.calls.notify[0].slice(0, 6)), ['/usr/bin/omarchy', 'notification', 'send', '--app-name', 'CyberGhost for Omarchy', 'VPN connected']);
});

test('backend and profile resets cancel pending saved-target intent', () => {
  for (const action of ['selectBackend', 'selectProfile']) {
    const w = widget();
    w.favoriteToApply = { country: 'DE', protocol: 'wireguard' };
    w.quickConnecting = true;
    if (action === 'selectBackend') w.selectBackend('manual-profile');
    else w.selectProfile('cyberghost');
    assert.equal(w.favoriteToApply, null);
    assert.equal(w.quickConnecting, false);
  }
});

test('stale country response cannot overwrite a newer selection', () => {
  const w = widget();
  w.quickTarget = { country: 'NL', city: '', protocol: 'wireguard', server: '' };
  w.quickConnect();
  w.selectionRevision++;
  finish(w, 'countries', { items: [{ code: 'NL', name: 'Netherlands' }] });
  assert.deepEqual(plain(w.discovery), { items: [], reason: 'Checking saved country…' });
  assert.equal(w.calls.later.length, 0);
});

test('health reset and state failure invalidate status and protection freshness', () => {
  const w = widget();
  Object.assign(w, { lastStatusAt: 100, statusFailed: false, verificationAt: 90,
    publicIpAt: 80, protectionCheck: 'verified', observedState: 'connected' });
  w.clearHealth();
  assert.equal(w.lastStatusAt, 0);
  assert.equal(w.statusFailed, false);
  assert.equal(w.verificationAt, 0);
  assert.equal(w.publicIpAt, 0);
  assert.equal(w.protectionCheck, '');
  assert.equal(w.observedState, '');
  w.noteStateFailure();
  assert.equal(w.statusFailed, true);
  assert.equal(w.observedState, 'unknown');
  assert.equal(w.verificationAt, 0);
});

test('invalid protection result clears the previous verification timestamp', () => {
  const w = widget();
  w.verificationAt = 90_000;
  w.protectionCheck = 'Last check: rules and tunnel matched.';
  finish(w, 'verify-protection', { protection_verified: 'true' });
  assert.equal(w.verificationAt, 0);
  assert.equal(w.protectionCheck, '');
});

test('status age becomes stale at 45 seconds and when the clock moves backwards', () => {
  const expression = qml.match(/^  readonly property bool statusStale: (.+)$/m)?.[1];
  assert.ok(expression, 'BarWidget.qml is missing statusStale binding');
  const w = widget();
  const stale = () => vm.runInNewContext(expression, w);
  assert.equal(stale(), true);
  w.lastStatusAt = 70_000;
  assert.equal(stale(), false);
  w.lastStatusAt = 54_999;
  assert.equal(stale(), true);
  w.lastStatusAt = 100_001;
  assert.equal(stale(), true);
});

test('session recovery defaults off and arms only after an explicit successful WireGuard operation', () => {
  const w = widget();
  assert.equal(w.recoveryEnabled, false);
  assert.equal(w.recoveryArmed, false);
  w.setRecovery(true);
  assert.equal(w.recoveryEnabled, true);
  assert.equal(w.recoveryArmed, false);

  w.pendingCountry = 'NL'; w.pendingCity = 'Amsterdam'; w.selectedProtocol = 'wireguard';
  w.selectedServer = 'nl-ams-s1'; w.killSwitch = true;
  w.observeState({ state: 'connected', protocol: 'WireGuard', device: 'cyberghost',
    interface_index: 23, ipv6_guard: true, kill_switch: true }, 'connect');
  assert.equal(w.recoveryArmed, true);
  assert.deepEqual(plain(w.recoveryTarget), {
    country: 'NL', city: 'Amsterdam', protocol: 'wireguard', server: 'nl-ams-s1',
  });
  assert.equal(w.recoveryIndex, 23);
  assert.equal(w.recoveryKillSwitch, true);
  assert.equal(w.recoveryAttempts, 0);

  const noAuth = widget();
  noAuth.recoveryEnabled = true;
  noAuth.pendingCountry = 'DE'; noAuth.selectedProtocol = 'openvpn';
  noAuth.observeState({ state: 'connected', protocol: 'OpenVPN', interface_index: 8 }, 'connect');
  assert.equal(noAuth.recoveryArmed, false);
});

test('recovery preserves its frozen target and invokes only the normal connect task', () => {
  const w = widget();
  w.recoveryEnabled = true; w.recoveryArmed = true;
  w.recoveryTarget = { country: 'NL', city: 'Amsterdam', protocol: 'wireguard', server: 'nl-ams-s1' };
  w.recoveryKillSwitch = true;
  w.snapshot = { state: 'disconnected', can_connect: true, uplink_ready: true };
  w.setupReady = true; w.statusStale = false; w.statusFailed = false;
  w.profileName = 'cyberghost'; w.runner = '/plugin/cg_bridge.py';
  w.process = { running: false };
  vm.runInNewContext(functionSource('invoke'), w);

  w.selectedCountry = 'DE'; w.selectedCity = ''; w.selectedProtocol = 'openvpn'; w.selectedServer = '';
  w.invoke('recover');
  assert.equal(w.recoveryAttempts, 1);
  assert.equal(w.recoveryInFlight, true);
  assert.deepEqual(plain(w.process.command), [
    '/usr/bin/python3', '/plugin/cg_bridge.py', 'connect', '--backend', 'official-cli',
    '--profile', 'cyberghost', '--protocol', 'wireguard', '--country', 'NL',
    '--city', 'Amsterdam', '--server', 'nl-ams-s1', '--kill-switch',
  ]);
});

test('manual disconnect and recovery toggle cancel queued recovery', () => {
  for (const cancel of [w => w.invoke('disconnect'), w => w.setRecovery(false)]) {
    const w = widget();
    w.recoveryEnabled = true; w.recoveryArmed = true;
    w.recoveryTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
    w.recoveryNextAt = 70_000;
    w.snapshot = { state: 'disconnected', can_connect: true, uplink_ready: true };
    w.setupReady = true; w.statusStale = false;
    vm.runInNewContext(functionSource('invoke'), w);
    w.lastStatusAt = 99_000; w.clockNow = 100_000;
    w.observeRecovery({ state: 'disconnected', can_connect: true, uplink_ready: true }, 'status');
    assert.equal(w.calls.later.length, 1);
    cancel(w);
    w.calls.later[0]();
    assert.equal(w.calls.invoke.includes('recover'), false);
  }
});

test('recovery keeps a surviving tunnel and waits for uplink, fresh status, and its delay', () => {
  const w = widget();
  w.recoveryEnabled = true; w.recoveryArmed = true; w.recoveryIndex = 23;
  w.recoveryTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  w.snapshot = { state: 'waiting-network', can_connect: false, interface_index: 23 };
  w.observeRecovery({ state: 'waiting-network', interface_index: 23 }, 'status');
  assert.equal(w.recoveryArmed, true);
  assert.match(w.recoveryMessage, /Keeping the existing tunnel/);
  assert.equal(w.calls.later.length, 0);

  w.snapshot = { state: 'disconnected', can_connect: true, uplink_ready: false };
  w.observeRecovery({ state: 'disconnected', can_connect: true, uplink_ready: false }, 'status');
  assert.equal(w.calls.later.length, 0);
  assert.equal(w.recoveryAttempts, 0);

  w.snapshot = { state: 'disconnected', can_connect: true, uplink_ready: true };
  w.lastStatusAt = 99_000; w.clockNow = 100_000;
  w.observeRecovery({ state: 'disconnected', can_connect: true, uplink_ready: true }, 'status');
  assert.equal(w.calls.later.length, 0);
  w.now += 15_000;
  w.observeRecovery({ state: 'disconnected', can_connect: true, uplink_ready: true }, 'status');
  assert.equal(w.calls.later.length, 0);
  w.now += 15_000;
  w.observeRecovery({ state: 'disconnected', can_connect: true, uplink_ready: true }, 'status');
  assert.equal(w.calls.later.length, 1);
  w.statusStale = true;
  w.calls.later.shift()();
  assert.equal(w.calls.invoke.includes('recover'), false);
  w.statusStale = false;
  w.observeRecovery({ state: 'disconnected', can_connect: true, uplink_ready: true }, 'status');
  w.calls.later.shift()();
  assert.deepEqual(w.calls.invoke, ['recover']);
});

test('recovery stops on blocked or protection-owned state and caps the session at two attempts', () => {
  for (const data of [
    { state: 'blocked', can_connect: false },
    { state: 'disconnected', can_connect: true, can_release_protection: true, uplink_ready: true },
  ]) {
    const w = widget();
    w.recoveryEnabled = true; w.recoveryArmed = true;
    w.recoveryTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
    w.observeRecovery(data, 'status');
    assert.equal(w.recoveryArmed, false);
    assert.equal(w.calls.later.length, 0);
  }

  const w = widget();
  w.recoveryEnabled = true; w.recoveryArmed = true;
  w.recoveryTarget = { country: 'DE', city: '', protocol: 'wireguard', server: '' };
  w.snapshot = { state: 'disconnected', can_connect: true, uplink_ready: true };
  w.setupReady = true; w.statusStale = false;
  w.runner = '/plugin/cg_bridge.py';
  vm.runInNewContext(functionSource('invoke'), w);
  w.invoke('recover'); w.awaiting = false; w.process.running = false;
  w.invoke('recover'); w.awaiting = false; w.process.running = false;
  w.invoke('recover');
  assert.equal(w.recoveryAttempts, 2);
  assert.equal(w.calls.invoke.length, 0);
  assert.equal(w.process.command[2], 'connect');
});

test('successful recovery does not reset its per-connection attempt budget', () => {
  const w = widget();
  w.recoveryEnabled = true; w.recoveryArmed = true; w.recoveryAttempts = 1;
  w.recoveryIndex = 23;
  w.observeRecovery({ state: 'connected', protocol: 'WireGuard', device: 'cyberghost',
    interface_index: 23, ipv6_guard: true }, 'recover');
  assert.equal(w.recoveryArmed, true);
  assert.equal(w.recoveryAttempts, 1);
  assert.equal(w.recoveryInFlight, false);
});

test('recovery refuses malformed tunnel identity or an unrecorded protection guard', () => {
  for (const fields of [
    { interface_index: 0 },
    { interface_index: 2.5 },
    { interface_index: Number.NaN },
    { interface_index: 23, ipv6_guard: false },
    { interface_index: 23, ipv6_guard: true, device: 'other' },
  ]) {
    const w = widget();
    w.recoveryEnabled = true;
    w.pendingCountry = 'DE'; w.selectedProtocol = 'wireguard';
    w.observeRecovery({ state: 'connected', protocol: 'WireGuard', device: 'cyberghost',
      interface_index: 23, ipv6_guard: true, ...fields }, 'connect');
    assert.equal(w.recoveryArmed, false, JSON.stringify(fields));
    assert.equal(w.recoveryTarget, null);
  }
});

test('recovery retries only a generic operation failure and stops on auth or uncertain failures', () => {
  for (const code of ['authentication', 'authorization', 'timeout', 'busy', 'unconfirmed', 'conflict']) {
    const w = widget();
    w.recoveryAttempts = 1; w.recoveryArmed = true; w.recoveryInFlight = true;
    fail(w, 'recover', 'generic sanitized error', code);
    assert.equal(w.recoveryArmed, false, code);
  }
  const retry = widget();
  retry.recoveryAttempts = 1; retry.recoveryArmed = true; retry.recoveryInFlight = true;
  retry.pending = 'recover'; retry.awaiting = true; retry.helperExit = 1;
  retry.output.text = JSON.stringify({ ok: false, code: 'operation_failed', error: 'Connection failed.' });
  retry.finish();
  assert.equal(retry.recoveryArmed, true);
  assert.equal(retry.recoveryInFlight, false);
  assert.equal(retry.recoveryNextAt, 160_000);
});

test('update failure preserves the last observed connection state', () => {
  const w = widget();
  w.snapshot = { state: 'connected', device: 'cyberghost' };
  w.releaseInfo = { tag: 'v1.0.0' };
  fail(w, 'updates', 'Update information is unavailable.');
  assert.equal(w.snapshot.state, 'connected');
  assert.equal(w.releaseInfo, null);
});

test('version report accepts only nullable helper API 4, 5 or 6', () => {
  const base = {
    schema: 1, plugin_version: '0.8.0', python_version: '3.12.1', platform: 'linux',
    backend: 'official-cli', packages: {}, prerequisites: [],
  };
  for (const api of [null, 4, 5, 6]) {
    const w = widget();
    w.backendMode = 'official-cli';
    finish(w, 'check', { state: 'disconnected', can_connect: true, can_disconnect: false,
      setup_ready: true, prerequisites: [], report: { ...base, helper_api: api } });
    assert.equal(w.versionReport.helper_api, api);
    assert.equal(w.snapshot.state, 'disconnected');
  }
  const bad = widget();
  bad.backendMode = 'official-cli';
  finish(bad, 'check', { state: 'disconnected', can_connect: true, can_disconnect: false,
    setup_ready: true, prerequisites: [], report: { ...base, helper_api: 7 } });
  assert.equal(bad.snapshot.state, 'unknown');
});

test('guarded recovery retains the exact prior tunnel generation and uses the distinct backend action', () => {
  const w = widget();
  w.recoveryEnabled = true; w.recoveryArmed = true; w.recoveryIndex = 23;
  w.recoveryTarget = { country: 'DE', city: 'Frankfurt', protocol: 'wireguard', server: 'frankfurt-s1-i01' };
  w.snapshot = { state: 'recovery-required', can_recover: true, can_connect: false,
    protection_phase: 'active', protection_index: 23, kill_switch: false,
    can_release_protection: true, uplink_ready: true, error: 'Tunnel absent.' };
  w.recoveryNextAt = 70_000;
  w.observeRecovery(w.snapshot, 'status');
  assert.equal(w.recoveryArmed, true);
  assert.equal(w.calls.later.length, 1);
  w.calls.later.shift()();
  assert.deepEqual(w.calls.invoke, ['recover']);
  vm.runInNewContext(functionSource('invoke'), w);
  w.invoke('recover');
  assert.equal(w.process.command[2], 'recover');
  assert.equal(w.recoveryAttempts, 1);
  assert.equal(w.process.command.includes('--kill-switch'), false);
});

test('guarded recovery pauses for a full block, changed generation or untrusted guard stage', () => {
  for (const fields of [{ kill_switch: true }, { protection_index: 24 },
    { protection_phase: 'prepared' }, { can_recover: false }]) {
    const w = widget();
    w.recoveryEnabled = true; w.recoveryArmed = true; w.recoveryIndex = 23;
    w.observeRecovery({ state: 'recovery-required', can_recover: true, can_connect: false,
      protection_phase: 'active', protection_index: 23, kill_switch: false,
      can_release_protection: true, uplink_ready: true, error: 'Tunnel absent.', ...fields }, 'status');
    assert.equal(w.recoveryArmed, false, JSON.stringify(fields));
    assert.equal(w.calls.later.length, 0);
  }
});
