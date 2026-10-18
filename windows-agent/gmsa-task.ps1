function New-RsatGmsaTaskDefinition {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]*\\[A-Za-z0-9][A-Za-z0-9_-]*\$$')][string]$Account,
        [Parameter(Mandatory)][string]$WorkerDirectory,
        [Parameter(Mandatory)][string]$StateDirectory
    )
    foreach ($path in @($WorkerDirectory, $StateDirectory)) {
        if ($path.Contains('"') -or $path.Contains("`n") -or $path.Contains("`r")) { throw 'Invalid deployment path' }
    }
    $arguments = '-NoProfile -NonInteractive -File "{0}\start-worker-unattended.ps1" -StateDirectory "{1}"' -f $WorkerDirectory.TrimEnd('\'), $StateDirectory.TrimEnd('\')
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $arguments -WorkingDirectory $WorkerDirectory
    # Password logon is the Task Scheduler mode for gMSA; no password is supplied.
    $principal = New-ScheduledTaskPrincipal -UserId $Account -LogonType Password -RunLevel Limited
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
    New-ScheduledTask -Action $action -Principal $principal -Trigger $trigger -Settings $settings -Description 'RSAT allow-listed worker under a delegated gMSA'
}
