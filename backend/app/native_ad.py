"""Direct AD access over certificate-verified LDAPS. No Windows process required."""
import json
import hashlib
import threading
import socket
import base64
import hmac
import re
import jwt
from .config import settings
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import ssl
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from fastapi import HTTPException
from ldap3 import BASE, SUBTREE, Connection, Server, Tls, NONE, MODIFY_REPLACE, MODIFY_ADD, MODIFY_DELETE
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn, parse_dn

from .db import SessionLocal, SystemSetting, DomainControllerConfig
from .secret_store import decrypt_secret
from .vault_agent import metadata as credential_metadata

_auth_lock = threading.RLock()
_failed_credentials = set()
_preferred_hosts = {}
_transport_failures = {}

def reset_auth_failure():
    with _auth_lock:
        _failed_credentials.clear()
        _transport_failures.clear()

SUPPORTED = {
    "directory": True, "account_actions": True, "group_membership": True,
    "gpo_inventory": True, "dns": True, "dhcp": True,
    "gpo_management": False, "replication": False, "recycle_bin": False,
    "ou_protection": False, "computer_reset": False,
}

def configuration():
    with SessionLocal() as db:
        rows = {x.key: x.value for x in db.query(SystemSetting).all()}
        hosts = [x.host for x in db.query(DomainControllerConfig).filter_by(enabled=True).order_by(DomainControllerConfig.id).all()]
    cfg = json.loads(rows.get("native_config", "{}"))
    cfg["certificate_pins"] = json.loads(rows.get("native_certificate_pins", "{}"))
    cfg["password"] = decrypt_secret(rows.get("native_password", ""))
    preferred = cfg.get("preferred_dc", "")
    cfg["hosts"] = [h.lower() for h in dict.fromkeys(([preferred] if preferred else []) + hosts) if cfg.get("domain") and h.lower().endswith("."+cfg["domain"].lower())]
    return cfg

def public_configuration(rows):
    cfg = json.loads(rows.get("native_config", "{}"))
    return {**{k:cfg.get(k, "") for k in ("domain", "username", "preferred_dc", "ca_pem", "mobile_attribute")}, **credential_metadata(rows.get("native_password", "")), "password_configured": bool(rows.get("native_password")), "capabilities": SUPPORTED, "trusted_dc_certificates": list(json.loads(rows.get("native_certificate_pins", "{}")))}

def certificate_details(host, der):
    cert = x509.load_der_x509_certificate(der)
    try:
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        names = []
    # Only exact AD DC names are accepted for pinning.
    name_ok = host.rstrip(".").lower() in [x.rstrip(".").lower() for x in names]
    now = datetime.now(timezone.utc)
    return {"host":host,"fingerprint":cert.fingerprint(hashes.SHA256()).hex(),"subject":cert.subject.rfc4514_string(),"issuer":cert.issuer.rfc4514_string(),"valid_from":cert.not_valid_before_utc.isoformat(),"valid_until":cert.not_valid_after_utc.isoformat(),"dns_names":names,"hostname_valid":name_ok,"time_valid":cert.not_valid_before_utc <= now <= cert.not_valid_after_utc}

def inspect_certificate(host):
    # No credentials are sent. Trust is established separately by a human action.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host,636),timeout=4) as sock:
            with context.wrap_socket(sock,server_hostname=host) as tls:
                return certificate_details(host,tls.getpeercert(binary_form=True))
    except (OSError, ssl.SSLError, ValueError) as exc:
        raise HTTPException(502,"Cannot inspect this DC certificate. Check DNS, VPN and LDAPS port 636.") from exc

class PinnedTls(Tls):
    def __init__(self, host, fingerprint):
        super().__init__(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLS_CLIENT, sni=host)
        self.host, self.fingerprint = host, fingerprint

    def wrap_socket(self, connection, do_handshake=False):
        super().wrap_socket(connection, do_handshake=True)
        info = certificate_details(self.host,connection.socket.getpeercert(binary_form=True))
        if info["fingerprint"] != self.fingerprint or not info["hostname_valid"] or not info["time_valid"]:
            connection.socket.close()
            raise HTTPException(502,"The approved DC certificate changed, expired or does not match its hostname. No AD password was sent. Review the certificate in Settings.")


def unavailable(feature):
    raise HTTPException(501, f"{feature} is not supported by the direct Mac LDAP connector.")

def scalar(entry, key, default=""):
    value = entry.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default

def number(entry, key, default=0):
    try:
        return int(scalar(entry, key, default))
    except (ValueError, TypeError):
        return default

def values(entry, key):
    v = entry.get(key, [])
    return v if isinstance(v, list) else [v] if v else []

def date(value):
    if isinstance(value, str) and re.fullmatch(r"\d{14}(?:\.\d+)?Z", value):
        return datetime.strptime(value.split(".")[0].rstrip("Z"), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        ticks = int(value)
        if ticks <= 0 or ticks >= 9223372036854775807:
            return None
        return (datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks // 10)).isoformat()
    except (ValueError, TypeError, OverflowError):
        return str(value) if value else None

def parent(dn):
    parts = parse_dn(dn)
    return "".join(a + "=" + b + sep for a, b, sep in parts[1:])

USER_ATTRS = ["sAMAccountName", "displayName", "givenName", "sn", "mail", "department", "title", "company", "manager", "mobile", "otherMobile", "telephoneNumber", "homePhone", "ipPhone", "employeeID", "physicalDeliveryOfficeName", "userAccountControl", "msDS-User-Account-Control-Computed", "lastLogonTimestamp", "whenCreated", "pwdLastSet", "msDS-UserPasswordExpiryTimeComputed"]
COMPUTER_ATTRS = ["name", "sAMAccountName", "operatingSystem", "dNSHostName", "userAccountControl", "lastLogonTimestamp"]
GROUP_ATTRS = ["name", "sAMAccountName", "description", "groupType"]

class Directory:
    def __init__(self, cfg=None):
        self.cfg = cfg if cfg is not None else configuration()
        self.conn = None
        self.host = ""
        self.base = ",".join("DC=" + x for x in self.cfg.get("domain", "").split(".") if x)
        self.config_base = "CN=Configuration," + self.base
        self.schema_base = "CN=Schema," + self.config_base

    def __enter__(self):
        # Serialise binds so simultaneous initial dashboard reads cannot lock an account.
        with _auth_lock:
            return self.connect()

    def connect(self):
        fingerprint = hashlib.sha256((self.cfg.get("username", "") + "\0" + self.cfg.get("password", "")).encode()).hexdigest()
        cache_key = fingerprint + hashlib.sha256(json.dumps({k:self.cfg.get(k) for k in ("hosts","ca_pem","certificate_pins")},sort_keys=True).encode()).hexdigest()
        cached = _transport_failures.get(cache_key)
        if cached and time.monotonic() < cached[0]:
            raise HTTPException(502,cached[1])
        if fingerprint in _failed_credentials:
            raise HTTPException(422, "AD previously rejected these credentials. Update or re-save the account in Settings before retrying.")
        if not self.cfg.get("password") or not self.cfg.get("username") or not self.base:
            raise HTTPException(409, "Set your domain account in Settings → Direct Mac connection first.")
        if not self.cfg.get("hosts"):
            raise HTTPException(409, "Configure a preferred DC or at least one enabled DC.")
        tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_data=self.cfg.get("ca_pem") or None, version=ssl.PROTOCOL_TLS_CLIENT)
        deadline = time.monotonic() + 18
        failures = []
        hosts = list(self.cfg["hosts"])
        pins = self.cfg.get("certificate_pins", {})
        if pins and not self.cfg.get("ca_pem"):
            hosts = [host for host in hosts if host.lower() in pins]
            if not hosts:
                raise HTTPException(409, "Approve a certificate for an enabled DC in Settings, or provide the corporate CA certificate.")
        recent = _preferred_hosts.get(self.cfg.get("domain"))
        if recent in hosts:
            hosts.remove(recent)
            hosts.insert(0, recent)
        for host in hosts:
            if time.monotonic() >= deadline:
                break
            host_tls = PinnedTls(host,self.cfg["certificate_pins"][host.lower()]) if not self.cfg.get("ca_pem") and host.lower() in self.cfg.get("certificate_pins",{}) else tls
            c = Connection(Server(host, port=636, use_ssl=True, tls=host_tls, get_info=NONE, connect_timeout=2), user=self.cfg["username"], password=self.cfg["password"], auto_referrals=False, receive_timeout=4, auto_range=True, raise_exceptions=False)
            try:
                if not c.bind():
                    # Never try a wrong password against every DC (account lockout).
                    if (c.result or {}).get("result") == 49:
                        _failed_credentials.add(fingerprint)
                        raise HTTPException(422, "AD rejected this account. Check the UPN/password and account status; no other DC was tried.")
                    raise HTTPException(502, f"AD bind failed on {host} (LDAP code {(c.result or {}).get('result', 'unknown')}).")
                self.conn, self.host = c, host
                root = self.search("", "(objectClass=*)", ["defaultNamingContext", "configurationNamingContext", "schemaNamingContext", "rootDomainNamingContext"], BASE)[0]
                if scalar(root, "defaultNamingContext").lower() != self.base.lower():
                    raise HTTPException(422, "The DC's domain does not match the configured AD domain.")
                self.config_base = scalar(root, "configurationNamingContext", self.config_base)
                self.schema_base = scalar(root, "schemaNamingContext", self.schema_base)
                self.root = root
                _preferred_hosts[self.cfg["domain"]] = host
                return self
            except HTTPException:
                c.unbind()
                raise
            except (LDAPException, OSError, ssl.SSLError) as exc:
                c.unbind()
                self.conn = None
                if "CERTIFICATE_VERIFY_FAILED" in str(exc).upper() or isinstance(exc, ssl.SSLCertVerificationError):
                    raise HTTPException(409, f"LDAPS certificate is not trusted for {host}. Your saved password has not been checked. In Settings, inspect the DC certificate and verify/approve its fingerprint, or add the corporate CA certificate, then use TEST DIRECT CONNECTION.") from exc
                failures.append(host)
        message = "Direct LDAPS connection failed. Check network/VPN, DNS, port 636 and the AD CA certificate, or approve a DC certificate in Settings. Tried: " + ", ".join(failures)
        _transport_failures[cache_key] = (time.monotonic()+30,message)
        raise HTTPException(502,message)

    def __exit__(self, *_):
        if self.conn:
            self.conn.unbind()

    def checked(self, ok):
        if not ok:
            code = (self.conn.result or {}).get("result", "unknown")
            raise HTTPException(403 if code == 50 else 422, f"AD operation failed (LDAP code {code}: {(self.conn.result or {}).get('description', 'unknown')}).")
        return {"ok": True, "dc": self.host}

    def search(self, base, filter, attrs, scope=SUBTREE):
        rows, cookie = [], None
        while True:
            self.conn.search(base, filter, search_scope=scope, attributes=attrs, paged_size=500 if scope != BASE else None, paged_cookie=cookie, time_limit=30)
            result = self.conn.result or {}
            # Do not report an incomplete directory as a successful empty list.
            if result.get("result") != 0:
                self.checked(False)
            rows.extend({**x["attributes"], "dn": x["dn"]} for x in self.conn.response if x.get("type") == "searchResEntry")
            cookie = result.get("controls", {}).get("1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie")
            if not cookie:
                return rows

    def find(self, identity, kind, attrs):
        escaped = escape_filter_chars(identity)
        f = f"(&(objectClass={kind})(|(sAMAccountName={escaped})(name={escaped})(distinguishedName={escaped})))"
        if kind == "user":
            f = f"(&(objectCategory=person){f})"
        if kind == "computer" and not identity.endswith("$"):
            f = f"(&(objectClass=computer)(|(sAMAccountName={escaped}$)(name={escaped})(distinguishedName={escaped})))"
        rows = self.search(self.base, f, attrs)
        if len(rows) != 1:
            raise HTTPException(404 if not rows else 409, "Object not found or identity is ambiguous; use its distinguished name.")
        return rows[0]

    def user_attributes(self):
        attribute = self.cfg.get("mobile_attribute") or "mobile"
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", attribute):
            raise HTTPException(422, "Invalid mobile attribute configuration")
        return list(dict.fromkeys(USER_ATTRS + [attribute]))

    def user(self, x):
        uac, computed = number(x, "userAccountControl"), number(x, "msDS-User-Account-Control-Computed")
        mapping = {"samAccountName":"sAMAccountName", "displayName":"displayName", "givenName":"givenName", "surname":"sn", "mail":"mail", "department":"department", "title":"title", "company":"company", "manager":"manager", "mobile":"mobile", "employeeId":"employeeID", "office":"physicalDeliveryOfficeName"}
        mapping.update({"telephoneNumber":"telephoneNumber", "homePhone":"homePhone", "ipPhone":"ipPhone"})
        # Keep additional numbers separate: editing mobile must never overwrite otherMobile.
        mapped = {k:scalar(x,v) for k,v in mapping.items()}
        mapped["otherMobile"] = values(x, "otherMobile")
        attribute = self.cfg.get("mobile_attribute") or "mobile"
        mapped["directoryMobile"] = scalar(x, attribute)
        mapped["mobileAttribute"] = attribute
        return {**mapped, "dn":x["dn"], "ou":parent(x["dn"]), "enabled":not bool(uac & 2), "lockedOut":bool(computed & 16), "passwordExpired":bool(computed & 8388608), "passwordNeverExpires":bool(uac & 65536), "lastLogon":date(scalar(x,"lastLogonTimestamp")), "created":date(scalar(x,"whenCreated")), "passwordLastSet":date(scalar(x,"pwdLastSet")), "passwordExpires":date(scalar(x,"msDS-UserPasswordExpiryTimeComputed"))}

    def group(self, x):
        flags = number(x, "groupType") & 0xffffffff
        return {"name":scalar(x,"name"), "dn":x["dn"], "description":scalar(x,"description"), "scope":"Universal" if flags & 8 else "DomainLocal" if flags & 4 else "Global", "category":"Security" if flags & 0x80000000 else "Distribution", "members":None}

    def controllers(self):
        servers = self.search("CN=Sites," + self.config_base, "(objectClass=server)", ["name","dNSHostName","serverReference"])
        dsas = {parent(x["dn"]).lower():number(x,"options") for x in self.search("CN=Sites," + self.config_base, "(objectClass=nTDSDSA)", ["options"])}
        computers = {x["dn"].lower():x for x in self.search(self.base, "(&(objectClass=computer)(userAccountControl:1.2.840.113556.1.4.803:=8192))", COMPUTER_ATTRS)}
        result = []
        for x in servers:
            if x["dn"].lower() not in dsas:
                continue
            ref = computers.get(str(scalar(x,"serverReference")).lower(), {})
            dnparts = parse_dn(x["dn"])
            site = next((dnparts[i-1][1] for i,p in enumerate(dnparts) if p[1].lower()=="sites" and i), "Unknown")
            result.append({"name":scalar(x,"name"), "hostName":scalar(x,"dNSHostName",scalar(ref,"dNSHostName")), "site":site, "ipv4":"", "os":scalar(ref,"operatingSystem"), "globalCatalog":bool(dsas[x["dn"].lower()] & 1), "enabled":not bool(number(ref,"userAccountControl") & 2)})
        return result

    def owner(self, dn):
        if not dn:
            return None
        rows = self.search(parent(str(dn)), "(objectClass=*)", ["dNSHostName"], BASE)
        return scalar(rows[0], "dNSHostName") if rows else None

    def user_page(self, filter, query, page_size, cursor):
        tag = hmac.new(settings.jwt_secret.encode(),json.dumps(self.cfg,sort_keys=True).encode(),hashlib.sha256).hexdigest()
        cookie = None
        if cursor:
            try:
                claims = jwt.decode(cursor,settings.jwt_secret,algorithms=["HS256"])
                if claims.get("kind") != "native-users-page" or claims.get("query") != query or claims.get("host") != self.host or claims.get("config") != tag or claims.get("page_size") != page_size:
                    raise ValueError("Cursor mismatch")
                cookie = base64.b64decode(claims["cookie"],validate=True)
            except (jwt.PyJWTError, ValueError, KeyError) as exc:
                raise HTTPException(409,"This directory page expired or the search/connection changed. Refresh the user list.") from exc
        self.conn.search(self.base,filter,search_scope=SUBTREE,attributes=self.user_attributes(),paged_size=page_size,paged_cookie=cookie,time_limit=15)
        if (self.conn.result or {}).get("result") != 0:
            self.checked(False)
        rows = [{**x["attributes"],"dn":x["dn"]} for x in self.conn.response if x.get("type")=="searchResEntry"]
        control = (self.conn.result or {}).get("controls",{}).get("1.2.840.113556.1.4.319",{}).get("value",{})
        next_cookie = control.get("cookie")
        next_cursor = jwt.encode({"kind":"native-users-page","host":self.host,"config":tag,"query":query,"page_size":page_size,"cookie":base64.b64encode(next_cookie).decode(),"exp":int(time.time())+600},settings.jwt_secret,algorithm="HS256") if next_cookie else None
        return {"items":[self.user(x) for x in rows],"next_cursor":next_cursor,"has_more":bool(next_cursor),"total":None,"dc":self.host}

    def request(self, method, path, payload=None, params=None):
        payload, params = payload or {}, params or {}
        if path == "/admin/ping":
            return {"ok":True, "host":self.host, "domain":self.cfg["domain"], "username":self.cfg["username"], "authentication":"LDAPS / approved certificate pin" if isinstance(self.conn.server.tls,PinnedTls) else "LDAPS / verified CA", "capabilities":SUPPORTED}
        if path in ("/domain/controllers", "/admin/discover-dcs"):
            rows = self.controllers()
            return [{**x,"host":x["hostName"],"ip":x["ipv4"]} for x in rows] if path.startswith("/admin") else rows
        if path == "/domain/summary":
            d = self.search(self.base,"(objectClass=*)",["msDS-Behavior-Version","fSMORoleOwner"],BASE)[0]
            c = self.search(self.config_base,"(objectClass=*)",["msDS-Behavior-Version"],BASE)[0]
            levels = {0:"Windows2000",1:"Windows2003Mixed",2:"Windows2003",3:"Windows2008",4:"Windows2008R2",5:"Windows2012",6:"Windows2012R2",7:"Windows2016",10:"Windows2025"}
            result = {"domain":self.cfg["domain"],"forest":".".join(p[1] for p in parse_dn(scalar(self.root,"rootDomainNamingContext",self.base)) if p[0].lower()=="dc"),"domainMode":levels.get(number(d,"msDS-Behavior-Version"),"Unknown"),"forestMode":levels.get(number(c,"msDS-Behavior-Version"),"Unknown"),"pdc":self.owner(scalar(d,"fSMORoleOwner")),"recycleBin":None}
            for key,base in [("rid","CN=RID Manager$,CN=System,"+self.base),("infrastructure","CN=Infrastructure,"+self.base),("schema",self.schema_base),("naming","CN=Partitions,"+self.config_base)]:
                rows = self.search(base,"(objectClass=*)",["fSMORoleOwner"],BASE)
                result[key] = self.owner(scalar(rows[0],"fSMORoleOwner")) if rows else None
            return result
        if path in ("/domain/sites","/domain/subnets"):
            subnets = self.search("CN=Subnets,CN=Sites,"+self.config_base,"(objectClass=subnet)",["name","siteObject"])
            subnet_rows = [{"name":scalar(x,"name"),"site":parse_dn(scalar(x,"siteObject"))[0][1] if scalar(x,"siteObject") else ""} for x in subnets]
            if path.endswith("subnets"):
                return subnet_rows
            return [{"name":scalar(x,"name"),"subnets":sum(y["site"]==scalar(x,"name") for y in subnet_rows)} for x in self.search("CN=Sites,"+self.config_base,"(objectClass=site)",["name"])]
        if path == "/domain/trusts":
            return [{"name":scalar(x,"trustPartner"),"direction":{1:"Inbound",2:"Outbound",3:"Bidirectional"}.get(number(x,"trustDirection"),"Disabled"),"type":{1:"Windows NT",2:"Active Directory",3:"MIT Kerberos"}.get(number(x,"trustType"),"Unknown"),"transitive":not bool(number(x,"trustAttributes") & 1)} for x in self.search(self.base,"(objectClass=trustedDomain)",["trustPartner","trustDirection","trustType","trustAttributes"])]
        if path == "/domain/password-policy":
            x = self.search(self.base,"(objectClass=*)",["minPwdLength","maxPwdAge","minPwdAge","pwdHistoryLength","pwdProperties","lockoutThreshold","lockoutDuration"],BASE)[0]
            return {"minPasswordLength":number(x,"minPwdLength"),"maxPasswordAgeDays":abs(number(x,"maxPwdAge"))/864000000000,"minPasswordAgeDays":abs(number(x,"minPwdAge"))/864000000000,"passwordHistoryCount":number(x,"pwdHistoryLength"),"complexityEnabled":bool(number(x,"pwdProperties") & 1),"lockoutThreshold":number(x,"lockoutThreshold"),"lockoutDurationMinutes":abs(number(x,"lockoutDuration"))/600000000}
        if path == "/domain/password-policies":
            attrs=["name","msDS-PasswordSettingsPrecedence","msDS-MinimumPasswordLength","msDS-MaximumPasswordAge","msDS-LockoutThreshold"]
            return [{"name":scalar(x,"name"),"precedence":number(x,attrs[1]),"minPasswordLength":number(x,attrs[2]),"maxPasswordAgeDays":abs(number(x,attrs[3]))/864000000000,"lockoutThreshold":number(x,attrs[4])} for x in self.search(self.base,"(objectClass=msDS-PasswordSettings)",attrs)]
        if path == "/ad/users" and method == "GET":
            q = escape_filter_chars(params.get("q", ""))
            f = "(&(objectCategory=person)(objectClass=user)" + (f"(|(sAMAccountName={q}*)(displayName={q}*)(mail={q}*))" if q else "") + ")"
            if params.get("page_size"):
                return self.user_page(f,params.get("q", ""),int(params["page_size"]),params.get("cursor"))
            return [self.user(x) for x in self.search(self.base,f,self.user_attributes())]
        if path == "/ad/groups" and method == "GET":
            return [self.group(x) for x in self.search(self.base,"(objectClass=group)",GROUP_ATTRS)]
        if path == "/ad/computers" and method == "GET":
            q = escape_filter_chars(params.get("q", ""))
            f = "(&(objectClass=computer)" + (f"(|(name=*{q}*)(dNSHostName=*{q}*))" if q else "") + ")"
            return [{"name":scalar(x,"name"),"dn":x["dn"],"os":scalar(x,"operatingSystem"),"enabled":not bool(number(x,"userAccountControl") & 2),"lastLogon":date(scalar(x,"lastLogonTimestamp")),"ipv4":"","ou":parent(x["dn"])} for x in self.search(self.base,f,COMPUTER_ATTRS)]
        if path == "/ad/ous" and method == "GET":
            return [{"name":scalar(x,"name"),"dn":x["dn"],"protected":None} for x in self.search(self.base,"(objectClass=organizationalUnit)",["name"])]
        if path == "/gpo" and method == "GET":
            return [{"displayName":scalar(x,"displayName"),"id":str(scalar(x,"name")).strip("{}"),"status":{0:"AllSettingsEnabled",1:"UserSettingsDisabled",2:"ComputerSettingsDisabled",3:"AllSettingsDisabled"}.get(number(x,"flags"),"Unknown"),"owner":None,"modified":date(scalar(x,"whenChanged"))} for x in self.search(self.base,"(objectClass=groupPolicyContainer)",["displayName","name","flags","whenChanged"])]
        parts = [unquote(x) for x in path.strip("/").split("/")]
        if len(parts) >= 3 and parts[0] == "ad" and parts[1] in ("users","computers","groups"):
            kind = {"users":"user","computers":"computer","groups":"group"}[parts[1]]
            obj = self.find(parts[2],kind, self.user_attributes() if kind == "user" else GROUP_ATTRS if kind == "group" else COMPUTER_ATTRS)
            dn = obj["dn"]
            action = parts[3] if len(parts) >= 4 else ""
            if kind == "user" and method == "GET" and not action:
                return self.user(obj)
            if method == "GET" and action == "groups" and kind == "user":
                return [self.group(x) for x in self.search(self.base,f"(&(objectClass=group)(member={escape_filter_chars(dn)}))",GROUP_ATTRS)]
            if kind == "group" and action == "members":
                if method == "GET":
                    return [{"name":scalar(x,"name"),"samAccountName":scalar(x,"sAMAccountName"),"objectClass":values(x,"objectClass")[-1],"dn":x["dn"]} for x in self.search(self.base,f"(memberOf={escape_filter_chars(dn)})",["name","sAMAccountName","objectClass"])]
                member = payload.get("member") if method == "POST" else parts[4] if len(parts)>4 else ""
                entry = self.find(member,"top",["name"])
                return self.checked(self.conn.modify(dn,{"member":[(MODIFY_ADD if method == "POST" else MODIFY_DELETE,[entry["dn"]])]}))
            if method == "DELETE" and not action:
                return self.checked(self.conn.delete(dn))
            if method == "PATCH" and kind == "user" and not action:
                keys = {"display_name":"displayName","email":"mail","department":"department","title":"title","company":"company","manager":"manager","mobile":"mobile"}
                changes = {}
                for k,v in payload.items():
                    if k in keys:
                        if k == "manager" and v:
                            v = self.find(v,"user",["name"])["dn"]
                        changes[keys[k]] = [(MODIFY_REPLACE,[v] if v else [])]
                return self.checked(self.conn.modify(dn,changes)) if changes else {"ok":True}
            if method == "POST" and action in ("enable","disable") and kind in ("user","computer"):
                flags = number(obj,"userAccountControl")
                flags = flags | 2 if action == "disable" else flags & ~2
                return self.checked(self.conn.modify(dn,{"userAccountControl":[(MODIFY_REPLACE,[flags])]}))
            if method == "POST" and action == "unlock" and kind == "user":
                return self.checked(self.conn.modify(dn,{"lockoutTime":[(MODIFY_REPLACE,[0])]}))
            if method == "POST" and action == "reset-password" and kind == "user":
                self.checked(self.conn.extend.microsoft.modify_password(dn,payload["new_password"]))
                try:
                    return self.checked(self.conn.modify(dn,{"pwdLastSet":[(MODIFY_REPLACE,[0 if payload.get("must_change",True) else -1])]}))
                except HTTPException as exc:
                    raise HTTPException(exc.status_code,"Password changed, but setting change-at-next-logon failed. Refresh the user before retrying.") from exc
            if method == "POST" and action == "move":
                target = payload["target_ou"]
                self.validate_parent(target)
                p = parse_dn(dn)[0]
                return self.checked(self.conn.modify_dn(dn,p[0]+"="+p[1],new_superior=target))
        if method == "POST" and path == "/ad/groups":
            target = payload["path"] or self.base
            self.validate_parent(target)
            flags = {"Global":2,"DomainLocal":4,"Universal":8}[payload["scope"]]
            if payload["category"] == "Security":
                flags -= 2147483648
            attrs={"sAMAccountName":payload["name"],"groupType":flags}
            if payload.get("description"):
                attrs["description"]=payload["description"]
            return self.checked(self.conn.add("CN="+escape_rdn(payload["name"])+","+target,["top","group"],attrs))
        if path == "/ad/ous" and method == "POST":
            if payload.get("protected",True):
                unavailable("Creating an OU with accidental-deletion protection")
            self.validate_parent(payload["path"])
            return self.checked(self.conn.add("OU="+escape_rdn(payload["name"])+","+payload["path"],["top","organizationalUnit"]))
        if path == "/ad/ous/delete" and method == "POST":
            if payload.get("recursive"):
                unavailable("Recursive OU deletion")
            obj=self.find(payload["dn"],"organizationalUnit",["name"])
            return self.checked(self.conn.delete(obj["dn"]))
        unavailable(path)

    def validate_parent(self, dn):
        try:
            parse_dn(dn)
        except Exception as exc:
            raise HTTPException(422,"Invalid target distinguished name") from exc
        if dn.lower() != self.base.lower() and not dn.lower().endswith(","+self.base.lower()):
            raise HTTPException(422,"Target must be inside the configured domain")
        if not self.search(dn,"(objectClass=*)",["objectClass"],BASE):
            raise HTTPException(404,"Target container not found")

def request(method, path, payload=None, params=None, cfg=None):
    # Unsupported requests must not cause binds or appear as successful operations.
    if path.startswith(("/dns/","/dhcp/","/ad/deleted")) or path == "/domain/replication" or (path.startswith("/gpo") and path != "/gpo") or (path == "/gpo" and method != "GET"):
        unavailable(path)
    if method == "POST" and path == "/ad/users":
        unavailable("User creation")
    try:
        with Directory(cfg) as directory:
            return directory.request(method,path,payload,params)
    except HTTPException:
        raise
    except (LDAPException, OSError, ValueError, KeyError) as exc:
        raise HTTPException(502,"Direct AD operation failed. Check network connectivity and the directory schema; refresh before retrying a write.") from exc
