# JF ALL ROUND CARPENTRY / JF LIFE

This repository now includes a local sync tool to link files from your computer (for example iCloud + `D:` external drive), sort them into library areas, generate a manifest, and push to GitHub.

## Repository map (everything linked)

**Start here**

- [README (this file)](README.md) — full JF LIFE guide
- [Repository entry page](index.html) — redirects to the library index
- [Library web app](App/Library-Index.html) — searchable file library (GitHub Pages ready, installable as an app)
- PWA: [app manifest](App/manifest.webmanifest) · [service worker](App/sw.js) · [icons](App/icons)

**Setup guides (Tools/)**

- [iPhone and iCloud handoff](Tools/IPHONE-JF-LIFE-SETUP.md)
- [Outlook to JF LIFE setup](Tools/OUTLOOK-JF-LIFE-SETUP.md)
- [Local dashboard template](Tools/Local-Dashboard.template.html)
- [Local helper notes](Tools/JF_LIFE_OMG_Start_Local_Helper_2.txt)

**iPhone app shell**

- [JF LIFE mobile app](mobile/jf-life-mobile/README.md) — Expo app shell
- [App source](mobile/jf-life-mobile/App.tsx) · [App config](mobile/jf-life-mobile/app.json) · [Package manifest](mobile/jf-life-mobile/package.json)

**Scripts (scripts/)**

- Linking: [jf_life_link.py](scripts/jf_life_link.py) · [connect_jf_life.ps1](scripts/connect_jf_life.ps1) · [RUN-JF-LINK.cmd](scripts/RUN-JF-LINK.cmd)
- One-click upload: [RUN-JF-UPLOAD.cmd](scripts/RUN-JF-UPLOAD.cmd) · [RUN-JF-UPLOAD.ps1](scripts/RUN-JF-UPLOAD.ps1)
- Bootstrap: [bootstrap_windows.ps1](scripts/bootstrap_windows.ps1)
- Local control centre: [jf_life_local.py](scripts/jf_life_local.py) · [RUN-JF-LIFE-LOCAL.ps1](scripts/RUN-JF-LIFE-LOCAL.ps1) · [RUN-JF-LIFE-LOCAL.cmd](scripts/RUN-JF-LIFE-LOCAL.cmd)
- Live sync: [jf_life_live_sync.py](scripts/jf_life_live_sync.py) · [RUN-JF-LIVE-SYNC.ps1](scripts/RUN-JF-LIVE-SYNC.ps1) · [RUN-JF-LIVE-SYNC.cmd](scripts/RUN-JF-LIVE-SYNC.cmd)
- Windows companion: [jf_life_windows_companion.py](scripts/jf_life_windows_companion.py) · [RUN-JF-WINDOWS-COMPANION.ps1](scripts/RUN-JF-WINDOWS-COMPANION.ps1) · [RUN-JF-WINDOWS-COMPANION.cmd](scripts/RUN-JF-WINDOWS-COMPANION.cmd)
- Companion API (mobile pairing): [jf_life_companion_api.py](scripts/jf_life_companion_api.py)
- Readiness check: [jf_life_readiness.py](scripts/jf_life_readiness.py) · [RUN-JF-READINESS-CHECK.ps1](scripts/RUN-JF-READINESS-CHECK.ps1) · [RUN-JF-READINESS-CHECK.cmd](scripts/RUN-JF-READINESS-CHECK.cmd)
- Outlook connector: [jf_life_outlook.py](scripts/jf_life_outlook.py)
- Dashboard: [jf_life_dashboard.py](scripts/jf_life_dashboard.py)
- Inventory: [jf_life_inventory.py](scripts/jf_life_inventory.py)
- Recovery copies: [jf_life_recovery.py](scripts/jf_life_recovery.py)
- Stripe/Xero integrations: [jf_life_integrations.py](scripts/jf_life_integrations.py)

**Tests (tests/)**

- [Linking](tests/test_jf_life_link.py) · [Local](tests/test_jf_life_local.py) · [Companion API](tests/test_jf_life_companion_api.py) · [Integrations](tests/test_jf_life_integrations.py) · [Readiness](tests/test_jf_life_readiness.py)

**Copilot and AI assistant integration**

- [Repository instructions for Copilot](.github/copilot-instructions.md)
- [Copilot settings (marketplace + plugin)](.github/copilot/settings.json)
- [Agent plugin marketplace](.github/plugin/marketplace.json)
- Agents: [JF Life Maintainer](.github/agents/jf-life-maintainer.agent.md) · [JF Life Reviewer](.github/agents/jf-life-reviewer.agent.md)
- Plugin: [jf-life-maintenance](plugins/jf-life-maintenance/plugin.json) · [maintenance agent](plugins/jf-life-maintenance/com.github.copilot/agents/jf-life-maintenance.agent.md) · [jf-life-sync skill](plugins/jf-life-maintenance/skills/jf-life-sync/SKILL.md)
- Cloud setup workflow: [copilot-setup-steps.yml](.github/workflows/copilot-setup-steps.yml)
- GitHub Pages deploy workflow: [pages.yml](.github/workflows/pages.yml)

> ChatGPT / other assistants: start at this map, then read
> [copilot-instructions.md](.github/copilot-instructions.md) for the project rules.

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

### Install as an app (iPhone, Android, Windows, Mac)

The library is an installable Progressive Web App, not just a webpage:

- **iPhone/iPad:** open the Pages site in Safari, tap **Share > Add to Home
  Screen**. It launches full-screen with the JF LIFE icon and works offline for
  the app shell.
- **Android / Chrome / Edge:** open the site and use **Install app** from the
  browser menu (or the install icon in the address bar).
- The app shell ([manifest](App/manifest.webmanifest) +
  [service worker](App/sw.js)) caches the interface; library data always
  loads fresh from the network when available.

### Upload JF LIFE, iCloud, D:, and ChatGPT sources

On the Windows PC connected to JF (D:) and iCloud, run:

```bat
scripts\RUN-JF-UPLOAD.cmd
```

The launcher inventories D:, iCloud, and ChatGPT exports found under Desktop,
Documents, Downloads, or OneDrive. It creates the private dashboard and
review plan; it does not delete or move source files. Publishing is explicit:

```bat
scripts\RUN-JF-UPLOAD.cmd -PublishLibrary
```

Publishing is blocked while this repository is public. Make the repository
private before publishing personal JF LIFE sources.

## Local Outlook, iPhone, and full-device workflow

Use the Windows companion app shell:

```powershell
.\scripts\RUN-JF-WINDOWS-COMPANION.cmd
```

This is a desktop app window (not a web page) for inventory, Outlook connect,
approval workflow execution, dashboard generation, and companion API hosting.
It also includes **Live updates** controls (one run or looped cadence).

For a quick pairing readiness check (API health + LAN + token presence):

```powershell
.\scripts\RUN-JF-READINESS-CHECK.cmd
```

If LAN health fails, keep the companion running and allow local private-network
access on port 8712 (the checker prints the exact firewall command).

For one-command live sync from Windows:

```powershell
.\scripts\RUN-JF-LIVE-SYNC.cmd `
  -ExternalDPath "D:\" `
  -ICloudPath "$env:USERPROFILE\iCloudDrive\JF LIFE" `
  -IntervalSeconds 300 `
  -Cycles 0
```

This writes per-cycle status to `%LOCALAPPDATA%\JF LIFE\live-sync-status.json`.

Run the review-first local control centre from a Windows PC connected to the
external drive and signed into iCloud:

```powershell
.\scripts\RUN-JF-LIFE-LOCAL.cmd `
  -ExternalDPath "D:\" `
  -ICloudPath "$env:USERPROFILE\iCloudDrive\JF LIFE"
```

This inventories local files, finds exact duplicate groups, creates a
recovery-copy plan, and opens a private dashboard under
`%LOCALAPPDATA%\JF LIFE`. It does not delete or move source files.
Add any other PC folder with repeatable
`-AdditionalSource "Documents=C:\Users\<you>\Documents"` arguments.
After marking a duplicate group's `approved` and candidate `decision` in
`recovery-plan.json`, run with `-ApplyRecoveryCopies` to create a verified backup
copy. The originals remain unchanged, and the existing review plan is preserved
until `-RefreshRecoveryPlan` is supplied.

To connect the real Outlook mailbox, first complete the local Microsoft public
client setup in `Tools/OUTLOOK-JF-LIFE-SETUP.md`, then supply
`-OutlookClientId "<APPLICATION-CLIENT-ID>"`. Device sign-in happens on the PC.
Outlook actions are proposed only until you review the private plan and run with
`-ApplyOutlookActions`.

To carry files and tasks onto the iPhone, follow
`Tools/IPHONE-JF-LIFE-SETUP.md`. Outlook/iCloud sync carries approved mail,
calendar, and To Do changes; alarms, Focus, widgets, and Home Screen placement
require the on-device checklist.

Optionally copy reviewed files into the generated `Library/` with `-BuildLibrary`.
Use `-PublishLibrary` only for an explicitly selected, reviewed set:

```powershell
.\scripts\RUN-JF-LIFE-LOCAL.cmd `
  -ExternalDPath "D:\" `
  -IncludePattern "*JF LIFE*","*.pdf" `
  -BuildLibrary
```

## iPhone app shell

An iPhone-first app shell lives in `mobile/jf-life-mobile` and pairs to the
Windows companion API over your local network.

1. Start companion API from the desktop app or run:
   ```powershell
   python .\scripts\jf_life_companion_api.py --state-dir "$env:LOCALAPPDATA\JF LIFE"
   ```
2. Start mobile app (on a dev machine with Expo):
   ```bash
   cd mobile/jf-life-mobile
   npm install
   npm run start
   ```
3. Open on iPhone via Expo, enter companion host + pairing token, then run
   inventory/recovery/outlook actions from the app.
   The app also supports auto-refresh every 20 seconds after pairing.

## Stripe and Xero connector checks

You can verify live connectivity to Stripe/Xero from local scripts:

```powershell
python .\scripts\jf_life_integrations.py `
  --stripe-api-key "<STRIPE_API_KEY>" `
  --xero-access-token "<XERO_ACCESS_TOKEN>" `
  --xero-tenant-id "<XERO_TENANT_ID>" `
  --json
```

For continuous checks, pass these values to `RUN-JF-LIVE-SYNC.cmd`; each cycle
records the connector status in `live-sync-status.json`.

> Keep API tokens local (Windows environment variables or secret manager). Do not commit them.

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