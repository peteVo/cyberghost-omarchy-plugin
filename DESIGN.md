# Native Omarchy VPN panel

Operate mode for a 13-inch ThinkPad. Preserve Omarchy's native `Ui.BarIconButton`,
`Ui.Panel`, `Ui.KeyboardPanel`, `Ui.PanelHero`, buttons, searchable dropdowns,
text fields, section labels and separators. Keep the panel within its 360-unit
design width and scroll above 550 units. Use the existing shell process and
settings API; do not add a daemon or second Quickshell.

Use `Style.font` and the shell's spacing, border, focus, hover, animation and
theme tokens. Follow the popup palette in dark and light themes; reserve
CyberGhost yellow for the connected mark. Render external text as plain text.
Keep connection state, selected next location and last public-IP lookup
separate.

Keep the primary action disabled until local prerequisites and backend state
make it actionable. Make loading, unknown, dependency, profile, authorization,
location-empty, waiting-network and recovery states clear and actionable.
Keyboard behavior stays native: Qt controls own editing and Tab navigation;
Escape closes and focused content scrolls into view. Offer only discovered
locations and servers. Label requested or client-reported location as such;
never imply independent provider verification.

The optional WireGuard kill switch is connection-scoped. Explain that full
blocking starts after connection and tunnel identification, and intentional
disconnect releases it. Full kill-switch switching is refused. Status reports configuration; explicit
Verify checks the current firewall fingerprint and tunnel generation. Neither
is continuous monitoring or proof of packets, handshake, provider identity or
universal leak protection. Preserve the startup and hard-kill caveats in the
interface.

## Verification

The native panel rendered in the existing shell at 1920×1080 and 150% scaling.
Final dark/light Locations, Details and Settings views and state fixtures were
reviewed after one correction batch. The independent interface review returned
ship. Keep all final captures private and unpublished.

The actual beta 0.5 GUI flow passed on package 1.5.0-7/API 4: mouse kill-switch
toggle, DE connect, tunnel-bound IPv4 lookup, protection Verify, fresh NL
discovery, specific-server selection, mouse switch, distinct tunnel-bound
IPv4, Verify and disconnect. The preference returned to off. Keyboard search,
selection and Escape checks passed. Package 1.5.0-7 dual-stack tests also
verified the connection guard, DNS routing and recovery; see [README.md](README.md)
and [SECURITY.md](SECURITY.md) for measured limits.

Qt lint completed without syntax or import errors; it reports 53
missing-property and 8 block-scope declaration warnings. Lint does not verify
rendering. A fresh second-PC Omarchy 4 VM remains untested.


The 0.6 candidate uses a single GhostIcon component for both toolbar and
panel hero. Toolbar opticalScale is applied inside the component because the
native loader owns its outer size; it retains the user-reviewed small
proportions while the panel uses its normal display size. Setup stays in the
official local terminal flow. Settings exposes a selectable read-only command,
a guide link and an explicit allowlisted report action; there is no credential
form or automatic privileged installation. The report has a bounded native
ScrollView, themed selection and clamped outer focus scrolling.

Actual dark/light rendering, report generation/selection, command focus and
Escape passed on the existing shell. First-use, auth/cancel/timeout, malformed
report and nonblocking loading fixtures passed with the real backend restored.
One correction bounded report focus scrolling. Independent source and visual
reviews found no material blocker. The existing VPN/guard and original theme
were preserved; captures are private. Qt lint exits 0 with dynamic-property
and declaration-style warnings, not syntax/import errors.


The 0.7 everyday-use update preserves this native visual system and the small
shared ghost. Connection health separates nullable tunnel/IPv4-route observations
from time-stamped explicit verification and public-IP lookup. Accepted status
expires after 45 seconds (or a backwards clock change); failed observations
show unavailable. Manual-profile routes remain unchecked.

Quick Connect validates a chosen favorite or last successful location through
fresh discovery before starting a connection. Missing chosen favorites never
fall back silently. Only confirmed connects/switches update the local preference,
which the user can forget. Cancellation applies during discovery. Quick Connect
controls stay in Locations so Details and Settings remain focused.

Guided setup reuses local prerequisites, a visible setup shortcut and the
copyable official terminal command. It never inspects authentication or handles
credentials. Native notifications use generic text, respect the user's toggle
and the shell's DND behavior, keep initial polling quiet and suppress repeated
passive states. They are observations, not proof of protection.

Native dark/light, setup focus and Escape checks passed. Mock native checks
covered saved targets, cancellation, unavailable servers, auth errors and a
delayed worker; stale status and keyboard navigation remained usable. One
layout correction kept Quick Connect out of other tabs. The real backend,
original theme and exact plugin preferences were restored; no live VPN
transition was performed. Captures stay private.

The 0.8 candidate adds a session-only recovery toggle and explicit installed
versions/release metadata in Settings. Recovery defaults off, arms after an
explicit widget WireGuard connection, keeps a surviving tunnel through uplink
loss and limits absent-tunnel retries to two after fresh safe observations.
API6 can retain an owned IPv6-only guard during retry of the exact previous
target. Full traffic blocks require manual recovery. Explain the limits next
to the toggle; never suggest startup or continuous protection.

Version information reuses the allowlisted local report. The separate update
button makes an anonymous request to this project's GitHub releases and shows
the published tag, time checked, fixed release-notes link and copyable Omarchy
update command. It does not install packages or fetch assets. Setup and update
results scroll into view using the existing native focus/scroll pattern.

Native dark/light recovery, versions, update result, toggle/cancellation, focus
and Escape checks passed with mock state in the existing shell. One correction
made the update result scroll into view. Final confirmation captures were
inspected; keep them private. Actual API6 network acceptance is recorded
separately in TESTING.md. The shared ghost proportions remain unchanged.

## Connection-home redesign

The connection home adopts the user-approved Windows reference's hierarchy
within the existing native Omarchy panel. A centered state label and 116-unit
circular power control lead, followed by the requested/client-reported location,
an explicit public IPv4 lookup placeholder or last result, protocol and duration.
The location row opens Locations. Quick Connect lives on Home; discovery,
server selection and switching remain in Locations. Details retains health,
freshness and verification context. A connected appearance remains reported
state, not a protection claim.

Settings separates Preferences, Safety and Support. Safety contains recovery,
its expandable explanation, kill-switch configuration and explicit protection
actions; Support contains setup and the allowlisted report. Existing controls
and backend behavior are retained. Keep the small shared ghost, Omarchy font,
palette and interaction tokens, 360-unit width and scrolling above 550 units.
This is a hierarchy change within the incumbent system, with no new visual
identity, dependencies, helper or package changes.

Actual connected dark/light views, tab and keyboard navigation, and Escape
passed in the existing native shell. Temporary mock-backend native fixtures
also passed disconnected Home, a power-control connect/disconnect roundtrip,
the explicit IP action and long-location dark/light rendering. The actual
active guard hash was unchanged; the real backend and original theme were
restored. Python ran 158 tests: 149 passed and nine private-package tests
skipped without an artifact. All 28 direct Node UI-logic behavior checks
passed. Qt lint exited 0 with dynamic-property warnings. No real
connect/disconnect was performed for this redesign; loading and error redesign
paths remain untested. Earlier evidence above is historical, not a claim that
every feature was retested. Captures under
`build/ui-redesign/` remain private and unpublished; this pass adds no network
protection evidence.

Home traffic extension: session download/upload totals sit above protocol/duration
using the same native two-column layout. The running widget accumulates validated
counter deltas across identified tunnel generations in memory; it resets on
disconnect, a new connection, backend/profile change or shell restart. An
initially observed connection starts tracking from its first fresh sample.
Unknown/stale counters stay unknown;
zero remains a real zero. The explicit IP action stays on Home with last-lookup
age and a tooltip identifying the third-party service. No automatic IP requests,
new privileges, dependencies or background processes are introduced.

Connected dark/light Home with real interface counters was inspected in the
existing shell; the new Home IP action completed a tunnel-bound lookup.
The active guard was preserved and the original theme restored. The focused
review found no material issue in this bounded scope. Automated checks ran
162 Python tests (153 passed, nine private-package skips), 29 Node checks,
and Qt lint exited 0 with existing warnings. No new VPN transitions were tested.
