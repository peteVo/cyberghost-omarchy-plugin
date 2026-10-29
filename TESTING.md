# Test the 0.6 candidate

Wider-machine validation of 0.6 is pending. When testing an unreleased candidate, test
only the exact pull request head commit: record its full SHA from GitHub, fetch
that commit into a disposable Omarchy 4 VM, and confirm `git rev-parse HEAD`
matches before testing. Do not report an unqualified default-branch install as
0.6. Protect the host by keeping the VM network and snapshot disposable. A VM
cannot validate physical Wi-Fi handoff or laptop suspend/resume.

## Before installing

- [ ] Confirm ordinary guest internet works with the VPN disconnected.
- [ ] Run the credential-free mock and static checks below.
- [ ] Review `packaging/cyberghostvpn/PKGBUILD`, `.SRCINFO`, the resolved-only
  hook patch and fixed-path API 4 helper.
- [ ] Build candidate package `cyberghostvpn-omarchy` 1.5.0-8 with
  `bash tools/build-client.sh` or pass `--archive /path/to/official.zip`. It
  builds without installing dependencies or the package; keep the archive
  and printed artifact private and outside Git. Inspect the inventory. The
  recipe provides/conflicts with the older `cyberghostvpn` package. Review any
  migration transaction; existing 1.5.0-7/API 4 users do not need to upgrade
  for the candidate panel UI.
- [ ] Review the exact package-manager transaction before installing. Stop if
  it proposes unexpected removals or upgrades. The previous package
  1.5.0-7/API 4 remains usable.
- [ ] Complete account/device setup only with `sudo cyberghostvpn --setup` in
  the VM's local terminal. Never place credentials in notes, chat, screenshots
  or Git.

## Panel and networking

- [ ] Confirm the native bar entry opens the panel and defaults to Official
  CLI / WireGuard.
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
  begins after connection; switching and intentional disconnect release it.
  There is no startup, automatic reconnect or hard-kill guarantee.
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
The candidate suite passed 134 tests with the built package and no skips on
the ThinkPad. CI runs the source suite on Python 3.12 and 3.14 with nine
private-package skips; native UI and live-network checks are separate. Static checks do
not prove native rendering or live VPN behavior.
