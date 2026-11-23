# Repository instructions

- Treat this repository as the JF LIFE file-linking and library website project.
- Keep local source folders read-only. The importer copies into `Library/`; it must
  never modify, delete, or move files at a source path.
- Never add personal source paths, secrets, credentials, or local drive roots to
  generated public manifests or documentation.
- Preserve the Windows PowerShell and batch launchers as first-class entry points.
- Keep the generated manifest compatible with `App/Library-Index.html`.
- Validate Python changes with `python -m unittest discover -s tests -v`.
- Keep Git operations scoped to generated library and manifest paths. Do not
  commit unrelated staged files.
