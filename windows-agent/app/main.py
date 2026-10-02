import re
import secrets
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal
from .config import settings
from .runner import run_ps

app = FastAPI(title="RSAT Windows Worker", version="0.2.0")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.@\\,=+() -]{1,512}$")

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
        raise HTTPException(status_code=400, detail="Invalid identity")
    return value

def list_result(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

class PasswordBody(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)
    must_change: bool = True

class UserCreate(BaseModel):
    sam_account_name: str = Field(min_length=1, max_length=64)
    given_name: str
    surname: str
    display_name: str
    email: str = ""
    department: str = ""
    title: str = ""
    company: str = ""
    manager: str = ""
    ou: str
    password: str = Field(min_length=12, max_length=256)
    enabled: bool = True
    must_change: bool = True

class UserPatch(BaseModel):
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    title: str | None = None
    company: str | None = None
    manager: str | None = None
    mobile: str | None = None

class MoveBody(BaseModel):
    target_ou: str

class GroupCreate(BaseModel):
    name: str
    scope: Literal["DomainLocal","Global","Universal"] = "Global"
    category: Literal["Security","Distribution"] = "Security"
    path: str
    description: str = ""

class MemberBody(BaseModel):
    member: str

class OUCreate(BaseModel):
    name: str
    path: str
    protected: bool = True

class OUDelete(BaseModel):
    dn: str
    recursive: bool = False

class DnsRecordBody(BaseModel):
    zone: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(pattern=r"^[A-Za-z0-9_.@-]+$")
    type: Literal["A","AAAA","CNAME","PTR"]
    value: str
    ttl: int = Field(default=3600, ge=60, le=86400)

class DnsDeleteBody(BaseModel):
    zone: str
    name: str
    type: Literal["A","AAAA","CNAME","PTR"]
    value: str = ""

class ReservationBody(BaseModel):
    scope_id: str
    ip_address: str
    client_id: str = Field(pattern=r"^[A-Fa-f0-9:-]{11,40}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=250)

class ReservationDelete(BaseModel):
    scope_id: str
    ip_address: str

class GpoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str = Field(default="", max_length=500)

class GpoLink(BaseModel):
    target: str
    enforced: bool = False
    enabled: bool = True
    order: int | None = None

class GpoStatus(BaseModel):
    status: Literal["AllSettingsEnabled","UserSettingsDisabled","ComputerSettingsDisabled","AllSettingsDisabled"]

class BackupBody(BaseModel):
    path: str = Field(min_length=3, max_length=1024)

@app.get("/health")
def health():
    modules = run_ps(r"""$m=@('ActiveDirectory','DnsServer','DhcpServer','GroupPolicy'); $r=@{}; foreach($x in $m){$r[$x]=[bool](Get-Module -ListAvailable $x)}; $r | ConvertTo-Json -Compress""")
    return {"status":"ok","service":"windows-worker","modules":modules}

@app.get("/domain/summary")
def domain_summary():
    return run_ps(r"""Import-Module ActiveDirectory
$d=Get-ADDomain
$f=Get-ADForest
[pscustomobject]@{
 domain=$d.DNSRoot; forest=$f.Name; domainMode=[string]$d.DomainMode; forestMode=[string]$f.ForestMode
 pdc=$d.PDCEmulator; rid=$d.RIDMaster; infrastructure=$d.InfrastructureMaster
 schema=$f.SchemaMaster; naming=$f.DomainNamingMaster
 recycleBin=[bool](Get-ADOptionalFeature -Filter "Name -eq 'Recycle Bin Feature'" | Where-Object EnabledScopes)
} | ConvertTo-Json -Depth 4 -Compress
""")

@app.get("/domain/controllers")
def domain_controllers():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADDomainController -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='hostName';e={$_.HostName}},@{n='site';e={$_.Site}},@{n='ipv4';e={$_.IPv4Address}},@{n='os';e={$_.OperatingSystem}},@{n='globalCatalog';e={$_.IsGlobalCatalog}},@{n='enabled';e={$_.Enabled}} | ConvertTo-Json -Depth 4 -Compress
"""))

@app.get("/domain/replication")
def replication():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADReplicationPartnerMetadata -Target * -Scope Forest -ErrorAction SilentlyContinue | Select-Object @{n='server';e={$_.Server}},@{n='partner';e={$_.Partner}},@{n='lastSuccess';e={$_.LastReplicationSuccess}},@{n='failures';e={$_.ConsecutiveReplicationFailures}},@{n='status';e={if($_.ConsecutiveReplicationFailures -eq 0){'Healthy'}else{'Error'}}} | ConvertTo-Json -Depth 4 -Compress
"""))

@app.get("/domain/trusts")
def trusts():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADTrust -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='direction';e={[string]$_.Direction}},@{n='type';e={[string]$_.TrustType}},@{n='transitive';e={$_.IsTransitive}} | ConvertTo-Json -Depth 4 -Compress
"""))

@app.get("/domain/sites")
def sites():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADReplicationSite -Filter * | ForEach-Object { $site=$_.Name; $count=(Get-ADReplicationSubnet -Filter * | Where-Object {$_.Site -like "*CN=$site,*"} | Measure-Object).Count; [pscustomobject]@{name=$site;subnets=$count} } | ConvertTo-Json -Depth 4 -Compress
"""))

@app.get("/ad/users")
def users(q: str = Query(default="", max_length=80)):
    q = re.sub(r"[^A-Za-z0-9_.@ -]", "", q)
    return list_result(run_ps(r"""Import-Module ActiveDirectory
$q=$env:RSAT_Q
if ([string]::IsNullOrWhiteSpace($q)) {
  $rows=Get-ADUser -Filter * -ResultSetSize 500 -Properties DisplayName,Mail,Department,Title,Company,Enabled,LockedOut,DistinguishedName,LastLogonDate
} else {
  $f="SamAccountName -like '*$q*' -or DisplayName -like '*$q*' -or Mail -like '*$q*'"
  $rows=Get-ADUser -Filter $f -ResultSetSize 500 -Properties DisplayName,Mail,Department,Title,Company,Enabled,LockedOut,DistinguishedName,LastLogonDate
}
$rows | Select-Object @{n='samAccountName';e={$_.SamAccountName}},@{n='displayName';e={$_.DisplayName}},@{n='mail';e={$_.Mail}},@{n='department';e={$_.Department}},@{n='title';e={$_.Title}},@{n='company';e={$_.Company}},@{n='enabled';e={$_.Enabled}},@{n='lockedOut';e={$_.LockedOut}},@{n='lastLogon';e={$_.LastLogonDate}},@{n='ou';e={$_.DistinguishedName -replace '^CN=[^,]+,',''}} | ConvertTo-Json -Depth 5 -Compress
""", {"q": q}))

@app.post("/ad/users")
def create_user(body: UserCreate):
    script=r"""Import-Module ActiveDirectory
$secure=ConvertTo-SecureString $env:RSAT_PASSWORD -AsPlainText -Force
$p=@{
 Name=$env:RSAT_DISPLAY_NAME; SamAccountName=$env:RSAT_SAM_ACCOUNT_NAME; GivenName=$env:RSAT_GIVEN_NAME
 Surname=$env:RSAT_SURNAME; DisplayName=$env:RSAT_DISPLAY_NAME; Path=$env:RSAT_OU
 AccountPassword=$secure; Enabled=[System.Convert]::ToBoolean($env:RSAT_ENABLED)
}
if($env:RSAT_EMAIL){$p.EmailAddress=$env:RSAT_EMAIL}
if($env:RSAT_DEPARTMENT){$p.Department=$env:RSAT_DEPARTMENT}
if($env:RSAT_TITLE){$p.Title=$env:RSAT_TITLE}
if($env:RSAT_COMPANY){$p.Company=$env:RSAT_COMPANY}
New-ADUser @p
if($env:RSAT_MANAGER){Set-ADUser -Identity $env:RSAT_SAM_ACCOUNT_NAME -Manager $env:RSAT_MANAGER}
Set-ADUser -Identity $env:RSAT_SAM_ACCOUNT_NAME -ChangePasswordAtLogon ([System.Convert]::ToBoolean($env:RSAT_MUST_CHANGE))
Get-ADUser -Identity $env:RSAT_SAM_ACCOUNT_NAME -Properties DisplayName,Mail,Enabled | Select-Object SamAccountName,DisplayName,Mail,Enabled | ConvertTo-Json -Compress
"""
    return run_ps(script, body.model_dump())

@app.get("/ad/users/{user_identity}")
def get_user(user_identity: str):
    return run_ps(r"""Import-Module ActiveDirectory
Get-ADUser -Identity $env:RSAT_ID -Properties * | Select-Object @{n='samAccountName';e={$_.SamAccountName}},@{n='displayName';e={$_.DisplayName}},@{n='givenName';e={$_.GivenName}},@{n='surname';e={$_.Surname}},@{n='mail';e={$_.Mail}},@{n='mobile';e={$_.MobilePhone}},@{n='department';e={$_.Department}},@{n='company';e={$_.Company}},@{n='title';e={$_.Title}},@{n='manager';e={$_.Manager}},@{n='enabled';e={$_.Enabled}},@{n='lockedOut';e={$_.LockedOut}},@{n='passwordExpired';e={$_.PasswordExpired}},@{n='passwordNeverExpires';e={$_.PasswordNeverExpires}},@{n='lastLogon';e={$_.LastLogonDate}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 5 -Compress
""", {"id":identity(user_identity)})

@app.patch("/ad/users/{user_identity}")
def update_user(user_identity: str, body: UserPatch):
    values=body.model_dump(exclude_none=True)
    values["id"]=identity(user_identity)
    return run_ps(r"""Import-Module ActiveDirectory
$id=$env:RSAT_ID
if(Test-Path Env:RSAT_DISPLAY_NAME){ if($env:RSAT_DISPLAY_NAME){Set-ADUser $id -DisplayName $env:RSAT_DISPLAY_NAME}else{Set-ADUser $id -Clear displayName} }
if(Test-Path Env:RSAT_EMAIL){ if($env:RSAT_EMAIL){Set-ADUser $id -EmailAddress $env:RSAT_EMAIL}else{Set-ADUser $id -Clear mail} }
if(Test-Path Env:RSAT_DEPARTMENT){ if($env:RSAT_DEPARTMENT){Set-ADUser $id -Department $env:RSAT_DEPARTMENT}else{Set-ADUser $id -Clear department} }
if(Test-Path Env:RSAT_TITLE){ if($env:RSAT_TITLE){Set-ADUser $id -Title $env:RSAT_TITLE}else{Set-ADUser $id -Clear title} }
if(Test-Path Env:RSAT_COMPANY){ if($env:RSAT_COMPANY){Set-ADUser $id -Company $env:RSAT_COMPANY}else{Set-ADUser $id -Clear company} }
if(Test-Path Env:RSAT_MOBILE){ if($env:RSAT_MOBILE){Set-ADUser $id -MobilePhone $env:RSAT_MOBILE}else{Set-ADUser $id -Clear mobile} }
if(Test-Path Env:RSAT_MANAGER){ if($env:RSAT_MANAGER){Set-ADUser $id -Manager $env:RSAT_MANAGER}else{Set-ADUser $id -Clear manager} }
@{ok=$true}|ConvertTo-Json -Compress
""", values)

@app.delete("/ad/users/{user_identity}")
def delete_user(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADUser -Identity $env:RSAT_ID -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/unlock")
def unlock(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Unlock-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/enable")
def enable_user(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Enable-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/disable")
def disable_user(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Disable-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@app.post("/ad/users/{user_identity}/reset-password")
def reset_password(user_identity: str, body: PasswordBody):
    return run_ps(r"""Import-Module ActiveDirectory
$secure=ConvertTo-SecureString $env:RSAT_PASSWORD -AsPlainText -Force
Set-ADAccountPassword -Identity $env:RSAT_ID -Reset -NewPassword $secure
Set-ADUser -Identity $env:RSAT_ID -ChangePasswordAtLogon ([System.Convert]::ToBoolean($env:RSAT_MUST_CHANGE))
@{ok=$true}|ConvertTo-Json -Compress
""", {"id":identity(user_identity),"password":body.new_password,"must_change":str(body.must_change)})

@app.post("/ad/users/{user_identity}/move")
def move_user(user_identity: str, body: MoveBody):
    return run_ps("Import-Module ActiveDirectory; Get-ADUser -Identity $env:RSAT_ID | Move-ADObject -TargetPath $env:RSAT_TARGET_OU; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity),"target_ou":body.target_ou})

@app.get("/ad/users/{user_identity}/groups")
def user_groups(user_identity: str):
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADPrincipalGroupMembership -Identity $env:RSAT_ID | Select-Object @{n='name';e={$_.Name}},@{n='scope';e={[string]$_.GroupScope}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 4 -Compress
""", {"id":identity(user_identity)}))

@app.get("/ad/groups")
def groups():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADGroup -Filter * -ResultSetSize 1000 -Properties Description,GroupScope,GroupCategory | ForEach-Object {
$count=(Get-ADGroupMember -Identity $_ -ErrorAction SilentlyContinue | Measure-Object).Count
[pscustomobject]@{name=$_.Name;description=$_.Description;scope=[string]$_.GroupScope;category=[string]$_.GroupCategory;members=$count;dn=$_.DistinguishedName}
} | ConvertTo-Json -Depth 4 -Compress
"""))

@app.post("/ad/groups")
def create_group(body: GroupCreate):
    return run_ps(r"""Import-Module ActiveDirectory
New-ADGroup -Name $env:RSAT_NAME -GroupScope $env:RSAT_SCOPE -GroupCategory $env:RSAT_CATEGORY -Path $env:RSAT_PATH -Description $env:RSAT_DESCRIPTION
Get-ADGroup -Identity $env:RSAT_NAME | Select-Object Name,DistinguishedName | ConvertTo-Json -Compress
""", body.model_dump())

@app.delete("/ad/groups/{name}")
def delete_group(name: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADGroup -Identity $env:RSAT_NAME -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@app.get("/ad/groups/{name}/members")
def group_members(name: str):
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADGroupMember -Identity $env:RSAT_NAME | Select-Object @{n='name';e={$_.Name}},@{n='samAccountName';e={$_.SamAccountName}},@{n='objectClass';e={$_.objectClass}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 4 -Compress
""", {"name":identity(name)}))

@app.post("/ad/groups/{name}/members")
def add_group_member(name: str, body: MemberBody):
    return run_ps("Import-Module ActiveDirectory; Add-ADGroupMember -Identity $env:RSAT_NAME -Members $env:RSAT_MEMBER; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name),"member":body.member})

@app.delete("/ad/groups/{name}/members/{member}")
def remove_group_member(name: str, member: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADGroupMember -Identity $env:RSAT_NAME -Members $env:RSAT_MEMBER -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name),"member":identity(member)})

@app.get("/ad/computers")
def computers(q: str = Query(default="", max_length=80)):
    q = re.sub(r"[^A-Za-z0-9_. -]", "", q)
    return list_result(run_ps(r"""Import-Module ActiveDirectory
$q=$env:RSAT_Q
if($q){$rows=Get-ADComputer -Filter "Name -like '*$q*'" -ResultSetSize 1000 -Properties OperatingSystem,Enabled,LastLogonDate,IPv4Address,DistinguishedName}
else{$rows=Get-ADComputer -Filter * -ResultSetSize 1000 -Properties OperatingSystem,Enabled,LastLogonDate,IPv4Address,DistinguishedName}
$rows | Select-Object @{n='name';e={$_.Name}},@{n='os';e={$_.OperatingSystem}},@{n='enabled';e={$_.Enabled}},@{n='lastLogon';e={$_.LastLogonDate}},@{n='ipv4';e={$_.IPv4Address}},@{n='ou';e={$_.DistinguishedName -replace '^CN=[^,]+,',''}} | ConvertTo-Json -Depth 4 -Compress
""",{"q":q}))

@app.post("/ad/computers/{name}/enable")
def computer_enable(name: str):
    return run_ps("Import-Module ActiveDirectory; Enable-ADAccount -Identity $env:RSAT_NAME; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@app.post("/ad/computers/{name}/disable")
def computer_disable(name: str):
    return run_ps("Import-Module ActiveDirectory; Disable-ADAccount -Identity $env:RSAT_NAME; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@app.post("/ad/computers/{name}/reset")
def computer_reset(name: str):
    return run_ps("Import-Module ActiveDirectory; Get-ADComputer -Identity $env:RSAT_NAME | Reset-ComputerMachinePassword; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@app.post("/ad/computers/{name}/move")
def computer_move(name: str, body: MoveBody):
    return run_ps("Import-Module ActiveDirectory; Get-ADComputer -Identity $env:RSAT_NAME | Move-ADObject -TargetPath $env:RSAT_TARGET_OU; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name),"target_ou":body.target_ou})

@app.delete("/ad/computers/{name}")
def computer_delete(name: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADComputer -Identity $env:RSAT_NAME -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@app.get("/ad/ous")
def ous():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADOrganizationalUnit -Filter * -Properties ProtectedFromAccidentalDeletion | Select-Object @{n='name';e={$_.Name}},@{n='dn';e={$_.DistinguishedName}},@{n='protected';e={$_.ProtectedFromAccidentalDeletion}} | Sort-Object dn | ConvertTo-Json -Depth 3 -Compress
"""))

@app.post("/ad/ous")
def create_ou(body: OUCreate):
    return run_ps(r"""Import-Module ActiveDirectory
$o=New-ADOrganizationalUnit -Name $env:RSAT_NAME -Path $env:RSAT_PATH -ProtectedFromAccidentalDeletion ([System.Convert]::ToBoolean($env:RSAT_PROTECTED)) -PassThru
$o | Select-Object Name,DistinguishedName,ProtectedFromAccidentalDeletion | ConvertTo-Json -Compress
""", body.model_dump())

@app.post("/ad/ous/delete")
def delete_ou(body: OUDelete):
    return run_ps(r"""Import-Module ActiveDirectory
$o=Get-ADOrganizationalUnit -Identity $env:RSAT_DN
if($o.ProtectedFromAccidentalDeletion){Set-ADOrganizationalUnit -Identity $o -ProtectedFromAccidentalDeletion $false}
Remove-ADOrganizationalUnit -Identity $o -Recursive:([System.Convert]::ToBoolean($env:RSAT_RECURSIVE)) -Confirm:$false
@{ok=$true}|ConvertTo-Json -Compress
""", body.model_dump())

@app.get("/dns/zones")
def dns_zones():
    return list_result(run_ps(r"""Import-Module DnsServer
Get-DnsServerZone | Select-Object @{n='name';e={$_.ZoneName}},@{n='type';e={[string]$_.ZoneType}},@{n='integrated';e={$_.IsDsIntegrated}},@{n='reverse';e={$_.IsReverseLookupZone}} | ConvertTo-Json -Depth 3 -Compress
"""))

@app.get("/dns/records")
def dns_records(zone: str = Query(default="", max_length=255)):
    return list_result(run_ps(r"""Import-Module DnsServer
$zones=if($env:RSAT_ZONE){@(Get-DnsServerZone -Name $env:RSAT_ZONE)}else{@(Get-DnsServerZone | Where-Object {$_.ZoneType -eq 'Primary'} | Select-Object -First 30)}
$all=@()
foreach($z in $zones){
  $zn=$z.ZoneName
  Get-DnsServerResourceRecord -ZoneName $zn -ErrorAction SilentlyContinue | Where-Object {$_.RecordType -in @('A','AAAA','CNAME','PTR')} | Select-Object -First 1000 | ForEach-Object {
    $value = switch($_.RecordType){'A'{$_.RecordData.IPv4Address.IPAddressToString};'AAAA'{$_.RecordData.IPv6Address.IPAddressToString};'CNAME'{$_.RecordData.HostNameAlias.ToString()};'PTR'{$_.RecordData.PtrDomainName.ToString()}}
    $all += [pscustomobject]@{zone=$zn;name=$_.HostName;type=$_.RecordType;value=$value;ttl=[int]$_.TimeToLive.TotalSeconds}
  }
}
$all | ConvertTo-Json -Depth 5 -Compress
""", {"zone":zone}))

@app.post("/dns/records")
def create_dns(body: DnsRecordBody):
    v=body.model_dump()
    if body.type=="A":
        script="Import-Module DnsServer; Add-DnsServerResourceRecordA -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -IPv4Address $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    elif body.type=="AAAA":
        script="Import-Module DnsServer; Add-DnsServerResourceRecordAAAA -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -IPv6Address $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    elif body.type=="CNAME":
        script="Import-Module DnsServer; Add-DnsServerResourceRecordCName -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -HostNameAlias $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    else:
        script="Import-Module DnsServer; Add-DnsServerResourceRecordPtr -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -PtrDomainName $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    return run_ps(script,v)

@app.post("/dns/records/delete")
def delete_dns(body: DnsDeleteBody):
    return run_ps(r"""Import-Module DnsServer
$r=Get-DnsServerResourceRecord -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -RRType $env:RSAT_TYPE -ErrorAction Stop
if($env:RSAT_VALUE){
  $r=$r | Where-Object {
    $v=switch($_.RecordType){'A'{$_.RecordData.IPv4Address.IPAddressToString};'AAAA'{$_.RecordData.IPv6Address.IPAddressToString};'CNAME'{$_.RecordData.HostNameAlias.ToString()};'PTR'{$_.RecordData.PtrDomainName.ToString()}}
    $v -eq $env:RSAT_VALUE
  }
}
$r | Remove-DnsServerResourceRecord -ZoneName $env:RSAT_ZONE -Force
@{ok=$true;removed=@($r).Count}|ConvertTo-Json -Compress
""", body.model_dump())

@app.get("/dhcp/scopes")
def dhcp_scopes():
    return list_result(run_ps(r"""Import-Module DhcpServer
Get-DhcpServerv4Scope | ForEach-Object { $s=$_; $st=Get-DhcpServerv4ScopeStatistics -ScopeId $s.ScopeId; [pscustomobject]@{scopeId=$s.ScopeId.IPAddressToString;name=$s.Name;state=[string]$s.State;startRange=$s.StartRange.IPAddressToString;endRange=$s.EndRange.IPAddressToString;free=$st.Free;inUse=$st.InUse} } | ConvertTo-Json -Depth 4 -Compress
"""))

@app.get("/dhcp/leases")
def dhcp_leases(scope_id: str = Query(default="", max_length=64)):
    return list_result(run_ps(r"""Import-Module DhcpServer
$rows=if($env:RSAT_SCOPE_ID){Get-DhcpServerv4Lease -ScopeId $env:RSAT_SCOPE_ID}else{Get-DhcpServerv4Scope | ForEach-Object {Get-DhcpServerv4Lease -ScopeId $_.ScopeId}}
$rows | Select-Object @{n='scopeId';e={$_.ScopeId.IPAddressToString}},@{n='ipAddress';e={$_.IPAddress.IPAddressToString}},@{n='hostName';e={$_.HostName}},@{n='clientId';e={$_.ClientId}},@{n='state';e={[string]$_.AddressState}},@{n='expiry';e={$_.LeaseExpiryTime}} | ConvertTo-Json -Depth 4 -Compress
""",{"scope_id":scope_id}))

@app.get("/dhcp/reservations")
def dhcp_reservations(scope_id: str = Query(default="", max_length=64)):
    return list_result(run_ps(r"""Import-Module DhcpServer
$rows=if($env:RSAT_SCOPE_ID){Get-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID}else{Get-DhcpServerv4Scope | ForEach-Object {Get-DhcpServerv4Reservation -ScopeId $_.ScopeId}}
$rows | Select-Object @{n='scopeId';e={$_.ScopeId.IPAddressToString}},@{n='ipAddress';e={$_.IPAddress.IPAddressToString}},@{n='clientId';e={$_.ClientId}},@{n='name';e={$_.Name}},@{n='description';e={$_.Description}} | ConvertTo-Json -Depth 4 -Compress
""",{"scope_id":scope_id}))

@app.post("/dhcp/reservations")
def dhcp_reservation(body: ReservationBody):
    return run_ps(r"""Import-Module DhcpServer
Add-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -ClientId $env:RSAT_CLIENT_ID -Name $env:RSAT_NAME -Description $env:RSAT_DESCRIPTION
@{ok=$true}|ConvertTo-Json -Compress
""",body.model_dump())

@app.post("/dhcp/reservations/delete")
def dhcp_reservation_delete(body: ReservationDelete):
    return run_ps("Import-Module DhcpServer; Remove-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress",body.model_dump())

@app.get("/gpo")
def gpos():
    return list_result(run_ps(r"""Import-Module GroupPolicy
Get-GPO -All | Select-Object @{n='displayName';e={$_.DisplayName}},@{n='id';e={$_.Id.Guid}},@{n='status';e={[string]$_.GpoStatus}},@{n='owner';e={$_.Owner}},@{n='modified';e={$_.ModificationTime}} | ConvertTo-Json -Depth 4 -Compress
"""))

@app.post("/gpo")
def create_gpo(body: GpoCreate):
    return run_ps("Import-Module GroupPolicy; $g=New-GPO -Name $env:RSAT_NAME -Comment $env:RSAT_COMMENT; $g | Select-Object @{n='displayName';e={$_.DisplayName}},@{n='id';e={$_.Id.Guid}} | ConvertTo-Json -Compress",body.model_dump())

@app.delete("/gpo/{gpo_id}")
def delete_gpo(gpo_id: str):
    return run_ps("Import-Module GroupPolicy; Remove-GPO -Guid $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress",{"id":identity(gpo_id)})

@app.get("/gpo/links")
def gpo_links():
    return list_result(run_ps(r"""Import-Module ActiveDirectory; Import-Module GroupPolicy
$d=(Get-ADDomain).DistinguishedName
$targets=@($d)+(Get-ADOrganizationalUnit -Filter * | Select-Object -ExpandProperty DistinguishedName)
$out=@()
foreach($t in $targets){
  try{
    (Get-GPInheritance -Target $t).GpoLinks | ForEach-Object {
      $out += [pscustomobject]@{displayName=$_.DisplayName;target=$t;enabled=$_.Enabled;enforced=$_.Enforced;order=$_.Order}
    }
  }catch{}
}
$out | ConvertTo-Json -Depth 4 -Compress
"""))

@app.post("/gpo/{gpo_id}/link")
def gpo_link(gpo_id: str, body: GpoLink):
    values=body.model_dump(); values["id"]=identity(gpo_id)
    return run_ps(r"""Import-Module GroupPolicy
$p=@{Guid=$env:RSAT_ID;Target=$env:RSAT_TARGET;LinkEnabled=if([System.Convert]::ToBoolean($env:RSAT_ENABLED)){'Yes'}else{'No'};Enforced=if([System.Convert]::ToBoolean($env:RSAT_ENFORCED)){'Yes'}else{'No'}}
if($env:RSAT_ORDER){$p.Order=[int]$env:RSAT_ORDER}
New-GPLink @p | Out-Null
@{ok=$true}|ConvertTo-Json -Compress
""",values)

@app.post("/gpo/{gpo_id}/unlink")
def gpo_unlink(gpo_id: str, body: GpoLink):
    return run_ps("Import-Module GroupPolicy; Remove-GPLink -Guid $env:RSAT_ID -Target $env:RSAT_TARGET -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress",{"id":identity(gpo_id),"target":body.target})

@app.post("/gpo/{gpo_id}/status")
def gpo_status(gpo_id: str, body: GpoStatus):
    return run_ps("Import-Module GroupPolicy; (Get-GPO -Guid $env:RSAT_ID).GpoStatus=$env:RSAT_STATUS; @{ok=$true}|ConvertTo-Json -Compress",{"id":identity(gpo_id),"status":body.status})

@app.post("/gpo/{gpo_id}/backup")
def gpo_backup(gpo_id: str, body: BackupBody):
    return run_ps(r"""Import-Module GroupPolicy
if(-not(Test-Path $env:RSAT_PATH)){New-Item -ItemType Directory -Path $env:RSAT_PATH -Force | Out-Null}
$b=Backup-GPO -Guid $env:RSAT_ID -Path $env:RSAT_PATH
$b | Select-Object BackupId,DisplayName,CreationTime,BackupDirectory | ConvertTo-Json -Compress
""",{"id":identity(gpo_id),"path":body.path})

@app.get("/gpo/{gpo_id}/report")
def gpo_report(gpo_id: str):
    return run_ps(r"""Import-Module GroupPolicy
$g=Get-GPO -Guid $env:RSAT_ID
$xml=Get-GPOReport -Guid $env:RSAT_ID -ReportType Xml
[pscustomobject]@{displayName=$g.DisplayName;id=$g.Id.Guid;status=[string]$g.GpoStatus;owner=$g.Owner;modified=$g.ModificationTime;xml=$xml} | ConvertTo-Json -Depth 5 -Compress
""",{"id":identity(gpo_id)})
