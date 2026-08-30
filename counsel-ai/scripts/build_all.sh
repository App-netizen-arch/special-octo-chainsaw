#!/bin/bash
# Counsel AI - Build all platform installers
# Usage: ./build_all.sh [VERSION] [--platform PLATFORM]
# Platforms: windows, macos, linux, all (default)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

VERSION="${1:-1.0.0}"
PLATFORM="${2:-all}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_help() {
    cat << EOF
Counsel AI - Multi-Platform Installer Builder

Usage: $0 [VERSION] [--platform PLATFORM]

Arguments:
  VERSION     Version number (default: 1.0.0)
  --platform  Target platform: windows, macos, linux, or all (default)

Examples:
  $0                    # Build all platforms with version 1.0.0
  $0 1.2.0              # Build all platforms with version 1.2.0
  $0 1.2.0 --platform macos  # Build only macOS

Prerequisites:
  Windows (MSI):
    - Inno Setup 6.x installed
    - Flutter Windows build tools
    - Visual Studio Build Tools
    
  macOS (DMG):
    - Xcode command line tools
    - create-dmg (optional, has fallback)
    - Flutter macOS build tools
    - Apple Developer account (for signing/notarization)
    
  Linux (.deb/.AppImage):
    - fpm (gem install fpm)
    - appimagetool
    - Flutter Linux build tools

Environment Variables (optional):
  CODESIGN_IDENTITY   macOS code signing identity
  APPLE_ID            Apple ID for notarization
  APPLE_PASSWORD      App-specific password
  APPLE_TEAM_ID       Apple Team ID
  SIGNTOOL_PATH       Path to Windows signtool

EOF
}

build_windows() {
    log_info "Building Windows installer..."
    
    if ! command -v iscc &> /dev/null; then
        log_error "Inno Setup compiler (iscc) not found. Please install Inno Setup."
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    iscc counsel_ai_installer.iss
    
    log_info "Windows installer created in scripts/output/windows/"
}

build_macos() {
    log_info "Building macOS DMG..."
    
    if [[ "$(uname)" != "Darwin" ]]; then
        log_warn "macOS build should run on macOS. Attempting anyway..."
    fi
    
    cd "$SCRIPT_DIR"
    chmod +x create_dmg.sh
    ./create_dmg.sh "$VERSION"
    
    log_info "macOS DMG created in scripts/output/macos/"
}

build_linux() {
    log_info "Building Linux packages..."
    
    if [[ "$(uname)" == "Darwin" ]]; then
        log_warn "Linux cross-compilation may have limitations."
    fi
    
    cd "$SCRIPT_DIR"
    chmod +x build_linux.sh
    ./build_linux.sh "$VERSION"
    
    log_info "Linux packages created in scripts/output/linux/"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            if [[ ! "$1" =~ ^- ]]; then
                VERSION="$1"
            fi
            shift
            ;;
    esac
done

echo "=========================================="
echo "Counsel AI Installer Builder"
echo "Version: $VERSION"
echo "Platform: $PLATFORM"
echo "=========================================="

case "$PLATFORM" in
    windows)
        build_windows
        ;;
    macos)
        build_macos
        ;;
    linux)
        build_linux
        ;;
    all)
        build_windows || log_warn "Windows build failed (expected on non-Windows)"
        build_macos || log_warn "macOS build failed (expected on non-macOS)"
        build_linux
        ;;
    *)
        log_error "Unknown platform: $PLATFORM"
        show_help
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Build Summary"
echo "=========================================="
echo "Check the output directories:"
echo "  Windows: scripts/output/windows/"
echo "  macOS:   scripts/output/macos/"
echo "  Linux:   scripts/output/linux/"
echo ""
log_info "Build complete!"
