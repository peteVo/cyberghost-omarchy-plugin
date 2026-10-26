# CyberGhost for Omarchy 4

A native Omarchy bar widget and VPN panel with an experimental official-CLI integration. The default backend can control an existing NetworkManager **OpenVPN** profile. The target ThinkPad uses the official CLI; its older **`cyberghost`** profile (previously `openvpn`) was revoked on the provider website and is preserved, but cannot serve as a working fallback. A reviewed local CyberGhost CLI package supplies dynamic country, city and individual-server selection.

**Germany/Frankfurt → Netherlands/Amsterdam WireGuard switching was verified through the native GUI**, including country/city/server selection, different tunnel-bound public IPv4 addresses, independent DE/NL country checks, DNS setup and disconnect. NL OpenVPN connected and routed traffic, but HTTPS requests stalled. IPv6 route recovery remains unresolved on this host. This development build has no automatic reconnect or kill switch. The panel never invents locations or treats a connection label as evidence of leak protection.

## Install the development branch

Implementation is on [feat/official-cli-bridge](https://github.com/peteVo/cyberghost-omarchy-plugin/tree/feat/official-cli-bridge), tracked in [draft PR #1](https://github.com/peteVo/cyberghost-omarchy-plugin/pull/1). The default branch does not yet contain the plugin. From a normal Omarchy terminal, after reviewing the source:

```bash
# Stop if this directory already exists; inspect it instead of overwriting it.
git clone --branch feat/official-cli-bridge \
  https://github.com/peteVo/cyberghost-omarchy-plugin.git \
  ~/.config/omarchy/plugins/petevo.cyberghost
omarchy plugin validate ~/.config/omarchy/plugins/petevo.cyberghost
omarchy-shell shell rescanPlugins
omarchy plugin enable petevo.cyberghost
```

Click **CG** in the bar. The panel shows reported connection state, connection details, optional public IPv4 lookup, backend/profile selection, protocol and server choices, saved favorites, location switching, and read-only diagnostics. Tab navigates native controls; Escape closes the panel. Favorites persist locally; backend and profile choices last for the shell session unless set on the bar entry. No second Quickshell process is started.

Requirements: Omarchy 4 / Quickshell, Python 3 and NetworkManager. Official-CLI mode additionally needs the reviewed client package and local account setup. The optional fallback needs NetworkManager's OpenVPN plugin and a valid configured OpenVPN profile. Authentication and secrets remain with NetworkManager's secret agent or the official CyberGhost client. The plugin never imports, edits or deletes VPN profiles.

For a valid fallback on another setup, select its existing profile name in Settings and choose **Use profile**. An absent, ambiguous or non-OpenVPN profile disables connection controls. To persist a choice, the existing bar entry in `~/.config/omarchy/shell.json` accepts:

```json
{ "id": "petevo.cyberghost", "profile": "cyberghost", "backend": "manual-profile" }
```

Back up that file before editing. Develop in the real user-owned plugin checkout. Saved files trigger a plugin reload, but this installed shell retained old QML in its component cache; use `omarchy restart shell` when edits are not reflected, only while the session is unlocked. The installed API rejects symlinks inside plugins and has no verified checkout-link workflow. Never edit `/usr/share/omarchy` or run another Quickshell instance.

Once this work is merged by the maintainer, the intended normal install command is:

```bash
omarchy plugin add https://github.com/peteVo/cyberghost-omarchy-plugin.git --enable
```

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

Official-CLI mode is explicit; installing a CLI does not silently change the default backend. After package installation and local setup, choose **Settings → Official CLI** and **Locations → WireGuard**. To persist these choices on the installed bar entry:

```bash
omarchy-shell shell setBarWidget petevo.cyberghost backend '"official-cli"' '{}'
omarchy-shell shell setBarWidget petevo.cyberghost protocol '"wireguard"' '{}'
``` The reviewed package's root-owned adapter maps the authenticated Polkit UID through NSS, uses a minimal environment, and accepts only the supported connect/stop grammar. A root lock serializes operations while the adapter remains alive; a vendor descendant may survive helper death or timeout, so refresh status before retrying. The adapter handles no passwords and adds no daemon or Polkit rule.

### Reviewed local package

See [SECURITY.md](SECURITY.md) and [packaging/cyberghostvpn/PKGBUILD](packaging/cyberghostvpn/PKGBUILD). Version **1.5.0-4**:

- Packages the original x86-64 binary unchanged; never runs the vendor installer, uninstaller or completion generator.
- Omits the unused HTTP certificate download and installs the bundled private key as root-owned `0600`.
- Uses `systemd-resolvconf`, the packaged compatibility layer for resolved; does not replace resolver services.
- Patches the OpenVPN resolver hook to refuse global `resolv.conf` rewriting and report DNS setup failures. This is not a tested leak-prevention guarantee.
- Adds the narrowly scoped, root-owned Polkit adapter.

Build without installing runtime dependencies, in a scratch directory outside the plugin. Place the reviewed vendor ZIP there first:

```bash
CG_BUILD_DIR=$(mktemp -d)
cp packaging/cyberghostvpn/PKGBUILD packaging/cyberghostvpn/resolved-only.patch \
  packaging/cyberghostvpn/omarchy-bridge "$CG_BUILD_DIR/"
cp ~/Downloads/aur-review/cyberghostvpn/cyberghostvpn-ubuntu-22.04-1.5.0.zip "$CG_BUILD_DIR/"
(cd "$CG_BUILD_DIR" && makepkg --nodeps)
bsdtar -tvf "$CG_BUILD_DIR/cyberghostvpn-1.5.0-4-x86_64.pkg.tar.zst"
```

`--nodeps` permits packaging without installing runtime packages; it is not a runtime compatibility check. Build artifacts contain the vendor-distributed key and must remain private and outside Git. Do not use the separately packaged `cyberghostvpn-gui`.

After reviewing the package inventory, install its dependencies and the local artifact in your own terminal. Stop on proposed removals or unexpected core upgrades:

```bash
sudo pacman -S --needed wireguard-tools systemd-resolvconf
sudo pacman -U "$CG_BUILD_DIR/cyberghostvpn-1.5.0-4-x86_64.pkg.tar.zst"
```

The reviewed 1.5.0-4 package was built and installed through the authorized Polkit flow. Its adapter checksum is synchronized in `PKGBUILD` and `.SRCINFO`. The target has `wireguard-tools` and `systemd-resolvconf`; official account setup remains in the vendor client. Stop on conflicts or unexpected core upgrades. Do not run `pacman -Sy` or replace essential libraries.

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
CG_TEST_PACKAGE=/path/to/cyberghostvpn-1.5.0-4-x86_64.pkg.tar.zst \
  python3 -m unittest discover -s tests -v
```

The current suite reports 75 passing tests, including all eight package tests using `CG_TEST_PACKAGE`. Tests cover parsing/input validation, profile identity, conflicting VPNs, timeouts, sanitized output, root/user locking, IP response validation, and the authorizer boundary. Package tests inspect metadata/hashes and run only the resolver helper with mocked system commands. Automated tests use no account credentials and make no host network changes.

The installed Qt tool is `/usr/lib/qt6/bin/qmllint`. Its `qs` imports need the shell's virtual namespace mapped outside the plugin:

```bash
CG_QML_IMPORTS=$(mktemp -d)
ln -s /usr/share/omarchy/shell "$CG_QML_IMPORTS/qs"
/usr/lib/qt6/bin/qmllint -I "$CG_QML_IMPORTS" -I /usr/lib/qt6/qml BarWidget.qml Panel.qml
```

The final Qt6 lint exited 0 with 42 dynamic-property warnings and eight JavaScript declaration-style warnings; no syntax/import errors were reported. Check each warning; lint does not establish that the panel loads or renders correctly.

`bash tools/host-baseline.sh` takes a read-only network snapshot without making an external IP request. Keep its output local: it contains personal network details. Live tests use tunnel/route/DNS evidence and explicit opt-in public-IP checks. Do not include local/public IPs or DNS configuration in shared notes. Wi-Fi handoff and suspend/resume need separate practical tests.

## Troubleshooting and removal

- **Unknown / status unavailable:** retry diagnostics. The UI clears stale Connected state on helper/status errors. Confirm NetworkManager and the named OpenVPN profile in a normal host terminal.
- **Profile rejected:** select one unambiguous OpenVPN profile; Wi-Fi, WireGuard and other VPN types cannot be activated through the fallback.
- **Another VPN active:** deliberately disconnect it first. The plugin refuses overlapping NetworkManager VPNs; vendor `--stop` may affect multiple VPNs.
- **CLI setup incomplete:** complete the established client setup locally. Do not weaken ownership checks or create a password cache in the plugin.
- **CLI lists empty:** inspect installed help and redacted list formatting locally. The parser does not guess country/city names.
- **Authorization cancelled:** retry when you can approve the system prompt. A missing adapter requires the reviewed package, not a user-writable root script.
- **Timeout:** refresh before retrying. A privileged child may still be finishing; the user lock does not guarantee termination of vendor descendants after a crash or timeout.
- **IPv6 missing after disconnect:** the tested host returned IPv6-disable flags to 0 but did not recover its previous RA default route. Native NetworkManager reapply, same-profile activation and one full reconnect did not restore it; normal IPv4 remained usable. Do not infer IPv6 recovery from sysctl flags alone. This build has no verified IPv6 leak protection.
- **Public IP failure:** the lookup is optional and uses IPv4 only. It does not prove DNS or IPv6 protection. The panel labels a successful address as the last lookup.
- **Trusted CLI unavailable:** check package ownership and parent-directory permissions in the host session. Do not relax executable trust checks to accommodate a remapped or writable installation.

After any active VPN has been deliberately disconnected, use `omarchy plugin disable petevo.cyberghost` and `omarchy plugin remove petevo.cyberghost` to remove the widget. This does not uninstall the vendor CLI or delete your NetworkManager profile. Review package removal separately.

There is **no kill switch** and no tested DNS/IPv6 leak-protection guarantee. See [SECURITY.md](SECURITY.md) for the precise security scope.

## Runtime evidence and remaining checks

The reviewed 1.5.0-4 adapter was installed through Polkit. An agent-run DE/Frankfurt OpenVPN session produced an `ovpn` tunnel with the IPv4 route and a successful bound IPv4 lookup. Disconnect restored the baseline IPv6 flags/routes and normal DNS resolver state. An NL automatic OpenVPN session connected and had a route, DNS setup and ICMP connectivity, but HTTPS stalled against three IPv4 endpoints while the normal network remained usable; it was disconnected and recovery succeeded. This protocol/location combination is not considered verified.

An explicitly discovered NL Amsterdam WireGuard server (`amsterdam-s405-i23`) connected through the official client. Kernel and NetworkManager external-device checks agreed, the client output reported the selected server, an independent country lookup reported NL, and the bound public IPv4 differed from the DE session. DNS routing with `~.` was present. These observations establish a successful spot check, not a verified privacy guarantee. Initial sessions changed the global IPv6-disable flag from 0 to 1; later WireGuard sessions showed flags at 0. WireGuard GUI disconnect removed its interface and tunnel DNS, restored the normal IPv4 route/public IP and left NetworkManager/resolved active with the stub symlink intact. IPv6 all/default/Wi-Fi disable flags were 0 afterward, but the immediate IPv6 default route was absent despite one in the baseline. Native NetworkManager reapply, same-profile activation and one full Wi-Fi reconnect preserved normal IPv4 but did not restore the previous IPv6 RA route. No persistent Wi-Fi settings or firewall rules were changed. Flag values alone do not establish IPv6 recovery or leak protection.

The native panel rendered in the existing 1920×1080 shell at 150% scaling, with one shell instance. Keyboard tests exercised searchable country/city/server pickers, protocol revalidation, connect/switch/disconnect, details/settings, the explicit IP lookup and Escape/reopen. Favorites survived a native shell restart and passed apply/remove/resave checks. Cold-start testing found and fixed an initial response from the previous backend arriving after configured settings. Plugin discovery, disable, removal, restoration and re-enable were exercised, preserving saved favorites and other plugin enabled states. The independent Impeccable finish review returned **ship**, with no material fixes. The NetworkManager fallback attempt failed; the user confirmed its provider-side record had been deleted. The obsolete profile was preserved and its remaining activation attempt was stopped. It needs a separately provisioned provider configuration to become usable again. There is no kill switch, automatic reconnect, or tested DNS/IPv6 leak protection.
