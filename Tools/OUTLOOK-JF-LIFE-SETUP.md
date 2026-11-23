# Outlook to JF LIFE setup

[← Back to main README and repository map](../README.md) · Related: [iPhone and iCloud handoff](IPHONE-JF-LIFE-SETUP.md) · [Mobile app shell](../mobile/jf-life-mobile/README.md)

This connector updates the real Outlook mailbox through Microsoft Graph, but the
OAuth sign-in and all review files stay on the Windows PC. It does not require a
client secret and never commits tokens.

## Create the local public-client application

In Microsoft Entra ID:

1. Open **App registrations > New registration**.
2. Choose **Accounts in any organizational directory and personal Microsoft
   accounts** if Outlook is a mixed personal/work account. Otherwise choose the
   account type required by your organization.
3. Under **Authentication**, add a **Mobile and desktop applications** platform
   and enable **Allow public client flows**.
4. Add delegated Microsoft Graph permissions:
   - `User.Read`
   - `Contacts.Read`
   - `Mail.ReadWrite`
   - `MailboxSettings.ReadWrite`
   - `Calendars.ReadWrite`
   - `Tasks.ReadWrite`
5. Grant consent as required by your organization.
6. Copy only the **Application (client) ID**. Do not create or save a client
   secret in this repository.

## Connect and build a review plan

Run from the repository's Windows folder:

```powershell
.\scripts\RUN-JF-LIFE-LOCAL.ps1 `
  -ExternalDPath "D:\" `
  -ICloudPath "$env:USERPROFILE\iCloudDrive\JF LIFE" `
  -OutlookClientId "<APPLICATION-CLIENT-ID>"
```

The script prints a Microsoft sign-in URL and short device code. Open that URL on
the same trusted PC and sign in. Do not paste the code or any token into chat.

The connector creates:

- `%LOCALAPPDATA%\JF LIFE\inventory.json`
- `%LOCALAPPDATA%\JF LIFE\recovery-plan.json`
- `%LOCALAPPDATA%\JF LIFE\outlook-state.json`
- `%LOCALAPPDATA%\JF LIFE\outlook-actions.json`
- `%LOCALAPPDATA%\JF LIFE\JF-LIFE-Dashboard.html`

These files are private and must remain outside Git.

## Review Outlook actions

The generated plan proposes only safe, reviewable actions:

- add `JF LIFE - Business` or `JF LIFE - Course` categories;
- mark selected old unread mail as read;
- create an Outlook To Do task for flagged mail;
- archive selected old, read, JF-related mail.

The same private snapshot reports possible Outlook contact duplicates. It does not
merge or delete contacts automatically because name/email data can be ambiguous.

Open `outlook-actions.json`, review the `summary`, and change each desired action
from `"approved": false` to `"approved": true`. Save the file locally. Then do a
dry run:

```powershell
.\scripts\RUN-JF-LIFE-LOCAL.ps1
```

The existing reviewed plan is preserved. Apply only approved actions:

```powershell
.\scripts\RUN-JF-LIFE-LOCAL.ps1 -ApplyOutlookActions
```

Use `-RefreshOutlookPlan` only when you intentionally want to discard the current
review file and build a new proposal.

## Verify Outlook, JF LIFE, and iPhone

1. Confirm the new category and task in the Outlook desktop app.
2. Confirm the Outlook account on iPhone shows the same categories, mail state,
   calendar, and Microsoft To Do task.
3. Confirm a test file in iCloud Drive appears under the private local inventory.
4. Optionally build generated public files with `-BuildLibrary`; use
   `-PublishLibrary` only after reviewing the selected file list.
5. Do not publish `%LOCALAPPDATA%\JF LIFE`, Outlook JSON, or tokens.
