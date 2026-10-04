# Copy the three local service config files up to the EC2 instance.
#
# Run from the repository root:
#   .\scripts\copy-env-to-ec2.ps1 -Host 34.235.183.74
#
# Avoids retyping secrets into a remote editor. Transfers run over SSH, so the
# files are encrypted in flight.

param(
    [Parameter(Mandatory = $true)]
    [string]$HostIp,

    [string]$KeyPath = "C:\Coding\Projects\chatgpt-clone-key.pem",

    [string]$User = "ec2-user",

    [string]$RemoteDir = "~/chatgpt-clone"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $KeyPath)) {
    Write-Error "SSH key not found: $KeyPath"
    exit 1
}

$services = @("ai-service", "chat-service", "gateway")

# Check all three exist locally before transferring any of them.
$missing = @()
foreach ($svc in $services) {
    $local = Join-Path $svc ".env"
    if (-not (Test-Path $local)) { $missing += $local }
}
if ($missing.Count -gt 0) {
    Write-Error "Missing locally: $($missing -join ', ')"
    exit 1
}

Write-Host "Copying config to $User@$HostIp" -ForegroundColor Cyan
Write-Host ""

foreach ($svc in $services) {
    $local = Join-Path $svc ".env"
    $remote = "${User}@${HostIp}:$RemoteDir/$svc/"

    Write-Host ("  {0,-14} -> {1}" -f $svc, $remote)
    & scp -i $KeyPath -o StrictHostKeyChecking=accept-new $local $remote

    if ($LASTEXITCODE -ne 0) {
        Write-Error "scp failed for $svc (exit $LASTEXITCODE). Has the repo been cloned on the instance yet?"
        exit 1
    }
}

Write-Host ""
Write-Host "All three copied." -ForegroundColor Green
Write-Host "On the instance, confirm with:" -ForegroundColor Yellow
Write-Host "  ls -la ~/chatgpt-clone/*/.env"
