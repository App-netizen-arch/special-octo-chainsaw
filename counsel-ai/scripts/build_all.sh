#!/bin/bash
# Counsel AI - Build all platform installers
# Usage: ./build_all.sh [VERSION] [--platform PLATFORM]
# Platforms: windows, linux, android, all (default)
# Note: macOS/iOS support has been removed.

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
  --platform  Target platform: windows, linux, android, or all (default)

Examples:
  $0                    # Build all platforms with version 1.0.0
  $0 1.2.0              # Build all platforms with version 1.2.0
  $0 1.2.0 --platform linux  # Build only Linux

Prerequisites:
  Windows (MSI):
    - Inno Setup 6.x installed
    - Flutter Windows build tools
    - Visual Studio Build Tools
    
  Linux (.deb/.AppImage):
    - fpm (gem install fpm)
    - appimagetool
    - Flutter Linux build tools
    
  Android (APK/AAB):
    - Android SDK with ANDROID_HOME set
    - Flutter Android build tools
    - Java JDK 11+

Environment Variables (optional):
  SIGNTOOL_PATH       Path to Windows signtool
  ANDROID_HOME        Android SDK path (required for Android build)
  KEYSTORE_PATH       Path to Android keystore for signing
  KEYSTORE_PASSWORD   Keystore password

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

build_android() {
    log_info "Building Android APK..."
    
    if [ -z "${ANDROID_HOME:-}" ]; then
        log_error "ANDROID_HOME not set. Please set it to your Android SDK path."
        return 1
    fi
    
    cd "$ROOT_DIR/app"
    
    if ! command -v flutter &> /dev/null; then
        log_error "Flutter not found. Please install Flutter."
        return 1
    fi
    
    flutter build apk --release
    
    log_info "Android APK created in app/build/app/outputs/flutter-apk/"
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
echo "Supported: Windows, Linux, Android"
echo "=========================================="

case "$PLATFORM" in
    windows)
        build_windows
        ;;
    linux)
        build_linux
        ;;
    android)
        build_android
        ;;
    all)
        build_windows || log_warn "Windows build failed (expected on non-Windows)"
        build_linux
        build_android || log_warn "Android build failed (ANDROID_HOME not set or Android SDK missing)"
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
echo "  Linux:   scripts/output/linux/"
echo "  Android: app/build/app/outputs/flutter-apk/"
echo ""
log_info "Build complete!"

