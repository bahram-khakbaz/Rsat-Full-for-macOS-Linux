"""User paging, explicit caps and filters for the directory inventories."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routers import ad


def rows(count):
    return [{"samAccountName": f"user{index:03d}"} for index in range(count)]


def call_users(q="", page_size="", cursor=""):
    # Called directly, so every query default is supplied explicitly.
    return ad.users(q=q, page_size=page_size, cursor=cursor)


def test_first_page_reads_one_extra_row_and_reports_more():
    with patch("app.routers.ad.run_ps_list", return_value=rows(26)) as runner:
        page = call_users(q="رضا", page_size="25")
    script, variables = runner.call_args.args
    assert "-LDAPFilter $env:RSAT_FILTER" in script
    assert "-Filter" not in script.replace("-LDAPFilter", "")
    assert variables == {
        "filter": "(&(&(objectCategory=person)(objectClass=user))"
        "(|(sAMAccountName=رضا*)(displayName=رضا*)(mail=رضا*)))",
        "limit": 26,
        "skip": 0,
    }
    assert len(page["items"]) == 25 and page["has_more"] and page["total"] is None
    assert isinstance(page["next_cursor"], str)


def test_cursor_continues_and_last_page_has_no_cursor():
    with patch("app.routers.ad.run_ps_list", return_value=rows(26)):
        first = call_users(page_size="25")
    with patch("app.routers.ad.run_ps_list", return_value=rows(3)) as runner:
        second = call_users(page_size="25", cursor=first["next_cursor"])
    assert runner.call_args.args[1]["skip"] == 25
    assert runner.call_args.args[1]["limit"] == 51
    assert second == {
        "items": rows(3),
        "next_cursor": None,
        "has_more": False,
        "total": None,
    }


def test_cursor_is_bound_to_its_search_and_rejects_garbage():
    with patch("app.routers.ad.run_ps_list", return_value=rows(26)):
        first = call_users(q="alpha", page_size="25")
    with patch("app.routers.ad.run_ps_list") as runner:
        for query, cursor in (("beta", first["next_cursor"]), ("alpha", "not-a-cursor")):
            with pytest.raises(HTTPException) as error:
                call_users(q=query, page_size="25", cursor=cursor)
            assert error.value.status_code == 409
        runner.assert_not_called()


@pytest.mark.parametrize("size", ["0", "101", "abc", "-1"])
def test_invalid_page_size_is_rejected(size):
    with patch("app.routers.ad.run_ps_list") as runner:
        with pytest.raises(HTTPException) as error:
            call_users(page_size=size)
        assert error.value.status_code == 422
        runner.assert_not_called()


def test_unpaged_list_fails_loudly_instead_of_truncating():
    limit = ad.settings.max_unpaged_results
    with patch("app.routers.ad.run_ps_list", return_value=rows(3)) as runner:
        assert call_users() == rows(3)
    assert runner.call_args.args[1]["limit"] == limit + 1
    with patch("app.routers.ad.run_ps_list", return_value=rows(limit + 1)):
        with pytest.raises(HTTPException) as error:
            call_users()
    assert error.value.status_code == 413


def test_empty_page_size_from_the_control_plane_means_unpaged():
    # httpx serializes page_size=None as an empty query value.
    from fastapi.testclient import TestClient

    from app import main as worker

    worker.settings.agent_token = "test-only-channel-credential" * 2
    headers = {"Authorization": f"Bearer {worker.settings.agent_token}"}
    client = TestClient(worker.app)
    try:
        with patch("app.routers.ad.run_ps_list", return_value=[]) as runner:
            response = client.get("/ad/users?q=&page_size=&cursor=", headers=headers)
            assert response.status_code == 200 and response.json() == []
            paged = client.get("/ad/users?q=&page_size=10&cursor=", headers=headers)
            assert paged.json() == {
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "total": None,
            }
            assert runner.call_count == 2
    finally:
        client.close()


def test_group_and_computer_filters_and_caps():
    with patch("app.routers.ad.run_ps_list", return_value=[]) as runner:
        assert ad.groups(q="Help") == []
        assert runner.call_args.args[1]["filter"] == (
            "(&(objectCategory=group)(|(name=Help*)(sAMAccountName=Help*)))"
        )
        assert "Get-ADGroupMember" not in runner.call_args.args[0]
        assert ad.computers(q="pc") == []
        assert runner.call_args.args[1]["filter"] == (
            "(&(objectCategory=computer)(|(name=*pc*)(dNSHostName=*pc*)))"
        )
    too_many = [{}] * (ad.settings.max_unpaged_results + 1)
    with patch("app.routers.ad.run_ps_list", return_value=too_many):
        for inventory in (ad.groups, ad.computers):
            with pytest.raises(HTTPException) as error:
                inventory(q="")
            assert error.value.status_code == 413
