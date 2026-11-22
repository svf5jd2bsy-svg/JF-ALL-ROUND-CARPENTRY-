param(
    [string]$StateDir = "$(Join-Path $env:LOCALAPPDATA 'JF LIFE')",
    [string]$ExternalDPath = "D:\",
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string[]]$IncludePattern = @(),
    [string[]]$ExcludePattern = @(),
    [string]$OutlookClientId = "",
    [switch]$ApplyOutlookActions,
    [switch]$ApplyRecoveryCopies,
    [string]$StripeApiKey = "",
    [string]$XeroAccessToken = "",
    [string]$XeroTenantId = "",
    [int]$IntervalSeconds = 300,
    [int]$Cycles = 0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

function Get-PythonRunner {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = "py"; Prefix = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Prefix = @() }
    }
    throw "Python not found. Install Python 3, then rerun."
}

$args = @(
    "scripts/jf_life_live_sync.py",
    "--state-dir", $StateDir,
    "--source", "DriveD=$ExternalDPath",
    "--source", "iCloud=$ICloudPath",
    "--interval-seconds", [string]$IntervalSeconds,
    "--cycles", [string]$Cycles
)

foreach ($pattern in $IncludePattern) {
    $args += @("--include", $pattern)
}
foreach ($pattern in $ExcludePattern) {
    $args += @("--exclude", $pattern)
}
if (-not [string]::IsNullOrWhiteSpace($OutlookClientId)) {
    $args += @("--outlook-client-id", $OutlookClientId)
}
if ($ApplyOutlookActions) {
    $args += "--apply-outlook-actions"
}
if ($ApplyRecoveryCopies) {
    $args += "--apply-recovery-copies"
}
if (-not [string]::IsNullOrWhiteSpace($StripeApiKey)) {
    $args += @("--stripe-api-key", $StripeApiKey)
}
if (-not [string]::IsNullOrWhiteSpace($XeroAccessToken)) {
    $args += @("--xero-access-token", $XeroAccessToken)
}
if (-not [string]::IsNullOrWhiteSpace($XeroTenantId)) {
    $args += @("--xero-tenant-id", $XeroTenantId)
}

$runner = Get-PythonRunner
& $runner.Exe @($runner.Prefix + $args)
exit $LASTEXITCODE
