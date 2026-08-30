# Counsel AI - User Manual

## Welcome to Counsel AI

Counsel AI is a professional legal AI workbench designed for lawyers, paralegals, and law firms. It provides:

- **Private AI Chat** - Confidential conversations with AI assistance
- **Deep Legal Research** - Verified citations from legitimate sources only
- **Document Generation** - Legal documents with live MDX preview
- **Multi-Agent Verification** - Automated checking of citations, clauses, and PII
- **Legal Update Monitoring** - Daily updates from official sources
- **Tool Integration** - Connect Gmail, Outlook, and Calendar (with consent)

---

## Getting Started

### First Launch
1. Open Counsel AI from your Applications folder or Start Menu
2. Complete the onboarding wizard:
   - Select your jurisdiction (country/state)
   - Choose privacy preference (Local-first recommended)
   - Accept Terms of Service and Privacy Policy

### Login
1. Enter your email and password provided by your firm administrator
2. Click **Sign In**
3. If you have 2FA enabled, enter the verification code

---

## Main Features

### 1. Chat Mode

**Purpose:** Quick questions, drafting assistance, legal analysis

**How to use:**
1. Select mode from top bar: Local (default), API, Research, or Tools
2. Type your question in the chat box
3. Press Enter or click Send
4. View AI response with citations below

**Tips:**
- Use "New Chat" (Ctrl+N) for new topics
- Attach documents using the paperclip icon
- Enable relevant skills in Skills Manager

### 2. Document Mode

**Purpose:** Create legal documents with templates

**How to use:**
1. Click **New Document** or use template shortcut
2. Select template: NDA, Legal Memo, Motion, Brief, Contract
3. Fill in prompted fields
4. View live preview on right panel
5. Export as PDF or Markdown

**Templates include mandatory disclaimer:**
> "This tool assists drafting and research; it is not a substitute for professional legal judgment."

### 3. Research Mode

**Purpose:** Deep legal research with verified sources

**How to use:**
1. Navigate to Research tab
2. Enter detailed research question
3. Click **Research**
4. Monitor progress through stages: Planning → Searching → Reading → Writing
5. Review sources and summary

**Example queries:**
- "What are the elements of breach of contract in California?"
- "Recent developments in GDPR enforcement actions"
- "Compare qualified immunity standards across circuits"

### 4. Legal Updates

**Purpose:** Stay informed about changes in your jurisdiction

**How to use:**
1. Navigate to Legal Updates tab
2. Filter by jurisdiction and type
3. Click any update for details
4. Use "Summarize Impact" for plain-English brief

**Sources include:**
- Government gazettes
- Court RSS feeds
- Bar association bulletins
- Regulatory agency updates

### 5. Skills Manager

**Purpose:** Customize AI behavior for specific tasks

**Built-in Skills:**
- Legal Memo Drafting
- NDA Drafting
- Bluebook Citation
- Case Law Summary
- Contract Review

**Create Custom Skill:**
1. Go to Skills tab
2. Click **+ Create Skill**
3. Enter name, description, trigger keyword
4. Save and enable

**Example:** Create "Patent Claim" skill triggered by "claim" with specific formatting instructions.

### 6. Settings

**Privacy & Security:**
- View privacy indicator (green = local, amber = API)
- Manage API keys (stored securely in OS keychain)
- Configure data retention

**Appearance:**
- Toggle dark/light mode
- Adjust font size

**Account:**
- Change password
- Manage 2FA
- View audit log (admin only)

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New Chat |
| Ctrl+Shift+D | New Document |
| Ctrl+K | Command Palette |
| Ctrl+, | Settings |
| Ctrl+Enter | Send Message |
| Esc | Close dialogs |

---

## Verification Report

When generating documents, Counsel AI runs automatic checks:

### Citation Validation
- Verifies Bluebook/OSCOLA format
- Checks citation existence via HTTP

### Source Existence
- Confirms URLs return 200 status
- Matches quoted text fuzzy

### Clause Structure
- Ensures required sections present (e.g., NDA must have Confidentiality, Term, Exclusions)

### PII Detection
- Scans for emails, phone numbers, SSNs, credit cards, addresses
- Offers redaction option

### Jurisdiction Check
- Verifies governing law clause
- Detects conflicts

**Report appears below generated document with:**
- Pass/Fail status
- Issue count by category
- Detailed findings
- Re-verify option

---

## Tool Actions (Gmail/Outlook/Calendar)

**Setup:**
1. Go to Settings → Tool Connections
2. Select provider (Gmail, Outlook, Calendar)
3. Click **Connect**
4. Complete OAuth flow in browser
5. Return to app

**Usage:**
1. Ask AI to draft email or create event
2. Review preview modal
3. Click **Confirm** to send/create
4. Action logged in audit trail

**Consent is always required before external actions.**

---

## Data Management

### Clear Conversations
1. Hover over conversation in sidebar
2. Click trash icon
3. Confirm deletion

### Clear All Data (Admin Only)
1. Admin → Firm Settings → Data Retention
2. Click **Clear All Data**
3. Confirm (irreversible)

### Export Data
1. Settings → Account
2. Click **Export My Data**
3. Receive ZIP file via email

---

## Troubleshooting

### App Won't Start
- Restart your computer
- Check if backend is running (should start automatically)
- Contact IT administrator

### Slow Performance
- Switch to smaller model in Settings
- Enable GPU offload (if available)
- Close other applications

### API Errors
- Verify internet connection
- Check API key in Settings
- Contact administrator for key refresh

### Missing Features
- Ensure you're logged in
- Check role permissions with admin
- Update to latest version

---

## Support

For help:
1. Check this manual
2. Contact firm administrator
3. Email support: support@counsel-ai.example.com

**Status Page:** https://status.counsel-ai.example.com

---

*Last updated: January 2025*
*Counsel AI Version 1.0.0*
