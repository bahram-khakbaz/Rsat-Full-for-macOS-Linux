[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]*\\[A-Za-z0-9][A-Za-z0-9_-]*\$$')][string]$Account,
    [string]$TaskName = 'RSAT-Full-Worker',
    [string]$StateDirectory = "$env:ProgramData\RSATFull\Worker"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\gmsa-task.ps1"
$current = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run deployment from an elevated administrator shell' }
$computer = Get-CimInstance Win32_ComputerSystem
if (-not $computer.PartOfDomain -or $computer.DomainRole -ge 4) { throw 'Use a domain-joined management host, not a Domain Controller' }
Import-Module ActiveDirectory
$expectedDomain = (Get-ADDomain).NetBIOSName
if (($Account -split '\\', 2)[0] -ne $expectedDomain) { throw 'Use a gMSA in the management host domain' }
$name = ($Account -split '\\', 2)[1].TrimEnd('$')
$gmsa = Get-ADServiceAccount -Identity $name
if ($gmsa.ObjectClass -ne 'msDS-GroupManagedServiceAccount' -or -not (Test-ADServiceAccount -Identity $name)) {
    throw 'Provision/authorize/install the gMSA on this host first; Test-ADServiceAccount must succeed'
}
if (-not (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") -or -not (Test-Path "$PSScriptRoot\.env")) { throw 'Initialize the worker virtual environment and channel credential first' }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw 'Task already exists; review it before replacing it' }
$definition = New-RsatGmsaTaskDefinition -Account $Account -WorkerDirectory $PSScriptRoot -StateDirectory $StateDirectory
if ($PSCmdlet.ShouldProcess($TaskName, 'Create protected pairing directory and register gMSA startup task')) {
    New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @('S-1-5-18', 'S-1-5-32-544')) {
        $identity = [Security.Principal.SecurityIdentifier]::new($sid)
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($Account, 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    Set-Acl -LiteralPath $StateDirectory -AclObject $acl
    Register-ScheduledTask -TaskName $TaskName -InputObject $definition | Out-Null
    Write-Host 'Task registered. Review deployment ACLs/firewall, then use Start-ScheduledTask to start it.'
}
