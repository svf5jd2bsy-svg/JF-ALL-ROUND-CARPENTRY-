import json
import base64
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from jf_life_companion_api import (  # noqa: E402
    ensure_pairing_token,
    run_library_publish,
    run_upload,
    source_arguments,
    state_summary,
)
from jf_life_local import atomic_write_json  # noqa: E402


class CompanionApiTests(unittest.TestCase):
    def test_pairing_token_is_stable_when_existing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            first = ensure_pairing_token(state_dir)
            second = ensure_pairing_token(state_dir)
            self.assertEqual(first, second)
            self.assertTrue((state_dir / "pairing-token.txt").is_file())

    def test_pairing_token_can_be_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            token = ensure_pairing_token(state_dir, "test-token")
            self.assertEqual(token, "test-token")
            self.assertEqual(
                (state_dir / "pairing-token.txt").read_text(encoding="utf-8"),
                "test-token",
            )

    def test_source_arguments_accept_only_string_sources(self) -> None:
        args = source_arguments(
            {"sources": ["DriveD=D:\\", "", {"bad": True}, "iCloud=C:\\iCloud"]}
        )
        self.assertEqual(
            args,
            ["--source", "DriveD=D:\\", "--source", "iCloud=C:\\iCloud"],
        )

    def test_library_publish_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            code, stdout, stderr = run_library_publish(
                Path(temp),
                {"sources": ["DriveD=D:\\"]},
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("Explicit publish confirmation", stderr)

    def test_phone_upload_stays_in_private_state_and_is_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = b"JF LIFE phone test"
            code, stdout, stderr = run_upload(
                Path(temp),
                {
                    "name": "invoice-test.txt",
                    "relative_path": "invoice-test.txt",
                    "mime_type": "text/plain",
                    "base64": base64.b64encode(payload).decode("ascii"),
                },
            )
            self.assertEqual(code, 0)
            self.assertIn("private JF LIFE state", stdout)
            self.assertEqual(stderr, "")
            manifest = json.loads(
                (Path(temp) / "phone-uploads-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["uploads"][0]["area"], "Business")

    def test_state_summary_reads_private_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            atomic_write_json(
                state_dir / "inventory.json",
                {"summary": {"files_inventoried": 7, "duplicate_groups": 2}},
            )
            atomic_write_json(
                state_dir / "outlook-state.json",
                {
                    "account": {"mail": "owner@example.invalid"},
                    "mail": [{"id": "1"}],
                    "calendar": [{"id": "2"}],
                    "tasks": [{"id": "3"}],
                    "contacts": [{"id": "4"}],
                },
            )
            atomic_write_json(
                state_dir / "outlook-actions.json",
                {
                    "actions": [
                        {"approved": True},
                        {"approved": False},
                    ],
                    "applied_actions": ["one"],
                },
            )
            atomic_write_json(
                state_dir / "recovery-plan.json",
                {"groups": [{"approved": True}, {"approved": False}]},
            )
            summary = state_summary(state_dir)

            self.assertEqual(summary["inventory"]["files_inventoried"], 7)
            self.assertEqual(summary["outlook"]["account"], "owner@example.invalid")
            self.assertEqual(summary["outlook_actions"]["approved"], 1)
            self.assertEqual(summary["recovery"]["approved_groups"], 1)
            self.assertNotIn(str(state_dir), json.dumps(summary))


if __name__ == "__main__":
    unittest.main()
