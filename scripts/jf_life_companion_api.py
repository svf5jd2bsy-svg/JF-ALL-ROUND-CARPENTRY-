#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

try:
    from jf_life_local import fail, read_json, resolve_state_dir
except ModuleNotFoundError:  # pragma: no cover - package-style import fallback
    from scripts.jf_life_local import fail, read_json, resolve_state_dir

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


def ensure_pairing_token(state_dir: Path, provided_token: str = "") -> str:
    token_path = state_dir / "pairing-token.txt"
    if provided_token:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(provided_token.strip(), encoding="utf-8")
        return provided_token.strip()
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    return token


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        return {}
    raw = handler.rfile.read(content_length)
    return json.loads(raw.decode("utf-8")) if raw else {}


def authorized(handler: BaseHTTPRequestHandler, token: str) -> bool:
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        candidate = auth.removeprefix("Bearer ").strip()
        return secrets.compare_digest(candidate, token)
    return False


def state_summary(state_dir: Path) -> dict[str, Any]:
    def safe_json(name: str, fallback: Any) -> Any:
        path = state_dir / name
        if not path.exists():
            return fallback
        try:
            return read_json(path)
        except (OSError, json.JSONDecodeError):
            return fallback

    inventory = safe_json("inventory.json", {})
    outlook = safe_json("outlook-state.json", {})
    actions = safe_json("outlook-actions.json", {})
    recovery = safe_json("recovery-plan.json", {})
    return {
        "inventory": inventory.get("summary", {}),
        "outlook": {
            "account": (outlook.get("account") or {}).get("mail", ""),
            "mail": len(outlook.get("mail", [])),
            "calendar": len(outlook.get("calendar", [])),
            "tasks": len(outlook.get("tasks", [])),
            "contacts": len(outlook.get("contacts", [])),
        },
        "outlook_actions": {
            "total": len(actions.get("actions", [])),
            "approved": len(
                [
                    action
                    for action in actions.get("actions", [])
                    if action.get("approved") is True
                ]
            ),
            "applied": len(actions.get("applied_actions", [])),
        },
        "recovery": {
            "groups": len(recovery.get("groups", [])),
            "approved_groups": len(
                [group for group in recovery.get("groups", []) if group.get("approved")]
            ),
        },
    }


def create_handler(state_dir: Path, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                json_response(self, 200, {"ok": True, "service": "jf-life-companion-api"})
                return
            if not authorized(self, token):
                json_response(self, 401, {"ok": False, "error": "Unauthorized"})
                return
            if parsed.path == "/state/summary":
                json_response(self, 200, {"ok": True, "summary": state_summary(state_dir)})
                return
            json_response(self, 404, {"ok": False, "error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/pairing/verify":
                payload = read_request_json(self)
                candidate = str(payload.get("pairing_token") or "")
                if candidate and secrets.compare_digest(candidate, token):
                    json_response(self, 200, {"ok": True})
                else:
                    json_response(self, 401, {"ok": False, "error": "Invalid pairing token"})
                return
            if not authorized(self, token):
                json_response(self, 401, {"ok": False, "error": "Unauthorized"})
                return
            payload = read_request_json(self)
            handlers: dict[str, Callable[[dict[str, Any]], tuple[int, str, str]]] = {
                "/run/inventory": lambda body: run_inventory(state_dir, body),
                "/run/recovery-plan": lambda body: run_recovery_plan(state_dir, body),
                "/run/recovery-apply": lambda body: run_recovery_apply(state_dir, body),
                "/run/outlook-inventory": lambda body: run_outlook_inventory(state_dir, body),
                "/run/outlook-plan": lambda body: run_outlook_plan(state_dir, body),
                "/run/outlook-apply": lambda body: run_outlook_apply(state_dir, body),
                "/run/dashboard": lambda body: run_dashboard(state_dir, body),
            }
            runner = handlers.get(parsed.path)
            if runner is None:
                json_response(self, 404, {"ok": False, "error": "Not found"})
                return
            code, stdout, stderr = runner(payload)
            json_response(
                self,
                200 if code == 0 else 400,
                {
                    "ok": code == 0,
                    "code": code,
                    "stdout": stdout[-30000:],
                    "stderr": stderr[-30000:],
                    "summary": state_summary(state_dir),
                },
            )

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return Handler


def source_arguments(body: dict[str, Any]) -> list[str]:
    source_specs = body.get("sources") or []
    if not isinstance(source_specs, list):
        return []
    args: list[str] = []
    for source in source_specs:
        if isinstance(source, str) and source.strip():
            args += ["--source", source.strip()]
    return args


def optional_glob_arguments(key: str, body: dict[str, Any]) -> list[str]:
    values = body.get(key) or []
    if not isinstance(values, list):
        return []
    args: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            args += [f"--{key[:-1]}", value.strip()]
    return args


def run_inventory(state_dir: Path, body: dict[str, Any]) -> tuple[int, str, str]:
    args = ["--state-dir", str(state_dir), *source_arguments(body)]
    args += optional_glob_arguments("includes", body)
    args += optional_glob_arguments("excludes", body)
    if "--source" not in args:
        return 2, "", "At least one source is required."
    return run_python("scripts/jf_life_inventory.py", *args)


def run_recovery_plan(state_dir: Path, _body: dict[str, Any]) -> tuple[int, str, str]:
    return run_python("scripts/jf_life_recovery.py", "plan", "--state-dir", str(state_dir))


def run_recovery_apply(state_dir: Path, body: dict[str, Any]) -> tuple[int, str, str]:
    args = ["apply", "--state-dir", str(state_dir)]
    if body.get("apply") is True:
        args.append("--apply")
    return run_python("scripts/jf_life_recovery.py", *args)


def run_outlook_inventory(state_dir: Path, body: dict[str, Any]) -> tuple[int, str, str]:
    args = ["--state-dir", str(state_dir), "inventory"]
    for key in ("message_limit", "calendar_days", "contact_limit"):
        if isinstance(body.get(key), int):
            args += [f"--{key.replace('_', '-')}", str(int(body[key]))]
    return run_python("scripts/jf_life_outlook.py", *args)


def run_outlook_plan(state_dir: Path, body: dict[str, Any]) -> tuple[int, str, str]:
    args = ["--state-dir", str(state_dir), "plan"]
    if body.get("all_unread") is True:
        args.append("--all-unread")
    if isinstance(body.get("mark_unread_before_days"), int):
        args += ["--mark-unread-before-days", str(int(body["mark_unread_before_days"]))]
    if isinstance(body.get("archive_read_before_days"), int):
        args += ["--archive-read-before-days", str(int(body["archive_read_before_days"]))]
    return run_python("scripts/jf_life_outlook.py", *args)


def run_outlook_apply(state_dir: Path, body: dict[str, Any]) -> tuple[int, str, str]:
    args = ["--state-dir", str(state_dir), "apply"]
    if body.get("apply") is True:
        args.append("--apply")
    return run_python("scripts/jf_life_outlook.py", *args)


def run_dashboard(state_dir: Path, _body: dict[str, Any]) -> tuple[int, str, str]:
    return run_python("scripts/jf_life_dashboard.py", "--state-dir", str(state_dir))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JF LIFE Windows companion API for iPhone + desktop app pairing."
    )
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8712)
    parser.add_argument("--pairing-token", default="")
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="Print the pairing token and exit without starting server.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
        token = ensure_pairing_token(state_dir, args.pairing_token)
    except (OSError, ValueError) as exc:
        return fail(str(exc))

    if args.print_token:
        print(token)
        return 0

    handler = create_handler(state_dir, token)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"JF LIFE companion API listening on http://{args.host}:{args.port}")
    print(f"State: {state_dir}")
    print(f"Pairing token: {token}")
    print("Use this token in the iPhone app pairing screen.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
