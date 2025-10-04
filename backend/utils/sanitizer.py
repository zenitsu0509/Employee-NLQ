# backend/utils/sanitizer.py
"""
Sanitizer utilities for NLQ input preprocessing and basic injection detection.
"""

import re
from typing import Tuple

# Allowed characters: basic punctuation, letters, digits, whitespace
# We'll remove control characters and other oddities.
_RE_CONTROL = re.compile(r'[\x00-\x1f\x7f]')

# Patterns that look suspicious for SQL / shell / code injection
_SUSPICIOUS_PATTERNS = [
    r';',                # statement terminator
    r'--',               # SQL comment
    r'/\*', r'\*/',      # SQL comments
    r'\bDROP\b', r'\bDELETE\b', r'\bINSERT\b', r'\bUPDATE\b',
    r'\bALTER\b', r'\bTRUNCATE\b', r'\bGRANT\b', r'\bREVOKE\b',
    r'\bEXEC\b', r'\bEXECUTE\b', r'\bUNION\b', r'\bSELECT\b',
    r'\bCREATE\b', r'\bREPLACE\b', r'\bMERGE\b',
    r'0x[0-9A-Fa-f]+',   # hex payloads
    r'\bshutdown\b', r'\bexecxp\b',
    r'\|', r'`', r'\$\(.*\)',  # shell injection tokens
    r'\\\\x',            # injected hex sequences
]

_SUSPICIOUS_RE = re.compile('|'.join(f'({p})' for p in _SUSPICIOUS_PATTERNS), flags=re.IGNORECASE)

# Basic email/URL pattern — allowed but can be flagged if abusive
_URL_RE = re.compile(r'https?://\S+|www\.\S+', flags=re.IGNORECASE)

# Maximum acceptable length for a single NLQ (tunable)
DEFAULT_MAX_LENGTH = 500


def clean_input(raw: str) -> str:
    """
    Clean the input string:
      - strip leading/trailing whitespace
      - collapse multiple whitespace characters into single space
      - remove control characters
    Returns the cleaned string.
    """
    if raw is None:
        return ''
    s = str(raw)
    # Remove control chars
    s = _RE_CONTROL.sub('', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def is_too_long(s: str, max_len: int = DEFAULT_MAX_LENGTH) -> bool:
    """Return True if the string is longer than max_len."""
    return len(s) > max_len


def has_suspicious_patterns(s: str) -> Tuple[bool, str]:
    """
    Check for suspicious tokens/patterns.
    Returns (True, matched_pattern) if suspicious pattern found, else (False, '').
    """
    m = _SUSPICIOUS_RE.search(s)
    if m:
        return True, m.group(0)
    return False, ''


def detect_url(s: str) -> bool:
    """Return True if a URL-like token is present."""
    return bool(_URL_RE.search(s))
