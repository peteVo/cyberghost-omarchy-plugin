# Security and evidence

## Trust boundaries

The 0.6 package candidate is `cyberghostvpn-omarchy` 1.5.0-8 with helper API
4. It provides and conflicts with the previous `cyberghostvpn` package, whose
1.5.0-7/API 4 version remains usable. The vendor executable is
checksum-pinned and unchanged. The package build includes vendor-distributed
material; never publish archives, keys, generated configurations, package
artifacts, account material, captures or personal diagnostics. The build
script runs as the user in private scratch space, prints one artifact path,
and does not install dependencies or the result. MIT applies to this project's code; vendor terms apply to the vendor
software and its distributed files. Arch packaging compliance, including
license text and the hardcoded `/usr/local` layout, is unresolved; no AUR
publication or compliance claim is made.

Authentication uses only the official client flow. The plugin does not read
account configuration, extract secrets, save passwords or embed application
credentials. Local diagnostics are read-only and return a fixed allowlist of
versions and prerequisite results. They omit usernames, profile names, IPs,
SSIDs, server lists, paths and raw errors; they make no external requests and
perform no authentication or network mutation. Raw vendor output is
sanitized before it reaches the UI. The explicit public IPv4 lookup is
third-party and binds to the detected tunnel interface; it is not part of
diagnostics.

The packaged API 4 root helper is root-owned, runs Python isolated mode, uses
fixed vendor/system command paths, strict arguments, a minimal environment,
NSS mapping for the authenticated Polkit UID and a private operation lock.
Its Polkit action binds authentication to the fixed helper path and relies on
Polkit's active-session cache. The unprivileged bridge checks ownership,
effective writability and parent directories before invoking it. No
user-writable privileged helper, permissive local Polkit rule or permanent
daemon is installed. Review the implementation and recipe before installing.

The helper serializes operations while it remains alive. It uses bounded
timeouts and attempts process-group cleanup on timeout and catchable
interruption. A detached vendor descendant or hard helper death may outlive
that cleanup. Refresh status before retrying; this is not a stronger
serialization guarantee.

## WireGuard protection limits

The optional WireGuard kill switch is connection-scoped. Preparation permits
only the native resolver UID to use IPv6 DNS ports 53/853; active and blocked
guards remove that exception. Full blocking starts only after the client
succeeds and the helper identifies the tunnel. Intentional disconnect and
switch release the guard. Startup and the interval between switched sessions
are not fully blocked. Hard helper death can leave an unverified preparation
state. There is no boot-time protection, automatic reconnect or hard-kill
guarantee.

Vendor connect/stop runs with IPv6 interface sysctls read-only in a private
mount namespace. This preserves host IPv6 configuration; it does not isolate
the vendor from the host network namespace. The helper creates only its own
nftables table and does not flush unrelated firewall tables. Full blocking
also blocks ordinary LAN traffic. Existing firewall chains still apply.

Ordinary status reports configuration. Explicit Verify checks the current
kernel table fingerprint and tunnel interface index/mark at that moment; it
is not continuous monitoring, a packet test, handshake check, provider
identity check or leak test. Firewall reloads or administrator changes can
remove protection. Do not infer routing, DNS, IPv6 protection or a kill switch
from an exit code, label or zero IPv6-disable flags.

OpenVPN does not use this WireGuard guard and can leave native IPv6 routed over
the physical network. Prefer WireGuard when using this experimental backend.
Automatic server reconnection and login startup are unsupported. The vendor
stop command may affect another unmanaged connection it cannot distinguish;
do not run competing unmanaged tunnels.

## Tested evidence and limits

On one dual-stack ThinkPad, package 1.5.0-7/API 4 WireGuard tests passed for
DE/Frankfurt and NL/Amsterdam, including changed tunnel-bound IPv4, randomized
A/AAAA DNS queries observed on the tunnel with no matching Wi-Fi egress,
blocking direct IPv6 and IPv6 DNS while guarded, and restoration of normal
IPv4, IPv6 route and DNS after disconnect. A forced link-down retained the
tested guard. Host addresses and IPv6 disable flags were preserved. These
results cover those bounded test paths only.

The 0.5 native GUI connect, individual-server selection, DE-to-NL switch,
tunnel-bound IP lookup, protection verification and disconnect passed on the
same host. Earlier 0.4 Wi-Fi handoff, suspend/resume and native UI checks
passed; they were not all repeated for 0.5. Package helper interruption,
firewall and DNS namespace checks passed. Automated CI uses Python 3.12 and
3.14 with mocks; package integration tests skip without a private package.
Fresh wider-machine validation has not been completed.

The earlier 0.4 IPv6 RA default-route loss cause remains unknown. IPv6 routing
returned before 0.5 testing without a plugin route, RA or firewall change.
OpenVPN UDP/TCP tests returned HTTPS from two endpoints each at default MTU,
but that does not establish that the earlier stall's cause was fixed; IPv6
remained on the physical route. The legacy test profile had a revoked provider-side record and was preserved;
no working fallback was claimed for it. Other explicitly selected
OpenVPN profiles remain supported, subject to local UUID/type validation.

No fresh second-machine VM result is available. A VM cannot establish physical
Wi-Fi roaming or laptop suspend/resume behavior. Report every untested path as
untested. No general privacy or leak-protection guarantee is made.

The 0.6 candidate passed 134 local mock/package tests with the private
cyberghostvpn-omarchy 1.5.0-8 artifact. The vendor binary, API 4 helper,
resolved patch and Polkit policy are unchanged from the reviewed 1.5.0-7
implementation. The new builder rejected an incorrect archive and kept
sources/artifacts private despite external makepkg destination overrides.
The package was built and inspected, not installed under its new name; its
fresh install/migration remains part of independent testing.

Native dark/light checks covered the shared panel/toolbar ghost, read-only
setup command, selectable allowlisted report, keyboard focus and Escape.
Non-networking fixtures covered missing setup, authentication failure,
cancelled authorization, timeout, malformed reports and asynchronous loading.
The real backend and original theme were restored. A pre-existing VPN and its
guard metadata remained unchanged; no VPN transition was performed for 0.6.
All captures remain private. These UI checks do not extend the earlier
packet-level protection evidence.
