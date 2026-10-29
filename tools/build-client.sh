#!/usr/bin/env bash
# Build the reviewed recipe without installing anything or running vendor setup.
set -euo pipefail
umask 077

archive=""
case $# in
  0) ;;
  2)
    [[ $1 == --archive && -f $2 ]] || { echo 'Usage: build-client.sh [--archive FILE.zip]' >&2; exit 2; }
    archive=$(realpath -- "$2")
    ;;
  *) echo 'Usage: build-client.sh [--archive FILE.zip]' >&2; exit 2 ;;
esac
(( EUID != 0 )) || { echo 'Build as your normal user, never as root.' >&2; exit 1; }
for command in makepkg patch bsdtar; do
  command -v "$command" >/dev/null || { echo "Missing $command; install Arch base-devel and libarchive locally." >&2; exit 1; }
done

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/cyberghost-build.XXXXXXXX")
# Keep vendor sources and key-bearing artifacts private even with user overrides.
export PKGDEST="$build_dir" SRCDEST="$build_dir" SRCPKGDEST="$build_dir"
export LOGDEST="$build_dir" BUILDDIR="$build_dir" PKGEXT='.pkg.tar.zst'
cp -- "$project_dir/packaging/cyberghostvpn/"{PKGBUILD,resolved-only.patch,omarchy-bridge,org.petevo.cyberghost.policy} "$build_dir/"
if [[ -n $archive ]]; then
  cp -- "$archive" "$build_dir/cyberghostvpn-ubuntu-22.04-1.5.0.zip"
fi

# Runtime dependencies are reviewed/installed separately; makepkg verifies hashes.
(cd -- "$build_dir" && makepkg --nodeps) >&2
mapfile -t artifacts < <(cd -- "$build_dir" && makepkg --packagelist)
[[ ${#artifacts[@]} == 1 && -f ${artifacts[0]} ]] || { echo 'Expected one built package; inspect the private build directory.' >&2; exit 1; }
chmod 600 -- "${artifacts[0]}"
printf '%s\n' "${artifacts[0]}"
