# JF LIFE iPhone app shell

[← Back to main README and repository map](../../README.md) · Related: [iPhone and iCloud handoff](../../Tools/IPHONE-JF-LIFE-SETUP.md) · [Companion API source](../../scripts/jf_life_companion_api.py)

This is the iPhone-first app shell that connects to the Windows companion API.

## Start

1. Install Node.js and Expo CLI prerequisites.
2. From this folder:
   ```bash
   npm install
   npm run start
   ```
3. On your iPhone, open the Expo app and load the project.

## Pairing

1. On Windows, run:
   ```powershell
   python scripts/jf_life_companion_api.py --state-dir "%LOCALAPPDATA%\JF LIFE"
   ```
2. Copy the pairing token shown in the Windows companion.
3. Enter companion host + token in the app, then tap **Verify Pairing**.
4. Keep **Live updates every 20s** enabled for continuous summary refresh.

The app can trigger inventory, recovery-plan, Outlook inventory/plan/apply, and
dashboard generation through the companion API.

Enter the Windows JF (D:) path and iCloud JF LIFE path in the app before
running Inventory. The app includes a **Publish library** action; it uses
explicit confirmation and requires the Windows companion to have repository
push access. Keep the repository private before publishing personal files.

Use **Upload iPhone/iCloud files** to choose files or iCloud documents from the
phone. The companion stores uploads only in the private Windows JF LIFE state
directory, where they can be reviewed before publishing.

## Build the real native app

From the Windows PC:

```bat
cd mobile\jf-life-mobile
RUN-MOBILE-BUILD.cmd android
RUN-MOBILE-BUILD.cmd ios
```

Android builds use an APK preview for direct installation. iOS builds require
an Expo/EAS account with Apple signing configured. The native app is separate
from the installable PWA in `App/`.

Alarms, Home Screen widgets, and iOS Messages still require on-device iPhone
configuration; they are not remotely controlled from this app shell.
