import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from jf_life_readiness import (  # noqa: E402
    build_health_urls,
    pairing_token_present,
    summarize_checks,
    unique_preserve_order,
)


class ReadinessTests(unittest.TestCase):
    def test_unique_preserve_order(self) -> None:
        self.assertEqual(
            unique_preserve_order(["1", "2", "1", "", "3", "2"]),
            ["1", "2", "3"],
        )

    def test_build_health_urls_includes_localhost_and_dedupes(self) -> None:
        urls = build_health_urls(8712, ["192.168.0.10", "192.168.0.10"])
        self.assertEqual(
            urls,
            [
                "http://127.0.0.1:8712/health",
                "http://192.168.0.10:8712/health",
            ],
        )

    def test_summarize_checks(self) -> None:
        summary = summarize_checks(
            [
                {"url": "http://127.0.0.1:8712/health", "ok": True},
                {"url": "http://192.168.0.10:8712/health", "ok": False},
            ]
        )
        self.assertTrue(summary["localhost_ok"])
        self.assertFalse(summary["lan_ok"])

    def test_pairing_token_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            self.assertFalse(pairing_token_present(state_dir))
            (state_dir / "pairing-token.txt").write_text("abc", encoding="utf-8")
            self.assertTrue(pairing_token_present(state_dir))


if __name__ == "__main__":
    unittest.main()
