# Beta test checklist

This checklist is for a fresh Omarchy 4 virtual machine. All VM results are
pending; none of these steps are claimed as tested. It tests the released 0.5
baseline. The native ghost icon follow-up is separate and unmerged, so this
checklist does not claim fresh VM validation of that follow-up. A VM can check
installation, dependencies, the native panel and VPN behavior. It cannot
validate physical Wi-Fi handoff or laptop suspend/resume.

## Get the intended build

- [ ] Use a disposable, current Omarchy 4 VM snapshot. Confirm the normal guest
  network works with VPN disconnected. Keep the test isolated from the host.
- [ ] Test tag `v0.5.0-beta.1`, expected commit
  `f78b2ed6a719ae619d0f774a825959c3441b2532`. The default branch does not
  identify this release candidate. Stop if the tag resolves to a different
  commit; do not test an unqualified default-branch install and report it as
  0.5.
- [ ] For a new checkout, run `omarchy plugin add
  https://github.com/peteVo/cyberghost-omarchy-plugin.git` and answer **No**
  when asked to enable it. Then run the commands below. If the plugin is
  already installed, preserve its checkout and local changes; stop unless it
  is clean and its `origin` is the expected repository.

  ```bash
  cd ~/.config/omarchy/plugins/petevo.cyberghost
  git status --short
  git remote -v
  git fetch origin tag v0.5.0-beta.1
  git rev-parse 'v0.5.0-beta.1^{commit}'
  git show --stat --format=fuller v0.5.0-beta.1
  ```

  Confirm the resolved commit equals the expected SHA above, inspect the tag
  diff, then install and enable that exact build:

  ```bash
  git switch --detach v0.5.0-beta.1
  omarchy plugin validate .
  omarchy plugin enable petevo.cyberghost
  ```

  If the checkout is not clean, do not replace or reset it; preserve its
  changes and use a separate disposable VM checkout.
- [ ] Run the repository's mock suite and static checks (below). Automated
  tests must not use credentials or change host networking.
- [ ] Review `packaging/cyberghostvpn/PKGBUILD`, `.SRCINFO`, the resolved-only
  hook patch, and the fixed-path adapter. Build package **1.5.0-7** from the
  reviewed recipe and its checksum-pinned vendor archive, in a private scratch
  directory outside the checkout. Inspect the package inventory. Do not commit
  the archive, package, keys, configs, or diagnostics. Follow the 0.5 release
  tag's [README.md](https://github.com/peteVo/cyberghost-omarchy-plugin/blob/v0.5.0-beta.1/README.md) for the matching package 1.5.0-7 / API 4 build and install
  procedure.
- [ ] Install only after reviewing the package-manager transaction. Required
  runtime dependencies are listed in the PKGBUILD (`bash`, `curl`, `glibc`,
  `zlib`, `python` (3.12+), `openvpn`, `wireguard-tools`, `systemd-resolvconf`,
  `util-linux`, `nftables`, `iproute2`, and `polkit`). Stop if unexpected removals/upgrades appear.
- [ ] Complete account/device setup only through `sudo cyberghostvpn --setup`
  in the VM's local terminal. Never put credentials in Git, test notes, chat,
  screenshots, or shell history you plan to share.

## Panel and VPN behavior

- [ ] Confirm the bar entry opens the native panel. New GUI entries should
  start with **Official CLI / WireGuard**.
- [ ] With VPN disconnected, run the read-only preflight:
  `python3 cg_bridge.py check --backend official-cli`. Record pass/fail and the
  client/package versions only; do not paste raw command output.
- [ ] Connect using Official CLI / WireGuard to Germany / Frankfurt. Confirm
  the guest has a tunnel and routed IPv4, then use the panel's explicit IPv4
  lookup. Record only whether it succeeds and whether the result changes after
  switching; do not record the addresses.
- [ ] Switch through the panel to Netherlands / Amsterdam. Confirm the old
  tunnel is stopped before a new one starts, the guest has a routed tunnel,
  and the explicit IPv4 result differs from Frankfurt. Treat displayed
  country/server as reported state, not proof of provider identity.
- [ ] Make one bounded randomized A lookup and one randomized AAAA lookup while
  connected. Manual packet capture is optional; if `tcpdump` is unavailable or
  capture is not performed, mark packet-routing evidence **untested**. When
  capture is performed, manually observe each matching randomized query on the
  tunnel interface (>0 packets) and guest uplink (0 packets) to pass. Any
  matching query observed on the uplink is a **failure**; an incomplete or
  inconclusive capture is **untested**. Discard query names, addresses, captures,
  and raw logs after
  recording only the pass/fail/untested result.
- [ ] Use **Verify traffic protection** while the WireGuard guard is configured
  and record its pass/fail result. Enable the optional kill switch before connecting
  for the full-block test. Check that direct guest IPv4
  is blocked while the connected guard is active and that normal IPv4 returns
  after intentional disconnect. Do not claim protection during startup or a
  hard kill; switching intentionally releases the guard between sessions.
- [ ] Confirm DNS and ordinary guest networking recover after disconnect.
  IPv6 results require both a verified global IPv6 address/default route inside
  the guest and an independent external IPv6 baseline. If either is absent,
  mark public IPv6 recovery/leak behavior **untested**; zero disable flags or a
  documentation-prefix address are not evidence of public IPv6 recovery.
- [ ] Keep the NetworkManager OpenVPN fallback separate. Only test it with a
  valid, explicitly selected OpenVPN profile. Do not recreate the deleted
  `cyberghost` profile, alter unrelated connections, or infer support from a
  successful CLI exit code.

## Cleanup and report

- [ ] Disconnect the VPN and confirm ordinary guest networking is restored.
- [ ] Plugin removal and CLI package removal are separate operations. Removing
  the widget removes the plugin checkout; it does not remove the vendor CLI or
  NetworkManager profiles. Review each package-manager transaction separately
  and never use the vendor uninstaller.
- [ ] Share a sanitized checklist with exact plugin commit/tag, package version,
  client version, protocol, tested VM/Omarchy version, and pass/fail/untested
  for each item. Do not share IPs, DNS names/configuration, credentials, keys,
  vendor configs, captures, screenshots with network details, or raw logs.

## Credential-free local checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cg_bridge.py packaging/cyberghostvpn/omarchy-bridge
bash -n tools/host-baseline.sh
```

The package integration tests skip unless `CG_TEST_PACKAGE` points to a
locally built artifact. Without it, 9 package tests are expected to skip; with
the private 1.5.0-7 artifact, run:

```bash
CG_TEST_PACKAGE=/path/to/cyberghostvpn-1.5.0-7-x86_64.pkg.tar.zst \
  python3 -m unittest discover -s tests -v
```

These checks do not validate the native GUI or live VPN behavior.
