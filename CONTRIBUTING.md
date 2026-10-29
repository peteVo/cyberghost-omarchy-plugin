# Contributing

Thanks for helping improve the Omarchy integration. Keep reports reproducible
and limited to information needed to understand the behavior.

## Bug reports

Use the bug report form and include the plugin commit, package/client versions,
Omarchy version, the selected backend/protocol, steps to reproduce and a
sanitized GUI message. The panel's **Generate shareable diagnostic report** output is designed for
sharing. Review it before posting.

Never attach raw vendor logs, account/profile/configuration files, credentials,
keys, IP addresses, DNS names, SSIDs, server lists, usernames, personal file
paths, packet captures or screenshots with network details. Do not post the
contents of `/etc/wireguard`, client account files or shell history. Do not change unrelated NetworkManager profiles to reproduce a report.

## Changes

Keep the native Omarchy APIs and short-lived Python/QML process model. Do not
add a permanent daemon or second Quickshell process. Automated tests must use
mocks and must not use account credentials or change host networking. Preserve
the root-owned API 4 package boundary, official-client authentication flow,
strict input validation and the rule that unrelated NetworkManager profiles
and firewall tables are not modified.

For UI changes, check the rendered panel in the existing shell when available;
static lint is not visual evidence. Keep documentation aligned with measured
evidence and clearly label untested behavior. The target's revoked
`cyberghost` provider entry must remain preserved without claiming it works.
