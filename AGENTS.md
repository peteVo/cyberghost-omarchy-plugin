# Agent instructions

- Use Ponytail full: prefer the smallest robust change and native Omarchy/NetworkManager APIs.
- Use Impeccable Operate mode: accessibility and truthful connection state take priority over decoration.
- Keep CyberGhost authentication in its official client; never extract vendor application secrets, store plaintext passwords, or guess servers.
- Do not claim DNS/IPv6 protection or a kill switch until tested on real hardware; do not introduce a privileged writable helper.
- Run tests with \`python3 -m unittest discover -s tests -v\`, plus \`qmllint\` and \`omarchy plugin validate\` on Omarchy 4.
- Treat CLI output as untrusted; do not log credentials, tokens, or raw CLI responses.
- Do not mutate unrelated VPN profiles. The existing \`openvpn\` profile is the fallback.
