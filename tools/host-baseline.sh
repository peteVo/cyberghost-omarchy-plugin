#!/usr/bin/env bash
# Read-only local baseline. Output can reveal personal device/network details.
set -u
export LC_ALL=C
failed=0

run() {
  local label=$1
  shift
  printf '\n## %s\n' "$label"
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'unavailable: %s is not installed\n' "$1"
    failed=1
  elif ! "$@"; then
    printf 'unavailable: command failed (service/socket may be inactive or inaccessible)\n'
    failed=1
  fi
}

optional() {
  local label=$1
  shift
  printf '\n## %s\n' "$label"
  if command -v "$1" >/dev/null 2>&1; then
    "$@" || printf '%s\n' 'unavailable: command is unsupported or failed'
  else
    printf 'unavailable: %s is not installed\n' "$1"
  fi
}

printf '%s\n' 'Read-only host baseline. Keep this output local; review and redact before sharing.'
run 'OS release' cat /etc/os-release
optional 'Omarchy version' omarchy version

printf '\n## Package versions\n'
if command -v pacman >/dev/null 2>&1; then
  for package in cyberghostvpn openvpn wireguard-tools resolvconf openresolv systemd-resolvconf systemd networkmanager; do
    if version=$(pacman -Q "$package" 2>/dev/null); then
      printf '%s\n' "$version"
    else
      printf '%s: not installed\n' "$package"
    fi
  done
else
  printf '%s\n' 'unavailable: pacman is not installed'
  failed=1
fi

printf '\n## Relevant service states\n'
if command -v systemctl >/dev/null 2>&1; then
  for service in NetworkManager systemd-resolved; do
    state=$(systemctl is-active "$service" 2>/dev/null) || state=inactive-or-unavailable
    printf '%s: %s\n' "$service" "$state"
    if [[ $state != active ]]; then
      failed=1
    fi
  done
else
  printf '%s\n' 'unavailable: systemctl is not installed'
  failed=1
fi
run 'Resolver configuration target' readlink -f /etc/resolv.conf
run 'NetworkManager profiles (name, UUID, type)' nmcli -t -f NAME,UUID,TYPE connection show
run 'Active NetworkManager connections (UUID, state, type, device)' nmcli -t -f UUID,STATE,TYPE,DEVICE connection show --active
run 'IPv4 routes' ip -4 route show
run 'IPv6 routes' ip -6 route show
run 'systemd-resolved status' resolvectl status

exit "$failed"
