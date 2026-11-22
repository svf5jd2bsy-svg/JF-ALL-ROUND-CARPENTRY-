#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from jf_life_local import (
    atomic_write_json,
    ensure_private_file,
    fail,
    read_json,
    resolve_state_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "Tools" / "Local-Dashboard.template.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a private local JF LIFE control-centre dashboard."
    )
    parser.add_argument(
        "--state-dir",
        default="",
        help="Private local state folder outside the repository.",
    )
    return parser.parse_args()


def optional_json(state_dir: Path, name: str, fallback: Any) -> Any:
    path = state_dir / name
    if not path.exists():
        return fallback
    value = read_json(path)
    return value


def dashboard_state(state_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": "private-local-only",
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "inventory": optional_json(state_dir, "inventory.json", {}),
        "recovery_plan": optional_json(state_dir, "recovery-plan.json", {}),
        "outlook": optional_json(state_dir, "outlook-state.json", {}),
        "outlook_actions": optional_json(state_dir, "outlook-actions.json", {}),
    }


def render_dashboard(state: dict[str, Any]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    marker = "/*__JF_LIFE_STATE__*/"
    if marker not in template:
        raise ValueError("Dashboard template marker is missing.")
    serialized = (
        json.dumps(state, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return template.replace(marker, serialized)


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
        state = dashboard_state(state_dir)
        atomic_write_json(state_dir / "dashboard-state.json", state)
        output_path = state_dir / "JF-LIFE-Dashboard.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_dashboard(state), encoding="utf-8")
        ensure_private_file(output_path)
        print(f"Private local dashboard written to {output_path}")
        print("Open that local file on this PC. Do not publish or upload it.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
