# Test the 0.8 candidate

Fresh-VM testing was explicitly excluded from this session and remains untested.
The following independent-install checklist is for future contributors. Record the exact
release tag and full commit SHA when testing a release. When testing an unreleased
candidate, test only the exact pull request head commit: record its full SHA from GitHub, fetch
that commit into a disposable Omarchy 4 VM, and confirm `git rev-parse HEAD`
matches before testing. Do not report an unqualified default-branch install as
0.8. Protect the host by keeping the VM network and snapshot disposable. A VM
cannot validate physical Wi-Fi handoff or laptop suspend/resume.

## Before installing

- [ ] Confirm ordinary guest internet works with the VPN disconnected.
- [ ] Run the credential-free mock and static checks below.
- [ ] Review `packaging/cyberghostvpn/PKGBUILD`, `.SRCINFO`, the resolved-only
  hook patch and fixed-path API 6 helper.
- [ ] Build candidate package `cyberghostvpn-omarchy` 1.5.0-10 with
  `bash tools/build-client.sh` or pass `--archive /path/to/official.zip`. It
  builds without installing dependencies or the package; keep the archive
  and printed artifact private and outside Git. Inspect the inventory. The
  recipe provides/conflicts with the older `cyberghostvpn` package. Review any
  migration transaction; existing 1.5.0-7/API 4 users do not need to upgrade
  for ordinary connect/disconnect; switching needs API 5 and guarded recovery API 6.
- [ ] Review the exact package-manager transaction before installing. Stop if
  it proposes unexpected removals or upgrades. The previous package
  1.5.0-7/API 4 remains usable.
- [ ] Complete account/device setup only with `sudo cyberghostvpn --setup` in
  the VM's local terminal. Never place credentials in notes, chat, screenshots
  or Git.

## Panel and networking

- [ ] Confirm the native bar entry opens the panel and defaults to Official
  CLI / WireGuard.
- [ ] Check nullable tunnel/IPv4-route observations and status staleness after
  45 seconds or a backward clock change. The manual NetworkManager profile
  route is unchecked. Protection checks and public IPv4 lookups are explicit
  timestamped actions, not continuous verification.
- [ ] Check Quick Connect with a selected favorite and no favorite selected.
  Confirm fresh discovery and validation, no substitution for unavailable
  targets, cancellation/setup/network failure stopping before connection,
  and the clear-last-successful action.
- [ ] Check notification opt-out, quiet initial polling, deduplicated passive
  notices and generic operation notices. Confirm saved locations stay local
  and are omitted from shareable diagnostics.
- [ ] Check the guided prerequisite list and copyable official
  `sudo cyberghostvpn --setup` command; never enter credentials in the panel.
- [ ] Use **Generate shareable diagnostic report** and verify the report contains only its
  schema, plugin/Python versions, platform status, selected backend, versions
  or nulls for Omarchy, Quickshell, NetworkManager, systemd and the two
  package names, and prerequisite IDs/ready flags. Confirm it does not expose
  account/profile/IP/SSID/server/username/path/raw-error data and makes no
  external request, authentication attempt or network change.
- [ ] Connect to Germany / Frankfurt through the panel. Check a routed tunnel
  and use the panel's explicit IPv4 lookup. Record success only, not the
  address.
- [ ] Switch to Netherlands / Amsterdam, then select a discovered individual
  server. Record whether tunnel-bound IPv4 changed; never treat displayed
  location as proof of endpoint identity.
- [ ] Use **Verify traffic protection** and record pass/fail. If exercising
  the optional guard, check only the tested WireGuard cases. Full blocking
  begins after connection; intentional disconnect releases it. Full-guard switching
  must be refused without changing the guard.
  There is no startup or hard-kill guarantee; opt-in recovery has the limits below.
- [ ] Confirm DNS and ordinary networking recover after disconnect. Public
  IPv6 recovery is testable only when the VM has a verified global IPv6 route
  and an independent external baseline. Otherwise record it as untested.
- [ ] Test the fallback only with a valid, explicitly selected OpenVPN profile;
  never modify unrelated saved connections for testing.

Do not collect or share raw vendor logs, keys, account/config files, addresses,
DNS query names, packet captures or screenshots containing network details.
Record pass/fail/untested and sanitized GUI errors only. Disconnect and
confirm ordinary networking before removing the plugin or package. Remove
them separately; never use the vendor uninstaller or change unrelated
connections/firewall rules.

## Automated and static checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cg_bridge.py packaging/cyberghostvpn/omarchy-bridge
bash -n tools/host-baseline.sh tools/build-client.sh
omarchy plugin validate .
CG_QML_IMPORTS=$(mktemp -d)
ln -s /usr/share/omarchy/shell "$CG_QML_IMPORTS/qs"
/usr/lib/qt6/bin/qmllint -I "$CG_QML_IMPORTS" -I /usr/lib/qt6/qml BarWidget.qml Panel.qml GhostIcon.qml
```

Mock tests use no credentials and do not change host networking. Set
`CG_TEST_PACKAGE=/path/to/private-package.pkg.tar.zst` to exercise package
integration tests; without it, report the actual skips from the test output.
The candidate suite passed 158 tests with the built package and no skips on
the ThinkPad. CI runs the source suite on Python 3.12 and 3.14 with nine
private-package skips; native UI and live-network checks are separate. Static checks do
not prove native rendering or live VPN behavior.

The current candidate has 28 mocked UI-logic tests runnable with Node.js 18
or newer:

```bash
node --test tests/test_ui_logic.mjs
```

Node is test-only, not an application dependency. Real native dark/light
status/setup and focus/Escape checks passed. Native mock fixtures passed
specific-server and Any-city Quick Connect, unavailable-server rejection,
cancellation, authentication failure without recording success, notification
toggling, distinguishing same-city favorites by searching server descriptions,
forgetting the saved last location, explicit verification timestamps
and disconnect invalidation, and stale-status navigation/Escape while a mock
worker was delayed.
The initial Escape assertion ran before the closing animation finished; an
isolated check with a bounded animation wait passed. The real backend, theme
and plugin preferences were restored, with no VPN transition. These checks
verify UI interaction, not fresh live VPN connectivity.


## 0.8 local evidence

- Reviewed migration from legacy cyberghostvpn 1.5.0-7 to
  cyberghostvpn-omarchy 1.5.0-9/API5 installed only the old/new client packages. The subsequent
  1.5.0-10/API6 upgrade and final reviewed reinstall changed only that package.
  The unchanged vendor executable and existing account flow continued working.
- Live 0.7 DE/Frankfurt Quick Connect and NL/Amsterdam GUI individual-server
  switching returned distinct bound IPv4 values and matching country results.
  The final GUI disconnect lost focus; reviewed backend cleanup succeeded.
- Live 0.8 opt-in recovery armed after an explicit connection and completed one
  bounded reconnect after a controlled stop through the reviewed helper.
  Native version/update metadata and tunnel DNS catchall checks passed.
- Initial API5 GUI switching was not confirmed. A targeted backend switch
  passed. A later GUI reproduction stopped safely before connecting because
  keyboard focus was lost. Do not count those GUI assertions as passed.
- The installed guard policy passed isolated namespace packet tests, including
  staged IPv6 guarding and old/new transport mark behavior. An actual full
  guard blocked the tested direct IPv4/IPv6 requests; cleanup restored both.
- A later root-helper full-guard refusal returned the exact policy-refusal
  exit and preserved guard metadata. Same-profile Wi-Fi down/up retained the
  tunnel/guard and restored bound IPv4; this is not an alternate-AP handoff.
  The initial RTC post-wake assertion was unconfirmed. The final API6 bounded
  run passed suspend/wake, the same kernel guard/tunnel and bound IPv4 after
  resume, followed by reviewed disconnect cleanup.
  Final API6 GUI acceptance connected, armed recovery and recovered once after
  deletion of the verified owned tunnel. The new generation/mark matched its
  kernel guard and a tunnel-bound IPv4 request passed. The root observer saw
  209 samples with no missing table. GUI NL individual-server switching and
  disconnect passed; exact preferences were restored. These samples are not
  continuous leak verification.
  Root grammar, guard ownership/fingerprint, kill-switch refusal and
  failure-cleanup paths have mock coverage.

Manual packet checks use only disposable network namespaces and load policy
from the reviewed, root-owned installed helper. Review before authorizing:

```bash
sudo python3 -I tests/check_guard_namespace.py
```

There is no fresh-machine, always-on, startup, hard-kill or general leak-proof
claim. Keep all diagnostics, public addresses, packet captures and vendor
artifacts private.

Final host check: the VPN and guard were absent, NetworkManager/resolved were
active, the resolved stub link was unchanged, IPv6 disable flags were zero,
and normal public IPv4 worked. The currently active Wi-Fi differed from the
earlier dual-stack test profile and had no global IPv6 address/default route.
A normal NetworkManager reapply did not restore one. IPv6 recovery is therefore
unconfirmed for this final run; neither a plugin regression nor network-side
IPv6 availability was established. No static route, RA, DNS, firewall or IPv6
configuration workaround was applied.
