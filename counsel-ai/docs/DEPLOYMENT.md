# Counsel AI - Deployment Guide

This guide covers deployment options for Counsel AI, from single-machine installations to multi-user firm deployments.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Single Machine Installation](#single-machine-installation)
3. [Docker Deployment](#docker-deployment)
4. [Multi-User Firm Setup](#multi-user-firm-setup)
5. [Backup and Restore](#backup-and-restore)
6. [Updating Counsel AI](#updating-counsel-ai)
7. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- **CPU**: Intel Core i5 / AMD Ryzen 5 (8th gen or newer)
- **RAM**: 16 GB (32 GB recommended for local LLM)
- **Storage**: 50 GB SSD (more for multiple models)
- **OS**: 
  - Windows 10/11 (64-bit)
  - macOS 12+ (Monterey or later)
  - Linux (Ubuntu 22.04+, Fedora 38+, or equivalent)

### For Local LLM Inference
- **GPU** (optional but recommended): NVIDIA RTX 3060+ with 12GB VRAM
- **Additional RAM**: 32-64 GB for larger models (7B+)

### Network
- Internet connection required for:
  - API mode (DeepSeek, OpenAI)
  - Legal update monitoring
  - Research mode (search queries)
- Local mode works offline after initial setup

---

## Single Machine Installation

### Windows

1. **Download Installer**
   ```powershell
   # Download from releases page
   # counsel-ai-setup-1.0.0.exe
   ```

2. **Run Installer**
   - Double-click the installer
   - Follow the wizard
   - Choose installation directory (default: `C:\Program Files\Counsel AI`)

3. **First Launch**
   - Launch from Start Menu
   - Complete onboarding wizard
   - Download a model or configure API keys

### macOS

1. **Download DMG**
   ```bash
   # Download counsel-ai-1.0.0.dmg from releases
   ```

2. **Install**
   - Open DMG file
   - Drag Counsel AI to Applications folder
   - Eject DMG

3. **First Launch**
   - Open from Applications
   - May need to approve in Security & Privacy settings
   - Complete onboarding

### Linux (.deb)

```bash
# Install .deb package
sudo dpkg -i counsel-ai_1.0.0_amd64.deb
sudo apt-get install -f  # Fix dependencies if needed

# Launch
counsel-ai
```

### Linux (AppImage)

```bash
# Make executable
chmod +x counsel-ai-1.0.0.AppImage

# Run
./counsel-ai-1.0.0.AppImage

# Optional: Integrate with desktop
./counsel-ai-1.0.0.AppImage --appimage-extract-and-run
```

---

## Docker Deployment

For firms wanting centralized deployment with optional Redis caching.

### Prerequisites
- Docker 24+
- Docker Compose 2.0+
- Optional: Redis for caching

### Basic Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  counsel-backend:
    image: counsel-ai/backend:latest
    ports:
      - "8000:8000"
    volumes:
      - counsel-data:/app/data
      - counsel-models:/models
    environment:
      - COUNSEL_ENV=production
      - COUNSEL_ENCRYPT_AT_REST=true
      - COUNSEL_JWT_SECRET=<generate-secret>
    restart: unless-stopped

  # Optional Redis for caching
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  counsel-data:
  counsel-models:
  redis-data:
```

### Deploy

```bash
# Generate JWT secret
openssl rand -hex 32

# Edit docker-compose.yml with your secret
# Start services
docker-compose up -d

# Check logs
docker-compose logs -f counsel-backend
```

### Configure Flutter App

In the Flutter app settings:
- Backend URL: `http://your-server:8000`
- Enable API mode if using external LLM providers

---

## Multi-User Firm Setup

### Admin Configuration

1. **Create Admin Account**
   - First user created during setup is admin
   - Default admin password shown in logs (change immediately)

2. **Add Users**
   - Navigate to Admin panel
   - Create users with appropriate roles:
     - `admin`: Full system access
     - `lawyer`: Full legal features
     - `paralegal`: Drafting and research
     - `readonly`: View-only access

3. **Configure Firm Settings**
   ```python
   # Via admin API or UI
   {
     "allowed_domains": ["westlaw.com", "lexisnexis.com", ...],
     "model_policy": "local-first",  # or "api-allowed"
     "audit_access_roles": "admin,lawyer",
     "disclaimer_text": "Your custom disclaimer..."
   }
   ```

### Role-Based Access Control

| Feature | Admin | Lawyer | Paralegal | Readonly |
|---------|-------|--------|-----------|----------|
| Chat | ✓ | ✓ | ✓ | ✓ |
| Research | ✓ | ✓ | ✓ | ✗ |
| Document Generation | ✓ | ✓ | ✓ | ✗ |
| Skills Management | ✓ | ✓ | ✗ | ✗ |
| User Management | ✓ | ✗ | ✗ | ✗ |
| Audit Logs | ✓ | ✓* | ✗ | ✗ |
| System Settings | ✓ | ✗ | ✗ | ✗ |

*Lawyers can view audit logs if configured in firm settings

### Workspace Isolation

Each user has isolated:
- Conversations
- Document indices
- Skills (personal + shared built-ins)
- Tool connections
- Audit trail

---

## Backup and Restore

### Data Locations

| OS | Data Directory | Config |
|----|---------------|--------|
| Windows | `%APPDATA%\CounselAI\` | Same |
| macOS | `~/Library/Application Support/CounselAI/` | Same |
| Linux | `~/.local/share/CounselAI/` | `$XDG_DATA_HOME` |

### Backup Script

```bash
#!/bin/bash
# backup_counsel.sh

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Windows example (PowerShell)
# $BACKUP_DIR = "D:\Backups"
# $DATE = Get-Date -Format "yyyyMMdd_HHmmss"

# Stop application if running
# (Optional but recommended for consistent backups)

# Create backup
tar -czf "$BACKUP_DIR/counsel_backup_$DATE.tar.gz" \
  ~/.local/share/CounselAI/data/ \
  ~/.local/share/CounselAI/models/

echo "Backup created: counsel_backup_$DATE.tar.gz"
```

### Restore

```bash
# Stop application
# Extract backup
tar -xzf counsel_backup_20240101_120000.tar.gz -C ~/

# Restart application
```

### Database Backup (SQLCipher)

If using encrypted SQLite:
```bash
# The encryption key is stored in OS keychain
# Backup includes the encrypted DB file
# Key must be restored separately if migrating systems
```

---

## Updating Counsel AI

### Desktop App (Auto-Update)

The app checks for updates on launch:
- **Windows**: WinSparkle
- **macOS**: Sparkle
- **Linux**: Manual update or package manager

### Manual Update

1. **Download Latest Release**
   - Visit GitHub releases page
   - Download appropriate installer

2. **Install Over Existing**
   - Run installer
   - Data preserved automatically

3. **Verify**
   - Check version in Settings > About
   - Test core functionality

### Docker Update

```bash
# Pull latest image
docker-compose pull

# Recreate containers
docker-compose up -d

# Verify
docker-compose logs counsel-backend
```

### Model Updates

```bash
# List available models
python scripts/model_downloader.py list

# Download updated model
python scripts/model_downloader.py download mistral-7b-instruct

# Verify checksum
python scripts/model_downloader.py verify /path/to/model.gguf
```

---

## Troubleshooting

### Common Issues

#### Application Won't Start

**Windows:**
```powershell
# Check Event Viewer for errors
# Run as administrator once
# Reinstall Visual C++ Redistributables
```

**macOS:**
```bash
# Check Console.app for crash reports
# Try: xattr -cr /Applications/Counsel\ AI.app
# Reinstall from DMG
```

**Linux:**
```bash
# Check dependencies
ldd $(which counsel-ai)

# Install missing libraries
sudo apt-get install libgtk-3-0 libwebkit2gtk-4.0-37
```

#### Backend Connection Failed

1. **Check if backend is running**
   ```bash
   curl http://localhost:8000/api/health
   ```

2. **Check logs**
   ```bash
   # Desktop app logs location varies by OS
   # Docker: docker-compose logs counsel-backend
   ```

3. **Firewall**
   - Ensure port 8000 is open
   - Allow localhost connections

#### Model Download Fails

1. **Check internet connection**
2. **Verify HuggingFace accessibility**
3. **Manual download alternative:**
   ```bash
   # Download manually from HuggingFace
   # Place in appropriate models directory
   # Verify checksum
   python scripts/model_downloader.py verify /path/to/model.gguf
   ```

#### Performance Issues

**Slow responses:**
- Switch to API mode if local GPU insufficient
- Reduce context length in settings
- Use smaller quantized models (Q4_K_M)

**High memory usage:**
- Close other applications
- Use smaller models
- Enable GPU offload if available

### Getting Help

1. **Check logs** (Settings > Advanced > View Logs)
2. **Search existing issues** on GitHub
3. **Create new issue** with:
   - OS and version
   - Counsel AI version
   - Steps to reproduce
   - Log excerpts (redact PII)

### Support Contacts

- **Community Support**: GitHub Issues
- **Professional Support**: support@counsel-ai.example.com
- **Enterprise SLA**: See SUPPORT.md

---

## Security Best Practices

1. **Enable encryption at rest** (default in production)
2. **Use strong admin passwords** (12+ characters, mixed case, numbers)
3. **Regular backups** (weekly minimum)
4. **Keep system updated** (enable auto-updates)
5. **Restrict audit log access** to necessary roles
6. **Review tool connections** periodically
7. **Monitor audit logs** for unusual activity

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `COUNSEL_ENV` | `development` | Environment (development/production) |
| `COUNSEL_JWT_SECRET` | (auto-generated) | JWT signing secret |
| `COUNSEL_ENCRYPT_AT_REST` | `true` | Enable database encryption |
| `COUNSEL_DB_PATH` | `./data/counsel.db` | SQLite database path |
| `COUNSEL_MODELS_DIR` | `./models` | Model storage directory |
| `COUNSEL_LOG_LEVEL` | `INFO` | Logging level |
| `COUNSEL_TOOLS_MODE` | `simulate` | Tools mode (simulate/live) |

Set these before first launch for production deployments.
