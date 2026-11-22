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
7. Commit only generated output and manifest paths unless the user explicitly
   requests another scope.
