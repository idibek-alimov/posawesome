import json
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKSPACE_PATH = REPO_ROOT / "posawesome" / "posawesome" / "workspace" / "pos_awesome" / "pos_awesome.json"
HOOKS_PATH = REPO_ROOT / "posawesome" / "hooks.py"
INSTALL_HOOK = "posawesome.setup.install"


class TestGiftCardWorkspaceExposure(unittest.TestCase):
    def test_workspace_json_exposes_gift_card_doctype(self):
        workspace = json.loads(WORKSPACE_PATH.read_text())
        links = workspace.get("links") or []
        content = json.loads(workspace.get("content") or "[]")

        self.assertTrue(
            any(link.get("type") == "Link" and link.get("link_to") == "POS Gift Card" for link in links)
        )
        self.assertTrue(
            any(
                block.get("type") == "card" and (block.get("data") or {}).get("card_name") == "Gift Cards"
                for block in content
            )
        )

    def test_hooks_register_install_and_migrate_setup(self):
        hooks = HOOKS_PATH.read_text()

        self.assertIn(INSTALL_HOOK, hooks)

    def test_workspace_json_exposes_submission_ledger_doctype(self):
        workspace = json.loads(WORKSPACE_PATH.read_text())
        links = workspace.get("links") or []
        content = json.loads(workspace.get("content") or "[]")

        self.assertTrue(
            any(
                link.get("type") == "Link" and link.get("link_to") == "POS Invoice Submission Ledger"
                for link in links
            )
        )
        self.assertTrue(
            any(
                block.get("type") == "card"
                and (block.get("data") or {}).get("card_name") == "Submission Ledger"
                for block in content
            )
        )


if __name__ == "__main__":
    unittest.main()
