param(
    [string]$RepoUrl = "https://github.com/svf5jd2bsy-svg/JF-ALL-ROUND-CARPENTRY-.git",
    [string]$RepoDir = "$env:USERPROFILE\JF-ALL-ROUND-CARPENTRY-",
    [string]$ICloudPath = "$env:USERPROFILE\iCloudDrive\JF LIFE",
    [string]$ExternalDPath = "D:\JF LIFE",
    [switch]$IncludeLarge,
    [string[]]$IncludePattern = @(),
    [string[]]$ExcludePattern = @(),
    [switch]$NoPush,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-DriveRoots {
    return @(Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue |
        Where-Object { $_.Root -match "^[A-Za-z]:\\$" -and [string]::IsNullOrWhiteSpace($_.DisplayRoot) } |
        Select-Object -ExpandProperty Root)
}

function Get-DriveInfo {
    $labelsByRoot = @{}
    try {
        $disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction Stop
        foreach ($disk in $disks) {
            if ([string]::IsNullOrWhiteSpace($disk.DeviceID)) { continue }
            $root = "$($disk.DeviceID)\"
            $labelsByRoot[$root] = [string]$disk.VolumeName
        }
    } catch {
        # Label lookup is optional. Continue without labels.
    }

    $results = @()
    foreach ($root in Get-DriveRoots) {
        $label = ""
        if ($labelsByRoot.ContainsKey($root)) {
            $label = [string]$labelsByRoot[$root]
        }
        $results += [pscustomobject]@{
            Root  = $root
            Label = $label
        }
    }
    return $results
}

function Resolve-RepoDir([string]$CurrentRepoDir, [string]$ExternalPath, [bool]$RepoDirExplicitlySet) {
    if ($RepoDirExplicitlySet) {
        return $CurrentRepoDir
    }

    $externalRoot = ""
    try {
        if (Test-Path -LiteralPath $ExternalPath -PathType Container) {
            $resolved = (Resolve-Path -LiteralPath $ExternalPath).Path
            $externalRoot = [System.IO.Path]::GetPathRoot($resolved)
        } elseif ($ExternalPath -match "^[A-Za-z]:\\") {
            $externalRoot = "$($ExternalPath.Substring(0,1).ToUpperInvariant()):\"
        }
    } catch {
        $externalRoot = ""
    }

    if ([string]::IsNullOrWhiteSpace($externalRoot)) {
        return $CurrentRepoDir
    }

    $currentRoot = [System.IO.Path]::GetPathRoot($CurrentRepoDir)
    if ($externalRoot -and ($externalRoot -ne $currentRoot)) {
        $suggested = Join-Path $externalRoot "JF-ALL-ROUND-CARPENTRY-"
        Write-Host "Using repository folder on external drive: $suggested"
        return $suggested
    }

    return $CurrentRepoDir
}

function Add-UniquePath([string[]]$Values) {
    $set = New-Object "System.Collections.Generic.HashSet[string]" ([System.StringComparer]::OrdinalIgnoreCase)
    $result = @()
    foreach ($value in $Values) {
        if ([string]::IsNullOrWhiteSpace($value)) { continue }
        if ($set.Add($value)) {
            $result += $value
        }
    }
    return $result
}

function Find-NamedDirectories([string]$SearchRoot, [string[]]$Names, [int]$MaxDepth = 4) {
    $results = @()
    if (-not (Test-Path -LiteralPath $SearchRoot -PathType Container)) {
        return $results
    }

    $queue = New-Object System.Collections.Queue
    $queue.Enqueue(@($SearchRoot, 0))
    while ($queue.Count -gt 0) {
        $item = $queue.Dequeue()
        $currentRoot = [string]$item[0]
        $depth = [int]$item[1]

        try {
            $children = Get-ChildItem -LiteralPath $currentRoot -Directory -ErrorAction Stop
        } catch {
            continue
        }

        foreach ($dir in $children) {
            if ($Names -contains $dir.Name) {
                $results += $dir.FullName
            }
            if ($depth -lt $MaxDepth) {
                $queue.Enqueue(@($dir.FullName, $depth + 1))
            }
        }
    }
    return $results
}

function Get-JFChildFolders([string]$RootPath) {
    $names = @(
        "JF",
        "JF LIFE",
        "JF_LIFE",
        "JF-LIFE",
        "JF_LIFE_Local_Sources",
        "JF LIFE Local Sources"
    )
    $results = @()
    if (-not ($RootPath -match "^[A-Za-z]:\\$")) {
        return $results
    }
    try {
        $children = Get-ChildItem -LiteralPath $RootPath -Directory -ErrorAction Stop
    } catch {
        return $results
    }
    foreach ($child in $children) {
        if ($names -contains $child.Name -or $child.Name -match "(?i)^jf([ _-]|$)") {
            $results += $child.FullName
        }
    }
    return Add-UniquePath $results
}

function Resolve-SourceCandidates([string]$PreferredICloudPath, [string]$PreferredExternalPath) {
    $names = @(
        "JF",
        "JF LIFE",
        "JF_LIFE",
        "JF-LIFE",
        "JF_LIFE_Local_Sources",
        "JF LIFE Local Sources"
    )
    $candidates = @(
        @{ Label = "iCloud"; Path = $PreferredICloudPath },
        @{ Label = "ExternalD"; Path = $PreferredExternalPath },
        @{ Label = "iCloud"; Path = "$env:USERPROFILE\iCloudDrive\JF LIFE" },
        @{ Label = "iCloud"; Path = "$env:USERPROFILE\iCloudDrive\JF_LIFE" },
        @{ Label = "iCloud"; Path = "$env:USERPROFILE\iCloud Drive\JF LIFE" },
        @{ Label = "Local"; Path = "$env:USERPROFILE\Documents\JF LIFE" },
        @{ Label = "Local"; Path = "$env:USERPROFILE\Desktop\JF LIFE" },
        @{ Label = "Local"; Path = "$env:USERPROFILE\Downloads\JF LIFE" },
        @{ Label = "Downloads"; Path = "$env:USERPROFILE\Downloads\JF_LIFE_Local_Sources" },
        @{ Label = "Downloads"; Path = "$env:USERPROFILE\Downloads\JF_LIFE_Local_Sources_Windows\JF_LIFE_Local_Sources" }
    )

    foreach ($drive in Get-DriveInfo) {
        $root = [string]$drive.Root
        $label = [string]$drive.Label
        $driveLetter = $root.Substring(0, 1).ToUpperInvariant()
        foreach ($name in $names) {
            $candidates += @{ Label = "Drive$driveLetter"; Path = (Join-Path $root $name) }
            $candidates += @{ Label = "Drive$driveLetter"; Path = (Join-Path $root "iCloudDrive\$name") }
        }

        if ($label -match "(?i)\bjf\b|jf\s*life") {
            $candidates += @{ Label = "Drive$driveLetter-LabelJF"; Path = $root }
            $candidates += @{ Label = "Drive$driveLetter-LabelJF"; Path = (Join-Path $root "JF") }
            $candidates += @{ Label = "Drive$driveLetter-LabelJF"; Path = (Join-Path $root "JF LIFE") }
        }
    }

    $scanRoots = Add-UniquePath @(
        $env:USERPROFILE,
        "$env:USERPROFILE\Documents",
        "$env:USERPROFILE\Desktop",
        "$env:USERPROFILE\Downloads",
        (Get-DriveRoots)
    )

    $autoFoundPaths = @()
    foreach ($scanRoot in $scanRoots) {
        $autoFoundPaths += Find-NamedDirectories -SearchRoot $scanRoot -Names $names -MaxDepth 3
    }
    $autoFoundPaths = Add-UniquePath $autoFoundPaths

    foreach ($path in $autoFoundPaths) {
        $label = if ($path -match "iCloud") { "iCloudAuto" } else { "Auto" }
        $candidates += @{ Label = $label; Path = $path }
    }

    return $candidates
}

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

function Test-IsInsidePath([string]$Path, [string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) {
        return $false
    }
    $pathNorm = $Path.TrimEnd("\")
    $rootNorm = $Root.TrimEnd("\")
    return $pathNorm.Equals($rootNorm, [System.StringComparison]::OrdinalIgnoreCase) -or
        $pathNorm.StartsWith("$rootNorm\", [System.StringComparison]::OrdinalIgnoreCase)
}

$repoDirExplicitlySet = $PSBoundParameters.ContainsKey("RepoDir")
$RepoDir = Resolve-RepoDir -CurrentRepoDir $RepoDir -ExternalPath $ExternalDPath -RepoDirExplicitlySet $repoDirExplicitlySet

Ensure-Git
Ensure-Repo -RepoUrlValue $RepoUrl -RepoDirValue $RepoDir

Set-Location $RepoDir
$repoRootResolved = (Resolve-Path -LiteralPath $RepoDir).Path

$linkArgs = @("scripts/jf_life_link.py")

$sources = @()
$sourceCounter = 0
$sourcePathSet = New-Object "System.Collections.Generic.HashSet[string]" ([System.StringComparer]::OrdinalIgnoreCase)
$candidateSources = Resolve-SourceCandidates -PreferredICloudPath $ICloudPath -PreferredExternalPath $ExternalDPath

foreach ($candidate in $candidateSources) {
    $candidatePath = [string]$candidate.Path
    if ([string]::IsNullOrWhiteSpace($candidatePath)) { continue }
    if (-not (Test-Path -LiteralPath $candidatePath -PathType Container)) { continue }
    $resolved = (Resolve-Path -LiteralPath $candidatePath).Path

    if ($resolved -match "^[A-Za-z]:\\$") {
        $jfChildren = Get-JFChildFolders -RootPath $resolved
        if ($jfChildren.Count -gt 0) {
            foreach ($childPath in $jfChildren) {
                if (Test-IsInsidePath -Path $childPath -Root $repoRootResolved) {
                    continue
                }
                if ($sourcePathSet.Add($childPath)) {
                    $sourceCounter += 1
                    $sourceLabel = "$($candidate.Label)-$sourceCounter"
                    $sources += @("--source", "$sourceLabel=$childPath")
                    Write-Host "Using source [$sourceLabel]: $childPath"
                }
            }
            continue
        }
    }

    if (Test-IsInsidePath -Path $resolved -Root $repoRootResolved) {
        continue
    }

    if ($sourcePathSet.Add($resolved)) {
        $sourceCounter += 1
        $sourceLabel = "$($candidate.Label)-$sourceCounter"
        $sources += @("--source", "$sourceLabel=$resolved")
        Write-Host "Using source [$sourceLabel]: $resolved"
    }
}

if ($sources.Count -eq 0) {
    throw @"
No source folders found.
Checked defaults:
- $ICloudPath
- $ExternalDPath

Find folders quickly, then rerun with explicit paths:
Get-ChildItem -Path "$env:USERPROFILE","D:\","E:\","F:\" -Directory -Recurse -ErrorAction SilentlyContinue |
  Where-Object { `$_.Name -in @('JF','JF LIFE','JF_LIFE','JF-LIFE','JF_LIFE_Local_Sources','JF LIFE Local Sources') } |
  Select-Object -ExpandProperty FullName

If your drive is shown as 'JF (D:)', rerun with:
powershell -ExecutionPolicy Bypass -File "$PSCommandPath" -ExternalDPath "D:\JF" -RepoDir "D:\JF-ALL-ROUND-CARPENTRY-" -IncludeLarge
"@
}

$linkArgs += $sources
if ($IncludeLarge) {
    $linkArgs += "--include-large"
}
if ($DryRun) {
    $linkArgs += "--dry-run"
}
foreach ($pattern in $IncludePattern) {
    $linkArgs += @("--include", $pattern)
}
foreach ($pattern in $ExcludePattern) {
    $linkArgs += @("--exclude", $pattern)
}
if (-not $NoPush -and -not $DryRun) {
    $linkArgs += @("--git-commit", "--git-push")
}

$runner = Get-PythonRunner
& $runner.Exe @($runner.Prefix + $linkArgs)
if ($LASTEXITCODE -ne 0) {
    throw "Link script failed with exit code $LASTEXITCODE"
}

Write-Host "JF LIFE linking completed."
