#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from jf_life_local import (
    atomic_write_json,
    fail,
    read_json,
    resolve_state_dir,
    resolve_state_file,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review and recovery-copy exact duplicate files without deleting sources."
    )
    parser.add_argument(
        "command",
        choices=("plan", "apply"),
        help="Create a review plan or copy already-approved recovery candidates.",
    )
    parser.add_argument(
        "--state-dir",
        default="",
        help="Private local JF LIFE state folder outside the repository.",
    )
    parser.add_argument(
        "--inventory",
        default="inventory.json",
        help="Private inventory filename in the state folder.",
    )
    parser.add_argument(
        "--plan",
        default="recovery-plan.json",
        help="Review plan filename in the state folder.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="For the apply command, create approved recovery copies.",
    )
    return parser.parse_args()


def build_plan(inventory: dict[str, Any]) -> dict[str, Any]:
    records = {item["record_id"]: item for item in inventory.get("files", [])}
    groups: list[dict[str, Any]] = []
    for group in inventory.get("duplicate_groups", []):
        candidate_ids = list(group.get("candidate_ids", []))
        recommended_keep = group.get("recommended_keep")
        candidates = []
        for record_id in candidate_ids:
            record = records.get(record_id)
            if not record:
                continue
            candidates.append(
                {
                    "record_id": record_id,
                    "absolute_path": record["absolute_path"],
                    "relative_path": record["relative_path"],
                    "source_label": record["source_label"],
                    "sha256": record["sha256"],
                    "size_bytes": record["size_bytes"],
                    "decision": (
                        "keep" if record_id == recommended_keep else "pending"
                    ),
                }
            )
        groups.append(
            {
                "group_id": group["group_id"],
                "sha256": group["sha256"],
                "size_bytes": group["size_bytes"],
                "approved": False,
                "review_note": "",
                "candidates": candidates,
                "recovery_copies": [],
            }
        )
    return {
        "schema_version": 1,
        "scope": "private-local-only",
        "policy": "Sources are read-only. Apply only copies explicitly approved candidates.",
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "groups": groups,
    }


def approved_recovery_copies(
    state_dir: Path, plan: dict[str, Any], apply_changes: bool
) -> tuple[int, list[str]]:
    copied = 0
    warnings: list[str] = []
    for group in plan.get("groups", []):
        if not group.get("approved"):
            continue
        expected_digest = str(group.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            warnings.append("Invalid SHA-256 in approved recovery group; skipped.")
            continue
        for candidate in group.get("candidates", []):
            if candidate.get("decision") != "recovery-copy":
                continue
            source = Path(candidate["absolute_path"])
            if not source.exists() or not source.is_file():
                warnings.append(f"Missing candidate: {source}")
                continue
            actual_digest = sha256_file(source)
            if actual_digest != expected_digest:
                warnings.append(
                    f"Candidate changed after inventory; not copied: {source}"
                )
                continue
            safe_name = source.name.replace("/", "_").replace("\\", "_")
            record_id = str(candidate["record_id"]).replace("/", "_").replace("\\", "_")
            if record_id in ("", ".", ".."):
                warnings.append("Invalid candidate record id; not copied.")
                continue
            destination = (
                state_dir
                / "recovery"
                / expected_digest
                / f"{record_id}-{safe_name}"
            )
            if destination.exists():
                try:
                    destination_digest = sha256_file(destination)
                except OSError:
                    destination_digest = ""
                if destination_digest == expected_digest:
                    continue
                warnings.append(
                    f"Recovery destination changed or is invalid; not overwritten: "
                    f"{destination}"
                )
                continue
            if not apply_changes:
                copied += 1
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            group.setdefault("recovery_copies", []).append(
                {
                    "record_id": candidate["record_id"],
                    "source": str(source),
                    "destination": str(destination),
                    "sha256": actual_digest,
                    "copied_at_utc": dt.datetime.now(
                        tz=dt.timezone.utc
                    ).isoformat(),
                }
            )
            copied += 1
    return copied, warnings


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
        inventory_path = resolve_state_file(state_dir, args.inventory)
        plan_path = resolve_state_file(state_dir, args.plan)
        if args.command == "plan":
            inventory = read_json(inventory_path)
            if not isinstance(inventory, dict):
                return fail("Inventory must contain a JSON object.")
            plan = build_plan(inventory)
            atomic_write_json(plan_path, plan)
            print(
                f"Created {len(plan['groups'])} duplicate review groups at {plan_path}"
            )
            print(
                "Edit decisions and set approved=true locally. Source files remain untouched."
            )
            return 0

        plan = read_json(plan_path)
        if not isinstance(plan, dict):
            return fail("Recovery plan must contain a JSON object.")
        copied, warnings = approved_recovery_copies(state_dir, plan, args.apply)
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        if not args.apply:
            print(
                f"Dry run: {copied} approved candidate copies are ready. "
                "No files were changed."
            )
            return 0
        atomic_write_json(plan_path, plan)
        print(
            f"Created {copied} recovery copies. Original source files were not modified."
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
