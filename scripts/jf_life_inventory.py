#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from jf_life_link import (
    REPO_ROOT,
    SKIP_DIR_NAMES,
    classify_area,
    parse_source,
    validate_source_labels,
)
from jf_life_local import (
    atomic_write_json,
    fail,
    resolve_state_dir,
    resolve_state_file,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a private, read-only inventory of JF LIFE files."
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="Local source folder to inventory. Repeat for D:, iCloud, and other folders.",
    )
    parser.add_argument(
        "--state-dir",
        default="",
        help="Private local state folder. Must be outside the repository.",
    )
    parser.add_argument(
        "--output",
        default="inventory.json",
        help="Inventory filename inside the private state folder.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Only inventory source-relative paths matching this glob.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude source-relative paths matching this glob.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and print a summary without writing private state.",
    )
    return parser.parse_args()


def is_match(path: str, patterns: list[str]) -> bool:
    value = path.casefold()
    return any(fnmatch.fnmatch(value, pattern.casefold()) for pattern in patterns)


def safe_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"File is outside its source root: {path}") from exc


def iter_files(
    root: Path, state_dir: Path
) -> tuple[list[Path], list[dict[str, str]]]:
    files: list[Path] = []
    errors: list[dict[str, str]] = []

    def on_walk_error(error: OSError) -> None:
        errors.append(
            {
                "reason": "walk_failed",
                "path": str(Path(error.filename)) if error.filename else str(root),
                "error": error.strerror or type(error).__name__,
            }
        )

    for current_root, dir_names, file_names in os.walk(
        root, followlinks=False, onerror=on_walk_error
    ):
        current_path = Path(current_root)
        kept_dirs: list[str] = []
        for name in dir_names:
            candidate = current_path / name
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if (
                name in SKIP_DIR_NAMES
                or name.startswith("$RECYCLE.BIN")
                or candidate.is_symlink()
                or resolved == REPO_ROOT.resolve()
                or REPO_ROOT.resolve() in resolved.parents
                or resolved == state_dir
                or state_dir in resolved.parents
            ):
                continue
            kept_dirs.append(name)
        dir_names[:] = kept_dirs
        for name in file_names:
            candidate = current_path / name
            if not candidate.is_symlink():
                files.append(candidate)
    files.sort()
    return files, errors


def build_duplicate_groups(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in files:
        by_hash[str(record["sha256"])].append(record)

    groups: list[dict[str, Any]] = []
    for digest, candidates in by_hash.items():
        if len(candidates) < 2:
            continue
        ordered = sorted(
            candidates,
            key=lambda item: (
                str(item["source_label"]).casefold(),
                str(item["relative_path"]).casefold(),
            ),
        )
        size_bytes = int(ordered[0]["size_bytes"])
        groups.append(
            {
                "group_id": digest,
                "sha256": digest,
                "size_bytes": size_bytes,
                "candidate_count": len(ordered),
                "recoverable_bytes": size_bytes * (len(ordered) - 1),
                "recommended_keep": ordered[0]["record_id"],
                "review_required": True,
                "candidate_ids": [item["record_id"] for item in ordered],
            }
        )
    groups.sort(key=lambda item: (-int(item["recoverable_bytes"]), str(item["group_id"])))
    return groups


def create_inventory(
    source_specs: list[Any], state_dir: Path, includes: list[str], excludes: list[str]
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    sequence = 0

    for source in source_specs:
        source_root = source.root.expanduser().resolve()
        if not source_root.exists() or not source_root.is_dir():
            skipped.append(
                {
                    "source_label": source.label,
                    "path": str(source_root),
                    "reason": "source_missing",
                }
            )
            source_results.append(
                {
                    "label": source.label,
                    "root": str(source_root),
                    "status": "missing",
                }
            )
            continue

        source_files, walk_errors = iter_files(source_root, state_dir)
        skipped.extend(
            {"source_label": source.label, **error} for error in walk_errors
        )
        source_seen = 0
        source_linked = 0
        for path in source_files:
            source_seen += 1
            relative_path = safe_relative(path, source_root)
            if excludes and is_match(relative_path, excludes):
                skipped.append(
                    {
                        "source_label": source.label,
                        "path": str(path),
                        "relative_path": relative_path,
                        "reason": "excluded",
                    }
                )
                continue
            if includes and not is_match(relative_path, includes):
                skipped.append(
                    {
                        "source_label": source.label,
                        "path": str(path),
                        "relative_path": relative_path,
                        "reason": "not_included",
                    }
                )
                continue

            try:
                stat = path.stat()
                digest = sha256_file(path)
            except OSError as exc:
                skipped.append(
                    {
                        "source_label": source.label,
                        "path": str(path),
                        "relative_path": relative_path,
                        "reason": "read_failed",
                        "error": exc.strerror or type(exc).__name__,
                    }
                )
                continue

            sequence += 1
            record: dict[str, Any] = {
                "record_id": f"file-{sequence:08d}",
                "source_label": source.label,
                "relative_path": relative_path,
                "absolute_path": str(path),
                "area": classify_area(source.label, Path(relative_path)),
                "size_bytes": stat.st_size,
                "modified_utc": dt.datetime.fromtimestamp(
                    stat.st_mtime, tz=dt.timezone.utc
                ).isoformat(),
                "sha256": digest,
            }
            records.append(record)
            source_linked += 1

        source_results.append(
            {
                "label": source.label,
                "root": str(source_root),
                "status": "processed",
                "files_seen": source_seen,
                "files_inventoried": source_linked,
            }
        )

    records.sort(key=lambda item: str(item["record_id"]))
    duplicate_groups = build_duplicate_groups(records)
    bytes_seen = sum(int(item["size_bytes"]) for item in records)
    duplicate_bytes = sum(
        int(group["recoverable_bytes"]) for group in duplicate_groups
    )
    return {
        "schema_version": 1,
        "scope": "private-local-only",
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "sources": source_results,
        "summary": {
            "sources_total": len(source_specs),
            "files_inventoried": len(records),
            "bytes_inventoried": bytes_seen,
            "duplicate_groups": len(duplicate_groups),
            "duplicate_files": sum(
                int(group["candidate_count"]) - 1 for group in duplicate_groups
            ),
            "recoverable_bytes": duplicate_bytes,
            "files_skipped": len(skipped),
        },
        "files": records,
        "duplicate_groups": duplicate_groups,
        "skipped": skipped,
    }


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
        sources = [parse_source(value) for value in args.source]
        validate_source_labels(sources)
        inventory = create_inventory(sources, state_dir, args.include, args.exclude)
    except (argparse.ArgumentTypeError, OSError, ValueError) as exc:
        return fail(str(exc))

    print(json.dumps(inventory["summary"], indent=2))
    if args.dry_run:
        print("Dry run complete. Private inventory was not written.")
        return 0

    try:
        output_path = resolve_state_file(state_dir, args.output)
    except ValueError as exc:
        return fail(str(exc))
    atomic_write_json(output_path, inventory)
    print(f"Private inventory written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
