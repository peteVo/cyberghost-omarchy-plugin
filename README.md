# CyberGhost for Omarchy 4

A native Omarchy bar widget and VPN panel with an experimental official-client
backend for dynamic CyberGhost locations. An optional fallback controls an
existing NetworkManager OpenVPN profile. The plugin does not import, edit or
delete VPN profiles.

## Beta 0.5 installation

Beta 0.5 is in [PR #2](https://github.com/peteVo/cyberghost-omarchy-plugin/pull/2) and is not merged. The default branch and normal plugin
installation still provide beta 0.4. To review the beta safely, install it
disabled, verify the exact PR head commit, then validate and enable it. If the
plugin is already installed, inspect and preserve its changes instead of
replacing the checkout:

```bash
omarchy plugin add https://github.com/peteVo/cyberghost-omarchy-plugin.git
cd ~/.config/omarchy/plugins/petevo.cyberghost
git status --short                 # stop unless the checkout is clean
git remote -v                      # verify origin is the expected repository
git fetch origin feat/privacy-recovery-0.5
git rev-parse FETCH_HEAD           # compare with the reviewed PR #2 head SHA
git show --stat --format=fuller FETCH_HEAD
```

`omarchy plugin add` prompts whether to enable: answer **No**. Do not pass
`--enable` or `--yes` before reviewing the PR code. Compare `FETCH_HEAD` with
the current PR #2 head SHA and inspect the commit diff on GitHub. Stop if the
SHA does not match. Only after review, switch to the commit, validate and enable:

```bash
git switch --detach FETCH_HEAD
omarchy plugin validate .
omarchy plugin enable petevo.cyberghost
```

See [TESTING.md](TESTING.md) for the future Omarchy 4 VM checklist. No fresh
second-PC VM test has been completed. During this pre-merge beta, keep the
reviewed commit pinned; the native plugin updater follows the default branch.

The widget uses Omarchy's native shell APIs and existing Quickshell process.
New entries default to **Official CLI / WireGuard**. The panel provides
country/city/server selection, favorites, switching, connection details and an
explicit public IPv4 lookup. That lookup is third-party and IPv4-only; it binds
curl to the detected tunnel interface, disables `.curlrc`, and has no
default-route fallback. Displayed connection/location data is not proof of
provider identity or tunnel integrity.

Requirements: Omarchy 4 / Quickshell, Python 3.12 or newer, and NetworkManager.
Official CLI mode also needs package 1.5.0-7 or newer (helper API 4),
`iproute2`, `polkit`, `nftables`, `wireguard-tools`, `systemd-resolvconf`, and
official local account setup. Run the read-only check before connecting or
switching; failed prerequisites disable those GUI controls:

```bash
python3 cg_bridge.py check --backend official-cli
/usr/local/cyberghost/omarchy-bridge --version
```

The fallback needs NetworkManager's OpenVPN plugin and one explicitly selected
valid OpenVPN profile. The old `cyberghost` profile was revoked provider-side;
preserve it, but do not treat it as usable or attempt to revive it.

The official client enumerates available locations; the plugin validates each
selection and asks the authenticated client to fetch connection configuration
when connecting. No per-location profile imports are needed. These catalog
commands are read-only:

```bash
python3 cg_bridge.py countries --backend official-cli
python3 cg_bridge.py cities --backend official-cli --country DE
python3 cg_bridge.py servers --backend official-cli --country DE --city Frankfurt
```

## Reviewed CLI package

The local Arch recipe packages the checksum-pinned CyberGhost 1.5.0 Ubuntu
22.04 client. Current recipe version is **1.5.0-7**. Its dependencies include
Python 3.12+, `iproute2` and `polkit`, in addition to the VPN, resolver and
system utilities in [PKGBUILD](packaging/cyberghostvpn/PKGBUILD). It keeps the
vendor executable unchanged, avoids vendor install/uninstall scripts, and
installs the fixed root-owned API 4 adapter and its bound Polkit action.

Build in a private scratch directory outside the checkout. `PKGBUILD` fetches
the official [vendor archive](https://download.cyberghostvpn.com/linux/cyberghostvpn-ubuntu-22.04-1.5.0.zip)
and verifies SHA-256 `c7cfd8e685f497ecc957636913bc32f8fa55b6ac0bbf19b2a4ebe64d188d03a6`.
The build contains a vendor-distributed key; never commit the archive, key,
package, account material or private diagnostics. Inspect the package inventory
before installing. Do not use the separately packaged `cyberghostvpn-gui`, run
`pacman -Sy`, or accept unexpected package removals/upgrades.

```bash
sudo pacman -S --needed base-devel
CG_BUILD_DIR=$(mktemp -d)
cp packaging/cyberghostvpn/PKGBUILD packaging/cyberghostvpn/resolved-only.patch \
  packaging/cyberghostvpn/omarchy-bridge packaging/cyberghostvpn/org.petevo.cyberghost.policy \
  "$CG_BUILD_DIR/"
(cd "$CG_BUILD_DIR" && makepkg --nodeps)
bsdtar -tvf "$CG_BUILD_DIR/cyberghostvpn-1.5.0-7-x86_64.pkg.tar.zst"
```

`--nodeps` skips dependency checks; it does not establish runtime compatibility.
`base-devel` supplies the Arch build tools and `patch`. After reviewing the
package and proposed transaction, install
its dependencies and the artifact from your own terminal:

```bash
sudo pacman -S --needed python bash curl openvpn wireguard-tools systemd-resolvconf util-linux nftables iproute2 polkit
sudo pacman -U "$CG_BUILD_DIR/cyberghostvpn-1.5.0-7-x86_64.pkg.tar.zst"
```

Complete account/device setup only through the official client flow:

```bash
sudo cyberghostvpn --setup
```

Never paste credentials into this plugin, Git or shared test notes. Do not use
the vendor uninstaller; remove the CLI package with the package manager after
disconnecting. Removing the Omarchy plugin is a separate operation and does
not remove the CLI or NetworkManager profiles.

## Protection and current evidence

The optional WireGuard kill switch is connection-scoped. During preparation,
the IPv6 guard permits only the `systemd-resolve` UID to use TCP/UDP DNS ports
53 and 853; the bootstrap exception is removed from active and blocked rules.
Full blocking begins only after the client succeeds and the adapter identifies
the tunnel. Intentional disconnect and location switching release the guard.
Timeout/interruption cleanup is bounded; a detached descendant or hard helper
kill can escape cleanup, and startup does not have a full-block guarantee.
Ordinary status reports configured protection. Explicit Verify compares the
current firewall fingerprint and tunnel interface index/mark at that moment;
it is not continuous monitoring or a packet/leak test. See [SECURITY.md](SECURITY.md).

Evidence is versioned:

- Package 1.5.0-7 / API 4 fixes the reproduced WireGuard preparation failure:
  only the `systemd-resolve` UID may use IPv6 TCP/UDP DNS ports 53/853 while
  starting; the exception is removed for active and blocked rules. Namespace
  rule tests and bounded startup/interruption/recovery tests passed.
- Latest package 1.5.0-7 dual-stack DE/Frankfurt and NL/Amsterdam checks passed.
  Public IPv6/default route were available at baseline, blocked while guarded,
  and restored after disconnect. Randomized A and AAAA queries each used the
  tunnel once with zero Wi-Fi egress. Direct IPv6 DNS and ordinary IPv6 were
  blocked while guarded; a forced link-down retained IPv6/DNS blocking, and
  the NL kill switch also blocked physical IPv4. Host addresses and disable
  flags were preserved.
- The beta 0.5 GUI flow passed on package 1.5.0-7 / API 4: mouse kill-switch
  toggle, DE connect, tunnel-bound IPv4 lookup, protection verification, fresh
  NL discovery, specific-server selection, mouse switch, changed tunnel-bound
  IPv4, second verification and disconnect. The preference returned to off;
  this exercised the real backend, not a fixture.
- Recent 1.5.0-7 NL OpenVPN UDP and TCP sessions returned HTTPS from two
  endpoints each at the default MTU. IPv6 remained routed over the physical
  interface; prefer WireGuard. This does not establish that the earlier
  OpenVPN failure's cause is fixed, and OpenVPN has no plugin kill switch.
- Final native dark/light screens and UI-state fixtures were reviewed after one
  correction batch. The independent review returned ship for the interface.
  Captures remain private and are not published.

The final host check passed with normal external IPv4/IPv6, a default IPv6
route, disable flags at zero, NetworkManager/resolved active, and no VPN tunnel
or guard metadata; the revoked NetworkManager profile remains preserved. The
cause of the old 0.4 RA-route issue remains unknown; IPv6 routing was restored
before these tests without changing routes, RA or firewall settings. The old
0.4 ThinkPad run included native controls, Wi-Fi handoff and bounded
suspend/resume. Those are historical results, not beta 0.5 or VM evidence. A
VM cannot validate physical Wi-Fi roaming or laptop suspend/resume. A public
IPv6 check requires a guest global IPv6 route and an independent external
baseline; otherwise report it as untested. Never infer protection from a
connected label, exit code or IPv6-disable flag.

## Troubleshooting

- **Missing dependency or old adapter:** run the preflight above; install the
  reviewed package and dependencies, and confirm the helper reports API 4.
- **Authentication failure:** complete account setup in the official client
  locally. Never enter credentials in this panel or share client output.
- **Timeout:** refresh status before retrying; a detached vendor process may
  outlive the bounded helper cleanup.
- **Traffic block remains:** disconnect first. Use Settings → **Release
  CyberGhost traffic block**, or run the following to remove only this plugin's
  guard. Do not flush unrelated firewall tables:

  ```bash
  pkexec /usr/local/cyberghost/omarchy-bridge --release-protection
  ```
- **OpenVPN fallback:** choose Settings → **Existing OpenVPN**, enter one valid
  configured profile name and select **Use profile**. Missing, ambiguous or
  non-OpenVPN profiles disable connection controls. Revoked provider records
  can still pass local profile checks but fail provider authentication.

## Credential-free checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cg_bridge.py packaging/cyberghostvpn/omarchy-bridge
bash -n tools/host-baseline.sh
omarchy plugin validate .
```

The workflow runs the mocked source suite on Python 3.12 and 3.14; 9
artifact-dependent package tests skip without `CG_TEST_PACKAGE`. The current
125-test suite passed locally with package 1.5.0-7 and no skips. Check PR #2
for the latest remote CI result. Mock tests use no credentials or host-network
changes.

Qt lint uses Omarchy's virtual `qs` import mapping:

```bash
CG_QML_IMPORTS=$(mktemp -d)
ln -s /usr/share/omarchy/shell "$CG_QML_IMPORTS/qs"
/usr/lib/qt6/bin/qmllint -I "$CG_QML_IMPORTS" -I /usr/lib/qt6/qml BarWidget.qml Panel.qml
```

Lint passed with 53 missing-property and 8 block-scope declaration warnings,
and no syntax/import errors. Static lint does not validate native rendering or
live VPN behavior.

To remove the widget, disconnect first, then run `omarchy plugin disable
petevo.cyberghost` and `omarchy plugin remove petevo.cyberghost`. Remove the
vendor package separately through the package manager after reviewing its
transaction. Never run the vendor uninstaller or change unrelated connections
or firewall rules.
