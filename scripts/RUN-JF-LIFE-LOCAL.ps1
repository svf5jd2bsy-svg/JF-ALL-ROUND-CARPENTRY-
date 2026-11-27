param(
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string]$ExternalDPath = "D:\",
    [string]$StateDir = "$(Join-Path $env:LOCALAPPDATA 'JF LIFE')",
    [string[]]$IncludePattern = @(),
    [string[]]$ExcludePattern = @(),
    [string[]]$AdditionalSource = @(),
    [string]$OutlookClientId = "",
    [switch]$RefreshRecoveryPlan,
    [switch]$ApplyRecoveryCopies,
    [switch]$RefreshOutlookPlan,
    [switch]$ApplyOutlookActions,
    [switch]$BuildLibrary,
    [switch]$PublishLibrary,
    [switch]$NoDashboard
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

function Invoke-JFPython([string[]]$Arguments) {
    $runner = Get-PythonRunner
    & $runner.Exe @($runner.Prefix + @("scripts/run_jf_life.py") + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "JF LIFE local command failed with exit code $LASTEXITCODE"
    }
}

if ([string]::IsNullOrWhiteSpace($StateDir)) {
    throw "StateDir is required and must point outside the repository."
}
$stateResolved = [System.IO.Path]::GetFullPath($StateDir)
$repoResolved = [string]$repoRoot.Path
if (
    $stateResolved.Equals($repoResolved.TrimEnd("\"), [System.StringComparison]::OrdinalIgnoreCase) -or
    $stateResolved.StartsWith("$($repoResolved.TrimEnd('\'))\", [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "Private local state must be outside the public repository."
}

$sources = @()
if (Test-Path -LiteralPath $ExternalDPath -PathType Container) {
    $sources += @("--source", "DriveD=$((Resolve-Path -LiteralPath $ExternalDPath).Path)")
    Write-Host "Inventory source [DriveD]: $ExternalDPath"
} else {
    Write-Warning "JF external drive source not found: $ExternalDPath"
}
if (Test-Path -LiteralPath $ICloudPath -PathType Container) {
    $sources += @("--source", "iCloud=$((Resolve-Path -LiteralPath $ICloudPath).Path)")
    Write-Host "Inventory source [iCloud]: $ICloudPath"
} else {
    Write-Warning "iCloud source not found yet: $ICloudPath"
}
foreach ($sourceSpec in $AdditionalSource) {
    $sources += @("--source", $sourceSpec)
    Write-Host "Additional inventory source: $sourceSpec"
}
if ($sources.Count -eq 0) {
    throw "No local sources found. Connect JF (D:) and enable iCloud Drive, then rerun."
}

$inventoryArgs = @(
    "scripts/jf_life_inventory.py",
    "--state-dir", $StateDir
)
$inventoryArgs += $sources
foreach ($pattern in $IncludePattern) {
    $inventoryArgs += @("--include", $pattern)
}
foreach ($pattern in $ExcludePattern) {
    $inventoryArgs += @("--exclude", $pattern)
}
Invoke-JFPython $inventoryArgs
$recoveryPlan = Join-Path $StateDir "recovery-plan.json"
if ($RefreshRecoveryPlan -or -not (Test-Path -LiteralPath $recoveryPlan)) {
    Invoke-JFPython @(
        "scripts/jf_life_recovery.py", "plan",
        "--state-dir", $StateDir
    )
} else {
    Write-Host "Keeping the existing duplicate review plan. Use -RefreshRecoveryPlan to regenerate it."
}
Invoke-JFPython @(
    "scripts/jf_life_recovery.py", "apply",
    "--state-dir", $StateDir
)
if ($ApplyRecoveryCopies) {
    Invoke-JFPython @(
        "scripts/jf_life_recovery.py", "apply", "--apply",
        "--state-dir", $StateDir
    )
}

$outlookConfig = Join-Path $StateDir "outlook-config.json"
$outlookRequested = -not [string]::IsNullOrWhiteSpace($OutlookClientId)
if ($outlookRequested -or (Test-Path -LiteralPath $outlookConfig)) {
    if ($outlookRequested) {
        Invoke-JFPython @(
            "scripts/jf_life_outlook.py", "--state-dir", $StateDir,
            "connect", "--client-id", $OutlookClientId
        )
    }
    Invoke-JFPython @(
        "scripts/jf_life_outlook.py", "--state-dir", $StateDir,
        "inventory"
    )
    $outlookPlan = Join-Path $StateDir "outlook-actions.json"
    if ($RefreshOutlookPlan -or -not (Test-Path -LiteralPath $outlookPlan)) {
        Invoke-JFPython @(
            "scripts/jf_life_outlook.py", "--state-dir", $StateDir,
            "plan", "--all-unread"
        )
    } else {
        Write-Host "Keeping the existing reviewed Outlook plan. Use -RefreshOutlookPlan to regenerate it."
    }
    if ($ApplyOutlookActions) {
        Invoke-JFPython @(
            "scripts/jf_life_outlook.py", "--state-dir", $StateDir,
            "apply", "--apply"
        )
    } else {
        Invoke-JFPython @(
            "scripts/jf_life_outlook.py", "--state-dir", $StateDir,
            "apply"
        )
        Write-Host "Outlook actions were proposed only. Review the private plan before using -ApplyOutlookActions."
    }
} else {
    Write-Host "Outlook is not configured. Supply -OutlookClientId after completing the local app registration."
}

if ($BuildLibrary -or $PublishLibrary) {
    $linkArgs = @("scripts/jf_life_link.py")
    $linkArgs += $sources
    foreach ($pattern in $IncludePattern) {
        $linkArgs += @("--include", $pattern)
    }
    foreach ($pattern in $ExcludePattern) {
        $linkArgs += @("--exclude", $pattern)
    }
    if ($PublishLibrary) {
        $linkArgs += @("--git-commit", "--git-push")
    }
    Invoke-JFPython $linkArgs
}

Invoke-JFPython @(
    "scripts/jf_life_dashboard.py",
    "--state-dir", $StateDir
)

$dashboard = Join-Path $StateDir "JF-LIFE-Dashboard.html"
if (-not $NoDashboard -and (Test-Path -LiteralPath $dashboard)) {
    Start-Process $dashboard
}

Write-Host "JF LIFE local review completed. Private state: $StateDir"
Write-Host "No source file was deleted or moved. Outlook changes require approved=true actions."
