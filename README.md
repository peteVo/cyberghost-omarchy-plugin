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
and confirm the reported version before connecting; do not label an older
default-branch installation as 0.6. See [TESTING.md](TESTING.md).

Requirements: x86-64 Linux, Omarchy 4, its native Quickshell, NetworkManager and Python
3.12+. The supported target is Omarchy 4; vanilla Arch with GNOME/KDE is not a
supported configuration. The tested stack is Omarchy 4.0.6-1,
Quickshell 0.3.2.r7.g2b4501a-1, NetworkManager 1.58.1-2 and systemd 262.1-1.
Fresh wider-machine validation is pending.

| Environment | Status |
| --- | --- |
| The x86-64 ThinkPad stack listed above | Tested locally |
| Other Omarchy 4 installations with the same APIs and resolved setup | Targeted; independent validation pending |
| GNOME, KDE or plain Hyprland without Omarchy shell | No compatible frontend |
| ARM, other resolver implementations or altered helper paths | Unsupported official-client setup |

Official CLI mode also needs the
reviewed package's Python 3.12+, OpenVPN, WireGuard, resolver, nftables,
iproute2 and Polkit dependencies.

## Official CLI setup

Official CLI mode needs the reviewed local package. The candidate package is
`cyberghostvpn-omarchy` 1.5.0-8, with helper API 4. It preserves the unchanged,
checksum-pinned CyberGhost 1.5.0 executable. The existing
`cyberghostvpn` 1.5.0-7/API 4 package remains usable; it does not need an update
for the plugin's candidate UI. The candidate package provides and conflicts
with `cyberghostvpn`. If migrating from the old package name, review the
package-manager transaction yourself; migration is not automatic.

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
controls. A displayed connected label or location is reported state, not proof
of provider identity, routed traffic, DNS/IPv6 protection or kill-switch
enforcement. WireGuard is the recommended protocol. The optional kill switch
starts full blocking only after connection, and intentional disconnect or
switch releases it. There is no always-on, startup, automatic reconnect or
hard-kill guarantee. OpenVPN has no plugin IPv6 guard and may bypass over IPv6.

The fallback can control one explicitly selected, existing NetworkManager
OpenVPN profile. It resolves the profile by UUID and rejects missing,
ambiguous or non-OpenVPN profiles. It never imports, edits, deletes or changes
unrelated connections. Profile authentication must still be valid at the
provider. A saved local profile alone does not prove its provider entry is usable.

## Troubleshooting

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

Bounded WireGuard testing on one ThinkPad passed DE-to-NL GUI switching,
distinct tunnel-bound IPv4 results, DNS and dual-stack disconnect recovery,
and the tested guard/firewall checks. Package 1.5.0-7/API 4 was used. The
older 0.4 IPv6 route-loss cause remains unknown. Physical Wi-Fi handoff,
suspend/resume and native UI checks passed on the earlier version; wider
machine validation is pending. See [SECURITY.md](SECURITY.md) for the exact
scope and limits. No broader leak-protection claim is made.

## Checks

Automated tests use mocks and do not use account credentials or change host
networking. Run `python3 -m unittest discover -s tests -v`,
`python3 -m py_compile cg_bridge.py packaging/cyberghostvpn/omarchy-bridge`,
`bash -n tools/host-baseline.sh tools/build-client.sh`,
`omarchy plugin validate .`, and Qt6 `qmllint` with the `qs` import mapping
documented in [TESTING.md](TESTING.md). Package tests skip unless
`CG_TEST_PACKAGE` points to a private locally built package. The candidate
suite passes 134 tests with the built package and no skips; without it, nine
package tests skip. Static checks do not
validate live VPN behavior or native rendering.

See [CONTRIBUTING.md](CONTRIBUTING.md) for safe reports and changes. To remove
the plugin, disconnect first, then run `omarchy plugin disable
petevo.cyberghost` and `omarchy plugin remove petevo.cyberghost`. Remove the
CLI package separately with the package manager; do not run the vendor
uninstaller.
