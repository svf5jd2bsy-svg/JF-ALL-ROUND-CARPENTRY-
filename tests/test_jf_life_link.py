import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "jf_life_link.py"
SPEC = importlib.util.spec_from_file_location("jf_life_link", SCRIPT)
assert SPEC and SPEC.loader
JF_LIFE_LINK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = JF_LIFE_LINK
SPEC.loader.exec_module(JF_LIFE_LINK)


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

    def test_rejects_source_inside_repository(self) -> None:
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
        self.assertIn("is inside the repository", result.stderr)

    def test_drive_root_source_prunes_nested_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            drive_root = Path(temp)
            virtual_repo = drive_root / "JF-ALL-ROUND-CARPENTRY-"
            source_file = drive_root / "JF quote.pdf"
            repo_file = virtual_repo / "Library" / "generated.pdf"
            repo_file.parent.mkdir(parents=True)
            source_file.write_text("source", encoding="utf-8")
            repo_file.write_text("generated", encoding="utf-8")

            previous_repo_root = JF_LIFE_LINK.REPO_ROOT
            JF_LIFE_LINK.REPO_ROOT = virtual_repo
            try:
                JF_LIFE_LINK.validate_source_destinations(
                    [JF_LIFE_LINK.SourceSpec("DriveD", drive_root)],
                    [virtual_repo / "Library"],
                )
                self.assertEqual(JF_LIFE_LINK.iter_files(drive_root), [source_file])
            finally:
                JF_LIFE_LINK.REPO_ROOT = previous_repo_root

    def test_checks_the_actual_push_urls_for_private_visibility(self) -> None:
        push_urls = (
            "https://github.com/example/first.git\n"
            "git@github.com:example/second.git\n"
            "ssh://git@ssh.github.com:443/example/third.git\n"
        )
        with (
            patch.object(
                JF_LIFE_LINK,
                "run_git_command",
                return_value=subprocess.CompletedProcess([], 0, stdout=push_urls),
            ) as git,
            patch.object(
                JF_LIFE_LINK.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout="private\n"),
            ) as gh,
        ):
            JF_LIFE_LINK.require_private_push_destinations()

        git.assert_called_once_with(["git", "remote", "get-url", "--push", "--all", "origin"])
        self.assertEqual(
            [call.args[0] for call in gh.call_args_list],
            [
                ["gh", "api", "--hostname", "github.com", f"repos/example/{repo}", "--jq", ".visibility"]
                for repo in ("first", "second", "third")
            ],
        )

    def test_public_destination_blocks_import_before_any_files_are_read(self) -> None:
        for flag in ("--git-commit", "--git-push"):
            with (
                self.subTest(flag=flag),
                tempfile.TemporaryDirectory() as source,
                patch.object(sys, "argv", [str(SCRIPT), "--source", f"DriveD={source}", flag]),
                patch.object(JF_LIFE_LINK.os, "chdir"),
                patch.object(
                    JF_LIFE_LINK,
                    "run_git_command",
                    return_value=subprocess.CompletedProcess(
                        [], 0, stdout="https://github.com/example/public.git\n"
                    ),
                ),
                patch.object(
                    JF_LIFE_LINK.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, stdout="public\n"),
                ),
                patch.object(JF_LIFE_LINK, "iter_files") as iter_files,
                patch.object(JF_LIFE_LINK, "stage_commit_push") as stage,
                patch.object(sys, "stderr") as stderr,
            ):
                self.assertEqual(JF_LIFE_LINK.main(), 2)
                iter_files.assert_not_called()
                stage.assert_not_called()
                self.assertIn("private GitHub repository", str(stderr.write.call_args_list))

    def test_unverified_destination_fails_closed(self) -> None:
        for visibility in ("", "null", "internal"):
            with (
                self.subTest(visibility=visibility),
                patch.object(
                    JF_LIFE_LINK,
                    "run_git_command",
                    return_value=subprocess.CompletedProcess(
                        [], 0, stdout="https://github.com/example/unknown.git\n"
                    ),
                ),
                patch.object(
                    JF_LIFE_LINK.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, stdout=visibility),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "private GitHub repository"):
                    JF_LIFE_LINK.require_private_push_destinations()

    def test_dry_run_skips_private_destination_check(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source,
            patch.object(
                sys, "argv", [str(SCRIPT), "--source", f"DriveD={source}", "--dry-run", "--git-push"]
            ),
            patch.object(JF_LIFE_LINK.os, "chdir"),
            patch.object(JF_LIFE_LINK, "require_private_push_destinations") as require_private,
            patch.object(sys, "stdout"),
        ):
            self.assertEqual(JF_LIFE_LINK.main(), 0)
        require_private.assert_not_called()

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
