$ErrorActionPreference = 'Stop'
$features = @(
  'Rsat.ActiveDirectory.DS-LDS.Tools~~~~0.0.1.0',
  'Rsat.Dns.Tools~~~~0.0.1.0',
  'Rsat.DHCP.Tools~~~~0.0.1.0',
  'Rsat.GroupPolicy.Management.Tools~~~~0.0.1.0'
)
foreach ($feature in $features) {
  $state = Get-WindowsCapability -Online -Name $feature
  if ($state.State -ne 'Installed') { Add-WindowsCapability -Online -Name $feature }
}
Get-Module -ListAvailable ActiveDirectory,DnsServer,DhcpServer,GroupPolicy | Select-Object Name,Version,Path
