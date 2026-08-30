#!/bin/bash
# Linux package creator for Counsel AI (.deb and AppImage)
# Usage: ./build_linux.sh [VERSION]
# Requires: Flutter Linux build, fpm, appimagetool

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$ROOT_DIR/app"
BUILD_DIR="$APP_DIR/build/linux/x64/release/bundle"
OUTPUT_DIR="$SCRIPT_DIR/output/linux"

VERSION="${1:-1.0.0}"
APP_NAME="counsel-ai"
APP_DISPLAY_NAME="Counsel AI"

echo "🔨 Building Counsel AI for Linux..."

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Build Flutter Linux release
cd "$APP_DIR"
flutter build linux --release

# Verify build
if [ ! -d "$BUILD_DIR" ]; then
    echo "❌ Error: Build directory not found at $BUILD_DIR"
    exit 1
fi

# Create .deb package using fpm
build_deb() {
    echo "📦 Creating .deb package..."
    
    DEB_BUILD_DIR=$(mktemp -d)
    DEB_INSTALL_DIR="$DEB_BUILD_DIR/usr/share/$APP_NAME"
    DEB_BIN_DIR="$DEB_BUILD_DIR/usr/bin"
    DEB_ICON_DIR="$DEB_BUILD_DIR/usr/share/icons/hicolor/512x512/apps"
    DEB_DESKTOP_DIR="$DEB_BUILD_DIR/usr/share/applications"
    
    # Copy application files
    mkdir -p "$DEB_INSTALL_DIR"
    cp -r "$BUILD_DIR"/* "$DEB_INSTALL_DIR/"
    
    # Create bin directory with launcher script
    mkdir -p "$DEB_BIN_DIR"
    cat > "$DEB_BIN_DIR/$APP_NAME" << 'EOF'
#!/bin/bash
exec /usr/share/counsel-ai/counsel_ai "$@"
EOF
    chmod +x "$DEB_BIN_DIR/$APP_NAME"
    
    # Copy icon (assuming it exists in the build)
    mkdir -p "$DEB_ICON_DIR"
    if [ -f "$APP_DIR/linux/flutter/assets/app_icon_512.png" ]; then
        cp "$APP_DIR/linux/flutter/assets/app_icon_512.png" "$DEB_ICON_DIR/$APP_NAME.png"
    else
        # Create placeholder or skip
        echo "⚠️  Icon not found, skipping"
    fi
    
    # Create desktop file
    mkdir -p "$DEB_DESKTOP_DIR"
    cat > "$DEB_DESKTOP_DIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_DISPLAY_NAME
Comment=AI workbench for legal professionals
Exec=/usr/bin/$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=Office;Development;
Keywords=legal;ai;document;research;
EOF
    
    # Build .deb with fpm
    if command -v fpm &> /dev/null; then
        fpm \
            --name "$APP_NAME" \
            --version "$VERSION" \
            --architecture amd64 \
            --description "Counsel AI - Local-first legal AI workbench" \
            --maintainer "Counsel AI <support@counsel-ai.example.com>" \
            --url "https://counsel-ai.example.com" \
            --license "MIT" \
            --package "$OUTPUT_DIR/${APP_NAME}_${VERSION}_amd64.deb" \
            -s dir \
            -t deb \
            "$DEB_BUILD_DIR=/"
        echo "✅ .deb created: $OUTPUT_DIR/${APP_NAME}_${VERSION}_amd64.deb"
    else
        echo "⚠️  fpm not found. Install with: gem install fpm"
    fi
    
    rm -rf "$DEB_BUILD_DIR"
}

# Create AppImage
build_appimage() {
    echo "📦 Creating AppImage..."
    
    APPIMAGE_BUILD_DIR=$(mktemp -d)
    APPIMAGE_APP_DIR="$APPIMAGE_BUILD_DIR/$APP_NAME.AppDir"
    
    # Create AppDir structure
    mkdir -p "$APPIMAGE_APP_DIR"
    cp -r "$BUILD_DIR"/* "$APPIMAGE_APP_DIR/"
    
    # Copy main executable
    cp "$BUILD_DIR/$APP_NAME" "$APPIMAGE_APP_DIR/"
    chmod +x "$APPIMAGE_APP_DIR/$APP_NAME"
    
    # Create AppRun symlink
    ln -sf "$APP_NAME" "$APPIMAGE_APP_DIR/AppRun"
    
    # Create desktop file
    cat > "$APPIMAGE_APP_DIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_DISPLAY_NAME
Comment=AI workbench for legal professionals
Exec=$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=Office;Development;
EOF
    
    # Copy or create icon
    if [ -f "$APP_DIR/linux/flutter/assets/app_icon_512.png" ]; then
        cp "$APP_DIR/linux/flutter/assets/app_icon_512.png" "$APPIMAGE_APP_DIR/$APP_NAME.png"
    fi
    
    # Create AppImage metadata
    cat > "$APPIMAGE_APP_DIR/appinfo.ini" << EOF
[AppImage]
Name=$APP_DISPLAY_NAME
Version=$VERSION
EOF
    
    # Build AppImage
    if command -v appimagetool &> /dev/null; then
        ARCH=x86_64 appimagetool \
            "$APPIMAGE_APP_DIR" \
            "$OUTPUT_DIR/${APP_NAME}-${VERSION}.AppImage"
        chmod +x "$OUTPUT_DIR/${APP_NAME}-${VERSION}.AppImage"
        echo "✅ AppImage created: $OUTPUT_DIR/${APP_NAME}-${VERSION}.AppImage"
    else
        echo "⚠️  appimagetool not found. Download from: https://github.com/AppImage/AppImageKit/releases"
    fi
    
    rm -rf "$APPIMAGE_BUILD_DIR"
}

# Run builds
build_deb
build_appimage

echo "🎉 Linux build complete!"
echo "   Outputs:"
echo "   - $OUTPUT_DIR/${APP_NAME}_${VERSION}_amd64.deb"
echo "   - $OUTPUT_DIR/${APP_NAME}-${VERSION}.AppImage"
