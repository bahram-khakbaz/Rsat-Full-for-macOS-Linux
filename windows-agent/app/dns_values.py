"""DNS record validation shared by create, update and delete.

Value formats match the control plane's direct connector, so a record written
in one connection mode reads back identically in the other:

    A / AAAA          address
    CNAME / PTR / NS  host name
    MX                "preference host"
    SRV               "priority weight port host"
    TXT               one shell-quoted text segment
"""

import ipaddress
import re
import shlex

from fastapi import HTTPException

RECORD_TYPES = ("A", "AAAA", "CNAME", "PTR", "NS", "MX", "SRV", "TXT")
_LABEL = re.compile(r"[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?")


def dns_name(value: str, allow_wildcard: bool = False) -> str:
    value = value.strip().rstrip(".").lower()
    if not value or len(value) > 253:
        raise ValueError("Invalid DNS name")
    for index, label in enumerate(value.split(".")):
        if allow_wildcard and index == 0 and label == "*":
            continue
        if len(label) > 63 or not _LABEL.fullmatch(label):
            raise ValueError("Invalid DNS label")
    return value


def _unsigned16(text: str) -> int:
    number = int(text)
    if not 0 <= number <= 65535:
        raise ValueError("Out of range")
    return number


def record_fields(kind: str, value: str, prefix: str = "") -> dict[str, str]:
    """Validated PowerShell variables for one record value.

    `value` is always present in canonical form; MX, SRV and TXT add the parts
    their cmdlets take separately. `prefix` namespaces the original value of an
    update ("old_").
    """
    if kind not in RECORD_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported DNS record type")
    value = value.strip()
    fields: dict[str, str] = {}
    try:
        if kind in ("A", "AAAA"):
            address = ipaddress.ip_address(value)
            if address.version != (4 if kind == "A" else 6):
                raise ValueError("Wrong address family")
            canonical = str(address)
        elif kind in ("CNAME", "PTR", "NS"):
            canonical = dns_name(value)
        elif kind == "MX":
            preference, target = value.split()
            fields = {"preference": str(_unsigned16(preference)), "target": dns_name(target)}
            canonical = f"{fields['preference']} {fields['target']}"
        elif kind == "SRV":
            priority, weight, port, target = value.split()
            fields = {
                "priority": str(_unsigned16(priority)),
                "weight": str(_unsigned16(weight)),
                "port": str(_unsigned16(port)),
                "target": "." if target == "." else dns_name(target),
            }
            canonical = " ".join(fields[key] for key in ("priority", "weight", "port", "target"))
        else:
            segments = shlex.split(value)
            if len(segments) != 1 or not 1 <= len(segments[0].encode("utf-8")) <= 255:
                raise HTTPException(
                    status_code=422,
                    detail="Worker mode writes TXT records with one text segment of at most "
                    "255 bytes. Use the direct connector for multi-segment records.",
                )
            fields = {"text": segments[0]}
            canonical = shlex.join(segments)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid DNS value or format") from exc
    return {f"{prefix}{key}": text for key, text in {"value": canonical, **fields}.items()}


def display_value(kind: str, value) -> str:
    """Present a value read from the DNS server in the shared format."""
    text = "" if value is None else str(value)
    return shlex.join([text]) if kind == "TXT" else text
