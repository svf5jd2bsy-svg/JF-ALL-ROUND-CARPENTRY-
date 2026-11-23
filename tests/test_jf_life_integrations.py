import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from jf_life_integrations import run_status  # noqa: E402
from jf_life_live_sync import list_arguments, source_arguments  # noqa: E402


class IntegrationTests(unittest.TestCase):
    def test_run_status_reports_ok_when_not_configured(self) -> None:
        args = argparse.Namespace(
            stripe_api_key="",
            xero_access_token="",
            xero_tenant_id="",
        )
        result = run_status(args)
        self.assertFalse(result["stripe"]["configured"])
        self.assertFalse(result["xero"]["configured"])
        self.assertTrue(result["ok"])

    def test_run_status_uses_connector_results(self) -> None:
        args = argparse.Namespace(
            stripe_api_key="sk_test",
            xero_access_token="token",
            xero_tenant_id="tenant",
        )
        with (
            patch("jf_life_integrations.stripe_status", return_value={"configured": True, "ok": True}),
            patch("jf_life_integrations.xero_status", return_value={"configured": True, "ok": False}),
        ):
            result = run_status(args)
        self.assertFalse(result["ok"])


class LiveSyncArgumentTests(unittest.TestCase):
    def test_source_arguments_filters_empty_values(self) -> None:
        self.assertEqual(
            source_arguments(["DriveD=D:\\", "", " iCloud=C:\\iCloud "]),
            ["--source", "DriveD=D:\\", "--source", "iCloud=C:\\iCloud"],
        )

    def test_list_arguments_filters_empty_values(self) -> None:
        self.assertEqual(
            list_arguments("--include", ["*.pdf", "", " *.docx "]),
            ["--include", "*.pdf", "--include", "*.docx"],
        )


if __name__ == "__main__":
    unittest.main()
