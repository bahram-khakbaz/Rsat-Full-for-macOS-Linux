import ssl
from urllib.parse import unquote

import httpx
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from . import demo
from .runtime_config import RuntimeConfig, get_runtime_config
from .worker_tls import verify_option


def _error_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    return str(detail)[:1500]


def _page(rows: list, page_size: int, cursor: str | None) -> dict:
    """Offset paging for demo fixtures, shaped like the directory connectors."""
    try:
        offset = max(0, int(cursor or 0))
    except ValueError as exc:
        raise HTTPException(409, "This page expired. Refresh the list.") from exc
    following = offset + page_size
    more = following < len(rows)
    return {
        "items": rows[offset:following],
        "next_cursor": str(following) if more else None,
        "has_more": more,
        "total": len(rows),
    }


class WorkerClient:
    async def call(
        self,
        method: str,
        path: str,
        *,
        payload=None,
        params=None,
        timeout: float = 45,
        runtime: RuntimeConfig | None = None,
        authenticated: bool = True,
    ):
        """Send one request to the paired Windows worker over its verified channel."""
        runtime = runtime or get_runtime_config()
        if not runtime.worker_url:
            raise HTTPException(status_code=503, detail="Windows worker is not configured")
        if authenticated and not runtime.worker_token:
            raise HTTPException(status_code=409, detail="Pair the Windows worker first")
        verify = verify_option(runtime.worker_url, runtime.worker_certificate)
        headers = {"Authorization": f"Bearer {runtime.worker_token}"} if authenticated else {}
        # httpx sends None as an empty value, which typed worker parameters reject.
        query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        try:
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as client:
                response = await client.request(
                    method,
                    f"{runtime.worker_url}{path}",
                    json=payload,
                    params=query or None,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            if isinstance(exc.__cause__, ssl.SSLCertVerificationError) or (
                "CERTIFICATE_VERIFY_FAILED" in str(exc)
            ):
                raise HTTPException(
                    status_code=502,
                    detail="The worker certificate is not trusted or has changed. Inspect the "
                    "certificate in Settings and pair the worker again.",
                ) from exc
            reason = f"{type(exc).__name__}: {exc}"[:300]
            raise HTTPException(
                status_code=502, detail=f"Worker connection failed: {reason}"
            ) from exc
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=_error_detail(response))
        return response.json()

    async def request(self, method: str, path: str, payload=None, params=None):
        runtime = get_runtime_config()
        if runtime.demo_mode:
            return self._demo(method, path, payload, params)
        if runtime.connection_mode == "native":
            if path.startswith(("/dns/", "/dhcp/")):
                from .native_network import request
            else:
                from .native_ad import request
            return await run_in_threadpool(request, method, path, payload, params)
        return await self.call(method, path, payload=payload, params=params, runtime=runtime)

    def _demo(self, method: str, path: str, payload, params):
        params = params or {}
        parts = [unquote(x) for x in path.strip("/").split("/")]
        query = (params.get("q") or "").lower()
        if path == "/domain/summary":
            return demo.DOMAIN
        if path == "/domain/controllers":
            return demo.DCS
        if path == "/domain/replication":
            return demo.REPLICATION
        if path == "/domain/trusts":
            return demo.TRUSTS
        if path == "/domain/sites":
            return demo.SITES
        if path == "/domain/subnets":
            return demo.SUBNETS
        if path == "/domain/password-policy":
            return demo.PASSWORD_POLICY
        if path == "/domain/password-policies":
            return demo.FINE_GRAINED_POLICIES
        if path == "/ad/users" and method == "GET":
            rows = [
                x
                for x in demo.USERS
                if not query
                or query in x["samAccountName"].lower()
                or query in x["displayName"].lower()
                or query in x.get("mail", "").lower()
            ]
            if params.get("page_size"):
                return _page(rows, int(params["page_size"]), params.get("cursor"))
            return rows
        if path.startswith("/ad/users/") and path.endswith("/groups"):
            return [
                {"name": "VPN-Users", "scope": "Global"},
                {"name": "Helpdesk", "scope": "Global"},
            ]
        if path.startswith("/ad/users/") and method == "GET":
            return next((x for x in demo.USERS if x["samAccountName"] == parts[2]), {})
        if path == "/ad/groups" and method == "GET":
            return [x for x in demo.GROUPS if not query or x["name"].lower().startswith(query)]
        if path.startswith("/ad/groups/") and path.endswith("/members") and method == "GET":
            return demo.GROUP_MEMBERS.get(parts[2], [])
        if path == "/ad/computers" and method == "GET":
            return demo.COMPUTERS
        if path == "/ad/ous" and method == "GET":
            return demo.OUS
        if path == "/ad/deleted" and method == "GET":
            return demo.DELETED_OBJECTS
        if path == "/dns/zones" and method == "GET":
            return demo.DNS_ZONES
        if path == "/dns/records" and method == "GET":
            zone = params.get("zone")
            return [x for x in demo.DNS if not zone or x["zone"] == zone]
        if path == "/dhcp/scopes":
            return demo.DHCP
        if path == "/dhcp/leases":
            scope = params.get("scope_id")
            return [x for x in demo.DHCP_LEASES if not scope or x["scopeId"] == scope]
        if path == "/dhcp/reservations" and method == "GET":
            scope = params.get("scope_id")
            return [x for x in demo.DHCP_RESERVATIONS if not scope or x["scopeId"] == scope]
        if path == "/gpo" and method == "GET":
            return demo.GPOS
        if path == "/gpo/links":
            return demo.GPO_LINKS
        if path.startswith("/gpo/") and path.endswith("/permissions"):
            return demo.GPO_PERMISSIONS
        if path.startswith("/gpo/") and path.endswith("/report"):
            return {
                "displayName": "Endpoint Security Baseline",
                "computerEnabled": True,
                "userEnabled": True,
                "links": demo.GPO_LINKS,
                "note": "Demo report",
            }
        # Demo writes change nothing; callers record them with status "demo".
        return {"ok": True, "demo": True}


worker = WorkerClient()
