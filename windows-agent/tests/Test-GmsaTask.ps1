$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'gmsa-task.ps1')
$task = New-RsatGmsaTaskDefinition -Account 'EXAMPLE\rsatWorker$' -WorkerDirectory 'C:\Program Files\RSAT Worker' -StateDirectory 'C:\ProgramData\RSATFull\Worker'
if ($task.Principal.UserId -ne 'EXAMPLE\rsatWorker$') { throw 'Wrong task identity' }
if ($task.Principal.RunLevel -notin @('Limited', 0)) { throw 'Task must not request elevated run level' }
if ($task.Principal.LogonType -notin @('Password', 1)) { throw 'Incorrect gMSA task logon mode' }
if ($task.Actions.Arguments -match 'ExecutionPolicy|password|AGENT_TOKEN') { throw 'Credentials/policy bypass must not appear in task arguments' }
if ($task.Actions.Arguments -notmatch 'start-worker-unattended.ps1') { throw 'Wrong entrypoint' }
if ($task.Triggers.CimClass.CimClassName -ne 'MSFT_TaskBootTrigger') { throw 'Expected startup trigger' }
$rejected = $false
try { New-RsatGmsaTaskDefinition -Account 'EXAMPLE\interactive-user' -WorkerDirectory 'C:\Worker' -StateDirectory 'C:\State' } catch { $rejected = $true }
if (-not $rejected) { throw 'Non-gMSA account syntax was accepted' }
Write-Host 'gMSA task definition checks passed; no task was registered and no domain account was used.'
