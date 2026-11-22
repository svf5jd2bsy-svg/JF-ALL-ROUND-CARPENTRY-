param(
    [string]$RepoUrl = "https://github.com/svf5jd2bsy-svg/JF-ALL-ROUND-CARPENTRY-.git",
    [string]$RepoDir = "$env:USERPROFILE\JF-ALL-ROUND-CARPENTRY-",
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string]$ExternalDPath = "D:\JF LIFE",
    [switch]$IncludeLarge,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Ensure-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        return
    }

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Git..."
        winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    } else {
        throw "Git is not installed and winget is unavailable. Install Git for Windows manually, then rerun this script."
    }

    $possiblePaths = @(
        "C:\Program Files\Git\cmd",
        "C:\Program Files (x86)\Git\cmd"
    )
    foreach ($pathEntry in $possiblePaths) {
        if ((Test-Path $pathEntry) -and ($env:Path -notlike "*$pathEntry*")) {
            $env:Path = "$pathEntry;$env:Path"
        }
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git was installed but is not available in PATH yet. Close PowerShell, reopen, and rerun."
    }
}

function Ensure-Repo([string]$RepoUrlValue, [string]$RepoDirValue) {
    if (Test-Path (Join-Path $RepoDirValue ".git")) {
        Write-Host "Updating existing repository..."
        git -C $RepoDirValue pull --ff-only
        return
    }

    if (Test-Path $RepoDirValue) {
        throw "Target folder exists but is not a git repo: $RepoDirValue"
    }

    Write-Host "Cloning repository..."
    git clone $RepoUrlValue $RepoDirValue
}

function Get-PythonRunner {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = "py"; Prefix = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Prefix = @() }
    }
    throw "Python not found. Install Python, then rerun."
}

Ensure-Git
Ensure-Repo -RepoUrlValue $RepoUrl -RepoDirValue $RepoDir

Set-Location $RepoDir

$linkArgs = @("scripts/jf_life_link.py")

$sources = @()
if (Test-Path $ICloudPath) {
    $sources += @("--source", "iCloud=$ICloudPath")
} else {
    Write-Warning "iCloud source not found: $ICloudPath"
}
if (Test-Path $ExternalDPath) {
    $sources += @("--source", "ExternalD=$ExternalDPath")
} else {
    Write-Warning "External D source not found: $ExternalDPath"
}

if ($sources.Count -eq 0) {
    throw "No source folders found. Checked: $ICloudPath and $ExternalDPath"
}

$linkArgs += $sources
if ($IncludeLarge) {
    $linkArgs += "--include-large"
}
if (-not $NoPush) {
    $linkArgs += @("--git-commit", "--git-push")
}

$runner = Get-PythonRunner
& $runner.Exe @($runner.Prefix + $linkArgs)
if ($LASTEXITCODE -ne 0) {
    throw "Link script failed with exit code $LASTEXITCODE"
}

Write-Host "JF LIFE linking completed."
