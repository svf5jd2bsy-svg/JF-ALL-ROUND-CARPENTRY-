#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = Path("Library")
DEFAULT_MANIFEST_PATH = Path("Organisation/latest/File-Library-Manifest.json")
DEFAULT_MAX_FILE_BYTES = 95 * 1024 * 1024
SKIP_DIR_NAMES = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".idea", ".vscode"}

BUSINESS_HINTS = (
    "business",
    "company",
    "accounts",
    "account",
    "invoice",
    "quote",
    "job",
    "work",
    "payroll",
    "bas",
    "gst",
    "abn",
)
PERSONAL_HINTS = (
    "personal",
    "private",
    "family",
    "medical",
    "tax",
    "contacts",
    "messages",
    "photos",
)
COURSE_HINTS = ("course", "training", "tafe", "evr", "assessment", "certificate", "apprentice")


@dataclass(frozen=True)
class SourceSpec:
    label: str
    root: Path


def normalize_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    return cleaned or "source"


def parse_source(value: str) -> SourceSpec:
    if "=" in value:
        raw_label, raw_path = value.split("=", 1)
        label = normalize_label(raw_label)
        path_text = raw_path.strip()
    else:
        path_text = value.strip()
        label = normalize_label(Path(path_text).name)
    if not path_text:
        raise argparse.ArgumentTypeError(f"Invalid source '{value}'. Expected PATH or NAME=PATH.")
    return SourceSpec(label=label, root=Path(path_text).expanduser())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Link JF LIFE files from local folders into this repository."
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        metavar="PATH|NAME=PATH",
        help="Source folder to import. Repeat for iCloud, D drive, etc.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Relative path in repo where linked files are copied (default: Library).",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Relative path for generated manifest JSON.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob pattern to exclude (match against source-relative path). Repeat as needed.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Only include source-relative paths matching this glob. Repeat for multiple patterns.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan only; no file copies, no manifest write, no git changes.",
    )
    parser.add_argument(
        "--dedupe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip copying duplicate files based on SHA256 (default: enabled).",
    )
    parser.add_argument(
        "--include-large",
        action="store_true",
        help="Include files larger than 95MB. By default these are skipped to avoid GitHub push failures.",
    )
    parser.add_argument(
        "--git-commit",
        action="store_true",
        help="Create a git commit after linking files.",
    )
    parser.add_argument(
        "--git-push",
        action="store_true",
        help="Push to origin after processing (and optional commit).",
    )
    parser.add_argument(
        "--branch",
        default="",
        help="Branch name to push when --git-push is used (default: current branch).",
    )
    parser.add_argument(
        "--commit-message",
        default="Link JF LIFE sources and refresh manifest",
        help="Commit message used with --git-commit.",
    )
    return parser.parse_args()


def resolve_repo_path(value: str, description: str) -> Path:
    candidate = (REPO_ROOT / Path(value)).resolve()
    try:
        relative = candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"{description} must stay inside the repository: {value}") from exc
    if not relative.parts:
        raise ValueError(f"{description} cannot be the repository root.")
    return candidate


def validate_source_labels(sources: list[SourceSpec]) -> None:
    labels: dict[str, str] = {}
    for source in sources:
        key = source.label.casefold()
        if key in labels and labels[key] != str(source.root):
            raise ValueError(
                f"Source label '{source.label}' is used by more than one folder. "
                "Choose a unique --source label."
            )
        labels[key] = str(source.root)


def validate_source_destinations(sources: list[SourceSpec], destinations: list[Path]) -> None:
    for source in sources:
        source_path = source.root.resolve()
        if is_within(source_path, REPO_ROOT):
            raise ValueError(
                f"Source '{source.label}' is inside the repository. "
                "Choose a local source folder outside the generated destination."
            )
        for destination in destinations:
            try:
                source_path.relative_to(destination)
            except ValueError:
                continue
            raise ValueError(
                f"Source '{source.label}' overlaps a generated destination. "
                "Choose separate source and output locations."
            )


def should_exclude(rel_path: str, patterns: list[str]) -> bool:
    rel_lower = rel_path.lower()
    for pattern in patterns:
        if fnmatch.fnmatch(rel_lower, pattern.lower()):
            return True
    return False


def should_include(rel_path: str, patterns: list[str]) -> bool:
    return not patterns or any(fnmatch.fnmatch(rel_path.lower(), pattern.lower()) for pattern in patterns)


def os_error_text(exc: OSError) -> str:
    message = exc.strerror or type(exc).__name__
    return f"{type(exc).__name__}: {message}"


def classify_area(source_label: str, rel_path: Path) -> str:
    text = " / ".join([source_label.lower(), *[part.lower() for part in rel_path.parts]])
    if any(hint in text for hint in BUSINESS_HINTS):
        return "Business"
    if any(hint in text for hint in COURSE_HINTS):
        return "Course"
    if any(hint in text for hint in PERSONAL_HINTS):
        return "Personal"
    return "Needs-review"


def iter_files(root: Path) -> list[Path]:
    output: list[Path] = []
    for current_root, dir_names, file_names in os.walk(root):
        current_path = Path(current_root)
        dir_names[:] = [
            name
            for name in dir_names
            if name not in SKIP_DIR_NAMES
            and not name.startswith("$RECYCLE.BIN")
            and not is_within(current_path / name, REPO_ROOT)
        ]
        for name in file_names:
            output.append(current_path / name)
    output.sort()
    return output


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def run_git_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, check=True, capture_output=True)


def get_current_branch() -> str:
    result = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip()


def stage_commit_push(
    output_root_rel: Path, manifest_rel: Path, do_commit: bool, do_push: bool, branch: str, message: str
) -> None:
    subprocess.run(
        ["git", "--no-pager", "add", output_root_rel.as_posix(), manifest_rel.as_posix()],
        check=True,
    )
    staged = run_git_command(
        [
            "git",
            "--no-pager",
            "diff",
            "--cached",
            "--name-only",
            "--",
            output_root_rel.as_posix(),
            manifest_rel.as_posix(),
        ]
    ).stdout.strip()
    if not staged:
        print("No git changes to commit.")
        return
    if do_commit:
        subprocess.run(
            [
                "git",
                "--no-pager",
                "commit",
                "-m",
                message,
                "--",
                output_root_rel.as_posix(),
                manifest_rel.as_posix(),
            ],
            check=True,
        )
    if do_push:
        push_branch = branch or get_current_branch()
        subprocess.run(["git", "--no-pager", "push", "origin", push_branch], check=True)


def main() -> int:
    args = parse_args()
    os.chdir(REPO_ROOT)

    try:
        output_root_rel = Path(args.output_root)
        manifest_rel = Path(args.manifest)
        output_root_abs = resolve_repo_path(args.output_root, "Output root")
        manifest_abs = resolve_repo_path(args.manifest, "Manifest path")
        source_specs = [parse_source(value) for value in args.source]
        validate_source_labels(source_specs)
        validate_source_destinations(source_specs, [output_root_abs, manifest_abs])
    except (argparse.ArgumentTypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    max_file_bytes = sys.maxsize if args.include_large else DEFAULT_MAX_FILE_BYTES
    hash_to_target: dict[str, str] = {}
    file_records: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    files_seen = 0
    files_copied = 0
    files_deduped = 0
    bytes_copied = 0

    source_results: list[dict[str, object]] = []
    stop_processing = False
    stop_reason = ""

    for source in source_specs:
        if stop_processing:
            break
        source_root = source.root
        if not source_root.exists() or not source_root.is_dir():
            skipped.append(
                {
                    "source_label": source.label,
                    "reason": "source_missing",
                }
            )
            source_results.append(
                {
                    "label": source.label,
                    "status": "missing",
                    "files_seen": 0,
                }
            )
            continue

        source_seen = 0
        source_files = iter_files(source_root)
        for absolute_file in source_files:
            if stop_processing:
                break
            source_seen += 1
            files_seen += 1
            rel_path = absolute_file.relative_to(source_root)
            rel_posix = rel_path.as_posix()

            if is_within(absolute_file, REPO_ROOT):
                skipped.append(
                    {
                        "source_label": source.label,
                        "relative_path": rel_posix,
                        "reason": "inside_repo_skipped",
                    }
                )
                continue

            if should_exclude(rel_posix, args.exclude):
                skipped.append(
                    {
                        "source_label": source.label,
                        "relative_path": rel_posix,
                        "reason": "excluded",
                    }
                )
                continue

            if not should_include(rel_posix, args.include):
                skipped.append(
                    {
                        "source_label": source.label,
                        "relative_path": rel_posix,
                        "reason": "not_included",
                    }
                )
                continue

            try:
                stat = absolute_file.stat()
            except OSError as exc:
                skipped.append(
                    {
                        "source_label": source.label,
                        "relative_path": rel_posix,
                        "reason": "stat_failed",
                        "error": os_error_text(exc),
                    }
                )
                continue

            if stat.st_size > max_file_bytes:
                skipped.append(
                    {
                        "source_label": source.label,
                        "relative_path": rel_posix,
                        "reason": "file_too_large",
                        "size_bytes": stat.st_size,
                        "size_limit_bytes": max_file_bytes,
                    }
                )
                continue

            try:
                digest = sha256_file(absolute_file)
            except OSError as exc:
                skipped.append(
                    {
                        "source_label": source.label,
                        "relative_path": rel_posix,
                        "reason": "hash_failed",
                        "error": os_error_text(exc),
                    }
                )
                continue

            area = classify_area(source.label, rel_path)
            target_rel = Path(area) / source.label / rel_path
            target_posix = target_rel.as_posix()

            duplicate_of = ""
            if args.dedupe and digest in hash_to_target:
                duplicate_of = hash_to_target[digest]
                files_deduped += 1
            else:
                target_abs = output_root_abs / target_rel
                try:
                    if not args.dry_run:
                        target_abs.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(absolute_file, target_abs)
                except OSError as exc:
                    skipped.append(
                        {
                            "source_label": source.label,
                            "relative_path": rel_posix,
                            "reason": "copy_failed",
                            "error": os_error_text(exc),
                            "target_path": target_posix,
                        }
                    )
                    if getattr(exc, "winerror", None) == 112 or getattr(exc, "errno", None) == 28:
                        stop_processing = True
                        stop_reason = "disk_full"
                    continue
                hash_to_target[digest] = target_posix
                files_copied += 1
                bytes_copied += stat.st_size

            linked_target = duplicate_of or target_posix

            file_records.append(
                {
                    "source_label": source.label,
                    "relative_path": rel_posix,
                    "area": area,
                    "target_path": linked_target,
                    "size_bytes": stat.st_size,
                    "modified_utc": dt.datetime.fromtimestamp(
                        stat.st_mtime, tz=dt.timezone.utc
                    ).isoformat(),
                    "sha256": digest,
                    "deduplicated_to": duplicate_of or None,
                }
            )

        source_status = "processed"
        if stop_processing and stop_reason == "disk_full":
            source_status = "aborted_disk_full"
        source_results.append(
            {
                "label": source.label,
                "status": source_status,
                "files_seen": source_seen,
            }
        )

    file_records.sort(key=lambda item: (str(item["area"]), str(item["target_path"])))

    manifest_data = {
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "output_root": output_root_rel.as_posix(),
        "summary": {
            "sources_total": len(source_specs),
            "files_seen": files_seen,
            "files_linked": files_copied,
            "files_deduplicated": files_deduped,
            "files_skipped": len(skipped),
            "bytes_linked": bytes_copied,
            "aborted_reason": stop_reason or None,
        },
        "sources": source_results,
        "files": file_records,
        "skipped": skipped,
    }

    if args.dry_run:
        print(json.dumps(manifest_data["summary"], indent=2))
        print("Dry run complete. No files copied and no manifest written.")
        return 0

    manifest_abs.parent.mkdir(parents=True, exist_ok=True)
    with manifest_abs.open("w", encoding="utf-8") as output_file:
        json.dump(manifest_data, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")

    print(json.dumps(manifest_data["summary"], indent=2))
    if stop_reason == "disk_full":
        print(
            "Stopped early: destination disk ran out of space. "
            "Free space or run from a larger drive, then rerun."
        )
    print(f"Manifest written to {manifest_rel.as_posix()}")

    if stop_processing:
        return 1

    if args.git_commit or args.git_push:
        stage_commit_push(
            output_root_rel=output_root_rel,
            manifest_rel=manifest_rel,
            do_commit=True,
            do_push=args.git_push,
            branch=args.branch,
            message=args.commit_message,
        )
        print("Git stage/commit/push complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
