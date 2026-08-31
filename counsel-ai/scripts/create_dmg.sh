#!/bin/bash
# macOS DMG creator for Counsel AI
# Usage: ./create_dmg.sh [VERSION]
# Requires: create-dmg, Flutter macOS build completed, Xcode command line tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$ROOT_DIR/app"
BUILD_DIR="$APP_DIR/build/macos/Build/Products/Release"
OUTPUT_DIR="$SCRIPT_DIR/output/macos"

VERSION="${1:-1.0.0}"
APP_NAME="Counsel AI"
APP_BUNDLE="Counsel AI.app"
DMG_NAME="counsel-ai-${VERSION}.dmg"

echo "🔨 Building Counsel AI for macOS..."

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Build Flutter macOS release
cd "$APP_DIR"
flutter build macos --release

# Verify build
if [ ! -d "$BUILD_DIR/$APP_BUNDLE" ]; then
    echo "❌ Error: App bundle not found at $BUILD_DIR/$APP_BUNDLE"
    exit 1
fi

echo "📦 Creating DMG..."

# Option 1: Using create-dmg (preferred if available)
if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --app-drop-link 400 200 \
        --icon "$APP_BUNDLE" 200 200 \
        --background "../scripts/dmg_background.png" \
        "$OUTPUT_DIR/$DMG_NAME" \
        "$BUILD_DIR/$APP_BUNDLE"
    echo "✅ DMG created: $OUTPUT_DIR/$DMG_NAME"
else
    # Fallback: manual DMG creation using hdiutil
    TEMP_DIR=$(mktemp -d)
    cp -r "$BUILD_DIR/$APP_BUNDLE" "$TEMP_DIR/"
    
    # Create symlink to Applications
    ln -s /Applications "$TEMP_DIR/Applications"
    
    # Create DMG
    hdiutil create -volname "$APP_NAME" -srcfolder "$TEMP_DIR" -ov -format UDZO "$OUTPUT_DIR/$DMG_NAME"
    rm -rf "$TEMP_DIR"
    echo "✅ DMG created (fallback method): $OUTPUT_DIR/$DMG_NAME"
fi

# Code signing (optional - requires developer certificate)
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    echo "🔐 Code signing with identity: $CODESIGN_IDENTITY"
    codesign --force --deep --sign "$CODESIGN_IDENTITY" "$BUILD_DIR/$APP_BUNDLE"
    codesign --verify --verbose "$BUILD_DIR/$APP_BUNDLE"
else
    echo "⚠️  Skipping code signing (set CODESIGN_IDENTITY env var to enable)"
fi

# Notarization (optional - requires Apple Developer account)
if [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_PASSWORD:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ]; then
    echo "🔒 Notarizing app..."
    xcrun notarytool submit "$OUTPUT_DIR/$DMG_NAME" \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_PASSWORD" \
        --team-id "$APPLE_TEAM_ID" \
        --wait
    echo "✅ Notarization complete"
else
    echo "⚠️  Skipping notarization (set APPLE_ID, APPLE_PASSWORD, APPLE_TEAM_ID env vars)"
fi

echo "🎉 macOS DMG build complete!"
echo "   Output: $OUTPUT_DIR/$DMG_NAME"
