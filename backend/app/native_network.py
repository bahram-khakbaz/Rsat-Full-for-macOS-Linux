"""Direct DNS/DHCP RPC and optional WinRM; Kerberos mutual authentication.
No worker, credential delegation, NTLM fallback, or unencrypted application data.
"""

import base64
import json
import os
import re
import threading

import winrm
from fastapi import HTTPException

from .db import SessionLocal, SystemSetting
from .kerberos_cache import credential_cache, reset_failures
from .native_ad import configuration
from .network_scripts import DNS_CREATE, SCRIPTS

_lock = threading.Lock()


def reset_auth_failure():
    reset_failures()


def configuration_network():
    cfg = configuration()
    with SessionLocal() as db:
        row = db.query(SystemSetting).filter_by(key="native_network").first()
        extra = json.loads(row.value) if row else {}
    preferred = cfg.get("preferred_dc") or next(iter(cfg.get("hosts", [])), "")
    return cfg, {
        "dns_host": extra.get("dns_host") or preferred,
        "dhcp_host": extra.get("dhcp_host") or preferred,
        "port": extra.get("port", 5985),
        "dns_mode": extra.get("dns_mode", "Direct"),
        "dhcp_mode": extra.get("dhcp_mode", "RPC"),
    }


def build_script(method, path, payload=None, params=None):
    data = dict(params or {})
    data.update(payload or {})
    script = SCRIPTS.get((method, path))
    if (method, path) == ("POST", "/dns/records"):
        script = DNS_CREATE.get(data.get("type"))
    if not script:
        raise HTTPException(501, "Unsupported direct network operation")
    # Allowlisted variable names; values never become PowerShell source.
    if any(not re.fullmatch("[a-z_]+", key) for key in data):
        raise HTTPException(422, "Invalid parameter name")
    encoded = base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
    header = "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    header += (
        "$inputData=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
        + encoded
        + "')) | ConvertFrom-Json); "
    )
    header += "foreach($p in $inputData.PSObject.Properties){[Environment]::SetEnvironmentVariable(('RSAT_'+$p.Name.ToUpperInvariant()),[string]$p.Value,'Process')}; "
    # ConvertTo-Json sees no pipeline object for empty reads: [] is normalized below.
    return header + script


def request(method, path, payload=None, params=None):
    cfg, network = configuration_network()
    service = path.split("/")[1]
    host = network.get(service + "_host", "").lower()
    domain = cfg.get("domain", "").lower()
    if not domain or not host.endswith("." + domain) or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise HTTPException(
            409, "Configure a DNS/DHCP server FQDN in this domain under Service connection."
        )
    if path.startswith("/dhcp/") and network["dhcp_mode"] == "RPC":
        from .native_dhcp import request as dhcp_rpc

        return dhcp_rpc(cfg, network["dhcp_host"], method, path, payload, params)
    if path.startswith("/dns/") and network["dns_mode"] == "Direct":
        if method == "GET":
            from .native_dns import request as ldap_dns

            return ldap_dns(path, params)
        if path in ("/dns/records", "/dns/records/delete", "/dns/records/update"):
            from .dns_rpc import request as dns_rpc

            return dns_rpc(
                cfg,
                network["dns_host"],
                payload,
                delete=path.endswith("/delete"),
                update=path.endswith("/update"),
            )
        raise HTTPException(
            409,
            "Direct mode supports DNS records. Zone creation and deletion require WinRM management mode.",
        )
    if path.startswith("/dns/") and network["dns_mode"] == "LDAP":
        if method != "GET":
            raise HTTPException(
                409,
                "LDAP DNS inventory is read-only. Select WinRM management and test its permissions before changing records.",
            )
        from .native_dns import request as ldap_dns

        return ldap_dns(path, params)
    script = build_script(method, path, payload, params)
    service = path.split("/")[1]
    host = network.get(service + "_host", "").lower()
    domain = cfg.get("domain", "").lower()
    if (
        not domain
        or not host
        or not host.endswith("." + domain)
        or not re.fullmatch(r"[a-z0-9.-]+", host)
    ):
        raise HTTPException(
            409, "Configure a DNS/DHCP server FQDN in this domain under Service connection."
        )
    if not cfg.get("username") or not cfg.get("password"):
        raise HTTPException(409, "Save the domain account under Settings first.")
    realm = domain.upper()
    user = cfg["username"].split("@")[0].split("\\")[-1] + "@" + realm
    # libkrb5 (used by pywinrm) reads the process environment. Serialize WinRM
    # calls and restore the environment afterwards; the ticket itself comes from
    # the shared private cache used by the RPC connectors.
    with _lock, credential_cache({**cfg, "preferred_dc": cfg.get("preferred_dc") or host}) as env:
        previous = {key: os.environ.get(key) for key in ("KRB5_CONFIG", "KRB5CCNAME")}
        os.environ.update(KRB5_CONFIG=env["KRB5_CONFIG"], KRB5CCNAME=env["KRB5CCNAME"])
        session = None
        try:
            session = winrm.Session(
                "http://" + host + ":" + str(network["port"]) + "/wsman",
                auth=(user, None),
                transport="kerberos",
                message_encryption="always",
                kerberos_delegation=False,
                read_timeout_sec=50,
                operation_timeout_sec=40,
                proxy=None,
            )
            response = session.run_ps(script)
            if response.status_code:
                # Fixed operations never contain passwords. Do not expose raw
                # PowerShell output, which may contain infrastructure details.
                raise HTTPException(
                    502,
                    f"{service.upper()} command failed on {host}. Verify WinRM permissions and the {'DnsServer' if service == 'dns' else 'DhcpServer'} PowerShell module on this service host. Refresh before retrying a write.",
                )
            raw = response.std_out.decode("utf-8-sig").strip()
            if len(raw.encode()) > 32 * 1024 * 1024:
                raise HTTPException(413, "Service output too large. Select one zone or scope.")
            if not raw:
                if method == "GET":
                    return []
                raise HTTPException(
                    502, "Service returned no write confirmation. Refresh before retrying."
                )
            result = json.loads(raw)
            if method == "GET":
                return result if isinstance(result, list) else [result]
            if not isinstance(result, dict) or result.get("ok") is not True:
                raise HTTPException(502, "Service returned an invalid write confirmation.")
            return result
        except HTTPException:
            raise
        except winrm.exceptions.InvalidCredentialsError as exc:
            raise HTTPException(
                403,
                f"Kerberos domain login succeeded, but {host} rejected WinRM access. Verify remote management permission and WinRM authentication policy on this service server. This is separate from AD/RSAT permissions.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                502,
                f"Direct {service.upper()} connection failed on {host}. Check WinRM port {network['port']}, Kerberos HTTP service identity and account permissions. No worker or NTLM fallback was used.",
            ) from exc
        finally:
            if session:
                session.protocol.transport.close_session()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
