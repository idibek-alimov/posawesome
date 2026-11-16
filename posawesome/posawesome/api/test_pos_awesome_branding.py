import ast
import json
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGE_PATH = REPO_ROOT / "package.json"
MANIFEST_PATH = REPO_ROOT / "posawesome" / "www" / "manifest.json"
WORKSPACE_PATH = (
    REPO_ROOT
    / "posawesome"
    / "posawesome"
    / "workspace"
    / "pos_awesome"
    / "pos_awesome.json"
)
HOOKS_PATH = REPO_ROOT / "posawesome" / "hooks.py"
FIXTURES_PATH = REPO_ROOT / "posawesome" / "fixtures" / "custom_field.json"


class TestPosAwesomeBrandingContract(unittest.TestCase):
    def test_desktop_brand_preserves_installed_identity_and_protocol(self):
        package = json.loads(PACKAGE_PATH.read_text())
        build = package["build"]
        protocol = next(
            entry for entry in build["protocols"] if "posawesome" in entry["schemes"]
        )

        self.assertEqual(package["name"], "posawesome")
        self.assertEqual(build["appId"], "com.posawesome.desktop")
        self.assertEqual(build["productName"], "POS Awesome Desktop")
        self.assertEqual(protocol["name"], "POS Awesome Links")

    def test_pwa_and_workspace_keep_pos_awesome_as_the_canonical_brand(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        workspace = json.loads(WORKSPACE_PATH.read_text())

        self.assertEqual(manifest["name"], "Radolfa")
        self.assertEqual(manifest["short_name"], "Radolfa")
        self.assertEqual(workspace["name"], "POS Awesome")
        self.assertEqual(workspace["module"], "POSAwesome")
        self.assertEqual(workspace["label"], "Radolfa")
        self.assertEqual(workspace["title"], "Radolfa")

    def test_profile_branding_options_are_registered_in_fixtures(self):
        hooks = HOOKS_PATH.read_text()
        fields = {
            f["name"]: f for f in json.loads(FIXTURES_PATH.read_text())
        }

        self.assertIn('app_name = "posawesome"', hooks)
        self.assertEqual(
            fields["POS Profile-posa_section_awesome_dashboard"]["label"],
            "Awesome Dashboard",
        )
        for fieldname in (
            "posa_branding_section",
            "posa_enable_custom_branding",
            "posa_brand_name",
            "posa_brand_short_name",
            "posa_brand_logo",
        ):
            self.assertIn(f"POS Profile-{fieldname}", fields)


if __name__ == "__main__":
    unittest.main()
