# Counsel AI - Support Guide

This document defines support tiers, response times, and procedures for getting help with Counsel AI.

## Table of Contents

1. [Support Tiers](#support-tiers)
2. [How to Get Help](#how-to-get-help)
3. [Response Times (SLA)](#response-times-sla)
4. [What's Included](#whats-included)
5. [Escalation Procedures](#escalation-procedures)
6. [Known Limitations](#known-limitations)

---

## Support Tiers

Counsel AI offers three levels of support to meet different organizational needs:

### 1. Community Support (Free)

**Available to:** All users

**Channels:**
- GitHub Issues (public)
- GitHub Discussions
- Documentation and FAQs

**Coverage:**
- Bug reports
- Feature requests
- Basic troubleshooting
- Installation guidance

**Response Time:** Best effort (typically 2-5 business days)

**Hours:** Community-driven, no guaranteed hours

---

### 2. Professional Support ($99/month or $990/year)

**Available to:** Small firms and individual practitioners

**Channels:**
- Email: support@counsel-ai.example.com
- GitHub Issues (priority labeled)
- Scheduled calls (30 min/month)

**Coverage:**
- Everything in Community tier, plus:
- Priority bug fixes
- Configuration assistance
- Data migration help
- Security advisories
- Update planning

**Response Time:** See SLA table below

**Hours:** Monday-Friday, 9 AM - 6 PM ET

---

### 3. Enterprise Support (Custom Pricing)

**Available to:** Law firms with 10+ users, organizations requiring SLA guarantees

**Channels:**
- Dedicated support email
- Phone support during business hours
- Slack/Teams integration (optional)
- Quarterly business reviews
- On-site training (additional fee)

**Coverage:**
- Everything in Professional tier, plus:
- Guaranteed SLA response times
- Dedicated support engineer
- Custom feature development
- Integration assistance
- Compliance documentation
- Audit log analysis
- Performance tuning
- Disaster recovery planning

**Response Time:** See SLA table below

**Hours:** 24/7 for critical issues; business hours for standard requests

---

## How to Get Help

### Step 1: Check Documentation

Before contacting support, please review:
- [USER_MANUAL.md](./USER_MANUAL.md) - Feature usage guide
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Installation and configuration
- [ADMIN_GUIDE.md](./ADMIN_GUIDE.md) - Administration tasks
- In-app help (Settings > Help)

### Step 2: Search Existing Issues

Search [GitHub Issues](https://github.com/counsel-ai/counsel-ai/issues) for:
- Similar error messages
- Your specific use case
- Known workarounds

### Step 3: Submit a Support Request

#### For Community Support

Create a GitHub Issue with:
```markdown
**Description:** Clear description of the problem
**Steps to Reproduce:** 
1. Step one
2. Step two
**Expected Behavior:** What should happen
**Actual Behavior:** What actually happened
**Environment:**
- OS: [e.g., Windows 11]
- Counsel AI Version: [e.g., 1.0.0]
- Mode: [Local/API/Research]
**Logs:** (redact PII first)
```

#### For Professional/Enterprise Support

Email support@counsel-ai.example.com with:
- Subject line format: `[Tier] [Severity] Brief Description`
  - Example: `[Professional] [Medium] Document export failing on macOS`
- Include:
  - Account email / license key
  - Counsel AI version
  - OS and version
  - Detailed description
  - Steps to reproduce
  - Screenshots (if applicable)
  - Log excerpts (PII redacted)

### Step 4: Provide Additional Information

Support may request:
- Full logs (via secure channel)
- Screen recording of the issue
- Remote session (Enterprise only, with consent)
- Sample data (anonymized)

---

## Response Times (SLA)

### Severity Definitions

| Severity | Definition | Examples |
|----------|------------|----------|
| **Critical (P1)** | System completely down; data loss imminent | Application won't start; corruption detected |
| **High (P2)** | Major feature broken; workaround unavailable | Document generation fails; research mode broken |
| **Medium (P3)** | Feature impaired; workaround exists | Slow performance; minor UI issues |
| **Low (P4)** | Cosmetic; enhancement request | Typo; feature suggestion |

### SLA Matrix

| Tier | Critical (P1) | High (P2) | Medium (P3) | Low (P4) |
|------|---------------|-----------|-------------|----------|
| **Community** | Best effort | Best effort | Best effort | Best effort |
| **Professional** | 4 business hours | 8 business hours | 2 business days | 5 business days |
| **Enterprise** | 1 hour (24/7) | 4 business hours | 1 business day | 3 business days |

**Business Hours:** Monday-Friday, 9 AM - 6 PM local time (Professional); 24/7 for Enterprise P1

### Resolution Targets

| Severity | Target Resolution |
|----------|-------------------|
| P1 | 24 hours (workaround or fix) |
| P2 | 3 business days |
| P3 | Next release cycle |
| P4 | Backlog for future consideration |

---

## What's Included

### In Scope

✅ **Software Defects**
- Crashes and freezes
- Incorrect outputs
- Performance regressions
- Security vulnerabilities

✅ **Installation & Configuration**
- Initial setup assistance
- Migration from previous versions
- Multi-user configuration
- Network/firewall setup

✅ **Usage Guidance**
- Feature explanations
- Best practices
- Workflow optimization
- Settings recommendations

✅ **Security**
- Vulnerability disclosures
- Patch deployment guidance
- Encryption configuration
- Audit log interpretation

### Out of Scope

❌ **Third-Party Issues**
- External API outages (OpenAI, DeepSeek)
- OS-level problems
- Hardware failures
- Network infrastructure issues

❌ **Custom Development**
- Custom integrations (available as paid service)
- Bespoke feature development
- Data extraction/transformation

❌ **Training**
- General legal research training
- AI/ML education
- Non-Counsel AI software training

❌ **Guarantees**
- Legal accuracy of outputs (see disclaimer)
- Specific research results
- Model behavior guarantees

---

## Escalation Procedures

### When to Escalate

Consider escalation if:
- SLA response time exceeded
- Issue not resolved after reasonable attempts
- Business impact increasing
- Need higher technical authority

### Escalation Paths

#### Professional Tier

1. Reply to support thread requesting escalation
2. Support manager reviews within 4 business hours
3. Senior engineer assigned if warranted

#### Enterprise Tier

1. Contact your dedicated support engineer
2. Request escalation to support manager
3. Emergency contact for P1 issues (provided at onboarding)

### Executive Escalation (Enterprise Only)

For unresolved critical issues affecting business operations:
- Contact: executive@counsel-ai.example.com
- Include: Case number, business impact, timeline
- Response: Within 2 business hours

---

## Known Limitations

### Technical Limitations

1. **Model Accuracy**
   - AI outputs may contain errors
   - Always verify citations and legal references
   - Not a substitute for professional judgment

2. **Offline Mode**
   - Research mode requires internet
   - Legal updates require internet
   - Local mode works offline after model download

3. **File Size Limits**
   - Maximum document upload: 50 MB
   - Maximum context: 128K tokens (model-dependent)

4. **Concurrent Users**
   - Single-machine: Optimized for 1-5 concurrent users
   - Docker deployment: Scale based on hardware

### Legal Limitations

⚠️ **IMPORTANT: Counsel AI is a tool, not a lawyer**

- Outputs are suggestions, not legal advice
- Users must exercise independent professional judgment
- Verify all citations, quotes, and legal references
- Comply with local bar association rules regarding AI use

### Support Limitations

- Support cannot provide legal advice
- Support cannot guarantee specific outcomes
- Support access may be suspended for abuse
- Data shared with support should be anonymized

---

## Feedback and Improvements

We welcome feedback on our support services:

- Rate your support experience (included in resolution emails)
- Suggest improvements: support-feedback@counsel-ai.example.com
- Annual satisfaction survey (Professional/Enterprise customers)

---

## Contact Information

### General Inquiries

- Email: info@counsel-ai.example.com
- Website: https://counsel-ai.example.com

### Support

- Community: GitHub Issues
- Professional/Enterprise: support@counsel-ai.example.com
- Emergency (Enterprise): +1-XXX-XXX-XXXX (provided at onboarding)

### Sales

- Email: sales@counsel-ai.example.com
- Demo requests: https://counsel-ai.example.com/demo

### Security

- Vulnerability reports: security@counsel-ai.example.com
- PGP Key: Available on request

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01-01 | Initial release |

---

*Last updated: January 2024*
