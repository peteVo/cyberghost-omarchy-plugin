# Security review and runtime evidence

## Package and privilege boundary

The package contains the checksum-pinned CyberGhost 1.5.0 Ubuntu 22.04 executable and a reviewed patch for its resolver hook. It omits the unused HTTP certificate download, never runs the vendor installer/uninstaller/completion generator, and installs the bundled OpenVPN private key as root-owned mode 0600. Do not print, copy, or commit vendor keys, account configuration, archives, packages, or private diagnostics.

Version 1.5.0-4 was built and installed through the authorized Polkit flow. The root-owned `/usr/local/cyberghost/omarchy-bridge` uses Python isolated mode, maps the authenticated Polkit UID through NSS, sets a minimal environment, validates a narrow country/city/server/protocol grammar, and launches only the fixed vendor executable. It adds no daemon or custom Polkit rule. A root-owned lock serializes operations while the adapter is alive; a vendor descendant may survive helper death or timeout, so status must be refreshed before retrying. The unprivileged bridge checks executable ownership, effective writability, and parent directories.

Authentication stays in CyberGhost's official client. The bridge does not read account configuration, store passwords, or infer endpoints. CLI output is untrusted and errors are sanitized. Public-IP lookup is explicit, IPv4-only, and sends the address to `api.ipify.org`; it does not prove routing integrity, DNS behavior, or IPv6 protection.

## Resolver and routing limits

The package depends on `systemd-resolvconf`. Its patched hook requires active `systemd-resolved`, configures per-link DNS and `~.` routing, and reverts settings on disconnect. It refuses to rewrite the global `resolv.conf`. Runtime DNS observations confirm the resolver stub remained in place and tunnel DNS routing was configured; they do not establish leak prevention.

Initial client sessions changed the global IPv6-disable flag from 0 to 1; later WireGuard sessions showed 0. DE OpenVPN disconnect restored the observed IPv6 routes and flags. WireGuard GUI disconnect restored normal IPv4 routing/public IP, removed tunnel DNS, retained the resolver stub and left NetworkManager/resolved active. IPv6-disable flags returned to 0, but the immediate IPv6 default route was missing despite one in the baseline; full IPv6 recovery is not established. Native NM reapply, same-profile activation and a full reconnect did not restore that route, while normal IPv4 and services remained usable. No persistent Wi-Fi settings or firewall rules were changed. There is no kill switch or tested DNS/IPv6 leak-protection guarantee. Do not infer location, handshake, or tunnel integrity from a connected label or exit code.

## Runtime tests

- **DE/Frankfurt OpenVPN:** agent-run session showed an `ovpn` device, IPv4 route, and successful bound IPv4 lookup. Disconnect restored the observed IPv6 flags/routes and normal resolver state.
- **NL automatic OpenVPN:** connected with route, DNS setup, and ICMP connectivity, but HTTPS stalled against three IPv4 endpoints while the normal network remained usable. The session was disconnected and recovery succeeded. This path remains unverified.
- **NL Amsterdam WireGuard:** the server was discovered from the official client, selected explicitly, and reported in client output. Kernel and NetworkManager external-device checks agreed; an independent country lookup reported NL, a bound public IPv4 lookup differed from DE, and `~.` DNS routing was present. This spot check does not establish leak protection.

These results are limited to the tested host and paths. No manual per-location configuration was downloaded. DE/Frankfurt WireGuard → NL/Amsterdam WireGuard switching was exercised through the GUI, with distinct bound IPv4 addresses and independent DE/NL country results. IPv6 route recovery remains unresolved. Do not share saved host captures: they may contain private IPs, DNS details, usernames, and device names.

The test suite reports 75 passing tests, including all eight package tests with `CG_TEST_PACKAGE`. Those tests use mocks and do not use account credentials or change host networking. Real connectivity tests use the official client's existing authentication flow.

## Remaining validation

The current native panel rendered in the existing 1920×1080 shell at 150% scaling. Keyboard search/selection, protocol changes, GUI connect/switch/disconnect, details/settings, IP lookup, favorites persistence and Escape/reopen were exercised. Plugin discovery, disable/remove/restore/enable were exercised without changing other plugin enabled states. Mouse clicks, light-theme rendering, Wi-Fi handoff, suspend/resume and packet-level leak testing remain unverified. The target's old NetworkManager profile was revoked on the provider website and failed its live activation check. It was preserved and its pending activation stopped; do not treat it as a working fallback. Credentials never enter this bridge.

OpenVPN status uses the vendor's reported state plus a routed tunnel, not cryptographic provider identity. Known NetworkManager VPNs are rejected before that attribution; an unrelated unmanaged OpenVPN tunnel can remain indistinguishable. The WireGuard interface name is also a convention, not cryptographic provider identity. NetworkManager's external-connection flag prevents attribution of a managed WireGuard profile, but an unrelated externally created tunnel with the same name may still be indistinguishable. Do not run one alongside this client. The vendor's stop operation may affect multiple client connections; the bridge refuses known conflicting NetworkManager VPNs but is not a global VPN ownership detector.
