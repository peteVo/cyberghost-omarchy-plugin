# Security and tested limits

## Package and authentication

The local 1.5.0-5 package preserves the SHA-pinned CyberGhost 1.5.0 Ubuntu 22.04 executable. It omits the unused HTTP certificate download and vendor installation scripts, patches the resolver hook for systemd-resolved, and installs the bundled OpenVPN key root-owned mode 0600. On this host the vendor-generated WireGuard configuration has a permissive file mode inside root-owned mode 0700 `/etc/wireguard`; ordinary users cannot traverse that directory. Never copy keys, account files, archives, packages or private diagnostics into Git.

Authentication stays in the official client. The bridge never reads account configuration, stores passwords or embeds application secrets. Errors are sanitized; raw vendor output does not enter the GUI. Public-IP lookup is explicit, IPv4-only and contacts `api.ipify.org`.

The root adapter uses Python isolated mode, a fixed vendor executable, strict operation/location grammar, NSS lookup of the authenticated Polkit UID, a minimal environment and a root-owned operation lock. The unprivileged bridge checks executable ownership, effective writability and parent directories. The packaged Polkit action binds administrator authentication to `/usr/local/cyberghost/omarchy-bridge`; active sessions use Polkit's temporary administrator-authentication cache. No permissive local `.rules` override or permanent daemon is installed. A vendor descendant can outlive helper death or timeout; refresh before retrying.

## WireGuard traffic guard

The adapter creates only its own `inet omarchy_cyberghost` nftables table and public, root-owned runtime metadata. It does not flush or alter unrelated firewall tables. Native loopback, WireGuard-marked transport, tunnel traffic and limited DHCP/IPv6 link-control traffic are allowed. Existing firewall chains still apply. Full blocking also blocks ordinary LAN access.

WireGuard connections stage an IPv6-only guard before starting the vendor. A private mount namespace makes IPv6 interface sysctls read-only for the vendor and its children, preserving host addresses instead of disabling host IPv6. The namespace is not a separate network namespace: the real tunnel remains usable by the desktop.

The optional **WireGuard-only kill switch is connection-scoped**. The full IPv4/IPv6 block starts after the vendor reports success and the adapter identifies the tunnel and nonzero transport mark. Unexpected link loss retains the block. A normal failed start attempts cleanup and installs a blocked state when requested. A hard kill/crash during startup can leave only the preparatory IPv6 guard or a recovery state; there is no boot-time or unconditional startup protection. Intentional disconnect releases the guard after proving tunnel absence; location switching releases it between sessions. Automatic server reconnection and automatic connection at login are unavailable.

Ordinary status says **configured** because it reads trusted metadata without privileged firewall polling. **Verify traffic protection** explicitly compares the current kernel-reported nft table fingerprint and, for an active session, interface index and WireGuard mark. It is a check at that moment, not continuous monitoring, a packet test, a handshake check or proof of provider identity. Recheck after firewall changes. An administrator or firewall reload can remove the rules. Release in Settings removes only this client's table, allowing normal networking without disconnecting another VPN.

## Resolver and IPv6 evidence

The patched hook requires active systemd-resolved, sets per-link DNS and `~.` routing, and reverts link settings on disconnect. It refuses to replace global `/etc/resolv.conf`; the host's resolved stub symlink remains in place. A bounded packet capture of a randomized DNS test query observed one outgoing tunnel packet and none on Wi-Fi. That demonstrates the tested query's path, not universal DNS leak prevention.

Early, unisolated vendor sessions disabled host IPv6. After disconnect an original IPv6 default route did not return, despite zero disable flags and native NM reapply/reactivation/full reconnect attempts. A bounded solicitation test observed no router advertisement, and the available networks currently have no global IPv6/default route. The cause and public IPv6 recovery remain unresolved; do not add stale routes or change RA/firewall settings blindly.

With the new namespace adapter, a pre-existing documentation-prefix IPv6 test address survived real connect/disconnect and all/default/Wi-Fi disable flags stayed zero. In fresh isolated network namespaces, actual TCP probes verified unmarked IPv4 and IPv6 blocking, marked transport allowance, IPv6-only behavior, normal recovery after removal and preservation of an unrelated nft table. These tests do not replace an external dual-stack leak test.

## Runtime evidence

- Dynamic DE/Frankfurt WireGuard to NL/Amsterdam switching worked through the native GUI without downloading manual location configurations. Earlier bound IPv4 and independent country lookups returned distinct DE/NL results. Automatic and explicitly discovered individual server selection were exercised.
- With package 1.5.0-5, NL/Amsterdam WireGuard connected, the explicit kernel guard check passed, bound VPN IPv4 differed from baseline, and direct Wi-Fi IPv4 requests failed. A forced tunnel link-down retained the guard and blocked direct IPv4; link-up recovered VPN traffic. Disconnect removed the table and restored ordinary IPv4. NM/resolved remained active.
- DE/Frankfurt OpenVPN had a routed tunnel and successful bound IPv4. NL automatic OpenVPN had routing/DNS/ICMP but HTTPS stalled against three endpoints. That path remains unverified; OpenVPN has no plugin traffic guard.
- The target's old NetworkManager profile `cyberghost` was revoked provider-side. It is preserved, not a working fallback. Other explicitly selected existing OpenVPN profiles remain supported through NM UUID checks.

105 automated tests pass with the built package, including resolver-hook failures, argument validation, serialization, privilege checks and malformed output. Mock tests do not change host networking or use account credentials. Approved live tests use the established vendor authentication flow. Host captures are private and ignored by Git.

## Attribution and remaining validation

Connection labels do not establish tunnel integrity, DNS protection, endpoint identity or location. Known conflicting NM VPNs are rejected. NM's external flag distinguishes the tested vendor WireGuard device from a managed profile, but an unrelated unmanaged tunnel named `cyberghost` may still be indistinguishable. OpenVPN attribution has a similar limitation. Do not run competing unmanaged tunnels. The vendor stop command can affect other client connections; this bridge is not a global VPN ownership detector.

Bidirectional saved-Wi-Fi/hotspot handoff passed with the same tunnel and recovered bound IPv4. Native suspend/resume slept for 16 seconds, woke automatically, retained the tunnel and passed bound IPv4 plus the kernel protection check; cleanup disconnected and removed the guard. Actual GUI mouse opening/tabs/toggle/connect/verify/specific-server switch/disconnect, keyboard search/Escape and native dark/light renders passed. Independent Impeccable review returned ship. External public IPv6 recovery/leak validation remains blocked by unavailable router advertisements/global IPv6. No blanket privacy guarantee is made.

## Toolbar icon follow-up

The ghost and its status badges describe reported connection state. They do not certify a handshake, route, firewall or leak test. The visual follow-up was checked on the installed 0.5 client using temporary non-networking UI fixtures; its real backend and theme were restored afterward. No privileged helper, account handling, VPN profile or networking configuration was changed for this icon update. Independent VM installation remains pending; TESTING.md pins the released baseline separately.
