param(
    [string]$StateDir = "$(Join-Path $env:LOCALAPPDATA 'JF LIFE')",
    [string]$ExternalDPath = "D:\",
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string[]]$IncludePattern = @(),
    [string[]]$ExcludePattern = @(),
    [string[]]$AdditionalSource = @(),
    [string]$OutlookClientId = "",
    [switch]$ApplyOutlookActions,
    [switch]$ApplyRecoveryCopies,
    [string]$StripeApiKey = "",
    [string]$XeroAccessToken = "",
    [string]$XeroTenantId = "",
    [switch]$PublishLibrary,
    [int]$IntervalSeconds = 300,
    [int]$Cycles = 0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

function Get-PythonRunner {
    if ($env:JF_LIFE_PYTHON) {
        if (-not (Test-Path -LiteralPath $env:JF_LIFE_PYTHON -PathType Leaf)) {
            throw "JF_LIFE_PYTHON does not point to a Python executable."
        }
        return @{ Exe = $env:JF_LIFE_PYTHON; Prefix = @() }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = "py"; Prefix = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Prefix = @() }
    }
    throw "Python not found. Install Python 3, then rerun."
}

$args = @(
    "scripts/run_jf_life.py",
    "scripts/jf_life_live_sync.py",
    "--state-dir", $StateDir,
    "--interval-seconds", [string]$IntervalSeconds,
    "--cycles", [string]$Cycles
)

if ($ExternalDPath) {
    $args += @("--source", "DriveD=$ExternalDPath")
}
if ($ICloudPath) {
    $args += @("--source", "iCloud=$ICloudPath")
}
foreach ($sourceSpec in $AdditionalSource) {
    $args += @("--source", $sourceSpec)
}
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
if ($PublishLibrary) {
    $args += "--publish-library"
}

$runner = Get-PythonRunner
& $runner.Exe @($runner.Prefix + $args)
exit $LASTEXITCODE
