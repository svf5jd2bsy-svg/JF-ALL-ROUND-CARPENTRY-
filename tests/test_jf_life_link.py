import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "jf_life_link.py"


class JfLifeLinkIntegrationTests(unittest.TestCase):
    def run_linker(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *arguments],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "NO_COLOR": "1"},
        )

    def test_links_files_and_uses_canonical_target_for_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as source_temp, tempfile.TemporaryDirectory(
            dir=REPO_ROOT
        ) as output_temp:
            source = Path(source_temp) / "source"
            root = Path(output_temp)
            (source / "Business Jobs").mkdir(parents=True)
            (source / "Business Jobs" / "quote.txt").write_text("same file", encoding="utf-8")
            (source / "Personal").mkdir()
            (source / "Personal" / "copy.txt").write_text("same file", encoding="utf-8")

            output_rel = root.relative_to(REPO_ROOT) / "Library"
            manifest_rel = root.relative_to(REPO_ROOT) / "manifest.json"
            result = self.run_linker(
                "--source",
                f"DriveD={source}",
                "--output-root",
                output_rel.as_posix(),
                "--manifest",
                manifest_rel.as_posix(),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((REPO_ROOT / manifest_rel).read_text(encoding="utf-8"))
            records = manifest["files"]
            self.assertEqual(manifest["summary"]["files_linked"], 1)
            self.assertEqual(manifest["summary"]["files_deduplicated"], 1)
            self.assertEqual({record["target_path"] for record in records}, {records[0]["target_path"]})
            canonical = REPO_ROOT / output_rel / records[0]["target_path"]
            self.assertEqual(canonical.read_text(encoding="utf-8"), "same file")
            self.assertNotIn(str(source), json.dumps(manifest))

    def test_rejects_paths_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            result = self.run_linker(
                "--source",
                f"DriveD={source}",
                "--output-root",
                "../outside",
                "--manifest",
                "manifest.json",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must stay inside the repository", result.stderr)

    def test_rejects_duplicate_normalized_source_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            result = self.run_linker(
                "--source",
                f"A B={first}",
                "--source",
                f"A-B={second}",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("used by more than one folder", result.stderr)

    def test_include_filters_only_copy_requested_paths(self) -> None:
        with tempfile.TemporaryDirectory() as source_temp, tempfile.TemporaryDirectory(
            dir=REPO_ROOT
        ) as output_temp:
            source = Path(source_temp) / "source"
            root = Path(output_temp)
            (source / "Business").mkdir(parents=True)
            (source / "Business" / "invoice.txt").write_text("invoice", encoding="utf-8")
            (source / "Business" / "notes.txt").write_text("notes", encoding="utf-8")
            output_rel = root.relative_to(REPO_ROOT) / "Library"
            manifest_rel = root.relative_to(REPO_ROOT) / "manifest.json"

            result = self.run_linker(
                "--source",
                f"DriveD={source}",
                "--include",
                "*invoice*",
                "--output-root",
                output_rel.as_posix(),
                "--manifest",
                manifest_rel.as_posix(),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((REPO_ROOT / manifest_rel).read_text(encoding="utf-8"))
            self.assertEqual([record["relative_path"] for record in manifest["files"]], ["Business/invoice.txt"])
            self.assertEqual(
                [record["relative_path"] for record in manifest["skipped"]],
                ["Business/notes.txt"],
            )

    def test_rejects_generated_output_inside_source(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as temp:
            source = Path(temp)
            output_rel = source.relative_to(REPO_ROOT) / "Library"
            result = self.run_linker(
                "--source",
                f"DriveD={source}",
                "--output-root",
                output_rel.as_posix(),
                "--manifest",
                "manifest.json",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("overlaps a generated destination", result.stderr)

    def test_repository_plugin_and_agent_links_are_valid(self) -> None:
        settings = json.loads((REPO_ROOT / ".github/copilot/settings.json").read_text())
        marketplace = json.loads((REPO_ROOT / ".github/plugin/marketplace.json").read_text())
        self.assertTrue(settings["extraKnownMarketplaces"]["jf-life-tools"])
        self.assertTrue(settings["enabledPlugins"]["jf-life-maintenance@jf-life-tools"])

        entry = next(
            plugin for plugin in marketplace["plugins"] if plugin["name"] == "jf-life-maintenance"
        )
        plugin_root = (REPO_ROOT / entry["source"]).resolve()
        self.assertEqual(
            json.loads((plugin_root / "plugin.json").read_text())["name"],
            entry["name"],
        )
        self.assertTrue((plugin_root / "com.github.copilot/agents/jf-life-maintenance.agent.md").is_file())
        self.assertTrue((plugin_root / "skills/jf-life-sync/SKILL.md").is_file())
        self.assertTrue((REPO_ROOT / ".github/agents/jf-life-maintainer.agent.md").is_file())
        self.assertTrue((REPO_ROOT / ".github/agents/jf-life-reviewer.agent.md").is_file())


if __name__ == "__main__":
    unittest.main()
