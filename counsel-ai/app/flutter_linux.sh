#!/usr/bin/env bash
# Counsel AI — Flutter Linux build/run helper.
#
# Your shell exports conda/miniforge toolchain variables (CC, CXX, CMAKE_ARGS,
# CMAKE_PREFIX_PATH) that confuse CMake's GTK discovery, and shadow pkg-config.
# This wrapper sanitizes them for the duration of one flutter invocation.
#
# Usage:
#   ./flutter_linux.sh run            # run the desktop app on Linux
#   ./flutter_linux.sh build linux --release
#   ./flutter_linux.sh analyze        # any flutter subcommand works

set -euo pipefail
cd "$(dirname "$0")"

unset CC CXX CMAKE_ARGS CMAKE_PREFIX_PATH CONDA_BUILD_SYSROOT || true

# CMake's FindPkgConfig scans PATH for `pkgconf`/`pkg-config` and ignores the
# PKG_CONFIG_EXECUTABLE env var. Conda ships its own pkgconf that cannot see
# system GTK packages, so shadow it with a shim dir holding symlinks to the
# real system binaries.
SHIM="$PWD/.tools-bin"
mkdir -p "$SHIM"
ln -sf "$(command -v /usr/bin/pkgconf || echo /usr/bin/pkgconf)" "$SHIM/pkgconf" 2>/dev/null || true
ln -sf /usr/bin/pkg-config "$SHIM/pkg-config"
export PATH="$SHIM:/usr/local/bin:/usr/bin:/bin:$PATH"

# Flutter's native-assets install step expects this dir to exist even when empty.
mkdir -p build/native_assets/linux

exec flutter "$@"
