from app.auth import ROLE_PERMISSIONS

def test_admin_has_wildcard():
    assert "*" in ROLE_PERMISSIONS["admin"]

def test_helpdesk_cannot_write_dns():
    assert "dns.write" not in ROLE_PERMISSIONS["helpdesk"]
