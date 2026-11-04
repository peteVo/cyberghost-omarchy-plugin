# CyberGhost for Omarchy

A native Omarchy 4 bar widget and panel for the official CyberGhost CLI, with
an optional fallback for an explicitly selected NetworkManager OpenVPN
profile. New entries use Official CLI / WireGuard. This integration is
experimental; Arch and Omarchy are not vendor-supported platforms.

## Installation

Release installations use Omarchy's plugin manager:

```bash
omarchy plugin add https://github.com/peteVo/cyberghost-omarchy-plugin.git --enable
```

For an existing checkout, use `omarchy plugin update petevo.cyberghost` after
reviewing and preserving local changes. The installer follows the default
branch. For an unreleased candidate, test the exact pull-request head commit
and confirm its reported version before connecting. See [TESTING.md](TESTING.md)
for the 0.8 beta evidence and remaining validation.

Requirements: x86-64 Linux, Omarchy 4, its native Quickshell, NetworkManager and Python
3.12+. The supported target is Omarchy 4; vanilla Arch with GNOME/KDE is not a
supported configuration. The tested stack is Omarchy 4.0.6-1,
Quickshell 0.3.2.r7.g2b4501a-1, NetworkManager 1.58.1-2 and systemd 262.1-1.
A later independent TryOmarchy guest pass and its remaining acceptance gaps
are recorded in [TESTING.md](TESTING.md).

| Environment | Status |
| --- | --- |
| The x86-64 ThinkPad stack listed above | Tested locally |
| TryOmarchy runtime 4.0.4-10 / Qt 6.12 | Independent installation and bounded guest tests; compatibility fixes below |
| Other Omarchy 4 installations with the same APIs and resolved setup | Broader validation pending |
| GNOME, KDE or plain Hyprland without Omarchy shell | No compatible frontend |
| ARM, other resolver implementations or altered helper paths | Unsupported official-client setup |

Official CLI mode also needs the
reviewed package's Python 3.12+, OpenVPN, WireGuard, resolver, nftables,
iproute2 and Polkit dependencies.

## Official CLI setup

Official CLI mode needs the reviewed local package. The 0.8 candidate uses
`cyberghostvpn-omarchy` 1.5.0-10 with helper API 6 and the unchanged,
checksum-pinned CyberGhost 1.5.0 executable. It provides and conflicts with the
legacy `cyberghostvpn` package. API 4 remains compatible with connect and
disconnect; location switching requires API 5 and guarded recovery API 6.
The renamed package was migrated from the legacy client and upgraded locally
without other package changes. Existing official-client authentication remained
usable; no account setup was repeated. The plugin's core dependencies did not change.

Build and install are separate. Install the build tools (`base-devel` and
`libarchive`) through your normal Arch package manager after reviewing its
transaction. The builder runs unprivileged in private scratch space, installs
no dependencies, and prints the artifact path:

```bash
bash tools/build-client.sh
# Or provide an already downloaded official archive:
bash tools/build-client.sh --archive /path/to/cyberghostvpn-ubuntu-22.04-1.5.0.zip
```

Review the artifact and proposed package-manager transaction, then install
it yourself with `sudo pacman -U /path/to/printed-artifact`. The builder does
not install packages, authenticate or connect. See [SECURITY.md](SECURITY.md)
for package boundaries and limitations.

Complete account/device setup only through the official local client flow:

```bash
sudo cyberghostvpn --setup
```

The panel's setup check and copyable setup command are read-only. The optional
diagnostics report contains a schema number, plugin/Python versions, Linux
platform status, selected backend, versions or nulls for Omarchy, Quickshell,
NetworkManager, systemd and the two package names, plus prerequisite IDs and
ready flags. It does not inspect account/profile data, contact an external
service, authenticate or change networking. Public IPv4 lookup is a separate
explicit action that contacts a third party and binds to the detected tunnel
interface.

The panel supports country, city, server, protocol, favorites and switching
controls. Protocol changes require disconnecting first. A WireGuard location
switch uses one privileged request and lock across the old stop and new
connect. Its own nftables guard remains through an atomic bootstrap stage.
IPv4 and the native resolver's IPv6 DNS exception remain allowed during that
stage; this is not a DNS-leak test or a full IPv4 privacy claim. Full
kill-switch sessions cannot switch: the UI, Python bridge and root helper
reject the request without mutation and retain the block. Safe full-guard
switching remains blocked until the vendor can be bootstrapped with a reviewed
endpoint constraint.

Quick Connect uses the explicitly selected favorite, or the last
successfully connected location when no favorite is selected. It rediscovers
and validates saved locations before connecting; unavailable targets stop
without substitution. Saved locations and notification preference stay local
and are omitted from shareable diagnostics. A displayed connected label or location is reported state, not proof
of provider identity, routed traffic, DNS/IPv6 protection or kill-switch
enforcement. WireGuard is the recommended protocol. The optional kill switch
starts full blocking only after connection, and intentional disconnect releases it. Full kill-switch switches are refused.
There is no always-on, startup or hard-kill guarantee. OpenVPN has no plugin IPv6 guard and may bypass over IPv6.

Optional recovery is off by default and lives only for the current shell
session. When enabled, only an explicit WireGuard connection from the widget
arms it. Recovery keeps a surviving tunnel while waiting for the network. If
the tunnel is gone, it requires fresh safe status and an available uplink,
waits at least 30 seconds, and makes at most two attempts per user connection.
With an owned active IPv6-only guard, API 6 validates its fingerprint and tunnel
absence, then retries only the last confirmed target bound to the same boot
and previous tunnel generation. It retains the guard throughout; a failed
retry removes the temporary resolver exception and requires manual recovery.
It does not rediscover targets through potentially blocked DNS or substitute
another server. Normal connects, switches and Quick Connect still use fresh
catalogs. A full kill-switch outage remains blocked for manual recovery.
A successful retry does not reset the attempt budget. Only a generic failure
with a subsequent safe state can schedule the last attempt after 60 seconds.
Authentication, cancellation, timeout, unknown/protection/conflict/status errors
pause recovery. Local Polkit may prompt normally. Panel disconnects and
selection changes cancel it; detected identity changes or conflicting VPNs
pause it. Disable recovery before external management, or use the pauseRecovery
IPC command documented in SECURITY.md.

Settings can explicitly check GitHub release metadata for this fixed project
and show the release notes plus a copyable Omarchy update command. The check
does not fetch release assets or install updates. The diagnostics allowlist
includes nullable helper API version alongside package and prerequisite
versions.

The fallback can control one explicitly selected, existing NetworkManager
OpenVPN profile. It resolves the profile by UUID and rejects missing,
ambiguous or non-OpenVPN profiles. It never imports, edits, deletes or changes
unrelated connections. Profile authentication must still be valid at the
provider. A saved local profile alone does not prove its provider entry is usable.

## Troubleshooting

The unreleased TryOmarchy compatibility fix qualifies the native palette as
`Commons.Color`, avoiding Qt 6.12's new `Color` singleton. The published
`v0.8.0-beta.1` can render black text and a black panel ghost in dark themes
on that stack. The fix also recognizes the fixed `try-omarchy-runtime`
package provider when reporting the Omarchy version; the diagnostic schema
and allowlist remain unchanged. A running shell may retain previously loaded
QML after a plugin rescan; see the verification notes in [TESTING.md](TESTING.md).

- **Needs attention:** fix the named prerequisite locally, then use Settings →
  **Refresh diagnostics**. The plugin does not start services or replace DNS
  configuration automatically.
- **Authentication or authorization failed:** use the official local setup
  flow for account problems, or retry when you can approve the system prompt.
  Never paste account information into a report.
- **Another VPN is active:** manage that connection deliberately before using
  this client. The plugin will not overwrite unrelated profiles.
- **Timeout or interrupted setup:** refresh before retrying; a vendor descendant
  may still be finishing. Use **Restore normal networking** to stop/recover.
- **Traffic block remains:** Settings → **Release CyberGhost traffic block**
  removes only this plugin's guard and allows normal networking. A terminal
  alternative is `pkexec /usr/local/cyberghost/omarchy-bridge --release-protection`.
  Approve authentication locally; never flush unrelated firewall tables.

## Evidence

The 0.7 beta adds nullable tunnel and IPv4-route observations for
the official CLI; manually selected NetworkManager profile routes remain
unchecked. Status becomes stale after 45 seconds or a backward clock change.
Protection verification and public IPv4 lookup are timestamped explicit
checks, not continuous monitoring. Generic notifications can be disabled;
initial polling is quiet, passive notices are deduplicated, and explicit
operations can notify. The guided setup checklist uses existing prerequisites
and offers a copyable official terminal command; it has no credential form or
automatic package installation.

On this host, native dark/light status, setup and focus/Escape checks passed.
Native mock fixtures passed Quick Connect with specific-server and Any-city
targets, unavailable-server rejection, cancellation, authentication failure,
notification toggling and stale-status keyboard interaction. The real backend,
original theme and plugin preferences were restored; no VPN transition was
performed. See [TESTING.md](TESTING.md) for remaining validation.

On the ThinkPad, live 0.7 DE/Frankfurt Quick Connect and NL/Amsterdam
specific-server GUI switching changed the tunnel-bound IPv4 and reported
country as expected. The final GUI disconnect lost focus and aborted; reviewed
backend cleanup succeeded, the IPv6 default route returned, disable flags
were zero, and saved preferences were restored.

The final 0.8/API6 native check connected and armed recovery, deleted only the
verified owned test tunnel, and completed one guarded reconnect. The new
interface generation matched the kernel guard and a tunnel-bound IPv4 request
succeeded. Across 209 sampled checks the table was never absent; sampling
does not prove continuous leak protection. The GUI then switched to a freshly
discovered NL individual server and disconnected normally. Exact plugin
preferences were restored. An earlier API5 GUI assertion was unconfirmed; its
cause remains unknown, and a read-only settling window now accommodates
asynchronous state publication without repeating operations.

Native dark/light recovery/version/update checks and isolated namespace packet
tests passed. Full-guard direct IPv4/IPv6 requests were blocked in the tested
cases; same-profile Wi-Fi down/up retained the tunnel and restored bound IPv4.
Full-guard switching was refused without changing the session. See
[TESTING.md](TESTING.md) and [SECURITY.md](SECURITY.md) for suspend evidence,
bootstrap/DNS limits and unresolved distribution constraints. Fresh VM testing
was excluded from that developer session; the later TryOmarchy pass is recorded
separately in [TESTING.md](TESTING.md).

Final host check: the VPN and guard were absent, NetworkManager/resolved were
active, the resolved stub link was unchanged, IPv6 disable flags were zero,
and normal public IPv4 worked. The currently active Wi-Fi differed from the
earlier dual-stack test profile and had no global IPv6 address/default route.
A normal NetworkManager reapply did not restore one. IPv6 recovery is therefore
unconfirmed for this final run; neither a plugin regression nor network-side
IPv6 availability was established. No static route, RA, DNS, firewall or IPv6
configuration workaround was applied.

## Checks

Automated tests use mocks and do not use account credentials or change host
networking. Run `python3 -m unittest discover -s tests -v`,
`python3 -m py_compile cg_bridge.py packaging/cyberghostvpn/omarchy-bridge`,
`bash -n tools/host-baseline.sh tools/build-client.sh`,
`omarchy plugin validate .`, and Qt6 `qmllint` with the `qs` import mapping
documented in [TESTING.md](TESTING.md). Package tests skip unless
`CG_TEST_PACKAGE` points to a private locally built package. The compatibility-fix branch passes 159 Python tests with its private built
package and no skips, plus 28 Node UI-logic tests. Static checks do not
validate live VPN behavior or native rendering.

See [CONTRIBUTING.md](CONTRIBUTING.md) for safe reports and changes. To remove
the plugin, disconnect first, then run `omarchy plugin disable
petevo.cyberghost` and `omarchy plugin remove petevo.cyberghost`. Remove the
CLI package separately with the package manager; do not run the vendor
uninstaller.


## Distribution status

The reviewed package remains a private local build. No vendor archive,
key-bearing package or generated account data is published with plugin releases.
AUR publication is blocked by the vendor's hardcoded `/usr/local` layout and
unresolved vendor redistribution/license text and package-source licensing
requirements. The installed CLI help advertises no relocation option. Do not
patch the executable or add a host-wide path workaround to claim compliance.
See [Arch packaging standards](https://wiki.archlinux.org/title/Arch_Packaging_Standards),
[AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines)
and [vendor terms](https://www.cyberghostvpn.com/terms). No vendor permission or
AUR eligibility is asserted.
