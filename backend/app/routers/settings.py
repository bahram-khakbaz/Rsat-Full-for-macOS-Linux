import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..audit import write_audit
from ..auth import Principal, require
from ..config import settings
from ..db import DomainControllerConfig, SiteConfig, SystemSetting, get_db
from ..runtime_config import get_runtime_config
from ..secret_store import encrypt_secret

router = APIRouter(prefix="/api/settings", tags=["settings"])

class DcBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    ip: str = Field(default="", max_length=64)
    enabled: bool = True
    notes: str = Field(default="", max_length=500)

class SiteBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=500)
    dcs: list[DcBody] = []

class SettingsBody(BaseModel):
    demo_mode: bool = True
    worker_url: str = Field(default="", max_length=500)
    worker_token: str | None = Field(default=None, max_length=1000)
    sites: list[SiteBody] = []

def _settings_rows(db: Session):
    return {x.key: x.value for x in db.query(SystemSetting).all()}

def _upsert(db: Session, key: str, value: str):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))

@router.get("")
def read_settings(_: Principal = Depends(require("settings.read")), db: Session = Depends(get_db)):
    rows = _settings_rows(db)
    sites = []
    for site in db.query(SiteConfig).order_by(SiteConfig.name).all():
        dcs = db.query(DomainControllerConfig).filter(DomainControllerConfig.site_id == site.id).order_by(DomainControllerConfig.name).all()
        sites.append({
            "id": site.id,
            "name": site.name,
            "code": site.code,
            "description": site.description,
            "dcs": [{
                "id": dc.id, "name": dc.name, "host": dc.host, "ip": dc.ip,
                "enabled": dc.enabled, "notes": dc.notes,
            } for dc in dcs],
        })
    runtime = get_runtime_config()
    return {
        "demo_mode": runtime.demo_mode,
        "worker_url": rows.get("worker_url", settings.worker_url),
        "worker_token_configured": bool(rows.get("worker_token", settings.worker_token)),
        "sites": sites,
    }

@router.put("")
def save_settings(body: SettingsBody, principal: Principal = Depends(require("settings.write")), db: Session = Depends(get_db)):
    site_names = []
    dc_hosts = []
    for site in body.sites:
        name = site.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Every site must have a name")
        site_names.append(name.lower())
        for dc in site.dcs:
            if not dc.name.strip() or not dc.host.strip():
                raise HTTPException(status_code=400, detail=f"Every DC in site {name} requires a name and host/FQDN")
            dc_hosts.append(dc.host.strip().lower())
    if len(site_names) != len(set(site_names)):
        raise HTTPException(status_code=400, detail="Duplicate site names are not allowed")
    if len(dc_hosts) != len(set(dc_hosts)):
        raise HTTPException(status_code=400, detail="A domain controller host/FQDN can only belong to one site")

    _upsert(db, "demo_mode", "true" if body.demo_mode else "false")
    _upsert(db, "worker_url", body.worker_url.strip())
    if body.worker_token is not None and body.worker_token.strip():
        _upsert(db, "worker_token", encrypt_secret(body.worker_token.strip()))

    db.query(DomainControllerConfig).delete()
    db.query(SiteConfig).delete()
    db.flush()
    for site_body in body.sites:
        site = SiteConfig(name=site_body.name.strip(), code=site_body.code.strip(), description=site_body.description.strip())
        db.add(site)
        db.flush()
        for dc_body in site_body.dcs:
            db.add(DomainControllerConfig(
                site_id=site.id, name=dc_body.name.strip(), host=dc_body.host.strip(),
                ip=dc_body.ip.strip(), enabled=dc_body.enabled, notes=dc_body.notes.strip()
            ))
    db.commit()
    write_audit(db, principal, "settings.save", "connection-and-sites", details={
        "demo_mode": body.demo_mode, "worker_url": body.worker_url,
        "sites": len(body.sites), "dcs": sum(len(x.dcs) for x in body.sites),
    })
    return {"ok": True}

@router.post("/test-worker")
async def test_worker(body: SettingsBody, _: Principal = Depends(require("settings.write"))):
    current = get_runtime_config()
    url = (body.worker_url or current.worker_url).rstrip("/")
    token = (body.worker_token or current.worker_token or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Worker URL is required")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(f"{url}/admin/ping", headers={"Authorization": f"Bearer {token}"})
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Worker returned HTTP {response.status_code}")
        return {"ok": True, "worker": response.json()}
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Worker connection failed: {exc}") from exc

@router.post("/discover-dcs")
async def discover_dcs(_: Principal = Depends(require("settings.write"))):
    runtime = get_runtime_config()
    if runtime.demo_mode:
        from .. import demo
        return [{"name":x["name"],"host":x["hostName"],"ip":x.get("ipv4",""),"site":x.get("site","Unknown")} for x in demo.DCS]
    if not runtime.worker_url:
        raise HTTPException(status_code=503, detail="Configure and save the Windows worker first")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{runtime.worker_url}/admin/discover-dcs",
                headers={"Authorization": f"Bearer {runtime.worker_token}"},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text[:1200])
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"DC discovery failed: {exc}") from exc

class DcTestBody(BaseModel):
    host: str = Field(min_length=1, max_length=255)

@router.post("/test-dc")
async def test_dc(body: DcTestBody, _: Principal = Depends(require("settings.write"))):
    runtime = get_runtime_config()
    if runtime.demo_mode:
        return {"ok": True, "host": body.host, "dns": True, "ldap": True, "kerberos": True, "smb": True, "globalCatalog": True}
    if not runtime.worker_url:
        raise HTTPException(status_code=503, detail="Configure and save the Windows worker first")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{runtime.worker_url}/admin/test-dc",
                json={"host": body.host},
                headers={"Authorization": f"Bearer {runtime.worker_token}"},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text[:1200])
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"DC test failed: {exc}") from exc
