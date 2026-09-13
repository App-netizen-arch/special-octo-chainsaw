#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

BUNDLE_DIR="build/linux/x64/debug/bundle"
EXEC="$BUNDLE_DIR/counsel_ai"

if [ ! -x "$EXEC" ]; then
  echo "Build not found. Run ./flutter_linux.sh build linux --debug first."
  exit 1
fi

# The binary was built with an RPATH pointing at the conda miniforge lib dir.
# That libpangoft2 is incompatible with the system GTK stack, so we:
# 1) remove conda paths from LD_LIBRARY_PATH
# 2) preload the system pangoft2 so the dynamic linker uses it instead of
#    the conda one from the embedded RPATH.
SYSTEM_PANGOFT2="/usr/lib/x86_64-linux-gnu/libpangoft2-1.0.so.0"
if [ ! -f "$SYSTEM_PANGOFT2" ]; then
  echo "System pangoft2 not found at $SYSTEM_PANGOFT2"
  exit 1
fi

SANITIZED_LD_LIBRARY_PATH=$(echo "${LD_LIBRARY_PATH:-}" | tr ':' '\n' | grep -v "miniforge3" | grep -v "conda" | paste -sd: -)
export LD_LIBRARY_PATH="${SANITIZED_LD_LIBRARY_PATH:-/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu}"
export LD_PRELOAD="$SYSTEM_PANGOFT2"

exec "$EXEC" "$@"
