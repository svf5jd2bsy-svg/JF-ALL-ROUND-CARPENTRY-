param(
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string]$ExternalDPath = "D:\JF LIFE",
    [switch]$Push,
    [switch]$IncludeLarge,
    [switch]$DryRun
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
if ($Push) {
    $pyArgs += "--git-commit"
    $pyArgs += "--git-push"
}

python @pyArgs
exit $LASTEXITCODE
