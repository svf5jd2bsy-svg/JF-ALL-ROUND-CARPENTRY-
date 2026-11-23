#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from jf_life_local import fail, resolve_state_dir
except ModuleNotFoundError:  # pragma: no cover - package-style import fallback
    from scripts.jf_life_local import fail, resolve_state_dir


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def discover_ipv4_addresses() -> list[str]:
    addresses: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.append(sock.getsockname()[0])
    except OSError:
        pass
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = entry[4][0]
            addresses.append(address)
    except OSError:
        pass
    return unique_preserve_order(addresses)


def build_health_urls(port: int, ipv4_addresses: list[str]) -> list[str]:
    hosts = unique_preserve_order(["127.0.0.1", *ipv4_addresses])
    return [f"http://{host}:{port}/health" for host in hosts]


def check_health(url: str, timeout_seconds: int = 3) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body) if body else {}
        return {
            "url": url,
            "reachable": True,
            "ok": bool(payload.get("ok") is True),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return {"url": url, "reachable": False, "ok": False, "error": str(exc)}


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, bool]:
    localhost_ok = any(
        check.get("url", "").startswith("http://127.0.0.1:") and check.get("ok") is True
        for check in checks
    )
    lan_ok = any(
        (not check.get("url", "").startswith("http://127.0.0.1:")) and check.get("ok") is True
        for check in checks
    )
    return {"localhost_ok": localhost_ok, "lan_ok": lan_ok}


def pairing_token_present(state_dir: Path) -> bool:
    token_path = state_dir / "pairing-token.txt"
    if not token_path.exists():
        return False
    return bool(token_path.read_text(encoding="utf-8").strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JF LIFE readiness check for Windows companion pairing."
    )
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--port", type=int, default=8712)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
    except (OSError, ValueError) as exc:
        return fail(str(exc))

    checks = [check_health(url) for url in build_health_urls(args.port, discover_ipv4_addresses())]
    summary = summarize_checks(checks)
    result = {
        "ok": summary["localhost_ok"],
        "localhost_ok": summary["localhost_ok"],
        "lan_ok": summary["lan_ok"],
        "pairing_token_present": pairing_token_present(state_dir),
        "checks": checks,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"Companion localhost health: {'OK' if result['localhost_ok'] else 'FAILED'}\n"
            f"Companion LAN health: {'OK' if result['lan_ok'] else 'FAILED'}\n"
            f"Pairing token present: {'YES' if result['pairing_token_present'] else 'NO'}"
        )
        if not result["localhost_ok"]:
            print(
                "\nStart API first:\n"
                "  python .\\scripts\\jf_life_companion_api.py --state-dir \"$env:LOCALAPPDATA\\JF LIFE\""
            )
        if result["localhost_ok"] and not result["lan_ok"]:
            print(
                "\nLAN check failed from this machine. Confirm API host is 0.0.0.0 and allow port 8712 on Private firewall:\n"
                "  netsh advfirewall firewall add rule name=\"JF LIFE Companion API 8712\" dir=in action=allow protocol=TCP localport=8712 profile=private"
            )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
