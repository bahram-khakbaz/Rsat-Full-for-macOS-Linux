import re
import shlex

from fastapi import APIRouter, HTTPException, Query

from ..dns_values import display_value, record_fields
from ..models import (
    DnsDeleteBody,
    DnsRecordBody,
    DnsUpdateBody,
    ReservationBody,
    ReservationDelete,
    ScopeCreate,
    ScopeDelete,
    ScopeState,
    ZoneCreate,
    ZoneDelete,
)
from ..runner import run_ps, run_ps_list

router = APIRouter(tags=["network"])

_ZONE_QUERY = re.compile(r"[A-Za-z0-9_.-]{0,253}")

# One textual form per record type, shared by listing, delete and update.
DNS_VALUE_FUNCTIONS = r"""Import-Module DnsServer
function RsatDnsValue($r){
  $d=$r.RecordData
  switch([string]$r.RecordType){
    'A'{return $d.IPv4Address.IPAddressToString}
    'AAAA'{return $d.IPv6Address.IPAddressToString}
    'CNAME'{return [string]$d.HostNameAlias}
    'PTR'{return [string]$d.PtrDomainName}
    'NS'{return [string]$d.NameServer}
    'MX'{return ('{0} {1}' -f $d.Preference,$d.MailExchange)}
    'SRV'{return ('{0} {1} {2} {3}' -f $d.Priority,$d.Weight,$d.Port,$d.DomainName)}
    'TXT'{return [string]$d.DescriptiveText}
    'SOA'{return ('{0} {1} {2}' -f $d.PrimaryServer,$d.ResponsiblePerson,$d.SerialNumber)}
    default{return ''}
  }
}
function RsatDnsSame($r,[string]$expected){
  $actual=[string](RsatDnsValue $r)
  if([string]$r.RecordType -eq 'TXT'){return $actual -ceq $expected}
  return $actual.TrimEnd('.').ToLowerInvariant() -eq $expected.TrimEnd('.').ToLowerInvariant()
}
"""

_TTL = "-TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL))"
_OWNER = "-ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME"
_DONE = "; @{ok=$true}|ConvertTo-Json -Compress"
DNS_CREATE = {
    "A": f"Add-DnsServerResourceRecordA {_OWNER} -IPv4Address $env:RSAT_VALUE {_TTL}",
    "AAAA": f"Add-DnsServerResourceRecordAAAA {_OWNER} -IPv6Address $env:RSAT_VALUE {_TTL}",
    "CNAME": f"Add-DnsServerResourceRecordCName {_OWNER} -HostNameAlias $env:RSAT_VALUE {_TTL}",
    "PTR": f"Add-DnsServerResourceRecordPtr {_OWNER} -PtrDomainName $env:RSAT_VALUE {_TTL}",
    "NS": f"Add-DnsServerResourceRecord -NS {_OWNER} -NameServer $env:RSAT_VALUE {_TTL}",
    "MX": f"Add-DnsServerResourceRecordMX {_OWNER} -MailExchange $env:RSAT_TARGET "
    f"-Preference ([uint16]$env:RSAT_PREFERENCE) {_TTL}",
    "SRV": f"Add-DnsServerResourceRecord -Srv {_OWNER} -DomainName $env:RSAT_TARGET "
    "-Priority ([uint16]$env:RSAT_PRIORITY) -Weight ([uint16]$env:RSAT_WEIGHT) "
    f"-Port ([uint16]$env:RSAT_PORT) {_TTL}",
    "TXT": f"Add-DnsServerResourceRecord -Txt {_OWNER} -DescriptiveText $env:RSAT_TEXT {_TTL}",
}

# Replace the record data on a copy and let the DNS server swap old for new.
DNS_UPDATE = (
    DNS_VALUE_FUNCTIONS
    + r"""$found=@(Get-DnsServerResourceRecord -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -RRType $env:RSAT_TYPE -ErrorAction Stop | Where-Object { RsatDnsSame $_ $env:RSAT_OLD_MATCH })
if($found.Count -ne 1){throw 'The original DNS record was not found or is ambiguous. Refresh the zone before retrying.'}
$old=$found[0]
$new=$old.Clone()
$new.TimeToLive=[TimeSpan]::FromSeconds([int]$env:RSAT_TTL)
$d=$new.RecordData
switch($env:RSAT_TYPE){
  'A'{$d.IPv4Address=[System.Net.IPAddress]::Parse($env:RSAT_VALUE)}
  'AAAA'{$d.IPv6Address=[System.Net.IPAddress]::Parse($env:RSAT_VALUE)}
  'CNAME'{$d.HostNameAlias=$env:RSAT_VALUE}
  'PTR'{$d.PtrDomainName=$env:RSAT_VALUE}
  'NS'{$d.NameServer=$env:RSAT_VALUE}
  'MX'{$d.MailExchange=$env:RSAT_TARGET;$d.Preference=[uint16]$env:RSAT_PREFERENCE}
  'SRV'{$d.DomainName=$env:RSAT_TARGET;$d.Priority=[uint16]$env:RSAT_PRIORITY;$d.Weight=[uint16]$env:RSAT_WEIGHT;$d.Port=[uint16]$env:RSAT_PORT}
  'TXT'{$d.DescriptiveText=$env:RSAT_TEXT}
  default{throw 'Unsupported DNS record type'}
}
Set-DnsServerResourceRecord -ZoneName $env:RSAT_ZONE -OldInputObject $old -NewInputObject $new
@{ok=$true}|ConvertTo-Json -Compress
"""
)


def _match_value(kind: str, value: str) -> str:
    """The text an existing record is compared with. More lenient than a write."""
    if kind != "TXT":
        return record_fields(kind, value)["value"]
    try:
        segments = shlex.split(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid DNS value or format") from exc
    if len(segments) != 1:
        raise HTTPException(
            status_code=422,
            detail="Worker mode addresses TXT records by one text segment. "
            "Use the direct connector for multi-segment records.",
        )
    return segments[0]


@router.get("/dns/zones")
def dns_zones():
    return run_ps_list(r"""Import-Module DnsServer
Get-DnsServerZone | Select-Object @{n='name';e={$_.ZoneName}},@{n='type';e={[string]$_.ZoneType}},@{n='integrated';e={$_.IsDsIntegrated}},@{n='reverse';e={$_.IsReverseLookupZone}} | ConvertTo-Json -Depth 3 -Compress
""")


@router.post("/dns/zones")
def create_dns_zone(body: ZoneCreate):
    return run_ps(
        r"""Import-Module DnsServer
Add-DnsServerPrimaryZone -Name $env:RSAT_NAME -ReplicationScope $env:RSAT_REPLICATION_SCOPE -DynamicUpdate $env:RSAT_DYNAMIC_UPDATE
@{ok=$true}|ConvertTo-Json -Compress
""",
        body.model_dump(),
    )


@router.post("/dns/zones/delete")
def delete_dns_zone(body: ZoneDelete):
    return run_ps(
        "Import-Module DnsServer; Remove-DnsServerZone -Name $env:RSAT_NAME -Force; @{ok=$true}|ConvertTo-Json -Compress",
        body.model_dump(),
    )


@router.get("/dns/records")
def dns_records(zone: str = Query(default="", max_length=253)):
    if not _ZONE_QUERY.fullmatch(zone):
        raise HTTPException(status_code=422, detail="Invalid DNS zone name")
    # Every record of the selected zone, or of every primary zone. A read error or
    # an oversized result fails the request; nothing is silently dropped.
    rows = run_ps_list(
        DNS_VALUE_FUNCTIONS
        + r"""$zones=if($env:RSAT_ZONE){@(Get-DnsServerZone -Name $env:RSAT_ZONE -ErrorAction Stop)}else{@(Get-DnsServerZone -ErrorAction Stop | Where-Object {$_.ZoneType -eq 'Primary' -and -not $_.IsAutoCreated -and $_.ZoneName -ne 'TrustAnchors'})}
$all=New-Object System.Collections.Generic.List[object]
foreach($z in $zones){
  $zn=$z.ZoneName
  foreach($r in @(Get-DnsServerResourceRecord -ZoneName $zn -ErrorAction Stop)){
    $all.Add([pscustomobject]@{zone=$zn;name=$r.HostName;type=[string]$r.RecordType;value=[string](RsatDnsValue $r);ttl=[int]$r.TimeToLive.TotalSeconds})
  }
}
$all | ConvertTo-Json -Depth 4 -Compress
""",
        {"zone": zone},
    )
    for row in rows:
        row["value"] = display_value(row.get("type", ""), row.get("value"))
    return rows


@router.post("/dns/records")
def create_dns(body: DnsRecordBody):
    script = DNS_CREATE.get(body.type)
    if script is None:
        raise HTTPException(status_code=422, detail="Unsupported DNS record type")
    values = {"zone": body.zone, "name": body.name, "ttl": body.ttl}
    values.update(record_fields(body.type, body.value))
    return run_ps("Import-Module DnsServer; " + script + _DONE, values)


@router.post("/dns/records/update")
def update_dns(body: DnsUpdateBody):
    values = {"zone": body.zone, "name": body.name, "type": body.type, "ttl": body.ttl}
    values.update(record_fields(body.type, body.value))
    values["old_match"] = _match_value(body.type, body.old_value)
    return run_ps(DNS_UPDATE, values)


@router.post("/dns/records/delete")
def delete_dns(body: DnsDeleteBody):
    values = {"zone": body.zone, "name": body.name, "type": body.type}
    if body.value.strip():
        values["match"] = _match_value(body.type, body.value)
    return run_ps(
        DNS_VALUE_FUNCTIONS
        + r"""$r=@(Get-DnsServerResourceRecord -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -RRType $env:RSAT_TYPE -ErrorAction Stop)
if(Test-Path Env:RSAT_MATCH){$r=@($r | Where-Object { RsatDnsSame $_ $env:RSAT_MATCH })}
if($r.Count -eq 0){throw 'No matching DNS record was found. Refresh the zone before retrying.'}
$r | Remove-DnsServerResourceRecord -ZoneName $env:RSAT_ZONE -Force
@{ok=$true;removed=$r.Count}|ConvertTo-Json -Compress
""",
        values,
    )


@router.get("/dhcp/scopes")
def dhcp_scopes():
    return run_ps_list(r"""Import-Module DhcpServer
Get-DhcpServerv4Scope | ForEach-Object {
  $s=$_
  $st=Get-DhcpServerv4ScopeStatistics -ScopeId $s.ScopeId
  [pscustomobject]@{scopeId=$s.ScopeId.IPAddressToString;name=$s.Name;state=[string]$s.State;startRange=$s.StartRange.IPAddressToString;endRange=$s.EndRange.IPAddressToString;free=$st.Free;inUse=$st.InUse}
} | ConvertTo-Json -Depth 4 -Compress
""")


@router.post("/dhcp/scopes")
def create_dhcp_scope(body: ScopeCreate):
    return run_ps(
        r"""Import-Module DhcpServer
Add-DhcpServerv4Scope -Name $env:RSAT_NAME -StartRange $env:RSAT_START_RANGE -EndRange $env:RSAT_END_RANGE -SubnetMask $env:RSAT_SUBNET_MASK -LeaseDuration ([TimeSpan]::FromDays([int]$env:RSAT_LEASE_DAYS)) -State $env:RSAT_STATE -Description $env:RSAT_DESCRIPTION
@{ok=$true}|ConvertTo-Json -Compress
""",
        body.model_dump(),
    )


@router.post("/dhcp/scopes/delete")
def delete_dhcp_scope(body: ScopeDelete):
    return run_ps(
        "Import-Module DhcpServer; Remove-DhcpServerv4Scope -ScopeId $env:RSAT_SCOPE_ID -Force; @{ok=$true}|ConvertTo-Json -Compress",
        body.model_dump(),
    )


@router.post("/dhcp/scopes/state")
def set_dhcp_scope_state(body: ScopeState):
    return run_ps(
        "Import-Module DhcpServer; Set-DhcpServerv4Scope -ScopeId $env:RSAT_SCOPE_ID -State $env:RSAT_STATE; @{ok=$true}|ConvertTo-Json -Compress",
        body.model_dump(),
    )


@router.get("/dhcp/leases")
def dhcp_leases(scope_id: str = Query(default="", max_length=64)):
    return run_ps_list(
        r"""Import-Module DhcpServer
$rows=if($env:RSAT_SCOPE_ID){Get-DhcpServerv4Lease -ScopeId $env:RSAT_SCOPE_ID}else{Get-DhcpServerv4Scope | ForEach-Object {Get-DhcpServerv4Lease -ScopeId $_.ScopeId}}
$rows | Select-Object @{n='scopeId';e={$_.ScopeId.IPAddressToString}},@{n='ipAddress';e={$_.IPAddress.IPAddressToString}},@{n='hostName';e={$_.HostName}},@{n='clientId';e={$_.ClientId}},@{n='state';e={[string]$_.AddressState}},@{n='expiry';e={$_.LeaseExpiryTime}} | ConvertTo-Json -Depth 4 -Compress
""",
        {"scope_id": scope_id},
    )


@router.get("/dhcp/reservations")
def dhcp_reservations(scope_id: str = Query(default="", max_length=64)):
    return run_ps_list(
        r"""Import-Module DhcpServer
$rows=if($env:RSAT_SCOPE_ID){Get-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID}else{Get-DhcpServerv4Scope | ForEach-Object {Get-DhcpServerv4Reservation -ScopeId $_.ScopeId}}
$rows | Select-Object @{n='scopeId';e={$_.ScopeId.IPAddressToString}},@{n='ipAddress';e={$_.IPAddress.IPAddressToString}},@{n='clientId';e={$_.ClientId}},@{n='name';e={$_.Name}},@{n='description';e={$_.Description}} | ConvertTo-Json -Depth 4 -Compress
""",
        {"scope_id": scope_id},
    )


@router.post("/dhcp/reservations")
def dhcp_reservation(body: ReservationBody):
    return run_ps(
        r"""Import-Module DhcpServer
Add-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -ClientId $env:RSAT_CLIENT_ID -Name $env:RSAT_NAME -Description $env:RSAT_DESCRIPTION
@{ok=$true}|ConvertTo-Json -Compress
""",
        body.model_dump(),
    )


@router.post("/dhcp/reservations/delete")
def dhcp_reservation_delete(body: ReservationDelete):
    return run_ps(
        "Import-Module DhcpServer; Remove-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress",
        body.model_dump(),
    )
