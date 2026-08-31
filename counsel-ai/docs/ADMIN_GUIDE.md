# Counsel AI - Administrator Guide

## Table of Contents
1. [Installation](#installation)
2. [User Management](#user-management)
3. [Model Configuration](#model-configuration)
4. [Security Settings](#security-settings)
5. [Backup & Recovery](#backup--recovery)
6. [Troubleshooting](#troubleshooting)

## Installation

### System Requirements
- **Windows:** 10/11 (64-bit), 8GB RAM, 10GB storage
- **Linux:** Ubuntu 20.04+/Debian 11+, 8GB RAM, 10GB storage
- **Android:** Android 10+, 4GB RAM, 5GB storage (mobile companion app)

### Silent Installation (Enterprise)

**Windows (PowerShell):**
```powershell
msiexec /i CounselAI-1.0.0.msi /quiet ADDLOCAL=all API_KEY="your-api-key"
```

**Linux (.deb):**
```bash
sudo dpkg -i counsel-ai_1.0.0_amd64.deb
```

**Linux (AppImage):**
```bash
chmod +x counsel-ai-1.0.0.AppImage
./counsel-ai-1.0.0.AppImage
```

**Android:**
```bash
adb install counsel-ai-1.0.0.apk
```

For enterprise Android deployment, use MDM solutions or Google Play Private Channel.

### First-Time Setup
1. Launch Counsel AI from Applications/Start Menu
2. Complete onboarding wizard (jurisdiction, privacy preferences)
3. Admin user should log in first to configure firm settings

## User Management

### Adding Users
1. Navigate to **Admin → Users**
2. Click **Add User**
3. Enter email, name, and assign role:
   - **Admin:** Full access including user management
   - **Lawyer:** Chat, research, documents, tools
   - **Paralegal:** Chat, documents (read-only on research)
   - **Viewer:** Read-only access

### Role-Based Access Control
| Feature | Admin | Lawyer | Paralegal | Viewer |
|---------|-------|--------|-----------|--------|
| Chat | ✓ | ✓ | ✓ | ✗ |
| Research | ✓ | ✓ | Read-only | ✗ |
| Documents | ✓ | ✓ | ✓ | Read-only |
| Skills Mgmt | ✓ | ✓ | ✗ | ✗ |
| User Mgmt | ✓ | ✗ | ✗ | ✗ |
| Audit Logs | ✓ | ✗ | ✗ | ✗ |

## Model Configuration

### Local Mode (Default)
- Uses llama.cpp with GGUF models
- No data leaves the device
- Recommended for maximum privacy

### API Mode
1. Go to **Settings → Model**
2. Select provider (DeepSeek, OpenAI-compatible)
3. Enter API key (stored in secure storage)
4. Toggle "API Mode" in mode selector

### Model Licensing
Counsel AI only includes commercially-licensed models:
- DeepSeek (commercial use allowed)
- Mistral (Apache 2.0)
- Gemma (commercial terms apply)

⚠️ **Warning:** Loading non-commercial models will trigger a license warning on startup.

## Security Settings

### Encryption
- SQLite database: AES-256-GCM encrypted
- Uploaded documents: Encrypted at rest
- API keys: OS secure storage (Windows Credential Manager, Linux Secret Service/KWallet, Android KeyStore)

### Two-Factor Authentication
1. **Admin → Firm Settings → Privacy & Security**
2. Enable "Enforce Two-Factor Authentication"
3. Users will be prompted to set up 2FA on next login

### Audit Logging
- All user actions logged by default
- View logs at **Admin → Audit Logs**
- Export available for compliance reviews

### Data Retention
Configure retention period:
1. **Admin → Firm Settings → Data Retention**
2. Set conversation retention (default: 90 days)
3. Configure auto-purge schedule

## Backup & Recovery

### Manual Backup
```bash
# Windows
copy "%APPDATA%\CounselAI\counsel.db" backup-location\

# Linux
cp ~/.local/share/CounselAI/counsel.db backup-location/

# Android (requires ADB)
adb pull /sdcard/Android/data/com.counselai.app/files/counsel.db backup-location/
```

### Restore from Backup
1. Close Counsel AI completely
2. Replace `counsel.db` with backup
3. Restart application

**Note for Android:** Use ADB to restore:
```bash
adb push counsel.db /sdcard/Android/data/com.counselai.app/files/
```

### Clear All Data
For complete wipe:
1. **Admin → Firm Settings → Data Retention**
2. Click **Clear All Data**
3. Confirm action (irreversible)

## Troubleshooting

### Backend Not Starting
1. Check if port 8000 is available
2. Review logs at:
   - Windows: `%APPDATA%\CounselAI\logs\`
   - Linux: `~/.local/share/CounselAI/logs/`
   - Android: Use `adb logcat | grep CounselAI`

### Model Loading Issues
- Verify GGUF file integrity (checksum provided)
- Ensure sufficient RAM (minimum 8GB for desktop, 4GB for Android)
- Try smaller model variant

### API Connection Errors
1. Verify API key is correct
2. Check network connectivity
3. Review firewall rules for outbound HTTPS

### Performance Issues
- Enable GPU offload in Settings → Advanced (Windows/Linux with CUDA/Vulkan)
- Reduce context window size
- Use smaller model variant

### Android-Specific Issues
- **Storage permissions:** Ensure app has storage permission enabled
- **Model downloads:** Use Wi-Fi for large model downloads
- **Background processing:** Disable battery optimization for background tasks

## Support

For additional support:
- Email: support@counsel-ai.example.com
- Documentation: https://docs.counsel-ai.example.com
- Status page: https://status.counsel-ai.example.com

---
*Last updated: January 2025*
