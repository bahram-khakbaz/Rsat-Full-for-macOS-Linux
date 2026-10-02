import httpx
from fastapi import HTTPException
from .config import settings
from .runtime_config import get_runtime_config
from . import demo

class WorkerClient:
    async def request(self, method: str, path: str, payload=None, params=None):
        runtime = get_runtime_config()
        if runtime.demo_mode:
            return self._demo(method, path, payload, params)
        if not runtime.worker_url:
            raise HTTPException(status_code=503, detail="Windows worker is not configured")
        headers = {"Authorization": f"Bearer {runtime.worker_token}"}
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.request(method, f"{runtime.worker_url}{path}", json=payload, params=params, headers=headers)
            if response.status_code >= 400:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                raise HTTPException(status_code=response.status_code, detail=str(detail)[:1500])
            return response.json()
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Worker connection failed: {exc}") from exc

    def _demo(self, method: str, path: str, payload, params):
        params = params or {}
        if path == "/domain/summary": return demo.DOMAIN
        if path == "/domain/controllers": return demo.DCS
        if path == "/domain/replication": return demo.REPLICATION
        if path == "/domain/trusts": return demo.TRUSTS
        if path == "/domain/sites": return demo.SITES
        if path == "/domain/subnets": return demo.SUBNETS
        if path == "/domain/password-policy": return demo.PASSWORD_POLICY
        if path == "/domain/password-policies": return demo.FINE_GRAINED_POLICIES
        if path == "/ad/users" and method == "GET":
            q = (params.get("q") or "").lower()
            return [x for x in demo.USERS if not q or q in x["samAccountName"].lower() or q in x["displayName"].lower() or q in x.get("mail","").lower()]
        if path.startswith("/ad/users/") and path.endswith("/groups"): return [{"name":"VPN-Users","scope":"Global"},{"name":"Helpdesk","scope":"Global"}]
        if path.startswith("/ad/users/") and method == "GET":
            identity = path.split("/")[3]
            return next((x for x in demo.USERS if x["samAccountName"] == identity), {})
        if path == "/ad/groups" and method == "GET": return demo.GROUPS
        if path.startswith("/ad/groups/") and path.endswith("/members") and method == "GET":
            name = path.split("/")[3]
            return demo.GROUP_MEMBERS.get(name, [])
        if path == "/ad/computers" and method == "GET": return demo.COMPUTERS
        if path == "/ad/ous" and method == "GET": return demo.OUS
        if path == "/ad/deleted" and method == "GET": return demo.DELETED_OBJECTS
        if path == "/dns/zones" and method == "GET": return demo.DNS_ZONES
        if path == "/dns/records" and method == "GET":
            zone = params.get("zone")
            return [x for x in demo.DNS if not zone or x["zone"] == zone]
        if path == "/dhcp/scopes": return demo.DHCP
        if path == "/dhcp/leases":
            scope = params.get("scope_id")
            return [x for x in demo.DHCP_LEASES if not scope or x["scopeId"] == scope]
        if path == "/dhcp/reservations" and method == "GET":
            scope = params.get("scope_id")
            return [x for x in demo.DHCP_RESERVATIONS if not scope or x["scopeId"] == scope]
        if path == "/gpo" and method == "GET": return demo.GPOS
        if path == "/gpo/links": return demo.GPO_LINKS
        if path.startswith("/gpo/") and path.endswith("/permissions"): return demo.GPO_PERMISSIONS
        if path.startswith("/gpo/") and path.endswith("/report"):
            return {"displayName":"Endpoint Security Baseline","computerEnabled":True,"userEnabled":True,"links":demo.GPO_LINKS,"note":"Demo report"}
        return {"ok": True, "demo": True}

worker = WorkerClient()
