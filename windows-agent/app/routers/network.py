from fastapi import APIRouter, Query
from ..common import list_result
from ..models import DnsDeleteBody, DnsRecordBody, ReservationBody, ReservationDelete, ScopeCreate, ScopeDelete, ScopeState, ZoneCreate, ZoneDelete
from ..runner import run_ps

router = APIRouter(tags=["network"])

@router.get("/dns/zones")
def dns_zones():
    return list_result(run_ps(r"""Import-Module DnsServer
Get-DnsServerZone | Select-Object @{n='name';e={$_.ZoneName}},@{n='type';e={[string]$_.ZoneType}},@{n='integrated';e={$_.IsDsIntegrated}},@{n='reverse';e={$_.IsReverseLookupZone}} | ConvertTo-Json -Depth 3 -Compress
"""))

@router.post("/dns/zones")
def create_dns_zone(body: ZoneCreate):
    return run_ps(r"""Import-Module DnsServer
Add-DnsServerPrimaryZone -Name $env:RSAT_NAME -ReplicationScope $env:RSAT_REPLICATION_SCOPE -DynamicUpdate $env:RSAT_DYNAMIC_UPDATE
@{ok=$true}|ConvertTo-Json -Compress
""",body.model_dump())

@router.post("/dns/zones/delete")
def delete_dns_zone(body: ZoneDelete):
    return run_ps("Import-Module DnsServer; Remove-DnsServerZone -Name $env:RSAT_NAME -Force; @{ok=$true}|ConvertTo-Json -Compress",body.model_dump())

@router.get("/dns/records")
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

@router.post("/dns/records")
def create_dns(body: DnsRecordBody):
    values=body.model_dump()
    if body.type=="A":
        script="Import-Module DnsServer; Add-DnsServerResourceRecordA -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -IPv4Address $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    elif body.type=="AAAA":
        script="Import-Module DnsServer; Add-DnsServerResourceRecordAAAA -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -IPv6Address $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    elif body.type=="CNAME":
        script="Import-Module DnsServer; Add-DnsServerResourceRecordCName -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -HostNameAlias $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    else:
        script="Import-Module DnsServer; Add-DnsServerResourceRecordPtr -ZoneName $env:RSAT_ZONE -Name $env:RSAT_NAME -PtrDomainName $env:RSAT_VALUE -TimeToLive ([TimeSpan]::FromSeconds([int]$env:RSAT_TTL)); @{ok=$true}|ConvertTo-Json -Compress"
    return run_ps(script,values)

@router.post("/dns/records/delete")
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

@router.get("/dhcp/scopes")
def dhcp_scopes():
    return list_result(run_ps(r"""Import-Module DhcpServer
Get-DhcpServerv4Scope | ForEach-Object {
  $s=$_
  $st=Get-DhcpServerv4ScopeStatistics -ScopeId $s.ScopeId
  [pscustomobject]@{scopeId=$s.ScopeId.IPAddressToString;name=$s.Name;state=[string]$s.State;startRange=$s.StartRange.IPAddressToString;endRange=$s.EndRange.IPAddressToString;free=$st.Free;inUse=$st.InUse}
} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.post("/dhcp/scopes")
def create_dhcp_scope(body: ScopeCreate):
    return run_ps(r"""Import-Module DhcpServer
Add-DhcpServerv4Scope -Name $env:RSAT_NAME -StartRange $env:RSAT_START_RANGE -EndRange $env:RSAT_END_RANGE -SubnetMask $env:RSAT_SUBNET_MASK -LeaseDuration ([TimeSpan]::FromDays([int]$env:RSAT_LEASE_DAYS)) -State $env:RSAT_STATE -Description $env:RSAT_DESCRIPTION
@{ok=$true}|ConvertTo-Json -Compress
""",body.model_dump())

@router.post("/dhcp/scopes/delete")
def delete_dhcp_scope(body: ScopeDelete):
    return run_ps("Import-Module DhcpServer; Remove-DhcpServerv4Scope -ScopeId $env:RSAT_SCOPE_ID -Force; @{ok=$true}|ConvertTo-Json -Compress",body.model_dump())

@router.post("/dhcp/scopes/state")
def set_dhcp_scope_state(body: ScopeState):
    return run_ps("Import-Module DhcpServer; Set-DhcpServerv4Scope -ScopeId $env:RSAT_SCOPE_ID -State $env:RSAT_STATE; @{ok=$true}|ConvertTo-Json -Compress",body.model_dump())

@router.get("/dhcp/leases")
def dhcp_leases(scope_id: str = Query(default="", max_length=64)):
    return list_result(run_ps(r"""Import-Module DhcpServer
$rows=if($env:RSAT_SCOPE_ID){Get-DhcpServerv4Lease -ScopeId $env:RSAT_SCOPE_ID}else{Get-DhcpServerv4Scope | ForEach-Object {Get-DhcpServerv4Lease -ScopeId $_.ScopeId}}
$rows | Select-Object @{n='scopeId';e={$_.ScopeId.IPAddressToString}},@{n='ipAddress';e={$_.IPAddress.IPAddressToString}},@{n='hostName';e={$_.HostName}},@{n='clientId';e={$_.ClientId}},@{n='state';e={[string]$_.AddressState}},@{n='expiry';e={$_.LeaseExpiryTime}} | ConvertTo-Json -Depth 4 -Compress
""",{"scope_id":scope_id}))

@router.get("/dhcp/reservations")
def dhcp_reservations(scope_id: str = Query(default="", max_length=64)):
    return list_result(run_ps(r"""Import-Module DhcpServer
$rows=if($env:RSAT_SCOPE_ID){Get-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID}else{Get-DhcpServerv4Scope | ForEach-Object {Get-DhcpServerv4Reservation -ScopeId $_.ScopeId}}
$rows | Select-Object @{n='scopeId';e={$_.ScopeId.IPAddressToString}},@{n='ipAddress';e={$_.IPAddress.IPAddressToString}},@{n='clientId';e={$_.ClientId}},@{n='name';e={$_.Name}},@{n='description';e={$_.Description}} | ConvertTo-Json -Depth 4 -Compress
""",{"scope_id":scope_id}))

@router.post("/dhcp/reservations")
def dhcp_reservation(body: ReservationBody):
    return run_ps(r"""Import-Module DhcpServer
Add-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -ClientId $env:RSAT_CLIENT_ID -Name $env:RSAT_NAME -Description $env:RSAT_DESCRIPTION
@{ok=$true}|ConvertTo-Json -Compress
""",body.model_dump())

@router.post("/dhcp/reservations/delete")
def dhcp_reservation_delete(body: ReservationDelete):
    return run_ps("Import-Module DhcpServer; Remove-DhcpServerv4Reservation -ScopeId $env:RSAT_SCOPE_ID -IPAddress $env:RSAT_IP_ADDRESS -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress",body.model_dump())
