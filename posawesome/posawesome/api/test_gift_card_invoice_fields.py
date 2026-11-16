import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
HOOKS_PATH = REPO_ROOT / "posawesome" / "hooks.py"
FIXTURES_PATH = REPO_ROOT / "posawesome" / "fixtures" / "custom_field.json"


class TestGiftCardInvoiceFieldRegistration(unittest.TestCase):
    def test_hooks_export_invoice_redemption_fields(self):
        hooks = HOOKS_PATH.read_text()

        self.assertIn("Sales Invoice-gift_card_redemptions", hooks)
        self.assertIn("POS Invoice-gift_card_redemptions", hooks)

    def test_fixtures_include_invoice_redemption_fields(self):
        fixtures = FIXTURES_PATH.read_text()

        self.assertIn("Sales Invoice-gift_card_redemptions", fixtures)
        self.assertIn("POS Invoice-gift_card_redemptions", fixtures)


if __name__ == "__main__":
    unittest.main()
