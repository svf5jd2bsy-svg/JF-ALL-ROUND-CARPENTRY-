# JF LIFE iPhone app shell

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

The app can trigger inventory, recovery-plan, Outlook inventory/plan/apply, and
dashboard generation through the companion API.
