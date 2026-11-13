"""DNS record parity with the control plane's direct connector."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.dns_values import display_value, record_fields
from app.models import DnsDeleteBody, DnsRecordBody, DnsUpdateBody
from app.routers import network


@pytest.mark.parametrize(
    ("kind", "value", "expected"),
    [
        ("A", " 192.0.2.7 ", {"value": "192.0.2.7"}),
        ("AAAA", "2001:DB8:0:0::1", {"value": "2001:db8::1"}),
        ("CNAME", "Host.Example.COM.", {"value": "host.example.com"}),
        ("PTR", "host.example.com", {"value": "host.example.com"}),
        ("NS", "ns1.example.com.", {"value": "ns1.example.com"}),
        (
            "MX",
            "10 Mail.example.com.",
            {"value": "10 mail.example.com", "preference": "10", "target": "mail.example.com"},
        ),
        (
            "SRV",
            "0 100 389 dc1.example.com",
            {
                "value": "0 100 389 dc1.example.com",
                "priority": "0",
                "weight": "100",
                "port": "389",
                "target": "dc1.example.com",
            },
        ),
        (
            "SRV",
            "0 0 0 .",
            {"value": "0 0 0 .", "priority": "0", "weight": "0", "port": "0", "target": "."},
        ),
        ("TXT", "'v=spf1 -all'", {"value": "'v=spf1 -all'", "text": "v=spf1 -all"}),
    ],
)
def test_record_values_are_validated_and_canonical(kind, value, expected):
    assert record_fields(kind, value) == expected


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("A", "2001:db8::1"),
        ("AAAA", "192.0.2.7"),
        ("A", "192.0.2.7; Remove-Item C:\\"),
        ("CNAME", "bad host.example.com"),
        ("MX", "mail.example.com"),
        ("MX", "70000 mail.example.com"),
        ("SRV", "0 100 dc1.example.com"),
        ("SRV", "0 100 70000 dc1.example.com"),
        ("TXT", "two segments"),
        ("TXT", "'" + "x" * 256 + "'"),
        ("TXT", "'unterminated"),
        ("SOA", "anything"),
    ],
)
def test_invalid_record_values_are_rejected(kind, value):
    with pytest.raises(HTTPException) as error:
        record_fields(kind, value)
    assert error.value.status_code == 422


def test_models_accept_all_eight_types_and_reject_others():
    for kind in ("A", "AAAA", "CNAME", "PTR", "NS", "MX", "SRV", "TXT"):
        DnsRecordBody(zone="example.com", name="@", type=kind, value="x")
    for owner in ("www", "_ldap._tcp", "*", "*.apps", "@"):
        DnsDeleteBody(zone="example.com", name=owner, type="A")
    for body in (
        {"zone": "example.com", "name": "www", "type": "SOA", "value": "x"},
        {"zone": "example.com;x", "name": "www", "type": "A", "value": "192.0.2.1"},
        {"zone": "example.com", "name": "w w", "type": "A", "value": "192.0.2.1"},
        {"zone": "example.com", "name": "a*", "type": "A", "value": "192.0.2.1"},
    ):
        with pytest.raises(ValidationError):
            DnsRecordBody(**body)


def test_every_type_has_its_own_create_script_and_values_stay_in_environment():
    assert set(network.DNS_CREATE) == {"A", "AAAA", "CNAME", "PTR", "NS", "MX", "SRV", "TXT"}
    cases = {
        "NS": ("ns1.example.com", "-NS", {"value": "ns1.example.com"}),
        "MX": ("10 mail.example.com", "MailExchange", {"preference": "10"}),
        "SRV": ("0 100 389 dc1.example.com", "-Srv", {"port": "389"}),
        "TXT": ("'hello world'", "-Txt", {"text": "hello world"}),
        "PTR": ("host.example.com", "ResourceRecordPtr", {"value": "host.example.com"}),
    }
    for kind, (value, marker, expected) in cases.items():
        with patch("app.routers.network.run_ps", return_value={"ok": True}) as runner:
            body = DnsRecordBody(zone="example.com", name="www", type=kind, value=value, ttl=300)
            assert network.create_dns(body) == {"ok": True}
        script, variables = runner.call_args.args
        assert marker in script and value not in script
        assert variables["zone"] == "example.com" and variables["ttl"] == 300
        for key, text in expected.items():
            assert variables[key] == text
    # Only PTR records use the PTR cmdlet; nothing falls through to it any more.
    assert sum("ResourceRecordPtr" in script for script in network.DNS_CREATE.values()) == 1


def test_update_identifies_the_original_record_and_delete_requires_a_match():
    with patch("app.routers.network.run_ps", return_value={"ok": True}) as runner:
        network.update_dns(
            DnsUpdateBody(
                zone="example.com",
                name="mail",
                type="MX",
                value="20 mx2.example.com",
                ttl=600,
                old_value="10 MX1.example.com.",
                old_ttl=0,
            )
        )
        script, variables = runner.call_args.args
        assert "Set-DnsServerResourceRecord" in script and "-OldInputObject $old" in script
        assert variables["old_match"] == "10 mx1.example.com"
        assert variables["target"] == "mx2.example.com" and variables["preference"] == "20"

        network.delete_dns(DnsDeleteBody(zone="example.com", name="www", type="TXT", value="'a b'"))
        script, variables = runner.call_args.args
        assert variables["match"] == "a b" and "RsatDnsSame" in script
        assert "No matching DNS record" in script

        network.delete_dns(DnsDeleteBody(zone="example.com", name="www", type="A"))
        assert "match" not in runner.call_args.args[1]


def test_listing_reads_whole_zone_and_quotes_text_like_the_direct_connector():
    found = [
        {"zone": "example.com", "name": "@", "type": "TXT", "value": "v=spf1 -all", "ttl": 3600},
        {"zone": "example.com", "name": "www", "type": "A", "value": "192.0.2.7", "ttl": 300},
    ]
    with patch("app.routers.network.run_ps_list", return_value=found) as runner:
        result = network.dns_records(zone="example.com")
    script = runner.call_args.args[0]
    assert "Select-Object -First" not in script and "SilentlyContinue" not in script
    assert result[0]["value"] == "'v=spf1 -all'" and result[1]["value"] == "192.0.2.7"
    assert display_value("TXT", None) == "''"
    with pytest.raises(HTTPException):
        network.dns_records(zone="example.com'; x")
