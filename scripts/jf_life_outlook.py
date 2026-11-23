#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from jf_life_local import atomic_write_json, fail, read_json, resolve_state_dir

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
DEFAULT_SCOPES = [
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Contacts.Read",
    "Mail.ReadWrite",
    "MailboxSettings.ReadWrite",
    "Calendars.ReadWrite",
    "Tasks.ReadWrite",
]
CATEGORY_PREFIX = "JF LIFE - "


class GraphError(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(
    method: str,
    url: str,
    *,
    form: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_headers = dict(headers or {})
    payload: bytes | None = None
    if form is not None:
        payload = urllib.parse.urlencode(form).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=payload, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        message = exc.reason
        try:
            parsed = json.loads(raw)
            error_value = parsed.get("error")
            if isinstance(error_value, dict):
                message = error_value.get("message", message)
            elif isinstance(error_value, str):
                description = parsed.get("error_description")
                message = f"{error_value}: {description or message}"
            elif isinstance(parsed.get("error_description"), str):
                message = parsed["error_description"]
        except (json.JSONDecodeError, AttributeError):
            pass
        raise GraphError(f"Microsoft Graph request failed ({exc.code}): {message}") from exc
    except urllib.error.URLError as exc:
        raise GraphError(f"Microsoft Graph connection failed: {exc.reason}") from exc


def load_config(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "outlook-config.json"
    config = read_json(path)
    if not isinstance(config, dict):
        raise ValueError("Outlook configuration must be a JSON object.")
    if not config.get("client_id"):
        raise ValueError("Outlook configuration is missing client_id.")
    return config


def save_config(
    state_dir: Path, client_id: str, tenant: str, scopes: list[str]
) -> dict[str, Any]:
    config = {
        "provider": "microsoft-graph",
        "client_id": client_id,
        "tenant": tenant,
        "scopes": scopes,
        "token_file": "outlook-token.json",
    }
    atomic_write_json(state_dir / "outlook-config.json", config)
    return config


class MicrosoftGraphClient:
    def __init__(self, state_dir: Path, config: dict[str, Any]) -> None:
        self.state_dir = state_dir
        self.client_id = str(config["client_id"])
        self.tenant = str(config.get("tenant") or "common")
        self.scopes = [
            str(scope) for scope in config.get("scopes", DEFAULT_SCOPES)
        ]
        self.token_path = state_dir / "outlook-token.json"
        self.token: dict[str, Any] | None = None
        if self.token_path.exists():
            loaded = read_json(self.token_path)
            if isinstance(loaded, dict):
                self.token = loaded

    def _token_is_valid(self) -> bool:
        if not self.token or not self.token.get("access_token"):
            return False
        expires_at = float(self.token.get("expires_at", 0))
        return time.time() < expires_at - 90

    def _save_token(self, token: dict[str, Any]) -> None:
        old_refresh_token = (
            str(self.token.get("refresh_token"))
            if self.token and self.token.get("refresh_token")
            else ""
        )
        self.token = dict(token)
        if not self.token.get("refresh_token") and old_refresh_token:
            self.token["refresh_token"] = old_refresh_token
        self.token["saved_at"] = int(time.time())
        self.token["expires_at"] = (
            int(time.time()) + int(self.token.pop("expires_in", 3600))
        )
        atomic_write_json(self.token_path, self.token)

    def _device_code_login(self) -> dict[str, Any]:
        authority = (
            f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0"
        )
        response = request_json(
            "POST",
            f"{authority}/devicecode",
            form={
                "client_id": self.client_id,
                "scope": " ".join(self.scopes),
            },
        )
        verification_uri = str(
            response.get("verification_uri")
            or response.get("verification_uri_complete")
            or ""
        )
        user_code = str(response.get("user_code") or "")
        if not verification_uri or not user_code or not response.get("device_code"):
            raise GraphError("Microsoft did not return a valid device sign-in request.")
        print(
            "Complete Outlook sign-in on this Windows PC:\n"
            f"1. Open {verification_uri}\n"
            f"2. Enter code {user_code}\n"
            "Do not send the code or a token to this chat."
        )
        if response.get("message"):
            print(str(response["message"]))

        interval = max(int(response.get("interval", 5)), 1)
        expires_in = int(response.get("expires_in", 900))
        deadline = time.time() + expires_in
        while time.time() < deadline:
            time.sleep(interval)
            try:
                token = request_json(
                    "POST",
                    f"{authority}/token",
                    form={
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "client_id": self.client_id,
                        "device_code": str(response["device_code"]),
                    },
                )
            except GraphError as exc:
                text = str(exc)
                if "authorization_pending" in text:
                    continue
                if "slow_down" in text:
                    interval += 5
                    continue
                raise
            self._save_token(token)
            return self.token or token
        raise GraphError("Outlook sign-in timed out. Run the connect command again.")

    def _refresh_token(self) -> bool:
        if not self.token or not self.token.get("refresh_token"):
            return False
        authority = (
            f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0"
        )
        try:
            token = request_json(
                "POST",
                f"{authority}/token",
                form={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "refresh_token": str(self.token["refresh_token"]),
                    "scope": " ".join(self.scopes),
                },
            )
        except GraphError:
            return False
        self._save_token(token)
        return True

    def connect(self) -> dict[str, Any]:
        if self._token_is_valid():
            return self.request_json("GET", "/me?$select=id,displayName,mail,userPrincipalName")
        if self._refresh_token():
            return self.request_json("GET", "/me?$select=id,displayName,mail,userPrincipalName")
        self._device_code_login()
        return self.request_json("GET", "/me?$select=id,displayName,mail,userPrincipalName")

    def _ensure_token(self) -> None:
        if self._token_is_valid():
            return
        if not self._refresh_token():
            raise GraphError(
                "Outlook is not connected. Run `jf_life_outlook.py connect` locally."
            )

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_token()
        url = path if path.startswith("http") else f"{GRAPH_ROOT}{path}"
        assert self.token
        return request_json(
            method,
            url,
            headers={
                "Authorization": f"Bearer {self.token['access_token']}",
                "Accept": "application/json",
            },
            body=body,
        )

    def list_pages(
        self, path: str, *, max_items: int | None = None
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_path = path
        while next_path and (max_items is None or len(items) < max_items):
            page = self.request_json("GET", next_path)
            values = page.get("value", [])
            if not isinstance(values, list):
                raise GraphError("Microsoft Graph returned an invalid list response.")
            for value in values:
                if isinstance(value, dict):
                    items.append(value)
                    if max_items is not None and len(items) >= max_items:
                        break
            next_path = str(page.get("@odata.nextLink") or "")
        return items


def safe_mail_address(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"name": "", "address": ""}
    address = value.get("emailAddress")
    if not isinstance(address, dict):
        return {"name": "", "address": ""}
    return {
        "name": str(address.get("name") or ""),
        "address": str(address.get("address") or ""),
    }


def message_summary(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(message.get("id") or ""),
        "subject": str(message.get("subject") or "(No subject)"),
        "from": safe_mail_address(message.get("from")),
        "is_read": bool(message.get("isRead")),
        "received_at": str(message.get("receivedDateTime") or ""),
        "flag_status": str(
            (message.get("flag") or {}).get("flagStatus") or "notFlagged"
        ),
        "categories": [
            str(category) for category in message.get("categories", [])
        ],
    }


def contact_summary(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(contact.get("id") or ""),
        "display_name": str(contact.get("displayName") or ""),
        "email_addresses": [
            str(item.get("address") or "")
            for item in contact.get("emailAddresses", [])
            if isinstance(item, dict) and item.get("address")
        ],
        "mobile_phone": str(contact.get("mobilePhone") or ""),
        "home_address": contact.get("homeAddress"),
        "business_address": contact.get("businessAddress"),
    }


def contact_duplicate_groups(contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, list[str]] = {}
    for contact in contacts:
        emails = sorted(
            address.casefold()
            for address in contact.get("email_addresses", [])
            if address
        )
        display_name = str(contact.get("display_name") or "").strip().casefold()
        if not display_name and not emails:
            continue
        key = "|".join([display_name, *emails])
        by_key.setdefault(key, []).append(str(contact.get("id") or ""))
    return [
        {
            "candidate_ids": candidate_ids,
            "candidate_count": len(candidate_ids),
            "review_required": True,
        }
        for candidate_ids in sorted(
            (ids for ids in by_key.values() if len(ids) > 1),
            key=lambda ids: len(ids),
            reverse=True,
        )
    ]


def fetch_outlook_inventory(
    client: MicrosoftGraphClient,
    *,
    message_limit: int,
    calendar_days: int,
    contact_limit: int = 500,
) -> dict[str, Any]:
    account = client.request_json(
        "GET", "/me?$select=id,displayName,mail,userPrincipalName"
    )
    messages = client.list_pages(
        "/me/messages"
        "?$top=50"
        "&$orderby=receivedDateTime%20desc"
        "&$select=id,subject,from,isRead,receivedDateTime,flag,categories",
        max_items=message_limit,
    )
    start = utc_now()
    end = start + dt.timedelta(days=calendar_days)
    calendar_path = (
        "/me/calendarView?"
        + urllib.parse.urlencode(
            {
                "startDateTime": iso_utc(start),
                "endDateTime": iso_utc(end),
                "$select": "id,subject,start,end,isAllDay,location,organizer",
                "$orderby": "start/dateTime",
                "$top": "100",
            }
        )
    )
    events = client.list_pages(calendar_path)
    lists = client.list_pages(
        "/me/todo/lists?$select=id,displayName,isOwner,isShared,wellknownListName"
    )
    tasks: list[dict[str, Any]] = []
    for todo_list in lists:
        list_id = urllib.parse.quote(str(todo_list.get("id") or ""), safe="")
        if not list_id:
            continue
        for task in client.list_pages(
            f"/me/todo/lists/{list_id}/tasks"
            "?$select=id,title,status,importance,isReminderOn,dueDateTime,reminderDateTime"
        ):
            task["listId"] = todo_list.get("id")
            task["listName"] = todo_list.get("displayName")
            tasks.append(task)
    contacts = client.list_pages(
        "/me/contacts"
        "?$select=id,displayName,emailAddresses,mobilePhone,homeAddress,businessAddress"
        "&$top=100",
        max_items=contact_limit,
    )
    contact_records = [contact_summary(contact) for contact in contacts]
    return {
        "schema_version": 1,
        "scope": "private-local-only",
        "generated_at_utc": iso_utc(utc_now()),
        "account": {
            "id": str(account.get("id") or ""),
            "display_name": str(account.get("displayName") or ""),
            "mail": str(account.get("mail") or account.get("userPrincipalName") or ""),
        },
        "mail": [message_summary(message) for message in messages],
        "calendar": events,
        "todo_lists": lists,
        "tasks": tasks,
        "contacts": contact_records,
        "contact_duplicate_groups": contact_duplicate_groups(contact_records),
    }


def parse_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def mail_area(message: dict[str, Any]) -> str:
    subject = str(message.get("subject") or "").casefold()
    sender = str((message.get("from") or {}).get("address") or "").casefold()
    text = f"{subject} {sender}"
    if any(
        hint in text
        for hint in (
            "jf life",
            "jf-life",
            "carpentry",
            "invoice",
            "quote",
            "quotation",
            "payroll",
            "job site",
            "account",
        )
    ):
        return "Business"
    if any(
        hint in text
        for hint in ("course", "training", "tafe", "assessment", "certificate")
    ):
        return "Course"
    return "Needs-review"


def default_task_list_id(inventory: dict[str, Any]) -> str:
    lists = inventory.get("todo_lists", [])
    for todo_list in lists:
        if todo_list.get("wellknownListName") == "defaultList":
            return str(todo_list.get("id") or "")
    return str((lists[0].get("id") if lists else "") or "")


def build_action_plan(
    inventory: dict[str, Any],
    *,
    mark_unread_before_days: int,
    all_unread: bool,
    archive_read_before_days: int,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    now = utc_now()
    task_list_id = default_task_list_id(inventory)
    for index, message in enumerate(inventory.get("mail", []), start=1):
        received = parse_datetime(str(message.get("received_at") or ""))
        age_days = (
            (now - received).total_seconds() / 86400 if received is not None else -1
        )
        area = mail_area(message)
        subject = str(message.get("subject") or "(No subject)")
        categories = list(message.get("categories") or [])
        if area != "Needs-review":
            jf_category = f"{CATEGORY_PREFIX}{area}"
            if jf_category not in categories:
                actions.append(
                    {
                        "action_id": f"mail-category-{index:06d}",
                        "approved": False,
                        "type": "categorize-message",
                        "message_id": message.get("id"),
                        "summary": f"Categorize: {subject}",
                        "payload": {
                            "category": jf_category,
                            "existing_categories": categories,
                        },
                    }
                )
        if not message.get("is_read") and (
            all_unread or age_days >= mark_unread_before_days
        ):
            actions.append(
                {
                    "action_id": f"mail-read-{index:06d}",
                    "approved": False,
                    "type": "mark-message-read",
                    "message_id": message.get("id"),
                    "summary": f"Mark read: {subject}",
                    "payload": {"isRead": True},
                }
            )
        if message.get("flag_status") == "flagged" and task_list_id:
            actions.append(
                {
                    "action_id": f"mail-task-{index:06d}",
                    "approved": False,
                    "type": "create-task-from-message",
                    "message_id": message.get("id"),
                    "list_id": task_list_id,
                    "summary": f"Create Outlook task: {subject}",
                    "payload": {
                        "title": subject,
                        "importance": "high",
                    },
                }
            )
        if (
            message.get("is_read")
            and area != "Needs-review"
            and age_days >= archive_read_before_days
        ):
            actions.append(
                {
                    "action_id": f"mail-archive-{index:06d}",
                    "approved": False,
                    "type": "archive-message",
                    "message_id": message.get("id"),
                    "summary": f"Archive: {subject}",
                    "payload": {"destinationId": "archive"},
                }
            )
    return {
        "schema_version": 1,
        "scope": "private-local-only",
        "generated_at_utc": iso_utc(now),
        "policy": "Only actions with approved=true are applied.",
        "account": inventory.get("account"),
        "actions": actions,
        "applied_actions": [],
    }


def ensure_master_categories(
    client: MicrosoftGraphClient, categories: Iterable[str]
) -> None:
    existing = {
        str(item.get("displayName") or "")
        for item in client.list_pages("/me/outlook/masterCategories")
    }
    for index, category in enumerate(categories):
        if category in existing:
            continue
        client.request_json(
            "POST",
            "/me/outlook/masterCategories",
            body={
                "displayName": category,
                "color": "preset{}".format((index % 25) + 1),
            },
        )


def apply_actions(
    client: MicrosoftGraphClient,
    plan: dict[str, Any],
    *,
    apply_changes: bool,
) -> dict[str, int]:
    approved = [
        action
        for action in plan.get("actions", [])
        if action.get("approved") is True
        and action.get("status") not in ("applied", "failed")
    ]
    result = {"approved": len(approved), "applied": 0, "skipped": 0, "failed": 0}
    if not apply_changes:
        return result

    category_names = {
        str((action.get("payload") or {}).get("category") or "")
        for action in approved
        if action.get("type") == "categorize-message"
    }
    if category_names:
        ensure_master_categories(
            client, (category for category in category_names if category)
        )

    for action in approved:
        action_type = action.get("type")
        message_id = urllib.parse.quote(str(action.get("message_id") or ""), safe="")
        if not message_id:
            action["status"] = "failed"
            action["error"] = "Missing message id."
            result["failed"] += 1
            continue
        try:
            if action_type == "categorize-message":
                payload = action.get("payload") or {}
                latest = client.request_json(
                    "GET",
                    f"/me/messages/{message_id}?$select=categories",
                )
                categories = list(latest.get("categories") or [])
                category = str(payload.get("category") or "")
                if category and category not in categories:
                    categories.append(category)
                client.request_json(
                    "PATCH",
                    f"/me/messages/{message_id}",
                    body={"categories": categories},
                )
            elif action_type == "mark-message-read":
                client.request_json(
                    "PATCH", f"/me/messages/{message_id}", body={"isRead": True}
                )
            elif action_type == "archive-message":
                client.request_json(
                    "POST",
                    f"/me/messages/{message_id}/move",
                    body={"destinationId": "archive"},
                )
            elif action_type == "create-task-from-message":
                list_id = urllib.parse.quote(str(action.get("list_id") or ""), safe="")
                if not list_id:
                    raise GraphError("Missing Outlook task list id.")
                client.request_json(
                    "POST",
                    f"/me/todo/lists/{list_id}/tasks",
                    body=action.get("payload") or {},
                )
            else:
                action["status"] = "failed"
                action["error"] = f"Unsupported action type: {action_type}"
                result["skipped"] += 1
                result["failed"] += 1
                continue
            action["status"] = "applied"
            action["applied_at_utc"] = iso_utc(utc_now())
            plan.setdefault("applied_actions", []).append(action["action_id"])
            result["applied"] += 1
        except (GraphError, OSError) as exc:
            action["status"] = "failed"
            action["error"] = str(exc)
            result["failed"] += 1
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect Outlook locally for approved JF LIFE actions."
    )
    parser.add_argument(
        "--state-dir",
        default="",
        help="Private local state folder outside the repository.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    connect = subparsers.add_parser("connect")
    connect.add_argument(
        "--client-id",
        default="",
        help="Microsoft Entra public-client application ID for local OAuth.",
    )
    connect.add_argument("--tenant", default="common")

    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--message-limit", type=int, default=200)
    inventory.add_argument("--calendar-days", type=int, default=60)
    inventory.add_argument("--contact-limit", type=int, default=500)

    planner = subparsers.add_parser("plan")
    planner.add_argument("--mark-unread-before-days", type=int, default=30)
    planner.add_argument("--all-unread", action="store_true")
    planner.add_argument("--archive-read-before-days", type=int, default=365)

    apply = subparsers.add_parser("apply")
    apply.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state_dir = resolve_state_dir(args.state_dir or None)
        if args.command == "connect":
            if not args.client_id:
                return fail("--client-id is required for Outlook sign-in.")
            config = save_config(
                state_dir, args.client_id, args.tenant, list(DEFAULT_SCOPES)
            )
            account = MicrosoftGraphClient(state_dir, config).connect()
            print(
                "Outlook connected locally for: "
                + str(account.get("mail") or account.get("userPrincipalName") or "")
            )
            return 0

        config = load_config(state_dir)
        client = MicrosoftGraphClient(state_dir, config)
        if args.command == "inventory":
            inventory = fetch_outlook_inventory(
                client,
                message_limit=max(args.message_limit, 1),
                calendar_days=max(args.calendar_days, 1),
                contact_limit=max(args.contact_limit, 1),
            )
            atomic_write_json(state_dir / "outlook-state.json", inventory)
            print(
                json.dumps(
                    {
                        "mail": len(inventory["mail"]),
                        "calendar": len(inventory["calendar"]),
                        "tasks": len(inventory["tasks"]),
                        "contacts": len(inventory["contacts"]),
                        "contact_duplicate_groups": len(
                            inventory["contact_duplicate_groups"]
                        ),
                    },
                    indent=2,
                )
            )
            print(f"Private Outlook inventory written to {state_dir / 'outlook-state.json'}")
            return 0

        inventory = read_json(state_dir / "outlook-state.json")
        if not isinstance(inventory, dict):
            return fail("Outlook state must contain a JSON object.")
        if args.command == "plan":
            plan = build_action_plan(
                inventory,
                mark_unread_before_days=max(args.mark_unread_before_days, 0),
                all_unread=args.all_unread,
                archive_read_before_days=max(args.archive_read_before_days, 1),
            )
            atomic_write_json(state_dir / "outlook-actions.json", plan)
            print(
                f"Created {len(plan['actions'])} proposed Outlook actions at "
                f"{state_dir / 'outlook-actions.json'}"
            )
            print("Set approved=true on reviewed actions before running apply --apply.")
            return 0

        plan = read_json(state_dir / "outlook-actions.json")
        if not isinstance(plan, dict):
            return fail("Outlook action plan must contain a JSON object.")
        result = apply_actions(client, plan, apply_changes=args.apply)
        if not args.apply:
            print(
                json.dumps(result, indent=2)
                + "\nDry run complete. Outlook was not changed."
            )
            return 0
        atomic_write_json(state_dir / "outlook-actions.json", plan)
        print(json.dumps(result, indent=2))
        return 1 if result.get("failed") else 0
    except (GraphError, OSError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
