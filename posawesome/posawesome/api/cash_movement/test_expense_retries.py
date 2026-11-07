"""Old queue receipts survive closure without creating new cash movements."""
import unittest
from inspect import unwrap
from unittest.mock import Mock, patch

import frappe
from posawesome.posawesome.api.cash_movement import service


class TestLegacyExpenseRetries(unittest.TestCase):
    def setUp(self):
        self.fake = Mock()
        self.fake.session.user = "cashier"
        self.fake.throw.side_effect = lambda message, *args: (_ for _ in ()).throw(frappe.PermissionError(message))
        self.doc = Mock()
        self.values = dict(name="CM-OLD", user="cashier", owner="cashier", company="Test", pos_profile="Register",
            pos_opening_shift="ClosedShift", movement_type="Expense", amount=50, source_account="Till",
            target_account="Tea expense", expense_account="Tea expense", posting_date="2026-11-04",
            against_name="Tea vendor", remarks="Tea", client_request_id="cm-old", docstatus=1, journal_entry="JE-OLD")
        for key, value in self.values.items():
            setattr(self.doc, key, value)
        self.doc.get.side_effect = self.values.get
        self.doc.as_dict.side_effect = lambda: dict(self.values)
        self.payload = dict(pos_opening_shift="ClosedShift", amount=50, client_request_id="cm-old", remarks="Tea")
        self.patches = [patch.object(service, "frappe", self.fake), patch.object(service, "_", lambda value: value),
            patch("erpnext.accounts.expense_services.commands.lock_actor"),
            patch("erpnext.accounts.expense_services.policy.check_company"),
            patch("erpnext.accounts.expense_services.policy.check_user_scope"),
            patch("erpnext.accounts.expense_services.policy.currency_precision", return_value=2),
            patch("frappe.get_system_settings", return_value="Banker's Rounding (legacy)"),
            patch("posawesome.posawesome.api.expense_context.validate_context"),
            patch.object(service, "ensure_no_duplicate_client_request", return_value=self.doc)]
        for patcher in self.patches:
            patcher.start(); self.addCleanup(patcher.stop)

    def test_closed_shift_returns_existing_even_when_creation_is_disabled(self):
        with patch.object(service, "get_opening_shift", side_effect=AssertionError("must not create")), \
                patch.object(service, "ensure_feature_enabled", side_effect=AssertionError("must not resolve current settings")):
            result = service._create_cash_movement(self.payload, "Expense")
        self.assertEqual(result["journal_entry"], "JE-OLD")
        self.fake.get_doc.assert_not_called()
        self.doc.submit.assert_not_called()
        self.doc.check_permission.assert_called_once_with("read")

    def test_closed_shift_cannot_post_a_missing_old_request(self):
        with patch.object(service, "ensure_no_duplicate_client_request", return_value=None), \
                patch.object(service, "get_opening_shift", side_effect=frappe.ValidationError("Closed")):
            with self.assertRaises(frappe.ValidationError):
                service._create_cash_movement(self.payload, "Expense")
        self.fake.get_doc.assert_not_called()

    def test_cross_actor_result_is_not_disclosed(self):
        self.doc.user = "another"
        with self.assertRaises(frappe.PermissionError):
            service._create_cash_movement(self.payload, "Expense")
        self.doc.as_dict.assert_not_called()

    def test_changed_intent_rejected(self):
        for changes in ({"amount": 51}, {"amount": "NaN"}, {"source_account": "OtherTill"},
                        {"remarks": "Different"}, {"posting_date": "2026-11-05"},
                        {"pos_profile": "OtherRegister"}, {"pos_opening_shift": "OtherShift"},
                        {"company": "OtherCompany"}, {"movement_type": "Deposit"}):
            with self.subTest(changes=changes), self.assertRaises(frappe.PermissionError):
                service._create_cash_movement(dict(self.payload, **changes), "Expense")

    def test_old_float_payload_replays_its_original_rounded_currency_amount(self):
        self.doc.amount = self.values['amount'] = 0.3
        result = service._create_cash_movement(dict(self.payload, amount=0.1 + 0.2), "Expense")
        self.assertEqual(result['amount'], 0.3)
        self.doc.submit.assert_not_called()

    def test_deposit_endpoint_cannot_replay_expense(self):
        with self.assertRaises(frappe.PermissionError):
            service._create_cash_movement(self.payload, "Deposit")

    def test_cancelled_original_is_returned_as_cancelled_never_reposted(self):
        self.doc.docstatus = self.values['docstatus'] = 2
        result = service._create_cash_movement(self.payload, "Expense")
        self.assertEqual(result['docstatus'], 2)
        self.doc.submit.assert_not_called()

    def test_outcome_is_authorized_original_receipt(self):
        result = unwrap(service.get_cash_movement_request_outcome)("cm-old")
        self.assertEqual(result, dict(name="CM-OLD", docstatus=1, journal_entry="JE-OLD", status="submitted"))
        self.doc.submit.assert_not_called()

    def test_outcome_respects_revoked_record_read_scope(self):
        self.doc.check_permission.side_effect = frappe.PermissionError("Revoked")
        with self.assertRaises(frappe.PermissionError):
            unwrap(service.get_cash_movement_request_outcome)("cm-old")

    def test_missing_outcome_does_not_create(self):
        with patch.object(service, "ensure_no_duplicate_client_request", return_value=None):
            result = unwrap(service.get_cash_movement_request_outcome)("cm-old")
        self.assertEqual(result['status'], "not_found")
        self.fake.get_doc.assert_not_called()


class TestLegacyDefaultSource(unittest.TestCase):
    def test_echoing_default_is_allowed_without_enabling_source_override(self):
        from posawesome.posawesome.api.cash_movement import validation
        profile = frappe._dict(company="Test", posa_default_source_account="Till", posa_allow_source_account_override=0,
                               posa_allowed_source_accounts=[])
        fake = Mock()
        fake.db.get_value.return_value = "Cash"
        fake.throw.side_effect = frappe.PermissionError("Override disabled")
        with patch.object(validation, "frappe", fake), patch.object(validation, "_", lambda value: value):
            self.assertEqual(validation.resolve_source_cash_account({"source_account": "Till"}, profile), "Till")
            with self.assertRaises(frappe.PermissionError):
                validation.resolve_source_cash_account({"source_account": "OtherTill"}, profile)
