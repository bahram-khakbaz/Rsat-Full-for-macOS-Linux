import httpx
from fastapi import HTTPException
from .config import settings
from . import demo

class WorkerClient:
    def __init__(self):
        self.base = settings.worker_url.rstrip("/")

    async def request(self, method: str, path: str, payload=None, params=None):
        if settings.demo_mode:
            return self._demo(method, path, payload, params)
        if not self.base:
            raise HTTPException(status_code=503, detail="Windows worker is not configured")
        headers = {"Authorization": f"Bearer {settings.worker_token}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(method, f"{self.base}{path}", json=payload, params=params, headers=headers)
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=response.text[:1000])
            return response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Worker connection failed: {exc}") from exc

    def _demo(self, method: str, path: str, payload, params):
        if path == "/ad/users":
            q = ((params or {}).get("q") or "").lower()
            return [x for x in demo.USERS if not q or q in x["samAccountName"].lower() or q in x["displayName"].lower()]
        if path.startswith("/ad/users/") and method == "GET":
            identity = path.split("/")[3]
            return next((x for x in demo.USERS if x["samAccountName"] == identity), None) or {}
        if path == "/ad/groups": return demo.GROUPS
        if path == "/ad/computers": return demo.COMPUTERS
        if path == "/ad/ous": return demo.OUS
        if path == "/dns/records": return demo.DNS
        if path == "/dhcp/scopes": return demo.DHCP
        if path == "/gpo": return demo.GPOS
        return {"ok": True, "demo": True}

worker = WorkerClient()
