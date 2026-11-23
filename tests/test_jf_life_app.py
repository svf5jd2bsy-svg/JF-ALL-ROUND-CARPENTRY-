import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class JfLifeAppTests(unittest.TestCase):
    def test_pwa_manifest_is_valid_and_standalone(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "App" / "manifest.webmanifest").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "JF LIFE Library")
        self.assertEqual(manifest["display"], "standalone")
        self.assertGreaterEqual(len(manifest["icons"]), 2)
        for icon in manifest["icons"]:
            self.assertTrue((REPO_ROOT / "App" / icon["src"]).is_file())

    def test_library_page_registers_pwa_features(self) -> None:
        html = (REPO_ROOT / "App" / "Library-Index.html").read_text(encoding="utf-8")
        self.assertIn('rel="manifest"', html)
        self.assertIn('navigator.serviceWorker.register("sw.js")', html)
        self.assertIn('id="filePicker"', html)
        self.assertIn('id="folderPicker"', html)
        self.assertIn('id="exportManifest"', html)

    def test_mobile_app_assets_exist(self) -> None:
        app_json = json.loads(
            (REPO_ROOT / "mobile" / "jf-life-mobile" / "app.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(app_json["expo"]["name"], "JF LIFE")
        self.assertEqual(app_json["expo"]["version"], "1.1.0")
        self.assertEqual(
            app_json["expo"]["ios"]["bundleIdentifier"],
            "com.jflife.mobile",
        )
        icon = REPO_ROOT / "mobile" / "jf-life-mobile" / "assets" / "icon.png"
        splash = REPO_ROOT / "mobile" / "jf-life-mobile" / "assets" / "splash.png"
        self.assertTrue(icon.is_file())
        self.assertTrue(splash.is_file())
        eas = json.loads(
            (REPO_ROOT / "mobile" / "jf-life-mobile" / "eas.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("preview", eas["build"])


if __name__ == "__main__":
    unittest.main()
