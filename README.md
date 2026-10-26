# CyberGhost for Omarchy 4

**Experimental** Omarchy Quattro/Quickshell VPN bar widget with a truthful status panel.

This project works with your existing CyberGhost OpenVPN **NetworkManager profile** today. If CyberGhost's **official Linux CLI** is independently installed, configured and works on your computer, the widget can use the CLI's documented dynamic **country and city** selection. **Arch/Omarchy is not an officially supported CLI platform, so dynamic switching is not verified on the target laptop.** There is no public documented API for discovering and selecting arbitrary individual CyberGhost servers.

No unofficial account endpoint, app key obtained from proprietary software, or guessed server list is used. This is not yet a full Windows CyberGhost replacement.

## Install

\`\`\`bash
omarchy plugin add https://github.com/peteVo/cyberghost-omarchy-plugin.git --enable
\`\`\`

**Important:** The implementation currently lives in the [feature branch](https://github.com/peteVo/cyberghost-omarchy-plugin/tree/feat/official-cli-bridge), not master. To test this branch now, clone it directly:

\`\`\`bash
git clone -b feat/official-cli-bridge https://github.com/peteVo/cyberghost-omarchy-plugin.git \
  ~/.config/omarchy/plugins/petevo.cyberghost
omarchy-shell shell rescanPlugins
omarchy plugin enable petevo.cyberghost
\`\`\`

Requirements: Omarchy 4 with Quickshell, Python 3, NetworkManager with a configured VPN named \`openvpn\`. If you are using an official CyberGhost CLI (supported distros only), it must already be installed by CyberGhost, logged in, located in a **root-owned non-writable** binary path and have \`pkexec\` installed. The plugin never installs or authenticates into proprietary software.

Click **CG** in the Omarchy bar to open the panel. Without the vendor CLI, Connect/Disconnect manage **only your existing named NetworkManager profile** (default \`openvpn\`). In CLI mode, the selector first asks CyberGhost's official CLI for countries and cities; unrecognized lists are not faked. A city can also be entered manually, with strict name validation.

## Local checks and diagnostics

\`\`\`bash
cd ~/.config/omarchy/plugins/petevo.cyberghost
python3 -m unittest discover -s tests -v
python3 -m py_compile cg_bridge.py
python3 cg_bridge.py check
python3 cg_bridge.py status
python3 cg_bridge.py countries
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" BarWidget.qml Panel.qml
\`\`\`

Test click, Escape, popup reopening, mouse/keyboard focus, connect/disconnect, network changes, sleep/resume, and update/removal locally. Test DNS and IPv6 routing separately before relying on the connection for privacy. Do not assume a green/connected UI proves safety.

## Security and limits

- Credential management belongs **exclusively to the official CLI** or your existing NetworkManager profile. No password entry, file, token cache or custom cipher.
- Dynamic mode uses documented CLI operations. Privileged changes invoke **only the installed root-owned CyberGhost executable** through Polkit. The helper runs as your ordinary user; there is no root daemon or custom Polkit rule.
- Manual mode uses \`nmcli connection up/down id <profile>\`; it does not generate, install or modify new profiles.
- Input is validated and passed as subprocess arguments, never through the shell. VPN operations are serialized by a user-owned runtime lock.
- Public IP lookup is **opt-in** (\`api.ipify.org\`). The browser stays offline during regular status checks.
- **Not implemented/verified:** native account login, Arch-compatible dynamic discovery, individual-server selection, kill switch, DNS/IPv6 leak protections, automatic reconnect, true tunnel handshake verification, server load/latency, favorites, or live server changes in the manual-profile mode.
- If status cannot be parsed, display **Unknown** rather than claiming a protected connection. Unexpected vendor responses may require parser adjustments; do not invent locations.

## Update and remove

From the feature branch, use \`git pull --ff-only\` in the plugin directory. After merging to master, \`omarchy plugin update petevo.cyberghost\` works for a normal Omarchy installation.

To remove: disconnect the VPN first, then \`omarchy plugin remove petevo.cyberghost\`. Removal does not delete your NetworkManager profiles or vendor CLI account configuration.

## References

- [Official CyberGhost Linux CLI FAQ](https://support.cyberghostvpn.com/hc/en-us/articles/360020835894-CyberGhost-VPN-CLI-App-Linux-FAQ) — country/city CLI and supported Linux distros, excluding Arch.
- [Official city listing](https://support.cyberghostvpn.com/hc/de/articles/360020673194-W%C3%A4hle-unter-Linux-ein-Land-oder-eine-Stadt-mit-der-CyberGhost-VPN-CLI-App).
- [Manual OpenVPN setup](https://support.cyberghostvpn.com/hc/en-us/articles/360007929314-Set-Up-OpenVPN-on-Linux-Ubuntu-via-Network-Manager).
- [Omarchy Quattro plugin reference](https://plugins.omarchy.org/develop.html).
- [miguel.cyberghost](https://github.com/27mfp/miguel.cyberghost) — useful MIT comparison implementation, but it relies on undocumented vendor API integration that this project intentionally avoids pending authorization.

## Practical next milestone

Verify which CyberGhost integration, if any, works on the actual ThinkPad. If CyberGhost provides a **supported, authorized API** or Arch-compatible official CLI, implement live country/city/server lists on top of it. No undocumented key extraction or access-control bypass.
