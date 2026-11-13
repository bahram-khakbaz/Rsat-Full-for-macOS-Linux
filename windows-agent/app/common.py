"""Shared validation helpers. Values reach PowerShell only as environment data."""

import unicodedata

from fastapi import HTTPException

# Punctuation that occurs in sAMAccountNames, UPNs, GUIDs and distinguished names.
# Quotes, backticks, $ ; | & < > * ? and all control characters stay rejected.
_IDENTITY_PUNCTUATION = frozenset("_.@\\,=+()- /#:")
_SEARCH_PUNCTUATION = frozenset("_.@- ")
# Zero-width (non-)joiners are ordinary orthography in Persian and Indic names.
_JOINERS = frozenset("\u200c\u200d")

IDENTITY_SCRIPT = r"""$who=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$domain=''
try { Import-Module ActiveDirectory; $domain=(Get-ADDomain).DNSRoot } catch {}
[pscustomobject]@{runAs=$who;computer=$env:COMPUTERNAME;domain=$domain} | ConvertTo-Json -Compress
"""


def _is_word(character: str) -> bool:
    """Unicode letters, combining marks and digits, plus the two joiners."""
    return character in _JOINERS or unicodedata.category(character)[0] in "LMN"


def identity(value: str) -> str:
    """Validate an account name, GUID or distinguished name from a URL segment."""
    if not 1 <= len(value) <= 512 or not all(
        _is_word(c) or c in _IDENTITY_PUNCTUATION for c in value
    ):
        raise HTTPException(status_code=400, detail="Invalid identity")
    return value


def search_term(value: str) -> str:
    """Drop everything except Unicode word characters and a little punctuation."""
    cleaned = "".join(c for c in value if _is_word(c) or c in _SEARCH_PUNCTUATION)
    return cleaned.strip()[:80]


def ldap_escape(value: str) -> str:
    """Escape an assertion value for an LDAP filter (RFC 4515)."""
    replacements = {"\\": r"\5c", "*": r"\2a", "(": r"\28", ")": r"\29", "\x00": r"\00"}
    return "".join(replacements.get(c, c) for c in value)


def prefix_filter(base: str, attributes: tuple[str, ...], term: str, contains: bool = False) -> str:
    """Build an LDAP filter matching `term` against any of `attributes`."""
    term = search_term(term)
    if not term:
        return base
    escaped = ldap_escape(term)
    pattern = f"*{escaped}*" if contains else f"{escaped}*"
    clauses = "".join(f"({attribute}={pattern})" for attribute in attributes)
    return f"(&{base}(|{clauses}))"


def capped(rows: list, limit: int, what: str) -> list:
    """Refuse to return a silently truncated inventory."""
    if len(rows) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"The directory holds more than {limit} {what}. "
            "Narrow the search or use paging; no partial list was returned.",
        )
    return rows
