# CyberGhost for Omarchy 4

A native Omarchy bar widget and VPN panel with an experimental official-CLI integration. A reviewed local CyberGhost CLI package supplies dynamic country, city and individual-server selection. An optional backend controls an existing NetworkManager **OpenVPN** profile.

**Germany/Frankfurt → Netherlands/Amsterdam WireGuard switching was verified through the native GUI**, including country/city/server selection, different tunnel-bound public IPv4 addresses, independent DE/NL country checks, DNS setup and disconnect. The optional WireGuard kill switch was exercised on the same host: it blocked direct Wi-Fi IPv4, retained the block after a forced WireGuard link-down, recovered on link-up, and released on intentional disconnect. IPv6 route recovery remains unresolved. These bounded checks do not establish general leak protection or a protection guarantee during connection startup. The panel distinguishes configured protection from its explicit verification check and never treats a connection label as proof of tunnel integrity.

## Installation

**Experimental beta 0.4.** Tested on one Omarchy 4 ThinkPad with CyberGhost WireGuard. External public IPv6 recovery/leak validation remains incomplete; see [SECURITY.md](SECURITY.md). This is an unofficial integration, and Arch/Omarchy is not a CyberGhost-supported platform.

Install the panel through Omarchy's native plugin manager:

```bash
omarchy plugin add https://github.com/peteVo/cyberghost-omarchy-plugin.git --enable
```

This installs the panel, not the CyberGhost CLI. Dynamic locations require the **reviewed compatibility package below**, an existing CyberGhost subscription and official local account setup. The unmodified AUR package does not supply this plugin's reviewed privileged adapter. Do not use it as a substitute for that package.

Click **CG** in the bar. The panel provides searchable countries/cities/servers, automatic server selection, favorites, connection details, optional public IPv4 lookup, switching, diagnostics and an optional WireGuard kill switch. Tab navigates native controls; Escape closes. Preferences and favorites persist through Omarchy's bar-widget state API. New entries default to **Official CLI / WireGuard**. No second Quickshell process is started.

Requirements: Omarchy 4 / Quickshell, Python 3 and NetworkManager. Official-CLI mode also needs the reviewed package and local account setup. The optional fallback needs NetworkManager's OpenVPN plugin and a valid configured OpenVPN profile. Authentication stays with NetworkManager's secret agent or the official client. The plugin never imports, edits or deletes VPN profiles.

For a valid fallback, choose **Existing OpenVPN** in Settings, enter the existing profile name and choose **Use profile**. Missing, ambiguous or non-OpenVPN profiles disable connection controls. No manual `shell.json` editing is needed.

Update a clean installation with:

```bash
omarchy plugin update petevo.cyberghost
```

Inspect existing installations before adding or updating them. Preserve local changes first. The native updater fetches the repository's default branch and fast-forwards; old feature-branch installations can update once their history is contained in the default branch. If cached QML still shows old code, use `omarchy restart shell` only while unlocked.

For development, inspect or clone the repository into `~/Projects/cyberghost-omarchy-plugin`, create a feature branch from the latest default branch, and follow [AGENTS.md](AGENTS.md). Develop in the inspected user-owned plugin checkout when testing the desktop. The installed API rejects symlinks inside plugins and has no verified checkout-link workflow. Never edit `/usr/share/omarchy` or run a second Quickshell instance. Save personal diagnostics and vendor artifacts outside Git.

## Official CLI and dynamic locations

Arch/Omarchy is not a vendor-supported platform. The reviewed Ubuntu 22.04 archive is CyberGhost **1.5.0**, SHA-256 `c7cfd8e685f497ecc957636913bc32f8fa55b6ac0bbf19b2a4ebe64d188d03a6`. Its bundled README documents these commands:

```bash
cyberghostvpn --help
cyberghostvpn --traffic --country-code
cyberghostvpn --traffic --country-code DE
cyberghostvpn --traffic --country-code DE --city Frankfurt
```

The first list supplies countries, the second cities, and the third servers. `--connect` selects a live provider location; the CLI obtains the connection configuration using its authenticated account. You do not manually download one OpenVPN file per country. Server and protocol flags are validated against the installed client. WireGuard was exercised with automatic server selection in Frankfurt and an explicitly selected Amsterdam server.

The adapter discovers countries, cities and servers from the installed client and validates each selection before connecting. The panel now exposes protocol/server choices, favorites and a switch action; switching stops the current session only after the target discovery checks succeed and disconnect is confirmed. A server returned by the client was selected for one NL WireGuard connection. Location and duration shown in the panel are recorded as requested/session metadata; they are not independently verified endpoint identity. Automatic reconnect is not implemented. The GUI switch path was exercised from Frankfurt to Amsterdam, after an Amsterdam-to-Frankfurt switch.

For a fresh official-CLI setup, complete these steps in order:

1. Build and review the local package below, then install the package and its dependencies from your own terminal. Stop if the transaction proposes removals or unexpected core upgrades.
2. Complete account/device setup through the official client in your own terminal: `sudo cyberghostvpn --setup`. Enter credentials only in that client flow.
3. Open **CG** and choose **Settings → Official CLI** and **Locations → WireGuard**. These settings persist through Omarchy's existing bar-widget API. The NetworkManager profile backend remains available for a valid OpenVPN profile.

Installing the CLI alone does not change the selected backend. To set the same choices directly with Omarchy's native bar-widget API:

```bash
omarchy-shell shell setBarWidget petevo.cyberghost backend '"official-cli"' '{}'
omarchy-shell shell setBarWidget petevo.cyberghost protocol '"wireguard"' '{}'
```

The reviewed package's root-owned adapter maps the authenticated Polkit UID through NSS, uses a minimal environment, and accepts a narrow connect/stop/protection command set. Its packaged Polkit action is bound to the fixed adapter path and requests administrator authentication; active-session authorization may be cached by Polkit. A root lock serializes operations while the adapter remains alive; a vendor descendant may survive helper death or timeout, so refresh status before retrying. The adapter handles no passwords and adds no daemon or local authorization override.

### Reviewed local package

See [SECURITY.md](SECURITY.md) and [packaging/cyberghostvpn/PKGBUILD](packaging/cyberghostvpn/PKGBUILD). Version **1.5.0-5**:

- Packages the original x86-64 binary unchanged; never runs the vendor installer, uninstaller or completion generator.
- Omits the unused HTTP certificate download and installs the bundled private key as root-owned `0600`.
- Uses `systemd-resolvconf`, the packaged compatibility layer for resolved; does not replace resolver services.
- Patches the OpenVPN resolver hook to refuse global `resolv.conf` rewriting and report DNS setup failures. This is not a tested leak-prevention guarantee.
- Adds the narrowly scoped, root-owned Polkit adapter and its fixed-path administrator-auth action.

Build without installing runtime dependencies, in a scratch directory outside the plugin. Place the reviewed vendor ZIP there first:

```bash
CG_BUILD_DIR=$(mktemp -d)
cp packaging/cyberghostvpn/PKGBUILD packaging/cyberghostvpn/resolved-only.patch \
  packaging/cyberghostvpn/omarchy-bridge packaging/cyberghostvpn/org.petevo.cyberghost.policy \
  "$CG_BUILD_DIR/"
cp ~/Downloads/aur-review/cyberghostvpn/cyberghostvpn-ubuntu-22.04-1.5.0.zip "$CG_BUILD_DIR/"
(cd "$CG_BUILD_DIR" && makepkg --nodeps)
bsdtar -tvf "$CG_BUILD_DIR/cyberghostvpn-1.5.0-5-x86_64.pkg.tar.zst"
```

`--nodeps` permits packaging without installing runtime packages; it is not a runtime compatibility check. Build artifacts contain the vendor-distributed key and must remain private and outside Git. Do not use the separately packaged `cyberghostvpn-gui`.

After reviewing the package inventory, install its dependencies and the local artifact in your own terminal. Stop on proposed removals or unexpected core upgrades:

```bash
sudo pacman -S --needed openvpn wireguard-tools systemd-resolvconf util-linux nftables
sudo pacman -U "$CG_BUILD_DIR/cyberghostvpn-1.5.0-5-x86_64.pkg.tar.zst"
```

The reviewed 1.5.0-5 package was built and installed through the authorized Polkit flow. Its source checksums are synchronized in `PKGBUILD` and `.SRCINFO`. The vendor-generated WireGuard configuration was observed beneath root-owned mode `0700` `/etc/wireguard`; ordinary users cannot traverse that directory. Official account setup remains in the vendor client. Stop on conflicts or unexpected core upgrades. Do not run `pacman -Sy` or replace essential libraries.

Use `sudo cyberghostvpn --setup` in your own terminal for official account/device setup. Never paste credentials, vendor configuration or logs into chat/Git. Do not invoke the vendor's uninstall command to remove this package; use the package manager after reviewing the transaction.

## Tests and diagnostics

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cg_bridge.py
bash -n tools/host-baseline.sh
omarchy plugin validate .
python3 cg_bridge.py check
python3 cg_bridge.py status
python3 cg_bridge.py countries
omarchy-shell petevo.cyberghost diagnostics
```

Run the optional built-package tests with the actual private artifact:

```bash
CG_TEST_PACKAGE=/path/to/cyberghostvpn-1.5.0-5-x86_64.pkg.tar.zst \
  python3 -m unittest discover -s tests -v
```

The current suite reports **105 passing tests with package tests enabled** (`CG_TEST_PACKAGE`). Automated tests use mocks, no account credentials, and make no host network changes. A separate isolated dual-stack nftables TCP test blocked unmarked IPv4/IPv6, allowed traffic carrying the WireGuard mark, and preserved an unrelated nftables table.

A manual packet-behavior check is also available after reviewing the source and installing the reviewed package:

```bash
sudo /usr/bin/python3 -I tests/check_guard_namespace.py
```

It enters fresh disposable network namespaces before creating links or nftables rules, uses the installed helper’s policy, and exercises actual IPv4/IPv6 TCP traffic. It does not change host routes, DNS or firewall tables. It was run successfully on the ThinkPad; it is separate from the 105 mock/package tests.

The installed Qt tool is `/usr/lib/qt6/bin/qmllint`. Its `qs` imports need the shell's virtual namespace mapped outside the plugin:

```bash
CG_QML_IMPORTS=$(mktemp -d)
ln -s /usr/share/omarchy/shell "$CG_QML_IMPORTS/qs"
/usr/lib/qt6/bin/qmllint -I "$CG_QML_IMPORTS" -I /usr/lib/qt6/qml BarWidget.qml Panel.qml
```

The final Qt6 lint exited 0 with 47 dynamic-property warnings and eight JavaScript declaration-style warnings; no syntax/import errors were reported. Check each warning; lint does not establish that the panel loads or renders correctly.

`bash tools/host-baseline.sh` takes a read-only network snapshot without making an external IP request. Keep its output local: it contains personal network details. Live tests use tunnel/route/DNS evidence and explicit opt-in public-IP checks. Do not include local/public IPs or DNS configuration in shared notes. A bidirectional handoff between the saved Wi-Fi and trusted hotspot passed with the same WireGuard tunnel and successful bound IPv4 after each change. A native suspend/resume check slept for 16 seconds, woke automatically, retained the tunnel and recovered bound IPv4; its kernel protection check passed. Cleanup disconnected and released the guard.

## Troubleshooting and removal

- **Unknown / status unavailable:** retry diagnostics. The UI clears stale Connected state on helper/status errors. Confirm NetworkManager and the named OpenVPN profile in a normal host terminal.
- **Profile rejected:** select one unambiguous OpenVPN profile; Wi-Fi, WireGuard and other VPN types cannot be activated through the fallback.
- **Another VPN active:** deliberately disconnect it first. The plugin refuses overlapping NetworkManager VPNs; vendor `--stop` may affect multiple VPNs.
- **CLI setup incomplete:** complete the established client setup locally. Do not weaken ownership checks or create a password cache in the plugin.
- **CLI lists empty:** inspect installed help and redacted list formatting locally. The parser does not guess country/city names.
- **Authorization cancelled:** retry when you can approve the system prompt. A missing adapter requires the reviewed package, not a user-writable root script.
- **Timeout:** refresh before retrying. A privileged child may still be finishing; the user lock does not guarantee termination of vendor descendants after a crash or timeout.
- **IPv6 missing after disconnect:** the tested host returned IPv6-disable flags to 0 but did not recover its previous RA default route. Native NetworkManager reapply, same-profile activation and one full reconnect did not restore it; normal IPv4 remained usable. Do not infer IPv6 recovery from sysctl flags alone. This build has no verified IPv6 leak protection.
- **Traffic block remains after a failure:** use **Restore normal networking**, or Settings → **Release CyberGhost traffic block**. The latter releases only this plugin’s guard. A local terminal can run `pkexec /usr/local/cyberghost/omarchy-bridge --stop`; approve authentication locally. Do not flush unrelated firewall tables.
- **Public IP failure:** the lookup is optional and uses IPv4 only. It does not prove DNS or IPv6 protection. The panel labels a successful address as the last lookup.
- **Trusted CLI unavailable:** check package ownership and parent-directory permissions in the host session. Do not relax executable trust checks to accommodate a remapped or writable installation.

After deliberately disconnecting any active VPN, remove the widget with Omarchy's native commands:

```bash
omarchy plugin disable petevo.cyberghost
omarchy plugin remove petevo.cyberghost
```

This removes the plugin checkout, not the vendor CLI package or your NetworkManager profile. Review the package-manager transaction separately to remove the CLI package; do not run the vendor uninstaller.

The optional kill switch is available only for Official CLI WireGuard. The preparatory guard restricts IPv6; the full IPv4/IPv6 block starts only after the client connects successfully and the WireGuard device is identified. A failed startup attempts rollback and retains a block, but helper death before full activation is not covered by a full-block guarantee. Intentional disconnect releases the block, and location switching temporarily releases it between sessions. See [SECURITY.md](SECURITY.md) for the precise scope.

## Runtime evidence and remaining checks

The reviewed 1.5.0-5 package was installed through the authorized Polkit flow. An agent-run DE/Frankfurt OpenVPN session produced an `ovpn` tunnel with the IPv4 route and a successful bound IPv4 lookup. An NL automatic OpenVPN session connected and had a route, DNS setup and ICMP connectivity, but HTTPS stalled against three IPv4 endpoints while the normal network remained usable; it was disconnected and recovery succeeded. This protocol/location combination is not considered verified.

An explicitly discovered NL Amsterdam WireGuard server (`amsterdam-s405-i23`) connected through the official client. Kernel and NetworkManager external-device checks agreed, the client output reported the selected server, an independent country lookup reported NL, and the bound public IPv4 differed from the DE session. A bounded capture of one randomized DNS query observed one outgoing packet on `cyberghost` and none on Wi-Fi; this verifies only that tested query path, not public IPv6 DNS or general leak protection. The doc-prefix IPv6 address survived connect/disconnect and host IPv6-disable flags remained 0. The previous IPv6 RA default route is still absent; a bounded router-discovery probe saw no valid advertisement during 12 seconds, which does not establish the cause. No saved Wi-Fi settings or unrelated firewall rules were changed.

With the kill switch enabled, the NL Amsterdam session had a different bound public IPv4 from the DE session and direct Wi-Fi IPv4 was blocked. A forced WireGuard link-down retained the traffic guard and blocked physical IPv4; link-up restored connectivity. Intentional disconnect removed the CyberGhost nftables table and restored normal IPv4. An explicit protection check compares the current kernel-reported nftables table fingerprint and WireGuard interface index/fwmark with the recorded values; it does not verify packets, handshake, provider identity, or IPv6 DNS.

The native panel loaded in the existing shell. Actual mouse checks passed bar opening with location discovery, tabs, the kill-switch toggle, connect, protection verification, saved individual-server selection, location switching and disconnect. Native Locations/Details/Settings renders were checked in dark and light themes at 1920×1080/150%; the original theme was restored. An independent Impeccable review returned `ship` with no material blockers. Keyboard tests exercised searchable country/city/server pickers, protocol revalidation, connect/switch/disconnect, details/settings, the explicit IP lookup and Escape/reopen. Favorites survived a native shell restart and passed apply/remove/resave checks. Plugin discovery, disable, removal, restoration and re-enable were exercised, preserving saved favorites and other plugin enabled states. Wi-Fi handoff in both directions and bounded suspend/resume passed, with the same tunnel and recovered bound IPv4. External public IPv6 recovery/leak checks remain blocked by the lack of current router advertisements/global IPv6 on the available networks. The NetworkManager fallback attempt failed; the user confirmed its provider-side record had been deleted. The obsolete profile was preserved and its activation attempt stopped. It needs a separately provisioned provider configuration to become usable again. Automatic reconnect is not implemented.
