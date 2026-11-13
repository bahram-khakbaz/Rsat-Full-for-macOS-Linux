"""Identity, search and LDAP filter handling, including non-Latin directory names."""

import pytest
from fastapi import HTTPException

from app.common import capped, identity, ldap_escape, prefix_filter, search_term

PERSIAN_USER = "علی رضایی"
PERSIAN_DN = "CN=سارا محمدی,OU=کارمندان,DC=example,DC=com"
ZWNJ_NAME = "می\u200cخواهم"


@pytest.mark.parametrize(
    "value",
    [
        "tester",
        "EXAMPLE\\tester",
        "user@example.com",
        "CN=Test User (Ops),OU=People,DC=example,DC=com",
        "0f8fad5b-d9cb-469f-a165-70867728950e",
        PERSIAN_USER,
        PERSIAN_DN,
        ZWNJ_NAME,
        "Zoë Müller",
        "山田太郎",
    ],
)
def test_identity_accepts_unicode_names_and_distinguished_names(value):
    assert identity(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "x" * 513,
        "tester'; Remove-Item C:\\ -Recurse",
        'tester"',
        "tester`whoami`",
        "$(whoami)",
        "a;b",
        "a|b",
        "a&b",
        "a<b",
        "a>b",
        "a*",
        "a?",
        "line\nbreak",
        "tab\there",
        "nul\x00byte",
        "bidi\u202eoverride",
    ],
)
def test_identity_rejects_shell_metacharacters_and_control_characters(value):
    with pytest.raises(HTTPException) as error:
        identity(value)
    assert error.value.status_code == 400


def test_search_term_keeps_unicode_and_drops_filter_syntax():
    assert search_term("  رضا  ") == "رضا"
    assert search_term(ZWNJ_NAME) == ZWNJ_NAME
    assert search_term("te*st)(objectClass=*") == "testobjectClass"
    assert search_term("a'b\"c`d$e;f") == "abcdef"
    assert len(search_term("x" * 200)) == 80


def test_ldap_escape_follows_rfc_4515():
    assert ldap_escape("a\\b*c(d)e\x00") == r"a\5cb\2ac\28d\29e\00"
    assert ldap_escape("رضا") == "رضا"


def test_prefix_filter_is_index_friendly_and_never_contains_raw_input_syntax():
    base = "(&(objectCategory=person)(objectClass=user))"
    assert prefix_filter(base, ("sAMAccountName",), "") == base
    built = prefix_filter(base, ("sAMAccountName", "displayName", "mail"), "رضا")
    assert built == f"(&{base}(|(sAMAccountName=رضا*)(displayName=رضا*)(mail=رضا*)))"
    assert "=*" not in built
    hostile = prefix_filter(base, ("sAMAccountName",), "*)(objectClass=*)")
    assert hostile == f"(&{base}(|(sAMAccountName=objectClass*)))"
    contains = prefix_filter("(objectCategory=computer)", ("name",), "pc", contains=True)
    assert contains == "(&(objectCategory=computer)(|(name=*pc*)))"


def test_capped_refuses_partial_inventories():
    assert capped([1, 2], 2, "users") == [1, 2]
    with pytest.raises(HTTPException) as error:
        capped([1, 2, 3], 2, "users")
    assert error.value.status_code == 413
    assert "no partial list" in error.value.detail
