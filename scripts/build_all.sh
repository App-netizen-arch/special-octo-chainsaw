#!/bin/bash
# scripts/build_all.sh
# Builds Counsel AI for Windows, Linux, and Android only.
# macOS/iOS support has been removed.

set -e

echo "🏗️  Starting Counsel AI Build Pipeline (Windows, Linux, Android)"

# Ensure dependencies are installed
echo "📦 Installing dependencies..."
cd backend
pip install -r requirements.txt
cd ../app
flutter pub get
cd ..

# Build Backend Wheels (Optional: for bundling)
echo "🐍 Building backend components..."
# Add any backend packaging steps here if needed

# --------------------------
# 1. Windows Build (.msi)
# --------------------------
echo "🪟  Building Windows Installer..."
if command -v iscc &> /dev/null; then
    bash scripts/build_windows.sh
    echo "✅ Windows installer created in dist/"
else
    echo "⚠️  Inno Setup (iscc) not found. Skipping Windows MSI build."
    echo "   Install Inno Setup: https://jrsoftware.org/isdl.php"
fi

# --------------------------
# 2. Linux Build (.deb, .AppImage)
# --------------------------
echo "🐧 Building Linux Packages..."
if command -v fpm &> /dev/null; then
    bash scripts/build_linux.sh
    echo "✅ Linux packages created in dist/"
else
    echo "⚠️  fpm not found. Skipping Linux .deb/.AppImage build."
    echo "   Install fpm: gem install fpm"
fi

# --------------------------
# 3. Android Build (.apk / .aab)
# --------------------------
echo "🤖 Building Android App..."
cd app
if command -v flutter &> /dev/null; then
    # Check if ANDROID_HOME is set
    if [ -z "$ANDROID_HOME" ]; then
        echo "⚠️  ANDROID_HOME not set. Skipping Android build."
        echo "   Set ANDROID_HOME to your Android SDK path."
    else
        flutter build apk --release
        # Optional: flutter build appbundle --release
        echo "✅ Android APK created in build/app/outputs/flutter-apk/"
    fi
else
    echo "⚠️  Flutter not found. Skipping Android build."
fi
cd ..

echo "🎉 Build pipeline finished."
echo "📦 Artifacts located in ./dist and ./app/build/"
