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
    Date: { now: () => 100_000 },
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
  for (const name of ['validTarget', 'favoriteKey', 'startSavedTarget', 'quickConnect', 'completeSavedTarget', 'cancelSavedTarget', 'cancelQuickConnect', 'notify', 'observeState', 'clearHealth', 'noteStateFailure', 'selectBackend', 'selectProfile', 'selectCountry', 'finish']) {
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

function fail(w, task, error) {
  w.pending = task;
  w.awaiting = true;
  w.helperExit = 1;
  w.output.text = JSON.stringify({ ok: false, error });
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
