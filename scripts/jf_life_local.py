#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def default_state_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "JF LIFE"
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "jf-life"
    return Path.home() / ".local" / "state" / "jf-life"


def resolve_state_dir(value: str | None = None) -> Path:
    state_dir = Path(value).expanduser() if value else default_state_dir()
    state_dir = state_dir.resolve()
    repo_root = REPO_ROOT.resolve()
    if (
        state_dir == repo_root
        or repo_root in state_dir.parents
        or state_dir in repo_root.parents
    ):
        raise ValueError(
            f"Local state must be separate from the public repository: {state_dir}"
        )
    return state_dir


def resolve_state_file(state_dir: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("State file must be a relative path inside the private folder.")
    resolved = (state_dir / relative).resolve()
    try:
        resolved.relative_to(state_dir.resolve())
    except ValueError as exc:
        raise ValueError(
            "State file must stay inside the private folder."
        ) from exc
    return resolved


def ensure_private_file(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output_file:
            json.dump(value, output_file, indent=2, ensure_ascii=False)
            output_file.write("\n")
        os.replace(temporary_path, path)
        ensure_private_file(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str, exit_code: int = 2) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return exit_code
