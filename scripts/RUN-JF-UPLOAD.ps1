param(
    [string]$ExternalDPath = "D:\",
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string[]]$AdditionalSource = @(),
    [switch]$PublishLibrary
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

function Get-PythonRunner {
    if (Get-Command py -ErrorActionSilentlyContinue) {
        return @{ Exe = "py"; Prefix = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Prefix = @() }
    }
    throw "Python not found. Install Python 3, then rerun."
}

$sources = @()
if (Test-Path -LiteralPath $ExternalDPath -PathType Container) {
    $sources += "DriveD=$((Resolve-Path -LiteralPath $ExternalDPath).Path)"
    Write-Host "Found JF drive: $ExternalDPath"
}

$icloudCandidates = @(
    $ICloudPath,
    (Join-Path $env:USERPROFILE "OneDrive\iCloudDrive\JF LIFE"),
    (Join-Path $env:USERPROFILE "iCloudDrive\JF LIFE")
)
foreach ($candidate in $icloudCandidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Container)) {
        $sources += "iCloud=$((Resolve-Path -LiteralPath $candidate).Path)"
        Write-Host "Found iCloud JF LIFE: $candidate"
        break
    }
}

$searchRoots = @(
    (Join-Path $env:USERPROFILE "Desktop"),
    (Join-Path $env:USERPROFILE "Documents"),
    (Join-Path $env:USERPROFILE "Downloads"),
    (Join-Path $env:USERPROFILE "OneDrive")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) }

$chatExportTemp = Join-Path $env:TEMP "JF-LIFE-ChatGPT-Import"
$chatExportFound = $false
foreach ($root in $searchRoots) {
    $zipFiles = Get-ChildItem -LiteralPath $root -File -Recurse -Filter "*.zip" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "chatgpt|openai|conversation|export" }
    foreach ($zip in $zipFiles) {
        $extract = Join-Path $chatExportTemp ($zip.BaseName)
        New-Item -ItemType Directory -Force -Path $extract | Out-Null
        try {
            Expand-Archive -LiteralPath $zip.FullName -DestinationPath $extract -Force
            $sources += "ChatGPT=$extract"
            $chatExportFound = $true
            Write-Host "Found ChatGPT export: $($zip.FullName)"
        } catch {
            Write-Warning "Could not read ChatGPT export: $($zip.FullName)"
        }
    }
}

foreach ($spec in $AdditionalSource) {
    if (-not [string]::IsNullOrWhiteSpace($spec)) {
        $sources += $spec
    }
}

if ($sources.Count -eq 0) {
    throw "No JF LIFE, iCloud, D drive, or ChatGPT source was found. Connect the drive and iCloud folder, or pass -AdditionalSource."
}

if ($PublishLibrary) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "Publishing requires GitHub CLI (gh). Install GitHub CLI and authenticate first."
    }
    $repo = gh repo view svf5jd2bsy-svg/JF-ALL-ROUND-CARPENTRY- --json isPrivate --jq ".isPrivate" 2>$null
    if ($repo -ne "true") {
        throw "Publishing personal JF LIFE sources is blocked while the GitHub repository is public. Make the repository private in GitHub Settings, then rerun with -PublishLibrary."
    }
}

$args = @("-ExternalDPath", $ExternalDPath)
$args += @("-ICloudPath", $ICloudPath)
$args += @("-BuildLibrary")
$chatSources = $sources | Where-Object { $_ -notmatch "^DriveD=|^iCloud=" }
foreach ($source in $chatSources) {
    $args += @("-AdditionalSource", $source)
}
if ($PublishLibrary) {
    $args += "-PublishLibrary"
}

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\RUN-JF-LIFE-LOCAL.ps1 @args
exit $LASTEXITCODE
