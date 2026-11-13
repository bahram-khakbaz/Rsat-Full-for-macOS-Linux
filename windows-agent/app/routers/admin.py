from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..common import IDENTITY_SCRIPT
from ..config import settings
from ..runner import run_ps, run_ps_list

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/ping")
def ping():
    return {
        "ok": True,
        "service": "windows-worker",
        "authenticated": True,
        "identity": run_ps(IDENTITY_SCRIPT),
        "gpo_backup_root": settings.effective_gpo_backup_root,
    }


class DcTestBody(BaseModel):
    host: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


@router.get("/discover-dcs")
def discover_dcs():
    return run_ps_list(r"""Import-Module ActiveDirectory
Get-ADDomainController -Filter * | Select-Object @{n='name';e={$_.Name}},@{n='host';e={$_.HostName}},@{n='ip';e={$_.IPv4Address}},@{n='site';e={$_.Site}},@{n='globalCatalog';e={$_.IsGlobalCatalog}},@{n='enabled';e={$_.Enabled}} | Sort-Object site,name | ConvertTo-Json -Depth 4 -Compress
""")


@router.post("/test-dc")
def test_dc(body: DcTestBody):
    return run_ps(
        r"""$hostName=$env:RSAT_HOST
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
""",
        {"host": body.host},
    )
