# Security and evidence

## Trust boundaries

The 0.8 source candidate uses `cyberghostvpn-omarchy` 1.5.0-10 with helper API
6. It provides and conflicts with the legacy `cyberghostvpn` package. API 4
remains compatible with connect/disconnect; switching requires API 5 and guarded recovery API 6. The
vendor executable is
checksum-pinned and unchanged. The package build includes vendor-distributed
material; never publish archives, keys, generated configurations, package
artifacts, account material, captures or personal diagnostics. The build
script runs as the user in private scratch space, prints one artifact path,
and does not install dependencies or the result. MIT applies to this project's
code; vendor terms apply to the vendor software and its distributed files.
There is no AUR compliance claim: Arch packaging standards prohibit installing
packages under `/usr/local`, and AUR submission requires a 0BSD source license
and REUSE metadata. The vendor's [published terms](https://www.cyberghostvpn.com/terms)
describe personal, non-transferable use and restrict distribution and
modification; they do not provide the permission needed for this repackaging
and resolved-hook patch. Its [Linux setup guide](https://support.cyberghostvpn.com/hc/en-us/articles/360020436274-Set-Up-CyberGhost-VPN-CLI-App-on-Linux)
documents account-dashboard downloads and the vendor installer, not an Arch
path override. These concrete `/usr/local` and license/permission issues leave
public AUR distribution blocked. Keep the build local and private.

Authentication uses only the official client flow. The plugin does not read
account configuration, extract secrets, save passwords or embed application
credentials. Local diagnostics are read-only and return a fixed allowlist of
versions and prerequisite results. They omit usernames, profile names, IPs,
SSIDs, server lists, paths and raw errors; they make no external requests and
perform no authentication or network mutation. Raw vendor output is
sanitized before it reaches the UI. The explicit public IPv4 lookup is
third-party and binds to the detected tunnel interface; it is not part of
diagnostics.

The packaged API 6 root helper is root-owned, runs Python isolated mode, uses
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
succeeds and the helper identifies the tunnel. Intentional disconnect releases
the guard. Location switching with a full kill switch is rejected by the UI,
Python bridge and root helper without mutation; the block remains. The vendor
cannot be safely bootstrapped under the full guard without a reviewed endpoint
constraint. Startup and the interval between ordinary guarded switched
sessions are not fully blocked. Hard helper death can leave an unverified
preparation state. There is no boot-time protection or hard-kill guarantee.

WireGuard location switching uses one privileged request and operation lock
across the old stop and new connect. It retains this plugin's nftables table
through an atomic bootstrap stage, but IPv4 and the native resolver's IPv6 DNS
exception remain allowed during that stage. The staged rules block IPv6 egress
and resolver DNS except for the native resolver, then check the new tunnel mark.
They preserve unrelated nftables tables. This evidence does not prove DNS
privacy or full IPv4 privacy. Protocol changes require disconnecting first.

Optional recovery is off by default, session-only, and arms only after an
explicit WireGuard connection started from the widget. It keeps a surviving
tunnel while waiting for network return. It waits at least 30 seconds after
fresh safe status and an uplink, with at most two attempts per user connection;
success does not reset that count. No guard uses the normal freshly validated
connect path. An absent tunnel with an owned active IPv6-only guard uses API 6:
root verifies its owner, kernel fingerprint and tunnel absence before staging
and one vendor connect. The unprivileged bridge requires the exact prior
requested target from a private boot/interface-bound record, avoiding catalog
DNS under the outage guard. Removed targets fail without substitution.
A failed guarded retry retains IPv6 guarding, removes the resolver bootstrap
exception, and leaves a prepared state requiring manual recovery. Full kill
switch recovery is refused without mutation. Generic failures can schedule a
last attempt after 60 seconds only if a new status is safe. Authentication,
authorization, timeout, uncertain status, protection and conflict errors pause
recovery. Polkit may prompt normally; there is no authorization bypass.
Panel disconnects and selection changes cancel it. Detected identity changes
or conflicting VPNs pause it. Disable it before external management with
`omarchy-shell petevo.cyberghost pauseRecovery`.

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
Login startup and recovery of full kill-switch outages are unsupported. The vendor
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
Broader independent validation remains incomplete; the later TryOmarchy guest
results and remaining gaps are recorded in TESTING.md.

The earlier 0.4 IPv6 RA default-route loss cause remains unknown. IPv6 routing
returned before 0.5 testing without a plugin route, RA or firewall change.
OpenVPN UDP/TCP tests returned HTTPS from two endpoints each at default MTU,
but that does not establish that the earlier stall's cause was fixed; IPv6
remained on the physical route. The legacy test profile had a revoked provider-side record and was preserved;
no working fallback was claimed for it. Other explicitly selected
OpenVPN profiles remain supported, subject to local UUID/type validation.

The later TryOmarchy guest pass exercised independent installation, bounded
WireGuard switching/recovery and disposable namespace policy checks; it did not
complete all live acceptance paths. A VM cannot establish physical
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

The 0.7 beta adds freshness timestamps for accepted status, explicit
protection checks and public IPv4 lookups. Tunnel and IPv4-route observations
are nullable; the manually selected NetworkManager profile route is unchecked.
These observations do not establish provider identity, DNS/IPv6 protection,
handshakes or continuous integrity. Quick Connect uses only the selected
favorite or last successfully connected location, freshly validates discovered
country/city/server choices, and stops when a saved target is unavailable.
Local saved-location settings are omitted from shareable diagnostics.

Notifications contain generic state/action text, not locations, IPs or raw
errors. Users can disable them; initial polling is silent, passive state
notices are deduplicated, and explicit operations may notify. Guided setup
offers the official terminal setup command without collecting credentials or
installing packages. No changes were made to the root helper, API 4, package
1.5.0-8, reconnection behavior or kill-switch behavior. Native dark/light
status/setup and focus/Escape checks passed. Native mock fixtures exercised
Quick Connect, cancellation, unavailable targets, authentication errors,
notification toggling and delayed-status navigation/Escape. The real backend,
original theme and plugin preferences were restored. No VPN transition was
performed; these UI checks add no network protection evidence.


The 0.8 live check exercised one bounded automatic reconnect after a controlled
stop through the reviewed helper. The session had been explicitly enabled and
armed through a GUI connection; recovery used one attempt. Its native GitHub
metadata check passed. The first native API5 switch was not confirmed. A
targeted backend switch subsequently returned a connected, active-guard session;
the original failure's cause is not established. Post-operation observation now
briefly settles kernel/NetworkManager state without repeating the mutation.
During the original attempt, 456 sampled kernel table checks found no missing
table, metadata absence or fingerprint mismatch. This sampled observation does
not prove continuous leak protection or convert the failed GUI assertion into
a passed connection test.

Isolated network-namespace packet checks passed for full-guard unmarked IPv4/IPv6
blocking, marked transport, the resolver-only bootstrap DNS exception, staged
IPv6 blocking, rejection of the old mark after replacement, acceptance of the
new mark, and preservation of an unrelated table. Actual host direct IPv4 and
IPv6 requests failed while the full guard was verified; both protocols worked
before connection and after cleanup. A later direct root-helper full-kill-switch refusal returned its policy-refusal
exit code and left guard metadata unchanged. Same-profile Wi-Fi down/up kept
the tunnel generation and guard; bound IPv4 worked after the network returned.
This was not an alternate-access-point handoff. The first RTC run did not confirm its post-wake assertion. A later bounded
API6 test passed actual suspend/wake, the same tunnel/guard fingerprint and
bound IPv4 after resume, then cleaned up through the reviewed helper. Further checks are
recorded in TESTING.md. No general privacy guarantee follows from these results.

The final API6 native acceptance deleted only the verified owned test tunnel,
retained its outage metadata and reconnected once through the widget's frozen
target. The new interface/mark matched the kernel firewall fingerprint, and
bound IPv4 worked. A bounded observer recorded 209 samples without a missing
table. The GUI then selected a freshly discovered NL individual server,
switched to a routed WireGuard connection and disconnected. Original
preferences were restored. This later passed GUI path does not establish the
cause of the original API5 failure or prove unsampled traffic protection.

Final host check: the VPN and guard were absent, NetworkManager/resolved were
active, the resolved stub link was unchanged, IPv6 disable flags were zero,
and normal public IPv4 worked. The currently active Wi-Fi differed from the
earlier dual-stack test profile and had no global IPv6 address/default route.
A normal NetworkManager reapply did not restore one. IPv6 recovery is therefore
unconfirmed for this final run; neither a plugin regression nor network-side
IPv6 availability was established. No static route, RA, DNS, firewall or IPv6
configuration workaround was applied.

The unreleased TryOmarchy compatibility fix changes only native palette
qualification and allowlisted local version parsing. It accepts the fixed
`try-omarchy-runtime` provider only for the existing `omarchy` report key;
unknown providers and malformed versions remain null. It adds no report keys,
vendor/account queries, public-IP requests or privileged operations. The
1.5.0-10/API6 helper, vendor executable, resolver patch, Polkit policy and
package recipe are unchanged. This fix does not extend the prior VPN or
protection evidence; the guest lacked a working public IPv6 baseline.
