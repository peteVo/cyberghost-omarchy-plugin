# CyberGhost for Omarchy 4

An experimental native Omarchy bar widget and VPN panel. The default backend controls your existing NetworkManager **OpenVPN** profile, named **`cyberghost`** on the target ThinkPad (previously `openvpn`). A reviewed local CyberGhost CLI package enables further testing of the provider's country, city and server commands.

**Germany/Frankfurt WireGuard was exercised in the host terminal; Netherlands switching and the rendered GUI have not been verified.** This is a development build, not a finished Windows-client replacement. The panel never invents locations or treats a connection label as evidence of leak protection.

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

Click **CG** in the bar. The panel shows the reported connection state, connect/disconnect, connection details, optional public IPv4 lookup, backend selection, profile selection, and diagnostics. Tab navigates native controls; Escape closes the panel. Settings chosen in the panel last for the shell session. No second Quickshell process is started.

Requirements: Omarchy 4 / Quickshell, Python 3, NetworkManager, its OpenVPN plugin, and an existing configured OpenVPN profile. Authentication and secrets remain with NetworkManager's secret agent or the official CyberGhost client. The plugin never imports, edits or deletes VPN profiles.

If your profile still has its old name, select `openvpn` in the panel and choose **Use profile**. An absent, ambiguous or non-OpenVPN profile disables connection controls. To persist a choice, the existing bar entry in `~/.config/omarchy/shell.json` accepts:

```json
{ "id": "petevo.cyberghost", "profile": "cyberghost", "backend": "manual-profile" }
```

Back up that file before editing. Develop in the real user-owned plugin checkout; edits hot-reload. The installed API rejects symlinks inside plugins and has no verified checkout-link workflow. Never edit `/usr/share/omarchy` or run another Quickshell instance.

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

The first list supplies countries, the second cities, and the third servers. `--connect` selects a live provider location; the CLI obtains the connection configuration using its authenticated account. You do not manually download one OpenVPN file per country. `--server` and protocol flags must be confirmed against the installed client's help before use.

The Python adapter implements country/city/server discovery and connect/stop commands. Parsing was checked against authenticated 1.5.0 captures: all 100 countries, three German cities, and 993 Frankfurt servers. Unrecognized output stays empty or Unknown. Individual-server controls, protocol controls, favorites, connection duration, verified endpoint/location details and automatic reconnect remain pending live validation. The experimental panel offers only discovered countries/cities and automatic server selection. Individual servers can be enumerated with `python3 cg_bridge.py servers --backend official-cli --country DE --city Frankfurt`, but server selection is not yet wired into connection controls. Disconnect before selecting a new connection; seamless switching is not established.

Official-CLI mode is explicit; installing a CLI does not silently change the default backend. A system installation must be root-owned and non-writable, including its parent directories. For graphical authorization it also needs the reviewed package's `omarchy-bridge` adapter. The vendor CLI uses `SUDO_USER` to find account configuration; direct `pkexec cyberghostvpn` incorrectly looks under `/home/root`. The small packaged adapter derives the username from Polkit's authenticated UID, accepts only connect/stop arguments, and launches the fixed vendor executable. It handles no passwords and adds no daemon or Polkit rule.

### Reviewed local package

See [SECURITY.md](SECURITY.md) and [packaging/cyberghostvpn/PKGBUILD](packaging/cyberghostvpn/PKGBUILD). Version **1.5.0-3**:

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
bsdtar -tvf "$CG_BUILD_DIR/cyberghostvpn-1.5.0-3-x86_64.pkg.tar.zst"
```

`--nodeps` permits packaging without installing runtime packages; it is not a runtime compatibility check. Build artifacts contain the vendor-distributed key and must remain private and outside Git. Do not use the separately packaged `cyberghostvpn-gui`.

**Package installation and account setup require explicit approval.** After approval, install `wireguard-tools` and `systemd-resolvconf` from the existing repository databases, then the inspected local package. Stop on conflicts or unexpected core upgrades. Do not run `pacman -Sy` or replace essential libraries. The target machine's 1.5.0-3 installation was confirmed through pacman metadata; the user confirmed official setup and `--help` succeeded.

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
```

Run the optional built-package tests with the actual private artifact:

```bash
CG_TEST_PACKAGE=/path/to/cyberghostvpn-1.5.0-3-x86_64.pkg.tar.zst \
  python3 -m unittest discover -s tests -v
```

Tests cover parsing/input validation, OpenVPN profile identity, UUID actions, conflicting VPNs, missing dependencies, authentication errors, timeouts, sanitized output, locking, IP responses, and the authorizer boundary. Package tests inspect metadata/hashes and run only the resolver helper with mocked system commands. Without `CG_TEST_PACKAGE`, package integration tests explicitly skip. No test connects a VPN or uses account credentials.

The installed Qt tool is `/usr/lib/qt6/bin/qmllint`. Its `qs` imports need the shell's virtual namespace mapped outside the plugin:

```bash
CG_QML_IMPORTS=$(mktemp -d)
ln -s /usr/share/omarchy/shell "$CG_QML_IMPORTS/qs"
/usr/lib/qt6/bin/qmllint -I "$CG_QML_IMPORTS" -I /usr/lib/qt6/qml BarWidget.qml Panel.qml
```

Dynamic shell/Loader properties may emit warnings even with exit status 0. Check each warning; lint does not establish that the panel loads or renders correctly.

`bash tools/host-baseline.sh` takes a read-only network snapshot without making an external IP request. Keep its output local: it contains personal network details. Before approved connection tests, save a private baseline of services, resolver target, active profiles, routes, IPv6 state and DNS. Test DE/Frankfurt → disconnect → NL with real tunnel/route/DNS evidence and explicit opt-in public-IP checks. Restore the normal connection and confirm DNS afterward. Wi-Fi handoff and suspend/resume need separate practical tests.

## Troubleshooting and removal

- **Unknown / status unavailable:** retry diagnostics. The UI clears stale Connected state on helper/status errors. Confirm NetworkManager and the named OpenVPN profile in a normal host terminal.
- **Profile rejected:** select one unambiguous OpenVPN profile; Wi-Fi, WireGuard and other VPN types cannot be activated through the fallback.
- **Another VPN active:** deliberately disconnect it first. The plugin refuses overlapping NetworkManager VPNs; vendor `--stop` may affect multiple VPNs.
- **CLI setup incomplete:** complete the established client setup locally. Do not weaken ownership checks or create a password cache in the plugin.
- **CLI lists empty:** inspect installed help and redacted list formatting locally. The parser does not guess country/city names.
- **Authorization cancelled:** retry when you can approve the system prompt. A missing adapter requires the reviewed package, not a user-writable root script.
- **Timeout:** refresh before retrying. A privileged child may still be finishing; the user lock does not guarantee termination of vendor descendants after a crash or timeout.
- **Public IP failure:** the lookup is optional and uses IPv4 only. It does not prove DNS or IPv6 protection. The panel labels a successful address as the last lookup.
- **Sandbox session reports no trusted CLI:** this agent session remaps system ownership and blocks DBus/netlink/desktop sockets. Do not relax checks to accommodate it. Verify from the real desktop session.

After any active VPN has been deliberately disconnected, use `omarchy plugin disable petevo.cyberghost` and `omarchy plugin remove petevo.cyberghost` to remove the widget. This does not uninstall the vendor CLI or delete your NetworkManager profile. Review package removal separately. Enable/disable/removal and live shell rendering still require host verification.

There is **no kill switch** and no tested DNS/IPv6 leak-protection guarantee. See [SECURITY.md](SECURITY.md) for the precise security scope.

## Target-machine evidence and remaining gate

On 26 October 2026, the user ran the approved Germany/Frankfurt WireGuard test in the host terminal. Saved private captures show: NetworkManager and systemd-resolved active; the normal resolver stub symlink preserved; a WireGuard device named `cyberghost`; an IPv4 internet route through that device; a successful public IPv4 response; and DNS servers plus the `~.` routing domain on the tunnel. This is user-assisted runtime evidence, not an agent-executed privileged test. The selected country was not independently geolocated.

The vendor's `--status` said **“No VPN connections found.”** both before and during the WireGuard connection. The bridge therefore checks the known WireGuard interface and kernel internet route before considering that CLI response. This reports operational tunnel state, not a current handshake or privacy guarantee.

IPv6 routes present before the connection disappeared afterward. Why they changed, whether IPv6 was disabled, and whether disconnect restores them remain unverified. Do not rely on leak protection. No Netherlands transition, disconnect recovery, GUI rendering, Polkit prompt, Wi-Fi handoff or suspend/resume test has been completed in this session.

The agent's managed shell denied system DBus/netlink queries and rejected the authorized disconnect attempt with `pkexec must be setuid root`. Textual user permission did not remove those restrictions. Remaining live actions need a permitted host session or explicit local user execution; do not bypass the sandbox. The draft PR must remain draft until the dynamic-switching and visual gates are complete.
