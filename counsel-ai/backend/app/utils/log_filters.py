"""
PII Redaction Filter for Logging

This module provides logging filters that scrub PII from log messages before they are written.
Use this to ensure sensitive data (emails, phones, names, case numbers, addresses) never
appears in logs or error tracking systems.

Usage:
    import logging
    from app.utils.log_filters import PIIFilter
    
    logger = logging.getLogger("counsel")
    logger.addFilter(PIIFilter())
"""

import re
from typing import Optional


class PIIFilter(logging.Filter):
    """Logging filter that redacts PII from log records."""
    
    # Email pattern
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    # Phone patterns (US formats)
    PHONE_PATTERNS = [
        re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),  # 123-456-7890
        re.compile(r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b'),  # (123) 456-7890
        re.compile(r'\b\d{3}\s\d{3}\s\d{4}\b'),  # 123 456 7890
    ]
    
    # SSN pattern
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    
    # Credit card patterns (basic)
    CC_PATTERNS = [
        re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),  # 16 digits
        re.compile(r'\b\d{4}[- ]?\d{6}[- ]?\d{5}\b'),  # Amex format
    ]
    
    # Case number patterns (varies by jurisdiction)
    CASE_NUMBER_PATTERNS = [
        re.compile(r'\b\d{1,2}:\d{2}-cv-\d{1,7}\b', re.IGNORECASE),  # Federal: 1:22-cv-12345
        re.compile(r'\b\d{2}-\d{4}-[A-Z]{2,4}-\d{4,6}\b', re.IGNORECASE),  # State formats
        re.compile(r'\bCase\s*[#]?\s*\d{2,}', re.IGNORECASE),
    ]
    
    # Address pattern (simplified - street addresses)
    ADDRESS_PATTERN = re.compile(
        r'\b\d{1,5}\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\b',
        re.IGNORECASE
    )
    
    # Names following common titles (simple heuristic)
    NAME_PATTERN = re.compile(
        r'\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'
    )
    
    # API keys / tokens (common patterns)
    API_KEY_PATTERN = re.compile(
        r'\b(?:sk-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|api[_-]?key[=:]\s*[A-Za-z0-9]{10,})\b',
        re.IGNORECASE
    )
    
    REPLACEMENT_MAP = {
        'email': '[EMAIL_REDACTED]',
        'phone': '[PHONE_REDACTED]',
        'ssn': '[SSN_REDACTED]',
        'credit_card': '[CARD_REDACTED]',
        'case_number': '[CASE_REDACTED]',
        'address': '[ADDRESS_REDACTED]',
        'name': '[NAME_REDACTED]',
        'api_key': '[API_KEY_REDACTED]',
    }
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        self.redaction_count = 0
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact PII from the log record message and arguments."""
        if isinstance(record.msg, str):
            record.msg = self._redact_string(record.msg)
        
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact_value(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact_value(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True
    
    def _redact_value(self, value: str) -> str:
        """Redact PII from a string value."""
        return self._redact_string(value)
    
    def _redact_string(self, text: str) -> str:
        """Apply all redaction patterns to a string."""
        if not text:
            return text
        
        # Track redactions for metrics
        original = text
        
        # Apply patterns in order of specificity
        text = self.EMAIL_PATTERN.sub(self.REPLACEMENT_MAP['email'], text)
        
        for pattern in self.PHONE_PATTERNS:
            text = pattern.sub(self.REPLACEMENT_MAP['phone'], text)
        
        text = self.SSN_PATTERN.sub(self.REPLACEMENT_MAP['ssn'], text)
        
        for pattern in self.CC_PATTERNS:
            text = pattern.sub(self.REPLACEMENT_MAP['credit_card'], text)
        
        for pattern in self.CASE_NUMBER_PATTERNS:
            text = pattern.sub(self.REPLACEMENT_MAP['case_number'], text)
        
        text = self.ADDRESS_PATTERN.sub(self.REPLACEMENT_MAP['address'], text)
        text = self.NAME_PATTERN.sub(self.REPLACE_MAP['name'], text)
        text = self.API_KEY_PATTERN.sub(self.REPLACEMENT_MAP['api_key'], text)
        
        # Update counter if redactions occurred
        if text != original:
            self.redaction_count += 1
        
        return text


class SensitiveFieldFilter(logging.Filter):
    """Filter that removes specific sensitive fields from JSON-like log content."""
    
    SENSITIVE_FIELDS = [
        'password', 'passwd', 'secret', 'token', 'api_key', 'apikey',
        'authorization', 'bearer', 'credential', 'cred', 'private_key'
    ]
    
    REPLACEMENT = '[REDACTED]'
    
    def __init__(self, name: str = "", fields: Optional[list] = None):
        super().__init__(name)
        self.fields = fields or self.SENSITIVE_FIELDS
        self.patterns = [
            re.compile(rf'"{field}"\s*:\s*"[^"]*"', re.IGNORECASE)
            for field in self.fields
        ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Remove sensitive fields from log record."""
        if isinstance(record.msg, str):
            for pattern in self.patterns:
                record.msg = pattern.sub(f'"[FIELD]": "{self.REPLACEMENT}"', record.msg)
        
        return True


def setup_pii_redaction(logger: Optional[logging.Logger] = None) -> logging.Logger:
    """Set up PII redaction on a logger (or root logger if none provided)."""
    if logger is None:
        logger = logging.getLogger()
    
    logger.addFilter(PIIFilter())
    logger.addFilter(SensitiveFieldFilter())
    
    return logger


# Convenience function for use with logging configuration
def get_pii_filter() -> PIIFilter:
    """Return a new PII filter instance."""
    return PIIFilter()


def get_sensitive_field_filter(fields: Optional[list] = None) -> SensitiveFieldFilter:
    """Return a new sensitive field filter instance."""
    return SensitiveFieldFilter(fields=fields)
