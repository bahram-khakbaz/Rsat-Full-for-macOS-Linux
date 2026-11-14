import pytest

from app import auth, native_ad


@pytest.fixture(autouse=True)
def isolated_module_state():
    """Sign-in throttling, pooled LDAP sessions and Kerberos tickets are process-wide."""
    yield
    auth.throttle.clear()
    native_ad.reset_auth_failure()
