import re, secrets
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .config import settings
from .runner import run_ps

app = FastAPI(title="RSAT Windows Worker", version="0.1.0")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.@\\ -]{1,160}$")

@app.middleware("http")
async def token_gate(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    supplied = request.headers.get("authorization", "")
    if not secrets.compare_digest(supplied, f"Bearer {settings.agent_token}"):
        return JSONResponse(status_code=401, content={"detail":"Invalid worker token"})
    return await call_next(request)

def identity(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError("Invalid identity")
    return value

class PasswordBody(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)
    must_change: bool = True

class DnsRecordBody(BaseModel):
    zone: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(pattern=r"^[A-Za-z0-9_.@-]+$")
    type: str = Field(pattern=r"^(A|AAAA|CNAME)$")
    value: str
    ttl: int = Field(default=3600, ge=60, le=86400)

class ReservationBody(BaseModel):
    scope_id: str
    ip_address: str
    client_id: str = Field(pattern=r"^[A-Fa-f0-9:-]{11,40}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=250)

class GpoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str = Field(default="", max_length=500)

@app.get("/health")
def health():
    return {"status":"ok","service":"windows-worker"}

@app.get("/ad/users")
def users(q: str = Query(default="", max_length=80)):
    q = re.sub(r"[^A-Za-z0-9_.@ -]", "", q)
    script = r"""
Import-Module ActiveDirectory
$q=$env:RSAT_Q
if ([string]::IsNullOrWhiteSpace($q)) {
  $rows=Get-ADUser -Filter * -ResultSetSize 250 -Properties DisplayName,Mail,Department,Title,Enabled,LockedOut,DistinguishedName
} else {
  $pattern="*$q*"
  $rows=Get-ADUser -Filter {SamAccountName -like $pattern -or DisplayName -like $pattern -or Mail -like $pattern} -ResultSetSize 250 -Properties DisplayName,Mail,Department,Title,Enabled,LockedOut,DistinguishedName
}
$rows | Select-Object @{n='samAccountName';e={$_.SamAccountName}},@{n='displayName';e={$_.DisplayName}},@{n='mail';e={$_.Mail}},@{n='department';e={$_.Department}},@{n='title';e={$_.Title}},@{n='enabled';e={$_.Enabled}},@{n='lockedOut';e={$_.LockedOut}},@{n='ou';e={$_.DistinguishedName -replace '^CN=[^,]+,',''}} | ConvertTo-Json -Depth 5 -Compress
"""
    result = run_ps(script, {"q": q})
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.get("/ad/users/{user_identity}")
def get_user(user_identity: str):
    user_identity = identity(user_identity)
    return run_ps(r"""Import-Module ActiveDirectory
Get-ADUser -Identity $env:RSAT_ID -Properties * | Select-Object SamAccountName,DisplayName,GivenName,Surname,Mail,MobilePhone,Department,Company,Title,Enabled,LockedOut,PasswordExpired,PasswordNeverExpires,LastLogonDate,DistinguishedName | ConvertTo-Json -Depth 5 -Compress
""", {"id":user_identity})

@app.post("/ad/users/{user_identity}/unlock")
def unlock(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Unlock-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/enable")
def enable(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Enable-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/disable")
def disable(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Disable-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/reset-password")
def reset_password(user_identity: str, body: PasswordBody):
    script=r"""Import-Module ActiveDirectory
$secure=ConvertTo-SecureString $env:RSAT_PASSWORD -AsPlainText -Force
Set-ADAccountPassword -Identity $env:RSAT_ID -Reset -NewPassword $secure
Set-ADUser -Identity $env:RSAT_ID -ChangePasswordAtLogon ([System.Convert]::ToBoolean($env:RSAT_MUST_CHANGE))
@{ok=$true}|ConvertTo-Json -Compress
"""
    return run_ps(script,{"id":identity(user_identity),"password":body.new_password,"must_change":str(body.must_change)})

@app.get("/ad/groups")
def groups():
    result=run_ps(r"""Import-Module ActiveDirectory
Get-ADGroup -Filter * -ResultSetSize 500 -Properties Description,GroupScope | ForEach-Object { $count=(Get-ADGroupMember -Identity $_ -Recursive:$false -ErrorAction SilentlyContinue | Measure-Object).Count; [pscustomobject]@{name=$_.Name;description=$_.Description;scope=[string]$_.GroupScope;members=$count} } | ConvertTo-Json -Depth 4 -Compress
""")
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.get("/ad/computers")
def computers():
    result=run_ps(r"""Import-Module ActiveDirectory
Get-ADComputer -Filter * -ResultSetSize 500 -Properties OperatingSystem,Enabled,LastLogonDate,DistinguishedName | Select-Object @{n='name';e={$_.Name}},@{n='os';e={$_.OperatingSystem}},@{n='enabled';e={$_.Enabled}},@{n='lastLogon';e={$_.LastLogonDate}},@{n='ou';e={$_.DistinguishedName -replace '^CN=[^,]+,',''}} | ConvertTo-Json -Depth 4 -Compress
""")
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.get("/ad/ous")
def ous():
    result=run_ps("Import-Module ActiveDirectory; Get-ADOrganizationalUnit -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 3 -Compress")
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.get("/dns/records")
def dns_records():
    result=run_ps(r"""Import-Module DnsServer
$all=@()
Get-DnsServerZone | Where-Object {$_.IsDsIntegrated -or $_.ZoneType -eq 'Primary'} | Select-Object -First 25 | ForEach-Object {
  $z=$_.ZoneName
  Get-DnsServerResourceRecord -ZoneName $z -ErrorAction SilentlyContinue | Where-Object {$_.RecordType -in @('A','AAAA','CNAME')} | Select-Object -First 250 | ForEach-Object {
    $value = if ($_.RecordType -eq 'A') {$_.RecordData.IPv4Address.IPAddressToString} elseif ($_.RecordType -eq 'AAAA') {$_.RecordData.IPv6Address.IPAddressToString} else {$_.RecordData.HostNameAlias.ToString()}
    $all += [pscustomobject]@{zone=$z;name=$_.HostName;type=$_.RecordType;value=$value;ttl=[int]$_.TimeToLive.TotalSeconds}
  }
}
$all | Select-Object -First 1000 | ConvertTo-Json -Depth 5 -Compress
""")
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.post("/dns/records")
def create_dns(body: DnsRecordBody):
    vars={"zone":body.zone,"name":body.name,"value":body.value,"ttl":str(body.ttl)}
    if body.type=="A": script="Import-Module DnsServer; Add-DnsServerResourceRecordA -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -IPv4Address $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    elif body.type=="AAAA": script="Import-Module DnsServer; Add-DnsServerResourceRecordAAAA -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -IPv6Address $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    else: script="Import-Module DnsServer; Add-DnsServerResourceRecordCName -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -HostNameAlias $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    return run_ps(script,vars)

@app.get("/dhcp/scopes")
def dhcp_scopes():
    result=run_ps(r"""Import-Module DhcpServer
Get-DhcpServerv4Scope | ForEach-Object { $s=$_; $st=Get-DhcpServerv4ScopeStatistics -ScopeId $s.ScopeId; [pscustomobject]@{scopeId=$s.ScopeId.IPAddressToString;name=$s.Name;startRange=$s.StartRange.IPAddressToString;endRange=$s.EndRange.IPAddressToString;free=$st.Free;inUse=$st.InUse} } | ConvertTo-Json -Depth 4 -Compress
""")
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.post("/dhcp/reservations")
def dhcp_reservation(body: ReservationBody):
    return run_ps(r"""Import-Module DhcpServer
Add-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -ClientId $env:RSAT_CLIENT_ID -Name $env:RSAT_NAME -Description $env:RSAT_DESCRIPTION
@{ok=$true}|ConvertTo-Json -Compress
""",body.model_dump())

@app.get("/gpo")
def gpos():
    result=run_ps("Import-Module GroupPolicy; Get-GPO -All | Select-Object @{n='displayName';e={$_.DisplayName}},@{n='id';e={$_.Id.Guid}},@{n='status';e={[string]$_.GpoStatus}},@{n='modified';e={$_.ModificationTime}} | ConvertTo-Json -Depth 4 -Compress")
    return result if isinstance(result,list) else ([] if result is None else [result])

@app.post("/gpo")
def create_gpo(body: GpoCreate):
    return run_ps("Import-Module GroupPolicy; $g=New-GPO -Name $env:RSAT_NAME -Comment $env:RSAT_COMMENT; $g | Select-Object @{n='displayName';e={$_.DisplayName}},@{n='id';e={$_.Id.Guid}} | ConvertTo-Json -Compress",body.model_dump())
