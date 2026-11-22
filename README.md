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

The launchers use the Windows Python launcher (`py -3`) when available and fall
back to `python`. To inspect a physical drive before publishing anything, preview
only:

```powershell
.\scripts\connect_jf_life.ps1 `
  -ExternalDPath "D:\" `
  -IncludePattern "*JF LIFE*" `
  -DryRun
```

Pass a comma-separated array such as
`-IncludePattern "*JF LIFE*","*.pdf","*.docx"` for multiple values, or use
`-ExcludePattern` to omit folders such as temporary or backup data. The command
above previews matches and does not copy or push anything; remove `-DryRun` only
after checking the summary.

Physical drives are not mounted inside Copilot or GitHub's cloud environment.
Run that helper on the Windows PC connected to `JF (D:)`; the cloud agent can
then work with the linked files only after the script commits and pushes them.

If Git is not installed yet, run this from **any** PowerShell window to auto-install Git (via winget), clone/update the repo, and run the linker:

```powershell
$u = "https://raw.githubusercontent.com/svf5jd2bsy-svg/JF-ALL-ROUND-CARPENTRY-/main/scripts/bootstrap_windows.ps1"
$f = Join-Path $env:TEMP "bootstrap_windows.ps1"
Invoke-WebRequest $u -OutFile $f
powershell -ExecutionPolicy Bypass -File $f -IncludeLarge
```

When `-ExternalDPath` points to another drive, bootstrap now places/clones the repo on that drive automatically to avoid filling `C:`.

Preview a drive without copying or publishing:

```powershell
powershell -ExecutionPolicy Bypass -File $f `
  -ExternalDPath "D:\" `
  -IncludePattern "*JF LIFE*","*.pdf","*.docx" `
  -DryRun `
  -NoPush
```

If your folders are in non-default paths, pass them explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File $f `
  -ICloudPath "C:\Users\<you>\OneDrive\iCloud\JF LIFE" `
  -ExternalDPath "E:\Backups\JF LIFE" `
  -IncludeLarge
```

If bootstrap says no source folders found, run:

```powershell
Get-ChildItem -Path "$env:USERPROFILE","D:\","E:\","F:\" -Directory -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @('JF','JF LIFE','JF_LIFE','JF-LIFE','JF_LIFE_Local_Sources','JF LIFE Local Sources') } |
  Select-Object -ExpandProperty FullName
```

Then rerun bootstrap with explicit paths from the output.

If your external drive appears as **JF (D:)** and files are at the drive root,
preview it safely. The linker prunes the generated repository folder from the
source walk:

```powershell
powershell -ExecutionPolicy Bypass -File $f `
  -ExternalDPath "D:\" `
  -IncludePattern "*JF LIFE*","*.pdf","*.docx" `
  -DryRun `
  -NoPush
```

If you see `Stopped early: destination disk ran out of space`, keep the repo on a larger drive (for example `D:`) and rerun.

## Useful options

```powershell
# Preview only (no copy)
python .\scripts\jf_life_link.py --source "ExternalD=D:\JF LIFE" --dry-run

# Include files larger than 95 MB (disabled by default to avoid GitHub upload failures)
python .\scripts\jf_life_link.py --source "ExternalD=D:\JF LIFE" --include-large

# Copy only matching files from a drive
python .\scripts\jf_life_link.py `
  --source "ExternalD=D:\" `
  --include "*JF LIFE*" `
  --include "*.pdf" `
  --dry-run
```

## App index

Open `App/Library-Index.html` locally or on GitHub Pages.  
It reads the manifest file and provides search/filter for your linked files. If
you opened the page directly from disk, use **Open a local manifest** to select
`Organisation/latest/File-Library-Manifest.json`. The repository root also links
to the index, so a GitHub Pages root deployment opens the library directly.

## Copilot agents and plugin

This repository includes two automatically discoverable agents in
`.github/agents`, plus the `jf-life-maintenance` Agent Plugin. Copilot in the
cloud reads `.github/copilot/settings.json`, registers the repository as its own
marketplace, and enables that plugin for future tasks once these files are on the
default branch. The plugin packages a focused agent and the `jf-life-sync`
workflow skill under `plugins/jf-life-maintenance`.

The cloud setup workflow installs Python and runs the integration tests before a
task starts. Select **JF Life Maintainer** for implementation work or **JF Life
Reviewer** for a read-only review in the Copilot agent picker.

## Important

This repository is currently public. If you need private-only data handling, make the repo private before pushing personal files.