from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..common import list_result
from ..runner import run_ps

router = APIRouter(prefix="/admin", tags=["administration"])

@router.get("/ping")
def ping():
    identity = run_ps(r"""$who=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$domain=''
try { Import-Module ActiveDirectory; $domain=(Get-ADDomain).DNSRoot } catch {}
[pscustomobject]@{runAs=$who;computer=$env:COMPUTERNAME;domain=$domain} | ConvertTo-Json -Compress
""")
    return {"ok": True, "service": "windows-worker", "authenticated": True, "identity": identity}

class DcTestBody(BaseModel):
    host: str = Field(min_length=1, max_length=255)

@router.get("/discover-dcs")
def discover_dcs():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADDomainController -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='host';e={$_.HostName}},@{n='ip';e={$_.IPv4Address}},@{n='site';e={$_.Site}},@{n='globalCatalog';e={$_.IsGlobalCatalog}},@{n='enabled';e={$_.Enabled}} | Sort-Object site,name | ConvertTo-Json -Depth 4 -Compress
"""))

@router.post("/test-dc")
def test_dc(body: DcTestBody):
    return run_ps(r"""$hostName=$env:RSAT_HOST
function PortOk([int]$port){
  try {
    $c=New-Object System.Net.Sockets.TcpClient
    $a=$c.BeginConnect($hostName,$port,$null,$null)
    $ok=$a.AsyncWaitHandle.WaitOne(2500,$false)
    if($ok){$c.EndConnect($a)}
    $c.Close()
    return [bool]$ok
  } catch { return $false }
}
$dns=$false
try {[System.Net.Dns]::GetHostAddresses($hostName) | Out-Null; $dns=$true}catch{}
$info=$null
try {
  Import-Module ActiveDirectory
  $info=Get-ADDomainController -Identity $hostName -ErrorAction Stop
}catch{}
[pscustomobject]@{
  ok=[bool]$info
  host=$hostName
  dns=$dns
  ldap=(PortOk 389)
  kerberos=(PortOk 88)
  smb=(PortOk 445)
  ldaps=(PortOk 636)
  globalCatalog=(PortOk 3268)
  site=if($info){$info.Site}else{''}
  ipv4=if($info){$info.IPv4Address}else{''}
} | ConvertTo-Json -Depth 4 -Compress
""", {"host": body.host})
