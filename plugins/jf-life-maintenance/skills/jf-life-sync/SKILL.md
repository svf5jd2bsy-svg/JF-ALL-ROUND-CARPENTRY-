---
name: jf-life-sync
description: Link and validate JF LIFE source files without exposing local paths or breaking manifest URLs.
---

When handling a JF LIFE linking request:

1. Read `README.md`, `scripts/jf_life_link.py`, the Windows launchers, and
   `App/Library-Index.html` before editing.
2. Treat every configured source as read-only. Copy accepted files into the
   generated library; never delete or move source data.
3. Keep absolute local source paths out of the manifest and generated site.
4. For deduplicated files, point the manifest and browser URL at the copied
   canonical target.
5. Run `python -m unittest discover -s tests -v`.
6. Exercise the linker with temporary sources and confirm the copied files and
   manifest records agree.
7. For full-device requests, run `RUN-JF-LIFE-LOCAL.ps1` concepts: private
   inventory, duplicate recovery report, local Microsoft Graph sign-in, and an
   approval-only Outlook plan. Source files are never moved or deleted.
8. Keep Outlook action plans, OAuth tokens, dashboard state, and local paths
   outside the repository. Apply only action records marked `approved=true`.
9. Treat iPhone alarms, widgets, Focus, and Home Screen changes as documented
   manual steps. Use Outlook/iCloud sync rather than claiming cloud device
   control.
10. Commit only generated output and manifest paths unless the user explicitly
    requests another scope.
