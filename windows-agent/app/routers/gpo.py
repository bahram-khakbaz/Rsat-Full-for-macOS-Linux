import ntpath
import os

from fastapi import APIRouter, HTTPException

from ..common import identity
from ..config import settings
from ..models import BackupBody, GpoCreate, GpoLink, GpoPermission, GpoStatus
from ..runner import run_ps, run_ps_list

router = APIRouter(prefix="/gpo", tags=["group-policy"])
# Junctions and symbolic links can only be resolved on the Windows host itself.
FOLLOW_LINKS = os.name == "nt"


def backup_directory(requested: str) -> str:
    """Resolve a backup destination, which must lie inside the configured root.

    Windows path rules are applied explicitly so the check behaves the same on
    every platform the tests run on. UNC, device and relative paths are refused.
    """
    root = ntpath.normpath(settings.effective_gpo_backup_root)
    path = requested.strip()
    drive, tail = ntpath.splitdrive(path)
    local_drive = len(drive) == 2 and drive[0].isalpha() and drive[1] == ":"
    if not local_drive or not tail.startswith(("\\", "/")) or any(c in tail for c in '<>"|?*:'):
        raise HTTPException(
            status_code=422,
            detail=f"Use an absolute local path below the GPO backup directory {root}",
        )
    resolved = ntpath.normpath(path)
    if FOLLOW_LINKS:
        # Follow junctions and symbolic links before comparing.
        root, resolved = os.path.realpath(root), os.path.realpath(resolved)
    inside = ntpath.normcase(resolved)
    base = ntpath.normcase(root).rstrip("\\")
    if inside != base and not inside.startswith(base + "\\"):
        raise HTTPException(status_code=422, detail=f"GPO backups may only be written below {root}")
    return resolved


@router.get("")
def gpos():
    return run_ps_list(r"""Import-Module GroupPolicy
Get-GPO -All | Select-Object @{n='displayName';e={$_.DisplayName}},@{n='id';e={$_.Id.Guid}},@{n='status';e={[string]$_.GpoStatus}},@{n='owner';e={$_.Owner}},@{n='modified';e={$_.ModificationTime}} | ConvertTo-Json -Depth 4 -Compress
""")


@router.post("")
def create_gpo(body: GpoCreate):
    return run_ps(
        "Import-Module GroupPolicy; $g=New-GPO -Name $env:RSAT_NAME -Comment $env:RSAT_COMMENT; $g | Select-Object @{n='displayName';e={$_.DisplayName}},@{n='id';e={$_.Id.Guid}} | ConvertTo-Json -Compress",
        body.model_dump(),
    )


@router.get("/links")
def gpo_links():
    return run_ps_list(r"""Import-Module ActiveDirectory
Import-Module GroupPolicy
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
""")


@router.delete("/{gpo_id}")
def delete_gpo(gpo_id: str):
    return run_ps(
        "Import-Module GroupPolicy; Remove-GPO -Guid $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress",
        {"id": identity(gpo_id)},
    )


@router.post("/{gpo_id}/link")
def gpo_link(gpo_id: str, body: GpoLink):
    values = body.model_dump()
    values["id"] = identity(gpo_id)
    return run_ps(
        r"""Import-Module GroupPolicy
$p=@{
  Guid=$env:RSAT_ID
  Target=$env:RSAT_TARGET
  LinkEnabled=if([System.Convert]::ToBoolean($env:RSAT_ENABLED)){'Yes'}else{'No'}
  Enforced=if([System.Convert]::ToBoolean($env:RSAT_ENFORCED)){'Yes'}else{'No'}
}
if($env:RSAT_ORDER){$p.Order=[int]$env:RSAT_ORDER}
New-GPLink @p | Out-Null
@{ok=$true}|ConvertTo-Json -Compress
""",
        values,
    )


@router.post("/{gpo_id}/unlink")
def gpo_unlink(gpo_id: str, body: GpoLink):
    return run_ps(
        "Import-Module GroupPolicy; Remove-GPLink -Guid $env:RSAT_ID -Target $env:RSAT_TARGET -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress",
        {"id": identity(gpo_id), "target": body.target},
    )


@router.post("/{gpo_id}/status")
def gpo_status(gpo_id: str, body: GpoStatus):
    return run_ps(
        r"""Import-Module GroupPolicy
$g=Get-GPO -Guid $env:RSAT_ID
$g.GpoStatus=$env:RSAT_STATUS
@{ok=$true}|ConvertTo-Json -Compress
""",
        {"id": identity(gpo_id), "status": body.status},
    )


@router.post("/{gpo_id}/backup")
def gpo_backup(gpo_id: str, body: BackupBody):
    return run_ps(
        r"""Import-Module GroupPolicy
if(-not(Test-Path $env:RSAT_PATH)){New-Item -ItemType Directory -Path $env:RSAT_PATH -Force | Out-Null}
$b=Backup-GPO -Guid $env:RSAT_ID -Path $env:RSAT_PATH
$b | Select-Object BackupId,DisplayName,CreationTime,BackupDirectory | ConvertTo-Json -Compress
""",
        {"id": identity(gpo_id), "path": backup_directory(body.path)},
    )


@router.get("/{gpo_id}/report")
def gpo_report(gpo_id: str):
    return run_ps(
        r"""Import-Module GroupPolicy
$g=Get-GPO -Guid $env:RSAT_ID
$xml=Get-GPOReport -Guid $env:RSAT_ID -ReportType Xml
[pscustomobject]@{displayName=$g.DisplayName;id=$g.Id.Guid;status=[string]$g.GpoStatus;owner=$g.Owner;modified=$g.ModificationTime;xml=$xml} | ConvertTo-Json -Depth 5 -Compress
""",
        {"id": identity(gpo_id)},
    )


@router.get("/{gpo_id}/permissions")
def gpo_permissions(gpo_id: str):
    return run_ps_list(
        r"""Import-Module GroupPolicy
Get-GPPermission -Guid $env:RSAT_ID -All | Select-Object @{n='trustee';e={$_.Trustee.Name}},@{n='type';e={[string]$_.Trustee.SidType}},@{n='permission';e={[string]$_.Permission}},@{n='inherited';e={$_.Inherited}} | ConvertTo-Json -Depth 4 -Compress
""",
        {"id": identity(gpo_id)},
    )


@router.post("/{gpo_id}/permissions")
def set_gpo_permission(gpo_id: str, body: GpoPermission):
    values = body.model_dump()
    values["id"] = identity(gpo_id)
    return run_ps(
        r"""Import-Module GroupPolicy
Set-GPPermission -Guid $env:RSAT_ID -TargetName $env:RSAT_TRUSTEE -TargetType $env:RSAT_TARGET_TYPE -PermissionLevel $env:RSAT_PERMISSION -Replace:([System.Convert]::ToBoolean($env:RSAT_REPLACE))
@{ok=$true}|ConvertTo-Json -Compress
""",
        values,
    )
