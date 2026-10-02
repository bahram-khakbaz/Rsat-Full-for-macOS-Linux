import re
from fastapi import APIRouter, Query
from ..common import identity, list_result
from ..models import GroupCreate, MemberBody, MoveBody, OUCreate, OUDelete, PasswordBody, RestoreBody, UserCreate, UserPatch
from ..runner import run_ps

router = APIRouter(prefix="/ad", tags=["active-directory"])

@router.get("/users")
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

@router.post("/users")
def create_user(body: UserCreate):
    return run_ps(r"""Import-Module ActiveDirectory
$secure=ConvertTo-SecureString $env:RSAT_PASSWORD -AsPlainText -Force
$p=@{
 Name=$env:RSAT_DISPLAY_NAME
 SamAccountName=$env:RSAT_SAM_ACCOUNT_NAME
 GivenName=$env:RSAT_GIVEN_NAME
 Surname=$env:RSAT_SURNAME
 DisplayName=$env:RSAT_DISPLAY_NAME
 Path=$env:RSAT_OU
 AccountPassword=$secure
 Enabled=[System.Convert]::ToBoolean($env:RSAT_ENABLED)
}
if($env:RSAT_EMAIL){$p.EmailAddress=$env:RSAT_EMAIL}
if($env:RSAT_DEPARTMENT){$p.Department=$env:RSAT_DEPARTMENT}
if($env:RSAT_TITLE){$p.Title=$env:RSAT_TITLE}
if($env:RSAT_COMPANY){$p.Company=$env:RSAT_COMPANY}
New-ADUser @p
if($env:RSAT_MANAGER){Set-ADUser -Identity $env:RSAT_SAM_ACCOUNT_NAME -Manager $env:RSAT_MANAGER}
Set-ADUser -Identity $env:RSAT_SAM_ACCOUNT_NAME -ChangePasswordAtLogon ([System.Convert]::ToBoolean($env:RSAT_MUST_CHANGE))
Get-ADUser -Identity $env:RSAT_SAM_ACCOUNT_NAME -Properties DisplayName,Mail,Enabled | Select-Object SamAccountName,DisplayName,Mail,Enabled | ConvertTo-Json -Compress
""", body.model_dump())

@router.get("/users/{user_identity}")
def get_user(user_identity: str):
    return run_ps(r"""Import-Module ActiveDirectory
Get-ADUser -Identity $env:RSAT_ID -Properties * | Select-Object @{n='samAccountName';e={$_.SamAccountName}},@{n='displayName';e={$_.DisplayName}},@{n='givenName';e={$_.GivenName}},@{n='surname';e={$_.Surname}},@{n='mail';e={$_.Mail}},@{n='mobile';e={$_.MobilePhone}},@{n='department';e={$_.Department}},@{n='company';e={$_.Company}},@{n='title';e={$_.Title}},@{n='manager';e={$_.Manager}},@{n='employeeId';e={$_.EmployeeID}},@{n='office';e={$_.Office}},@{n='enabled';e={$_.Enabled}},@{n='lockedOut';e={$_.LockedOut}},@{n='passwordExpired';e={$_.PasswordExpired}},@{n='passwordNeverExpires';e={$_.PasswordNeverExpires}},@{n='passwordLastSet';e={$_.PasswordLastSet}},@{n='passwordExpires';e={if($_.'msDS-UserPasswordExpiryTimeComputed' -and [int64]$_.'msDS-UserPasswordExpiryTimeComputed' -gt 0){[datetime]::FromFileTime([int64]$_.'msDS-UserPasswordExpiryTimeComputed')}else{$null}}},@{n='lastLogon';e={$_.LastLogonDate}},@{n='created';e={$_.whenCreated}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 5 -Compress
""", {"id":identity(user_identity)})

@router.patch("/users/{user_identity}")
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

@router.delete("/users/{user_identity}")
def delete_user(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADUser -Identity $env:RSAT_ID -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@router.post("/users/{user_identity}/unlock")
def unlock(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Unlock-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@router.post("/users/{user_identity}/enable")
def enable_user(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Enable-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@router.post("/users/{user_identity}/disable")
def disable_user(user_identity: str):
    return run_ps("Import-Module ActiveDirectory; Disable-ADAccount -Identity $env:RSAT_ID; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity)})

@router.post("/users/{user_identity}/reset-password")
def reset_password(user_identity: str, body: PasswordBody):
    return run_ps(r"""Import-Module ActiveDirectory
$secure=ConvertTo-SecureString $env:RSAT_PASSWORD -AsPlainText -Force
Set-ADAccountPassword -Identity $env:RSAT_ID -Reset -NewPassword $secure
Set-ADUser -Identity $env:RSAT_ID -ChangePasswordAtLogon ([System.Convert]::ToBoolean($env:RSAT_MUST_CHANGE))
@{ok=$true}|ConvertTo-Json -Compress
""", {"id":identity(user_identity),"password":body.new_password,"must_change":str(body.must_change)})

@router.post("/users/{user_identity}/move")
def move_user(user_identity: str, body: MoveBody):
    return run_ps("Import-Module ActiveDirectory; Get-ADUser -Identity $env:RSAT_ID | Move-ADObject -TargetPath $env:RSAT_TARGET_OU; @{ok=$true}|ConvertTo-Json -Compress", {"id":identity(user_identity),"target_ou":body.target_ou})

@router.get("/users/{user_identity}/groups")
def user_groups(user_identity: str):
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADPrincipalGroupMembership -Identity $env:RSAT_ID | Select-Object @{n='name';e={$_.Name}},@{n='scope';e={[string]$_.GroupScope}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 4 -Compress
""", {"id":identity(user_identity)}))

@router.get("/groups")
def groups():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADGroup -Filter * -ResultSetSize 1000 -Properties Description,GroupScope,GroupCategory | ForEach-Object {
  $count=(Get-ADGroupMember -Identity $_ -ErrorAction SilentlyContinue | Measure-Object).Count
  [pscustomobject]@{name=$_.Name;description=$_.Description;scope=[string]$_.GroupScope;category=[string]$_.GroupCategory;members=$count;dn=$_.DistinguishedName}
} | ConvertTo-Json -Depth 4 -Compress
"""))

@router.post("/groups")
def create_group(body: GroupCreate):
    return run_ps(r"""Import-Module ActiveDirectory
New-ADGroup -Name $env:RSAT_NAME -GroupScope $env:RSAT_SCOPE -GroupCategory $env:RSAT_CATEGORY -Path $env:RSAT_PATH -Description $env:RSAT_DESCRIPTION
Get-ADGroup -Identity $env:RSAT_NAME | Select-Object Name,DistinguishedName | ConvertTo-Json -Compress
""", body.model_dump())

@router.delete("/groups/{name}")
def delete_group(name: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADGroup -Identity $env:RSAT_NAME -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@router.get("/groups/{name}/members")
def group_members(name: str):
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADGroupMember -Identity $env:RSAT_NAME | Select-Object @{n='name';e={$_.Name}},@{n='samAccountName';e={$_.SamAccountName}},@{n='objectClass';e={$_.objectClass}},@{n='dn';e={$_.DistinguishedName}} | ConvertTo-Json -Depth 4 -Compress
""", {"name":identity(name)}))

@router.post("/groups/{name}/members")
def add_group_member(name: str, body: MemberBody):
    return run_ps("Import-Module ActiveDirectory; Add-ADGroupMember -Identity $env:RSAT_NAME -Members $env:RSAT_MEMBER; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name),"member":body.member})

@router.delete("/groups/{name}/members/{member}")
def remove_group_member(name: str, member: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADGroupMember -Identity $env:RSAT_NAME -Members $env:RSAT_MEMBER -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name),"member":identity(member)})

@router.get("/computers")
def computers(q: str = Query(default="", max_length=80)):
    q = re.sub(r"[^A-Za-z0-9_. -]", "", q)
    return list_result(run_ps(r"""Import-Module ActiveDirectory
$q=$env:RSAT_Q
if($q){$rows=Get-ADComputer -Filter "Name -like '*$q*'" -ResultSetSize 1000 -Properties OperatingSystem,Enabled,LastLogonDate,IPv4Address,DistinguishedName}
else{$rows=Get-ADComputer -Filter * -ResultSetSize 1000 -Properties OperatingSystem,Enabled,LastLogonDate,IPv4Address,DistinguishedName}
$rows | Select-Object @{n='name';e={$_.Name}},@{n='os';e={$_.OperatingSystem}},@{n='enabled';e={$_.Enabled}},@{n='lastLogon';e={$_.LastLogonDate}},@{n='ipv4';e={$_.IPv4Address}},@{n='ou';e={$_.DistinguishedName -replace '^CN=[^,]+,',''}} | ConvertTo-Json -Depth 4 -Compress
""",{"q":q}))

@router.post("/computers/{name}/enable")
def computer_enable(name: str):
    return run_ps("Import-Module ActiveDirectory; Enable-ADAccount -Identity $env:RSAT_NAME; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@router.post("/computers/{name}/disable")
def computer_disable(name: str):
    return run_ps("Import-Module ActiveDirectory; Disable-ADAccount -Identity $env:RSAT_NAME; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@router.post("/computers/{name}/reset")
def computer_reset(name: str):
    return run_ps(r"""Import-Module ActiveDirectory
$alphabet='abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*'
$plain=-join (1..40 | ForEach-Object {$alphabet[(Get-Random -Maximum $alphabet.Length)]})
$secure=ConvertTo-SecureString $plain -AsPlainText -Force
Set-ADAccountPassword -Identity (Get-ADComputer -Identity $env:RSAT_NAME) -Reset -NewPassword $secure
@{ok=$true;warning='Computer account password reset. Repair secure channel or rejoin if the client is no longer synchronized.'}|ConvertTo-Json -Compress
""", {"name":identity(name)})

@router.post("/computers/{name}/move")
def computer_move(name: str, body: MoveBody):
    return run_ps("Import-Module ActiveDirectory; Get-ADComputer -Identity $env:RSAT_NAME | Move-ADObject -TargetPath $env:RSAT_TARGET_OU; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name),"target_ou":body.target_ou})

@router.delete("/computers/{name}")
def computer_delete(name: str):
    return run_ps("Import-Module ActiveDirectory; Remove-ADComputer -Identity $env:RSAT_NAME -Confirm:$false; @{ok=$true}|ConvertTo-Json -Compress", {"name":identity(name)})

@router.get("/ous")
def ous():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
Get-ADOrganizationalUnit -Filter * -Properties ProtectedFromAccidentalDeletion | Select-Object @{n='name';e={$_.Name}},@{n='dn';e={$_.DistinguishedName}},@{n='protected';e={$_.ProtectedFromAccidentalDeletion}} | Sort-Object dn | ConvertTo-Json -Depth 3 -Compress
"""))

@router.post("/ous")
def create_ou(body: OUCreate):
    return run_ps(r"""Import-Module ActiveDirectory
$o=New-ADOrganizationalUnit -Name $env:RSAT_NAME -Path $env:RSAT_PATH -ProtectedFromAccidentalDeletion ([System.Convert]::ToBoolean($env:RSAT_PROTECTED)) -PassThru
$o | Select-Object Name,DistinguishedName,ProtectedFromAccidentalDeletion | ConvertTo-Json -Compress
""", body.model_dump())

@router.post("/ous/delete")
def delete_ou(body: OUDelete):
    return run_ps(r"""Import-Module ActiveDirectory
$o=Get-ADOrganizationalUnit -Identity $env:RSAT_DN
if($o.ProtectedFromAccidentalDeletion){Set-ADOrganizationalUnit -Identity $o -ProtectedFromAccidentalDeletion $false}
Remove-ADOrganizationalUnit -Identity $o -Recursive:([System.Convert]::ToBoolean($env:RSAT_RECURSIVE)) -Confirm:$false
@{ok=$true}|ConvertTo-Json -Compress
""", body.model_dump())

@router.get("/deleted")
def deleted_objects():
    return list_result(run_ps(r"""Import-Module ActiveDirectory
$base=(Get-ADDomain).DistinguishedName
Get-ADObject -Filter 'isDeleted -eq $true -and Name -ne "Deleted Objects"' -IncludeDeletedObjects -SearchBase $base -Properties lastKnownParent,whenChanged,objectClass,ObjectGUID | Select-Object @{n='name';e={($_.Name -split '\0ADEL:')[0]}},@{n='objectClass';e={@($_.ObjectClass)[-1]}},@{n='lastKnownParent';e={$_.lastKnownParent}},@{n='deletedAt';e={$_.whenChanged}},@{n='objectGuid';e={$_.ObjectGUID.Guid}} | Sort-Object deletedAt -Descending | ConvertTo-Json -Depth 4 -Compress
"""))

@router.post("/deleted/restore")
def restore_deleted_object(body: RestoreBody):
    return run_ps(r"""Import-Module ActiveDirectory
$o=Get-ADObject -Identity $env:RSAT_OBJECT_GUID -IncludeDeletedObjects
if($env:RSAT_TARGET_PATH){Restore-ADObject -Identity $o -TargetPath $env:RSAT_TARGET_PATH}else{Restore-ADObject -Identity $o}
@{ok=$true}|ConvertTo-Json -Compress
""",body.model_dump())
