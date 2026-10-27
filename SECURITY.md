# Security and tested limits

## Package and authentication

The local 1.5.0-7 package preserves the SHA-pinned CyberGhost 1.5.0 Ubuntu 22.04 executable. It omits the unused HTTP certificate download and vendor installation scripts, patches the resolver hook for systemd-resolved, and installs the bundled OpenVPN key root-owned mode 0600. The vendor-generated WireGuard configuration is beneath root-owned mode 0700 `/etc/wireguard`; ordinary users cannot traverse that directory. Vendor subprocesses now inherit umask 0077. Never copy keys, account files, archives, packages or private diagnostics into Git or release assets.

Authentication stays in the official client. The bridge never reads account configuration, stores passwords or embeds application secrets. Errors are sanitized; raw vendor output does not enter the GUI. Public-IP lookup is explicit, IPv4-only and contacts `api.ipify.org`. It ignores curl configuration and binds to the detected VPN interface with `if!`; a missing interface cannot become a hostname or fall back to the ordinary network. The same interface generation must still exist afterward.

The API 4 root adapter uses Python isolated mode, fixed command paths, strict argument grammar, NSS lookup of the authenticated Polkit UID, a minimal environment and a root-owned operation lock. The unprivileged bridge checks executable ownership, effective writability and parent directories. The packaged Polkit action binds administrator authentication to the fixed adapter path; active sessions use Polkit's temporary administrator-authentication cache. No permissive local `.rules` override or permanent daemon is installed.

The vendor runs in a separate process group. On timeout or catchable interruption, the adapter kills that invocation's still-running group and waits before rollback. SIGTERM/SIGINT enter the rollback path, including interruption during guard preparation. Deliberately detached descendants and hard helper death remain limitations; refresh before retrying. Never kill processes by a broad name match.

## WireGuard guard and bootstrap DNS

The adapter creates only its own `inet omarchy_cyberghost` nftables table and public, root-owned runtime metadata. It does not flush or alter unrelated firewall tables. Loopback, marked WireGuard transport, tunnel traffic and limited DHCP/IPv6 link control are allowed. Existing firewall chains still apply. Full blocking also blocks ordinary LAN access.

All vendor connect/stop operations run in a private mount namespace with IPv6 interface sysctls read-only. The real host network namespace remains shared, so the desktop uses the tunnel while host IPv6 settings and addresses are preserved.

An IPv6-only guard is staged before explicit WireGuard startup. On a network using IPv6 DNS, the original preparation rules could prevent the vendor from resolving its endpoints. A controlled comparison reproduced the failure and restored startup by allowing only the `systemd-resolve` UID to send IPv6 TCP/UDP on DNS ports 53/853 during preparation. The active/blocked table replaces those rules atomically and contains no bootstrap resolver exception. A hard kill during preparation may retain that exception until explicit recovery. There is no full startup-protection guarantee.

The optional **WireGuard-only kill switch is connection-scoped**. The full IPv4/IPv6 block begins after client success and identification of the tunnel/nonzero transport mark. Unexpected link loss retains it. Normal failed startup or catchable interruption attempts stop and establishes a blocked state when requested. A hard SIGKILL cannot run cleanup and can leave only unconfirmed preparation metadata; IPv4 may remain available. The UI must distinguish that state from configured full blocking.

Intentional disconnect releases protection after proving tunnel absence. Location switching releases it between sessions. In a bounded test, the documented vendor connect command under a retained full guard returned success but removed the old tunnel without yielding usable new VPN traffic. The guard remained present throughout the observed samples. Protected atomic switching is therefore not implemented; no undocumented API or broad network exception was added to force it. Automatic server reconnection and login connection remain unavailable. Native WireGuard already recovered during the earlier Wi-Fi and suspend tests.

## Verification and recovery

Ordinary status reports **configured**, using trusted metadata without privileged firewall polling. **Verify traffic protection** compares the kernel table fingerprint and active interface index/mark at that moment. It does not continuously monitor firewall rules, handshakes, provider identity or leaks. An administrator/firewall reload can remove the table; recheck after firewall changes. Simulated removal of only this client's table was detected as unverified.

An absent tunnel or interrupted preparation has explicit recovery copy and an actionable disconnect/release path. Release removes only this plugin's table and can work through the trusted adapter even if the vendor binary is missing. It allows normal networking without disconnecting another VPN. Root/service/adapter prerequisites are checked locally without authentication or external requests; Python independently checks them before connect/switch. Account validity is established through the official flow when connecting, not by inspecting credentials.

## IPv6 and DNS evidence

The old 0.4 baseline lost an IPv6 RA default route, and its cause remains unknown. The route and working public IPv6 returned before the 0.5 tests; the plugin did not add routes or change RA/firewall settings to restore it.

On the verified dual-stack ThinkPad network with package 1.5.0-7/API 4, DE/Frankfurt and NL/Amsterdam WireGuard tests showed working tunnel-bound IPv4, changed public IPv4, blocked ordinary/physical IPv6 and blocked direct IPv6 DNS. Randomized A and AAAA test queries were observed leaving the tunnel, with no matching Wi-Fi egress. Disconnect restored public IPv6, the default route and existing global addresses; all/default/Wi-Fi disable flags stayed zero. These observations cover the tested paths, not every application or resolver mode.

Real disposable network-namespace TCP tests verify IPv4/IPv6 rejection, marked-transport allowance, IPv6-only behavior, removal/recovery and preservation of an unrelated nft table. Additional TCP/53 probes verify that the bootstrap UID is allowed DNS only, other UIDs/non-DNS traffic remain blocked, and activation removes the exception. The harness never modifies the host network namespace.

## Runtime evidence and protocol scope

- Native DE/Frankfurt to NL/Amsterdam WireGuard GUI switching, automatic and discovered individual servers, distinct bound IPv4 and earlier independent DE/NL country checks passed without manual location downloads.
- API 4 live tests: normal connection/verification passed; simulated table removal was detected; SIGTERM startup returned 130 with a verified blocked state; explicit release restored IPv4/IPv6; hard SIGKILL left a correctly unverified prepared state; stop/reconnect recovered and cleanup removed protection.
- The earlier NL automatic OpenVPN HTTPS stall did not recur in the new isolated-sysctl UDP/TCP tests: both passed two HTTPS endpoints at MTU 1500. This does not identify or permanently fix the original failure. OpenVPN left native IPv6 routed over Wi-Fi. Automatic/OpenVPN modes do not enable the plugin IPv6 guard or kill switch; the panel warns about possible IPv6 bypass. Prefer explicit WireGuard.
- The target's old NetworkManager profile was revoked provider-side. Preserve it; it is not a working fallback. Other explicitly selected valid OpenVPN profiles remain supported through UUID checks.

The local suite passes 125 tests with the built package and no skips. CI runs credential-free tests on Python 3.12/3.14; its nine artifact-dependent package tests explicitly skip when no private package is supplied. Native GUI, real account/network behavior and namespace packet checks are separate tests. Captures and host diagnostics remain private and ignored by Git.

## Attribution and wider validation

Status detects a tunnel and IPv4 route, not continuously verified traffic or cryptographic provider identity. Known conflicting NM VPNs are rejected. NM's external flag distinguishes the tested vendor WireGuard device from a managed profile, but an unrelated unmanaged tunnel named `cyberghost` may remain indistinguishable. OpenVPN attribution has a similar limitation. Do not run competing unmanaged tunnels; vendor stop may affect other client connections.

The 0.5 native panel passed mouse connect, fresh individual-server selection, Germany-to-Netherlands switching, interface-bound IP lookup, protection-check actions and disconnect. Dark/light Locations, Details and Settings renders plus missing-dependency, interrupted-startup, waiting-network and malformed-response fixtures were inspected after one correction batch. The original theme and real backend were restored. The preceding version also passed bidirectional Wi-Fi/hotspot handoff and bounded suspend/resume; those physical tests were not repeated for 0.5. A fresh Omarchy 4 VM on a second PC is planned but unavailable now; see TESTING.md. A VM can validate setup/GUI/networking, not physical Wi-Fi roaming or laptop sleep. No general privacy or leak-protection guarantee is made.
