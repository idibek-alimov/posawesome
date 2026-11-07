import unittest
from unittest.mock import Mock, patch

from posawesome.patches import add_pos_cash_movement_settings as fields
from posawesome.patches import repair_expense_source_settings as repair


class TestExpenseSourceRepair(unittest.TestCase):
    def test_repeated_repair_adds_only_missing_fields_and_does_not_rewrite_profile_values(self):
        existing = {"POS Profile-posa_enable_cash_movement", "POS Profile-posa_allow_pos_expense"}
        fake = Mock()
        fake.db.exists.side_effect = lambda dt, name: name in existing
        created = []
        def create(doctype, field):
            created.append(field["fieldname"])
            existing.add(f"{doctype}-{field['fieldname']}")
        with patch.object(fields, "frappe", fake), patch.object(fields, "create_custom_field", side_effect=create), patch.object(repair, "frappe", fake):
            repair.execute()
            count = len(created)
            repair.execute()
        self.assertEqual(len(created), count)
        self.assertIn("posa_default_source_account", created)
        self.assertIn("posa_allow_source_account_override", created)
        self.assertNotIn("posa_enable_cash_movement", created)
        self.assertNotIn("posa_allow_pos_expense", created)
        fake.db.set_value.assert_not_called()
        fake.db.commit.assert_not_called()
        self.assertEqual(fake.db.updatedb.call_count, 2)
