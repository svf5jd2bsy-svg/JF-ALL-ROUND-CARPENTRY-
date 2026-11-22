#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    timeout: int = 20,
) -> dict[str, Any]:
    request = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def stripe_status(api_key: str) -> dict[str, Any]:
    if not api_key.strip():
        return {"configured": False, "ok": False, "error": "Stripe API key is missing."}
    try:
        payload = _request_json(
            "GET",
            "https://api.stripe.com/v1/account",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
        )
        return {
            "configured": True,
            "ok": True,
            "id": str(payload.get("id") or ""),
            "business_name": str(payload.get("business_profile", {}).get("name") or ""),
        }
    except urllib.error.HTTPError as exc:
        return {
            "configured": True,
            "ok": False,
            "error": f"Stripe API error ({exc.code}).",
        }
    except urllib.error.URLError as exc:
        return {"configured": True, "ok": False, "error": f"Stripe connection failed: {exc.reason}"}


def xero_status(access_token: str, tenant_id: str) -> dict[str, Any]:
    if not access_token.strip() or not tenant_id.strip():
        return {
            "configured": False,
            "ok": False,
            "error": "Xero access token or tenant id is missing.",
        }
    try:
        payload = _request_json(
            "GET",
            "https://api.xero.com/api.xro/2.0/Organisation",
            headers={
                "Authorization": f"Bearer {access_token.strip()}",
                "Xero-tenant-id": tenant_id.strip(),
                "Accept": "application/json",
            },
        )
        organisations = payload.get("Organisations") or []
        first = organisations[0] if organisations else {}
        return {
            "configured": True,
            "ok": True,
            "name": str(first.get("Name") or ""),
            "short_code": str(first.get("ShortCode") or ""),
        }
    except urllib.error.HTTPError as exc:
        return {
            "configured": True,
            "ok": False,
            "error": f"Xero API error ({exc.code}).",
        }
    except urllib.error.URLError as exc:
        return {"configured": True, "ok": False, "error": f"Xero connection failed: {exc.reason}"}


def run_status(args: argparse.Namespace) -> dict[str, Any]:
    stripe = stripe_status(args.stripe_api_key or "")
    xero = xero_status(args.xero_access_token or "", args.xero_tenant_id or "")
    return {
        "stripe": stripe,
        "xero": xero,
        "ok": bool((not stripe["configured"] or stripe["ok"]) and (not xero["configured"] or xero["ok"])),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checks live status for optional Stripe and Xero integrations."
    )
    parser.add_argument("--stripe-api-key", default="")
    parser.add_argument("--xero-access-token", default="")
    parser.add_argument("--xero-tenant-id", default="")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_status(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Integration status:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
