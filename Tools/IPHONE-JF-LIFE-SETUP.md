# iPhone and iCloud handoff

[← Back to main README and repository map](../README.md) · Related: [Outlook to JF LIFE setup](OUTLOOK-JF-LIFE-SETUP.md) · [Mobile app shell](../mobile/jf-life-mobile/README.md)

The private data on the phone is not mounted in GitHub or Copilot. Complete these
steps on the iPhone and Windows PC once, then use Outlook and iCloud as the
ongoing connection.

## 1. Enable iCloud file sync

1. On iPhone, open **Settings > Apple Account > iCloud > iCloud Drive** and
   turn on **Sync this iPhone**.
2. In the Windows iCloud app, sign in with the same account and enable
   **iCloud Drive**.
3. In iCloud Drive, create `JF LIFE/Inbox`, `JF LIFE/Review`, and
   `JF LIFE/Complete` if they do not already exist.
4. On the Windows PC, note the local iCloud Drive folder path. The JF LIFE
   local runner will inventory it but will not delete or move files there.

## 2. Use Outlook as the main mail and task view

1. Install Outlook for iOS and Microsoft To Do, then sign in to the same Outlook
   mailbox used on the PC.
2. Enable mail, contacts, calendars, and tasks/reminders for that account in the
   iOS account settings.
3. Create or use these Outlook categories:
   - `JF LIFE - Business`
   - `JF LIFE - Course`
4. Keep a To Do list named **JF LIFE** for items carried from Outlook flags,
   iCloud files, and phone captures.
5. Run the Windows Outlook connector to generate a review plan. Review
   `outlook-actions.json` locally and set `approved: true` only on actions that
   should be applied.

## 3. Add a JF LIFE capture Shortcut

In Apple's **Shortcuts** app, create a shortcut named `Capture to JF LIFE`:

1. Ask for **Business**, **Personal**, or **Course**.
2. Ask for the file, photo, voice note, or typed note.
3. Save files to `iCloud Drive/JF LIFE/Inbox`.
4. For typed notes, append a line containing the local date and chosen area to
   `JF LIFE/Inbox/JF-LIFE-Captures.txt`.
5. Add a reminder to the **JF LIFE** To Do list that reads
   `Review JF LIFE Inbox capture`.
6. Add the shortcut to the Home Screen or Action Button.

Open the shortcut once on the iPhone, then confirm the file appears in the local
iCloud Drive folder on Windows. Do not store passwords, account numbers, or
private email text in a shortcut name.

## 4. Complete phone-only controls manually

Apple does not expose alarms, Focus modes, widgets, or Home Screen layout to this
cloud session. Review these on-device:

- Clock alarms needed for jobs, courses, and follow-ups.
- Calendar alerts that match the related Outlook/JF LIFE task.
- A Home Screen widget for Outlook Calendar and Microsoft To Do.
- A Files widget or Shortcuts widget pointing to `JF LIFE/Inbox`.
- Focus rules so important work alarms and Outlook notifications are not hidden.

## 5. Verify the round trip

1. Run `scripts\RUN-JF-LIFE-LOCAL.cmd` with preview options.
2. Open the generated private `JF-LIFE-Dashboard.html`.
3. Create one safe test file in iCloud Drive from the iPhone.
4. Confirm it appears in the local inventory.
5. Flag one safe test email in Outlook, review its proposed Outlook action, and
   confirm the resulting task in Microsoft To Do on iPhone.
6. Never publish the private dashboard, Outlook token, source inventory, or
   recovery plan.
