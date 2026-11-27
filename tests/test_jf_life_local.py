import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from jf_life_inventory import build_duplicate_groups, create_inventory  # noqa: E402
from jf_life_link import SourceSpec  # noqa: E402
from jf_life_local import (  # noqa: E402
    atomic_write_json,
    read_json,
    resolve_state_dir,
    resolve_state_file,
)
from jf_life_outlook import (  # noqa: E402
    apply_actions,
    build_action_plan,
    contact_duplicate_groups,
    fetch_outlook_inventory,
)
from jf_life_recovery import approved_recovery_copies, build_plan  # noqa: E402


class LiveSyncTests(unittest.TestCase):
    def run_sync(self, state: Path, drive: Path, icloud: Path, *flags: str):
        return subprocess.run(
            [
                sys.executable, "-I", str(SCRIPTS / "run_jf_life.py"),
                str(SCRIPTS / "jf_life_live_sync.py"),
                "--state-dir", str(state), "--cycles", "1",
                "--source", f"DriveD={drive}", "--source", f"iCloud={icloud}", *flags,
            ],
            capture_output=True, text=True, check=False, timeout=30,
        )

    def test_live_sync_keeps_review_and_stops_publication_after_a_source_disconnects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            drive, icloud, state = (root / name for name in ("drive", "icloud", "state"))
            drive.mkdir()
            icloud.mkdir()
            (drive / "quote.txt").write_text("Work fixture", encoding="utf-8")
            (icloud / "copy.txt").write_text("Work fixture", encoding="utf-8")

            first = self.run_sync(state, drive, icloud)
            self.assertEqual(first.returncode, 0, first.stderr)
            plan_path = state / "recovery-plan.json"
            plan = read_json(plan_path)
            plan["groups"][0]["review_note"] = "Keep this review"
            atomic_write_json(plan_path, plan)
            reviewed = plan_path.read_bytes()

            (drive / "new.txt").write_text("Another fixture", encoding="utf-8")
            again = self.run_sync(state, drive, icloud)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(plan_path.read_bytes(), reviewed)
            self.assertEqual(read_json(state / "inventory.json")["summary"]["files_inventoried"], 3)

            icloud.rename(root / "disconnected")
            partial = self.run_sync(state, drive, icloud, "--publish-library")
            self.assertEqual(partial.returncode, 1, partial.stderr)
            status = read_json(state / "live-sync-status.json")
            self.assertIn({"name": "source-coverage", "ok": False}, status["steps"])
            self.assertNotIn("library-publish", [step["name"] for step in status["steps"]])
            self.assertEqual(plan_path.read_bytes(), reviewed)


class LocalInventoryTests(unittest.TestCase):
    def test_state_directory_cannot_be_inside_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "separate from the public repository"):
            resolve_state_dir(REPO_ROOT / ".jf-life-local")

    def test_state_directory_cannot_contain_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "separate from the public repository"):
            resolve_state_dir(REPO_ROOT.parent)

    def test_private_state_file_cannot_escape_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "inside the private folder"):
                resolve_state_file(Path(temp), "../private.json")

    def test_inventory_finds_exact_duplicates_without_modifying_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "JF DRIVE"
            state = root / "Private State"
            source.mkdir()
            original = source / "Business" / "Quote.pdf"
            original.parent.mkdir()
            original.write_bytes(b"same document")
            duplicate = source / "Backup" / "Quote-copy.pdf"
            duplicate.parent.mkdir()
            duplicate.write_bytes(b"same document")
            unique = source / "Personal" / "Notes.txt"
            unique.parent.mkdir()
            unique.write_text("notes", encoding="utf-8")

            inventory = create_inventory(
                [SourceSpec("DriveD", source)],
                state,
                includes=[],
                excludes=[],
            )

            self.assertEqual(inventory["summary"]["files_inventoried"], 3)
            self.assertEqual(inventory["summary"]["duplicate_groups"], 1)
            group = inventory["duplicate_groups"][0]
            self.assertEqual(group["candidate_count"], 2)
            self.assertEqual(group["recoverable_bytes"], len(b"same document"))
            self.assertEqual(original.read_bytes(), b"same document")
            self.assertEqual(duplicate.read_bytes(), b"same document")

    def test_recovery_plan_only_copies_explicit_approved_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            state = root / "state"
            source.mkdir()
            first = source / "first.txt"
            second = source / "second.txt"
            first.write_text("duplicate", encoding="utf-8")
            second.write_text("duplicate", encoding="utf-8")
            inventory = create_inventory(
                [SourceSpec("DriveD", source)], state, includes=[], excludes=[]
            )
            plan = build_plan(inventory)
            group = plan["groups"][0]

            copied, warnings = approved_recovery_copies(state, plan, False)
            self.assertEqual((copied, warnings), (0, []))
            self.assertFalse(group["approved"])

            group["approved"] = True
            group["candidates"][1]["decision"] = "recovery-copy"
            copied, warnings = approved_recovery_copies(state, plan, True)

            self.assertEqual((copied, warnings), (1, []))
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            self.assertTrue(
                any(
                    Path(copy["destination"]).is_file()
                    for copy in group["recovery_copies"]
                )
            )
            copied_again, warnings_again = approved_recovery_copies(state, plan, True)
            self.assertEqual((copied_again, warnings_again), (0, []))
            self.assertEqual(len(group["recovery_copies"]), 1)

    def test_duplicate_group_recommendation_is_deterministic(self) -> None:
        files = [
            {
                "record_id": "file-2",
                "source_label": "DriveD",
                "relative_path": "z.txt",
                "sha256": "same",
                "size_bytes": 10,
            },
            {
                "record_id": "file-1",
                "source_label": "DriveD",
                "relative_path": "a.txt",
                "sha256": "same",
                "size_bytes": 10,
            },
        ]
        groups = build_duplicate_groups(files)
        self.assertEqual(groups[0]["recommended_keep"], "file-1")


class OutlookActionTests(unittest.TestCase):
    def sample_inventory(self) -> dict:
        return {
            "account": {"mail": "local@example.invalid"},
            "todo_lists": [
                {
                    "id": "tasks-list",
                    "displayName": "Tasks",
                    "wellknownListName": "defaultList",
                }
            ],
            "mail": [
                {
                    "id": "unread-1",
                    "subject": "JF LIFE invoice follow-up",
                    "from": {"address": "accounts@example.invalid"},
                    "is_read": False,
                    "received_at": "2020-01-01T00:00:00+00:00",
                    "flag_status": "flagged",
                    "categories": [],
                },
                {
                    "id": "old-read-1",
                    "subject": "JF LIFE old quote",
                    "from": {"address": "client@example.invalid"},
                    "is_read": True,
                    "received_at": "2020-01-02T00:00:00+00:00",
                    "flag_status": "notFlagged",
                    "categories": [],
                },
            ],
        }

    def test_outlook_plan_is_unapproved_by_default(self) -> None:
        plan = build_action_plan(
            self.sample_inventory(),
            mark_unread_before_days=30,
            all_unread=False,
            archive_read_before_days=365,
        )
        self.assertGreaterEqual(len(plan["actions"]), 4)
        self.assertTrue(all(action["approved"] is False for action in plan["actions"]))
        self.assertTrue(
            any(action["type"] == "categorize-message" for action in plan["actions"])
        )
        self.assertTrue(
            any(action["type"] == "create-task-from-message" for action in plan["actions"])
        )

    def test_only_explicitly_approved_outlook_actions_are_applied(self) -> None:
        plan = build_action_plan(
            self.sample_inventory(),
            mark_unread_before_days=0,
            all_unread=True,
            archive_read_before_days=365,
        )
        selected = next(
            action for action in plan["actions"] if action["type"] == "mark-message-read"
        )
        selected["approved"] = True
        calls: list[tuple[str, str, dict | None]] = []

        class FakeClient:
            def list_pages(self, path: str) -> list:
                self_path = path
                if self_path == "/me/outlook/masterCategories":
                    return []
                return []

            def request_json(
                self, method: str, path: str, *, body: dict | None = None
            ) -> dict:
                calls.append((method, path, body))
                return {}

        dry_result = apply_actions(FakeClient(), plan, apply_changes=False)
        self.assertEqual(dry_result["approved"], 1)
        self.assertEqual(calls, [])

        result = apply_actions(FakeClient(), plan, apply_changes=True)
        self.assertEqual(result["applied"], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0:2], ("PATCH", "/me/messages/unread-1"))
        self.assertEqual(calls[0][2], {"isRead": True})

    def test_category_action_preserves_categories_added_after_planning(self) -> None:
        plan = build_action_plan(
            self.sample_inventory(),
            mark_unread_before_days=30,
            all_unread=False,
            archive_read_before_days=365,
        )
        selected = next(
            action
            for action in plan["actions"]
            if action["type"] == "categorize-message"
        )
        selected["approved"] = True
        calls: list[tuple[str, str, dict | None]] = []

        class FakeClient:
            def list_pages(self, path: str) -> list:
                if path == "/me/outlook/masterCategories":
                    return [{"displayName": "JF LIFE - Business"}]
                return []

            def request_json(
                self, method: str, path: str, *, body: dict | None = None
            ) -> dict:
                calls.append((method, path, body))
                if method == "GET":
                    return {"categories": ["Added on phone"]}
                return {}

        result = apply_actions(FakeClient(), plan, apply_changes=True)

        self.assertEqual(result["applied"], 1)
        self.assertEqual(
            calls[-1][2],
            {"categories": ["Added on phone", "JF LIFE - Business"]},
        )

    def test_contact_duplicates_require_review(self) -> None:
        contacts = [
            {
                "id": "one",
                "display_name": "Alex Example",
                "email_addresses": ["alex@example.invalid"],
            },
            {
                "id": "two",
                "display_name": "Alex Example",
                "email_addresses": ["ALEX@example.invalid"],
            },
        ]
        groups = contact_duplicate_groups(contacts)
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["review_required"])
        self.assertEqual(groups[0]["candidate_count"], 2)

    def test_outlook_inventory_includes_contacts_and_tasks(self) -> None:
        class FakeClient:
            def request_json(self, method: str, path: str) -> dict:
                self_method = method
                self_path = path
                if self_method == "GET" and self_path.startswith("/me?"):
                    return {"id": "account", "displayName": "Test", "mail": "test@example.invalid"}
                return {}

            def list_pages(self, path: str, *, max_items: int | None = None) -> list:
                if path.startswith("/me/messages"):
                    return []
                if path.startswith("/me/calendarView"):
                    return []
                if path.startswith("/me/todo/lists?"):
                    return [{"id": "tasks", "displayName": "Tasks"}]
                if path.startswith("/me/todo/lists/tasks/tasks"):
                    return [
                        {
                            "id": "task",
                            "title": "Follow up",
                            "status": "notStarted",
                        }
                    ]
                if path.startswith("/me/contacts"):
                    return [
                        {
                            "id": "contact-one",
                            "displayName": "A Person",
                            "emailAddresses": [{"address": "a@example.invalid"}],
                        }
                    ]
                return []

        inventory = fetch_outlook_inventory(
            FakeClient(), message_limit=10, calendar_days=7, contact_limit=10
        )

        self.assertEqual(len(inventory["tasks"]), 1)
        self.assertEqual(inventory["tasks"][0]["listName"], "Tasks")
        self.assertEqual(inventory["contacts"][0]["display_name"], "A Person")

    def test_private_json_round_trip_keeps_sensitive_data_out_of_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state"
            path = state / "outlook-state.json"
            value = {"account": {"mail": "private@example.invalid"}}
            atomic_write_json(path, value)
            self.assertEqual(read_json(path), value)
            self.assertFalse(REPO_ROOT in path.parents)


class LocalDashboardTests(unittest.TestCase):
    def test_dashboard_embeds_private_state_without_script_termination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            payload = {
                "schema_version": 1,
                "scope": "private-local-only",
                "files": [],
                "duplicate_groups": [],
                "sources": [],
                "summary": {},
            }
            outlook = {
                "account": {"mail": "private@example.invalid"},
                "mail": [
                    {
                        "id": "message-1",
                        "subject": "</script><script>alert('x')</script>",
                    }
                ],
                "calendar": [],
                "tasks": [],
            }
            atomic_write_json(state_dir / "inventory.json", payload)
            atomic_write_json(state_dir / "outlook-state.json", outlook)

            rendered = render_dashboard(dashboard_state(state_dir))

            self.assertIn("\\u003c/script\\u003e", rendered)
            self.assertNotIn("</script><script>alert", rendered)
            self.assertIn("JF LIFE Local Control Centre", rendered)


if __name__ == "__main__":
    unittest.main()
from jf_life_dashboard import dashboard_state, render_dashboard  # noqa: E402
