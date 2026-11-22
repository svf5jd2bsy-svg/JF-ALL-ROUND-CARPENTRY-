# JF ALL ROUND CARPENTRY / JF LIFE

This repository now includes a local sync tool to link files from your computer (for example iCloud + `D:` external drive), sort them into library areas, generate a manifest, and push to GitHub.

> This tool runs on your computer. It does not remotely control your PC.

## What this does

- Scans local source folders you choose
- Copies files into `Library/` grouped as:
  - `Business`
  - `Personal`
  - `Course`
  - `Needs-review`
- Generates `Organisation/latest/File-Library-Manifest.json`
- Optionally commits and pushes to GitHub

## Quick start (Windows PowerShell)

Run from this repository folder on your own PC:

```powershell
python .\scripts\jf_life_link.py `
  --source "iCloud=C:\Users\<you>\iCloudDrive\JF LIFE" `
  --source "ExternalD=D:\JF LIFE" `
  --git-commit `
  --git-push
```

Or use the helper batch file:

```bat
scripts\RUN-JF-LINK.cmd
```

Or PowerShell helper:

```powershell
.\scripts\connect_jf_life.ps1 -Push
```

If Git is not installed yet, run this from **any** PowerShell window to auto-install Git (via winget), clone/update the repo, and run the linker:

```powershell
$u = "https://raw.githubusercontent.com/svf5jd2bsy-svg/JF-ALL-ROUND-CARPENTRY-/main/scripts/bootstrap_windows.ps1"
$f = Join-Path $env:TEMP "bootstrap_windows.ps1"
Invoke-WebRequest $u -OutFile $f
powershell -ExecutionPolicy Bypass -File $f -IncludeLarge
```

If your folders are in non-default paths, pass them explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File $f `
  -ICloudPath "C:\Users\<you>\OneDrive\iCloud\JF LIFE" `
  -ExternalDPath "E:\Backups\JF LIFE" `
  -IncludeLarge
```

## Useful options

```powershell
# Preview only (no copy)
python .\scripts\jf_life_link.py --source "ExternalD=D:\JF LIFE" --dry-run

# Include files larger than 95 MB (disabled by default to avoid GitHub upload failures)
python .\scripts\jf_life_link.py --source "ExternalD=D:\JF LIFE" --include-large
```

## App index

Open `App/Library-Index.html` locally or on GitHub Pages.  
It reads the manifest file and provides search/filter for your linked files.

## Important

This repository is currently public. If you need private-only data handling, make the repo private before pushing personal files.