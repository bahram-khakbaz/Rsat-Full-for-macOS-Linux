import json
import re
import ssl
from typing import Literal
from starlette.concurrency import run_in_threadpool
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..audit import write_audit
from ..auth import Principal, require
from ..config import settings
from ..db import DomainControllerConfig, SiteConfig, SystemSetting, get_db
from ..runtime_config import get_runtime_config
from ..secret_store import encrypt_secret, store_credential
from ..native_ad import public_configuration

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
    dcs: list[DcBody] = Field(default_factory=list)

class SettingsBody(BaseModel):
    demo_mode: bool = True
    connection_mode: Literal["worker", "native"] | None = None
    worker_url: str = Field(default="", max_length=500)
    sites: list[SiteBody] = Field(default_factory=list)

class PairWorkerBody(BaseModel):
    worker_url: str = Field(min_length=4, max_length=500)
    pairing_code: str = Field(min_length=4, max_length=128)

class ConnectionProbe(BaseModel):
    worker_url: str = ""
    demo_mode: bool = False

class DcTestBody(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    worker_url: str = ""
    demo_mode: bool = False

def _settings_rows(db: Session):
    return {x.key: x.value for x in db.query(SystemSetting).all()}

def _upsert(db: Session, key: str, value: str):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))

def _delete_setting(db: Session, key: str):
    db.query(SystemSetting).filter(SystemSetting.key == key).delete()

def _worker_identity(rows: dict[str, str]):
    raw = rows.get("worker_identity", "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

@router.get("")
def read_settings(_: Principal = Depends(require("settings.read")), db: Session = Depends(get_db)):
    rows = _settings_rows(db)
    sites = []
    for site in db.query(SiteConfig).order_by(SiteConfig.name).all():
        dcs = db.query(DomainControllerConfig).filter(
            DomainControllerConfig.site_id == site.id
        ).order_by(DomainControllerConfig.name).all()
        sites.append({
            "id": site.id,
            "name": site.name,
            "code": site.code,
            "description": site.description,
            "dcs": [{
                "id": dc.id,
                "name": dc.name,
                "host": dc.host,
                "ip": dc.ip,
                "enabled": dc.enabled,
                "notes": dc.notes,
            } for dc in dcs],
        })
    runtime = get_runtime_config()
    return {
        "demo_mode": runtime.demo_mode,
        "worker_url": rows.get("worker_url", settings.worker_url),
        "worker_paired": bool(rows.get("worker_token") or settings.worker_token),
        "worker_identity": _worker_identity(rows),
        "authentication_model": "direct-ldaps" if runtime.connection_mode == "native" else "domain-integrated-worker",
        "connection_mode": runtime.connection_mode,
        "native": public_configuration(rows),
        "sites": sites,
    }

@router.put("")
def save_settings(
    body: SettingsBody,
    principal: Principal = Depends(require("settings.write")),
    db: Session = Depends(get_db),
):
    site_names = []
    dc_hosts = []
    for site in body.sites:
        name = site.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Every site must have a name")
        site_names.append(name.lower())
        for dc in site.dcs:
            if not dc.name.strip() or not dc.host.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"Every DC in site {name} requires a name and host/FQDN",
                )
            dc_hosts.append(dc.host.strip().lower())
    if len(site_names) != len(set(site_names)):
        raise HTTPException(status_code=400, detail="Duplicate site names are not allowed")
    if len(dc_hosts) != len(set(dc_hosts)):
        raise HTTPException(
            status_code=400,
            detail="A domain controller host/FQDN can only belong to one site",
        )

    rows = _settings_rows(db)
    previous_url = rows.get("worker_url", settings.worker_url).rstrip("/")
    next_url = body.worker_url.strip().rstrip("/")
    if previous_url and next_url and previous_url != next_url:
        _delete_setting(db, "worker_token")
        _delete_setting(db, "worker_identity")

    _upsert(db, "demo_mode", "true" if body.demo_mode else "false")
    _upsert(db, "worker_url", next_url)
    if body.connection_mode is not None:
        _upsert(db, "connection_mode", body.connection_mode)

    db.query(DomainControllerConfig).delete()
    db.query(SiteConfig).delete()
    db.flush()
    for site_body in body.sites:
        site = SiteConfig(
            name=site_body.name.strip(),
            code=site_body.code.strip(),
            description=site_body.description.strip(),
        )
        db.add(site)
        db.flush()
        for dc_body in site_body.dcs:
            db.add(DomainControllerConfig(
                site_id=site.id,
                name=dc_body.name.strip(),
                host=dc_body.host.strip(),
                ip=dc_body.ip.strip(),
                enabled=dc_body.enabled,
                notes=dc_body.notes.strip(),
            ))
    db.commit()
    write_audit(db, principal, "settings.save", "connection-and-sites", details={
        "demo_mode": body.demo_mode,
        "worker_url": next_url,
        "sites": len(body.sites),
        "dcs": sum(len(x.dcs) for x in body.sites),
    })
    return {"ok": True}

@router.post("/pair-worker")
async def pair_worker(
    body: PairWorkerBody,
    principal: Principal = Depends(require("settings.write")),
    db: Session = Depends(get_db),
):
    url = body.worker_url.strip().rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                f"{url}/pair",
                json={"code": body.pairing_code.strip()},
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=str(detail)[:1200])
        data = response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Worker pairing failed: {exc}") from exc

    token = str(data.get("worker_token") or "")
    identity = data.get("identity") or {}
    if not token:
        raise HTTPException(status_code=502, detail="Worker did not return a pairing credential")

    _upsert(db, "worker_url", url)
    _upsert(db, "worker_token", encrypt_secret(token))
    _upsert(db, "worker_identity", json.dumps(identity, ensure_ascii=False))
    db.commit()
    write_audit(db, principal, "settings.worker.pair", url, details={
        "computer": identity.get("computer", ""),
        "runAs": identity.get("runAs", ""),
        "domain": identity.get("domain", ""),
    })
    return {
        "ok": True,
        "worker_url": url,
        "worker_identity": identity,
    }

@router.post("/unpair-worker")
def unpair_worker(
    principal: Principal = Depends(require("settings.write")),
    db: Session = Depends(get_db),
):
    rows = _settings_rows(db)
    url = rows.get("worker_url", "")
    _delete_setting(db, "worker_token")
    _delete_setting(db, "worker_identity")
    db.commit()
    write_audit(db, principal, "settings.worker.unpair", url)
    return {"ok": True}

@router.post("/test-worker")
async def test_worker(
    body: ConnectionProbe,
    _: Principal = Depends(require("settings.write")),
):
    runtime = get_runtime_config()
    if body.demo_mode:
        return {
            "ok": True,
            "worker": {
                "service": "windows-worker",
                "authenticated": True,
                "demo": True,
            },
        }
    url = (body.worker_url or runtime.worker_url).rstrip("/")
    if not url:
        raise HTTPException(status_code=400, detail="Worker URL is required")
    if not runtime.worker_token:
        raise HTTPException(status_code=409, detail="Worker is not paired yet")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                f"{url}/admin/ping",
                headers={"Authorization": f"Bearer {runtime.worker_token}"},
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Worker returned HTTP {response.status_code}",
            )
        return {"ok": True, "worker": response.json()}
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Worker connection failed: {exc}") from exc

@router.post("/discover-dcs")
async def discover_dcs(
    body: ConnectionProbe,
    _: Principal = Depends(require("settings.write")),
):
    runtime = get_runtime_config()
    if runtime.connection_mode == "native" and not body.demo_mode:
        from ..native_ad import request
        return await run_in_threadpool(request, "GET", "/admin/discover-dcs")
    if body.demo_mode:
        from .. import demo
        return [{
            "name": x["name"],
            "host": x["hostName"],
            "ip": x.get("ipv4", ""),
            "site": x.get("site", "Unknown"),
            "enabled": x.get("enabled", True),
            "globalCatalog": x.get("globalCatalog", False),
        } for x in demo.DCS]
    worker_url = (body.worker_url or runtime.worker_url).rstrip("/")
    if not worker_url:
        raise HTTPException(status_code=503, detail="Windows worker URL is required")
    if not runtime.worker_token:
        raise HTTPException(status_code=409, detail="Pair the Windows worker first")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{worker_url}/admin/discover-dcs",
                headers={"Authorization": f"Bearer {runtime.worker_token}"},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text[:1200])
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"DC discovery failed: {exc}") from exc

@router.post("/test-dc")
async def test_dc(
    body: DcTestBody,
    _: Principal = Depends(require("settings.write")),
):
    runtime = get_runtime_config()
    if runtime.connection_mode == "native" and not body.demo_mode:
        from ..native_ad import configuration, request
        cfg = configuration()
        if body.host not in cfg["hosts"]:
            raise HTTPException(422, "Save this DC in settings before testing it")
        cfg["hosts"] = [body.host]
        result = await run_in_threadpool(request, "GET", "/admin/ping", None, None, cfg)
        return {**result, "dns": True, "ldap": True, "ldaps": True}
    if body.demo_mode:
        return {
            "ok": True,
            "host": body.host,
            "dns": True,
            "ldap": True,
            "kerberos": True,
            "smb": True,
            "ldaps": True,
            "globalCatalog": True,
            "site": "Demo",
        }
    worker_url = (body.worker_url or runtime.worker_url).rstrip("/")
    if not worker_url:
        raise HTTPException(status_code=503, detail="Windows worker URL is required")
    if not runtime.worker_token:
        raise HTTPException(status_code=409, detail="Pair the Windows worker first")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{worker_url}/admin/test-dc",
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


class NativeBody(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
    username: str = Field(min_length=3, max_length=256)
    preferred_dc: str = Field(default="", max_length=253)
    password: str | None = Field(default=None, max_length=1024)
    vault_key: str | None = Field(default=None, max_length=80)
    ca_pem: str = Field(default="", max_length=65536)


def validate_native(body: NativeBody):
    domain = body.domain.strip().lower()
    host = body.preferred_dc.strip().lower()
    hostname = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if not hostname.fullmatch(domain) or (host and (not hostname.fullmatch(host) or not host.endswith("." + domain))):
        raise HTTPException(422, "Use the AD domain and a DC FQDN inside that domain")
    username = body.username.strip()
    if "@" not in username or "\\" in username or any(ord(x) < 32 for x in username):
        raise HTTPException(422, "Enter your AD user principal name, for example operator@example.com")
    if body.ca_pem.strip():
        try:
            ssl.create_default_context(cadata=body.ca_pem.strip())
        except (ssl.SSLError, ValueError) as exc:
            raise HTTPException(422, "The AD CA certificate must be a valid PEM certificate or certificate chain") from exc
    return {"domain": domain, "username": username, "preferred_dc": host, "ca_pem": body.ca_pem.strip()}

@router.put("/native")
def save_native(body: NativeBody, principal: Principal = Depends(require("settings.write")), db: Session = Depends(get_db)):
    cfg = validate_native(body)
    rows = _settings_rows(db)
    previous = json.loads(rows.get("native_config", "{}"))
    identity_changed = any(previous.get(k) != cfg[k] for k in ("domain", "username"))
    if not (body.password or body.vault_key) and (identity_changed or not rows.get("native_password")):
        raise HTTPException(422, "Enter the AD password for this account")
    credential = store_credential(body.password or "", body.vault_key, principal.username, rows.get("native_password", ""))
    _upsert(db, "native_password", credential)
    _upsert(db, "native_config", json.dumps(cfg))
    _upsert(db, "connection_mode", "native")
    _upsert(db, "demo_mode", "false")
    db.commit()
    from ..native_ad import reset_auth_failure
    reset_auth_failure()
    write_audit(db, principal, "settings.native.save", cfg["domain"], details={"username":cfg["username"],"preferred_dc":cfg["preferred_dc"]})
    return {"ok": True, "connection_mode": "native"}

@router.post("/native/test")
async def test_native(_: Principal = Depends(require("settings.write"))):
    from ..native_ad import request
    return await run_in_threadpool(request, "GET", "/admin/ping")

@router.delete("/native/credentials")
def forget_native(principal: Principal = Depends(require("settings.write")), db: Session = Depends(get_db)):
    _delete_setting(db, "native_password")
    db.commit()
    write_audit(db, principal, "settings.native.forget", "native-account")
    return {"ok": True}


class CertificateProbe(BaseModel):
    host: str = Field(min_length=3, max_length=253)

class CertificateTrust(CertificateProbe):
    fingerprint: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


def allowed_certificate_host(db: Session, host: str):
    host = host.strip().lower()
    cfg = json.loads(_settings_rows(db).get("native_config", "{}"))
    hosts = [x.host.lower() for x in db.query(DomainControllerConfig).filter_by(enabled=True).all()]
    if cfg.get("preferred_dc"):
        hosts.append(cfg["preferred_dc"].lower())
    if host not in hosts:
        raise HTTPException(422, "Choose an enabled, saved domain controller")
    return host

@router.post("/native/certificate")
async def inspect_native_certificate(body: CertificateProbe, _: Principal = Depends(require("settings.write")), db: Session = Depends(get_db)):
    from ..native_ad import inspect_certificate
    return await run_in_threadpool(inspect_certificate, allowed_certificate_host(db,body.host))

@router.post("/native/trust-certificate")
async def trust_native_certificate(body: CertificateTrust, principal: Principal = Depends(require("settings.write")), db: Session = Depends(get_db)):
    from ..native_ad import inspect_certificate
    host = allowed_certificate_host(db,body.host)
    info = await run_in_threadpool(inspect_certificate,host)
    if info["fingerprint"] != body.fingerprint.lower():
        raise HTTPException(409, "The certificate changed since inspection. Inspect it again before approving.")
    if not info["hostname_valid"] or not info["time_valid"]:
        raise HTTPException(422, "Certificate is expired/not yet valid, or its DNS names do not match this DC")
    pins = json.loads(_settings_rows(db).get("native_certificate_pins", "{}"))
    pins[host] = info["fingerprint"]
    _upsert(db,"native_certificate_pins",json.dumps(pins))
    # Prefer the approved DC. One DC provides the whole domain's directory.
    cfg = json.loads(_settings_rows(db).get("native_config", "{}"))
    cfg["preferred_dc"] = host
    _upsert(db,"native_config",json.dumps(cfg))
    db.commit()
    write_audit(db,principal,"settings.native.trust_certificate",host,details={"fingerprint":info["fingerprint"]})
    return {"ok":True,"host":host,"fingerprint":info["fingerprint"]}
