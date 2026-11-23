param(
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string]$ExternalDPath = "D:\JF LIFE",
    [switch]$Push,
    [switch]$IncludeLarge,
    [switch]$DryRun,
    [string[]]$IncludePattern = @(),
    [string[]]$ExcludePattern = @()
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$pyArgs = @(
    "scripts/jf_life_link.py",
    "--source", "iCloud=$ICloudPath",
    "--source", "ExternalD=$ExternalDPath"
)

if ($DryRun) { $pyArgs += "--dry-run" }
if ($IncludeLarge) { $pyArgs += "--include-large" }
foreach ($pattern in $IncludePattern) {
    $pyArgs += @("--include", $pattern)
}
foreach ($pattern in $ExcludePattern) {
    $pyArgs += @("--exclude", $pattern)
}
if ($Push) {
    $pyArgs += "--git-commit"
    $pyArgs += "--git-push"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 @pyArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python @pyArgs
} else {
    throw "Python not found. Install Python, then rerun."
}
exit $LASTEXITCODE
