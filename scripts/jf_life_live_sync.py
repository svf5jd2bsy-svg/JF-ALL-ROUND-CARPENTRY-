#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path

from jf_life_integrations import stripe_status, xero_status
from jf_life_local import atomic_write_json, fail, resolve_state_dir

import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(script: str, *arguments: str) -> tuple[int, str, str]:
    command = [sys.executable, str(REPO_ROOT / script), *arguments]
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )
    return completed.returncode, completed.stdout, completed.stderr


def source_arguments(source_specs: list[str]) -> list[str]:
    args: list[str] = []
    for source in source_specs:
        value = source.strip()
        if value:
            args += ["--source", value]
    return args


def list_arguments(name: str, values: list[str]) -> list[str]:
    args: list[str] = []
    for value in values:
        item = value.strip()
        if item:
            args += [name, item]
    return args


def run_cycle(args: argparse.Namespace, cycle_index: int, state_dir: Path) -> dict:
    started_at = time.time()
    sources = source_arguments(args.source)
    if not sources:
        raise ValueError("At least one --source Label=Path is required.")
    filters = list_arguments("--include", args.include) + list_arguments("--exclude", args.exclude)
    steps: list[dict] = []

    def record_step(name: str, script: str, *arguments: str) -> bool:
        code, stdout, stderr = run_python(script, *arguments)
        steps.append(
            {
                "name": name,
                "code": code,
                "ok": code == 0,
                "stdout_tail": stdout[-4000:],
                "stderr_tail": stderr[-4000:],
            }
        )
        return code == 0

    inventory_ok = record_step(
        "inventory",
        "scripts/jf_life_inventory.py",
        "--state-dir",
        str(state_dir),
        *sources,
        *filters,
    )
    recovery_plan_ok = record_step(
        "recovery-plan", "scripts/jf_life_recovery.py", "plan", "--state-dir", str(state_dir)
    )
    recovery_apply_args = ["apply", "--state-dir", str(state_dir)]
    if args.apply_recovery_copies:
        recovery_apply_args.append("--apply")
    recovery_apply_ok = record_step("recovery-apply", "scripts/jf_life_recovery.py", *recovery_apply_args)

    outlook_ok = True
    if args.outlook_client_id.strip():
        outlook_ok = record_step(
            "outlook-connect",
            "scripts/jf_life_outlook.py",
            "--state-dir",
            str(state_dir),
            "connect",
            "--client-id",
            args.outlook_client_id.strip(),
        )
    if (state_dir / "outlook-config.json").exists() or args.outlook_client_id.strip():
        outlook_ok = (
            record_step(
                "outlook-inventory",
                "scripts/jf_life_outlook.py",
                "--state-dir",
                str(state_dir),
                "inventory",
            )
            and record_step(
                "outlook-plan",
                "scripts/jf_life_outlook.py",
                "--state-dir",
                str(state_dir),
                "plan",
                "--all-unread",
            )
            and record_step(
                "outlook-apply",
                "scripts/jf_life_outlook.py",
                "--state-dir",
                str(state_dir),
                "apply",
                *(["--apply"] if args.apply_outlook_actions else []),
            )
            and outlook_ok
        )

    dashboard_ok = record_step(
        "dashboard", "scripts/jf_life_dashboard.py", "--state-dir", str(state_dir)
    )

    integration_status = {
        "stripe": stripe_status(args.stripe_api_key),
        "xero": xero_status(args.xero_access_token, args.xero_tenant_id),
    }
    integration_status["ok"] = bool(
        (not integration_status["stripe"]["configured"] or integration_status["stripe"]["ok"])
        and (not integration_status["xero"]["configured"] or integration_status["xero"]["ok"])
    )
    steps.append({"name": "integrations", "ok": integration_status["ok"], "status": integration_status})

    finished_at = time.time()
    status = {
        "cycle": cycle_index,
        "started_at_epoch": started_at,
        "finished_at_epoch": finished_at,
        "duration_seconds": round(finished_at - started_at, 2),
        "steps": steps,
        "ok": bool(
            inventory_ok
            and recovery_plan_ok
            and recovery_apply_ok
            and dashboard_ok
            and outlook_ok
            and integration_status["ok"]
        ),
    }
    atomic_write_json(state_dir / "live-sync-status.json", status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Runs JF LIFE live update cycles for inventory, Outlook, dashboard, and integrations."
    )
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--outlook-client-id", default="")
    parser.add_argument("--apply-recovery-copies", action="store_true")
    parser.add_argument("--apply-outlook-actions", action="store_true")
    parser.add_argument("--stripe-api-key", default="")
    parser.add_argument("--xero-access-token", default="")
    parser.add_argument("--xero-tenant-id", default="")
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--cycles", type=int, default=0, help="0 means run forever.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
    except (OSError, ValueError) as exc:
        return fail(str(exc))

    cycle = 1
    while True:
        try:
            status = run_cycle(args, cycle, state_dir)
        except ValueError as exc:
            return fail(str(exc))
        print(f"Cycle {cycle}: {'OK' if status['ok'] else 'FAILED'}")
        if args.cycles > 0 and cycle >= args.cycles:
            return 0 if status["ok"] else 1
        cycle += 1
        time.sleep(max(args.interval_seconds, 10))


if __name__ == "__main__":
    raise SystemExit(main())
