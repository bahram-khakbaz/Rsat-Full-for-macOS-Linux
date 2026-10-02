from fastapi import APIRouter
from ..common import list_result
from ..runner import run_ps

router = APIRouter(prefix="/domain", tags=["domain"])

@router.get("/summary")
def summary():
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

@router.get("/controllers")
def controllers():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADDomainController -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='hostName';e={$_.HostName}},@{n='site';e={$_.Site}},@{n='ipv4';e={$_.IPv4Address}},@{n='os';e={$_.OperatingSystem}},@{n='globalCatalog';e={$_.IsGlobalCatalog}},@{n='enabled';e={$_.Enabled}} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.get("/replication")
def replication():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADReplicationPartnerMetadata -Target * -Scope Forest -ErrorAction SilentlyContinue | Select-Object @{n='server';e={$_.Server}},@{n='partner';e={$_.Partner}},@{n='lastSuccess';e={$_.LastReplicationSuccess}},@{n='failures';e={$_.ConsecutiveReplicationFailures}},@{n='status';e={if($_.ConsecutiveReplicationFailures -eq 0){'Healthy'}else{'Error'}}} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.get("/trusts")
def trusts():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADTrust -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='direction';e={[string]$_.Direction}},@{n='type';e={[string]$_.TrustType}},@{n='transitive';e={$_.IsTransitive}} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.get("/sites")
def sites():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
$subnets=Get-ADReplicationSubnet -Filter *
Get-ADReplicationSite -Filter * | ForEach-Object {
  $site=$_.Name
  $count=@($subnets | Where-Object {$_.Site -and $_.Site -match ("CN=" + [regex]::Escape($site) + ",")}).Count
  [pscustomobject]@{name=$site;subnets=$count}
} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.get("/subnets")
def subnets():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADReplicationSubnet -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='site';e={if($_.Site){($_.Site -split ',')[0] -replace '^CN=',''}else{''}}} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.get("/password-policy")
def password_policy():
    return run_ps(r"""Import-Module ActiveDirectory
$p=Get-ADDefaultDomainPasswordPolicy
[pscustomobject]@{
 minPasswordLength=$p.MinPasswordLength
 maxPasswordAgeDays=[int]$p.MaxPasswordAge.TotalDays
 minPasswordAgeDays=[int]$p.MinPasswordAge.TotalDays
 passwordHistoryCount=$p.PasswordHistoryCount
 complexityEnabled=$p.ComplexityEnabled
 lockoutThreshold=$p.LockoutThreshold
 lockoutDurationMinutes=[int]$p.LockoutDuration.TotalMinutes
} | ConvertTo-Json -Compress
""")

@router.get("/password-policies")
def fine_grained_password_policies():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADFineGrainedPasswordPolicy -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='precedence';e={$_.Precedence}},@{n='minPasswordLength';e={$_.MinPasswordLength}},@{n='maxPasswordAgeDays';e={[int]$_.MaxPasswordAge.TotalDays}},@{n='lockoutThreshold';e={$_.LockoutThreshold}} | ConvertTo-Json -Depth 4 -Compress
"""))
