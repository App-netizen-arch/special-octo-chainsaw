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
export PKG_CONFIG_EXECUTABLE="/usr/bin/pkg-config"
export PKG_CONFIG_PATH="/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig"

# Flutter's native-assets install step expects this dir to exist even when empty.
mkdir -p build/native_assets/linux

# Run the flutter command
FLUTTER_BIN="${REAL_FLUTTER:-flutter}"

# Special handling for `flutter run -d linux`:
# Flutter embeds conda/miniforge library paths in the CMake cache, which
# causes runtime symbol lookup failures. We work around this by:
# 1. Clean build to start fresh
# 2. Initial flutter build (populates CMake cache with conda paths)
# 3. Strip conda paths from CMake cache
# 4. Rebuild with cleaned cache
# 5. Let flutter run use the fixed binary
if [[ "$*" == *"run"* ]] && [[ "$*" == *"-d linux"* ]]; then
  BUILD_MODE="debug"
  if [[ "$*" == *"--release"* ]]; then
    BUILD_MODE="release"
  fi
  
  # Clean build to ensure CMake picks up sanitized environment
  rm -rf build/linux
  
  # Initial build
  "$FLUTTER_BIN" build linux --${BUILD_MODE}
  
  # Strip conda/miniforge paths from CMake cache
  CACHE_FILE="build/linux/x64/${BUILD_MODE}/CMakeCache.txt"
  if [ -f "$CACHE_FILE" ]; then
    sed -i 's|-Wl,-rpath,/home/amanoy/miniforge3/lib||g' "$CACHE_FILE"
    sed -i 's|-Wl,-rpath-link,/home/amanoy/miniforge3/lib||g' "$CACHE_FILE"
    sed -i 's|-isystem /home/amanoy/miniforge3/include||g' "$CACHE_FILE"
    sed -i 's|-L/home/amanoy/miniforge3/lib||g' "$CACHE_FILE"
  fi
  
  # Rebuild with cleaned cache
  "$FLUTTER_BIN" build linux --${BUILD_MODE}
  
  # Let flutter handle the run, which sets up the debugger connection
  # Strip the 'run -d linux' part from args to avoid duplication
  RUN_ARGS=("$@")
  FILTERED_ARGS=()
  skip_next=0
  for arg in "${RUN_ARGS[@]}"; do
    if [ $skip_next -eq 1 ]; then
      skip_next=0
      continue
    fi
    if [ "$arg" = "run" ] || [ "$arg" = "-d" ] || [ "$arg" = "linux" ]; then
      if [ "$arg" = "-d" ]; then
        skip_next=1
      fi
      continue
    fi
    FILTERED_ARGS+=("$arg")
  done
  
  exec "$FLUTTER_BIN" run -d linux "${FILTERED_ARGS[@]}"
else
  # For all other commands, just run flutter normally
  # If this was a build command, strip any conda paths from the binary RPATH
  "$FLUTTER_BIN" "$@"
  
  if [[ "$*" == *"build"* ]]; then
    BUNDLE_DIR="build/linux/x64/debug/bundle"
    if [[ "$*" == *"--release"* ]]; then
      BUNDLE_DIR="build/linux/x64/release/bundle"
    fi
    EXEC="$BUNDLE_DIR/counsel_ai"
    if [ -f "$EXEC" ]; then
      chrpath -r '$ORIGIN/lib' "$EXEC" >/dev/null 2>&1 || true
    fi
  fi
fi
