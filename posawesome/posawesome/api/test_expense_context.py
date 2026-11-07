"""POS adapter regressions with stored shift/profile fixtures; no financial posting."""

import unittest
from unittest.mock import patch

import frappe

from erpnext.accounts.expense_services import policy
from erpnext.accounts.expense_services import test_expense_policy as fixtures
from posawesome.posawesome.api import expense_context


class TestExpenseContext(unittest.TestCase):
    # Reuse fixture setup only; the generic policy tests have their own suite.
    def setUp(self):
        fixtures.PolicyFixture.setUp(self)
        self.stack.enter_context(patch.object(expense_context, "frappe", self.f))
        self.stack.enter_context(patch.object(expense_context, "_", lambda text: text))
        self.shift = frappe._dict(name="Shift", company="Test", pos_profile="Register", user="cashier", status="Open", docstatus=1)
        self.profile = frappe._dict(name="Register", company="Test", disabled=0,
            applicable_for_users=[frappe._dict(user="cashier")], payments=[frappe._dict(mode_of_payment="Cash")])
        self.records[("POS Profile", "Register")] = self.profile
        self.f.get_doc.side_effect = lambda dt, name, **kw: self.shift if dt == "POS Opening Shift" else self.records[(dt, name)]
        self.f.db.get_value.return_value = "Till"
        self.roles = ["Retail Cashier", "Sales User"]

    def validate(self, **kwargs):
        args = dict(company="Test", pos_profile="Register", pos_opening_shift="Shift", entry_context="POS", action="create", user="cashier")
        args.update(kwargs)
        return expense_context.validate_context(**args)

    def test_register_comes_from_stored_shift(self):
        context = self.validate(pos_profile=None)
        self.assertEqual(context["pos_profile"], "Register")
        self.assertEqual(context["source_accounts"], ["Till"])
        self.f.db.get_value.assert_any_call("POS Opening Shift", "Shift", "name", for_update=True)

    def test_form_note_requirement_comes_from_stored_register(self):
        self.profile.posa_require_cash_movement_remarks = 1
        self.assertTrue(self.validate()["note_required"])
        self.profile.posa_require_cash_movement_remarks = 0
        self.assertFalse(self.validate()["note_required"])

    def test_other_cashiers_shift_is_rejected(self):
        self.shift.user = "other cashier"
        with self.assertRaises(frappe.PermissionError):
            self.validate()

    def test_profile_and_company_spoofs_are_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.validate(pos_profile="Other Register")
        with self.assertRaises(frappe.ValidationError):
            self.validate(company="Other Company")

    def test_cashier_cannot_record_after_closing(self):
        self.shift.status = "Closed"
        with self.assertRaises(frappe.ValidationError):
            self.validate()
        self.assertEqual(self.validate(action="read")["pos_opening_shift"], "Shift")

    def test_manager_can_correct_closed_shift_within_assigned_register(self):
        self.shift.status = "Closed"
        self.shift.user = "other cashier"
        self.roles = ["Retail Manager", "Accounts User"]
        self.assertEqual(self.validate(entry_context="POS Correction")["pos_opening_shift"], "Shift")
        self.profile.applicable_for_users = [frappe._dict(user="someone else")]
        with self.assertRaises(frappe.PermissionError):
            self.validate(entry_context="POS Correction")

    def test_manager_can_read_unassigned_legacy_record_but_cannot_write_without_shift(self):
        self.roles = ["Retail Manager", "Accounts User"]
        context = self.validate(pos_opening_shift=None, entry_context="POS Correction", action="read")
        self.assertIsNone(context["pos_opening_shift"])
        with self.assertRaises(frappe.ValidationError):
            self.validate(pos_opening_shift=None, entry_context="POS Correction")

    def test_cashier_cannot_cancel_legacy_expense(self):
        original = frappe._dict(name="CM-1", company="Test", pos_profile="Register", pos_opening_shift="Shift",
            user="cashier", movement_type="Expense", amount=50, source_account="Till", target_account="Taxi Expense")
        self.f.get_doc.side_effect = lambda *args, **kw: original
        self.profile.posa_enable_cash_movement = 1
        self.profile.posa_allow_cancel_submitted_cash_movement = 1
        with self.assertRaises(frappe.PermissionError):
            expense_context.before_cancel_legacy_expense(original)

    def test_posted_legacy_expense_history_is_preserved(self):
        with self.assertRaises(frappe.ValidationError):
            expense_context.protect_legacy_expense_history(frappe._dict(movement_type="Expense", docstatus=2))
        expense_context.protect_legacy_expense_history(frappe._dict(movement_type="Deposit", docstatus=2))

    def test_cancellation_cannot_relabel_stored_expense_as_deposit(self):
        original = frappe._dict(name="CM-1", company="Test", movement_type="Expense", amount=50)
        self.f.get_doc.side_effect = lambda *args, **kw: original
        incoming = frappe._dict(original, movement_type="Deposit")
        with self.assertRaises(frappe.ValidationError):
            expense_context.before_cancel_legacy_expense(incoming)

    def test_old_native_sales_role_can_read_own_legacy_movement(self):
        self.roles = ["Sales User"]
        self.assertEqual(self.validate(action="read", legacy=True)["pos_opening_shift"], "Shift")
        self.shift.user = "another cashier"
        with self.assertRaises(frappe.PermissionError):
            self.validate(action="read", legacy=True)

    def test_session_discovers_own_native_permitted_shift_without_bootstrap_writes(self):
        self.f.get_list.return_value = [self.shift]
        self.f.get_hooks.return_value = ["pos-validator"]
        self.f.get_attr.return_value = expense_context.validate_context
        result = expense_context.get_pos_expense_session.__wrapped__()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["pos_opening_shift"], "Shift")
        self.assertTrue(result["can_record"])
        filters = self.f.get_list.call_args.kwargs["filters"]
        self.assertEqual(filters["user"], "cashier")
        self.assertEqual(filters["status"], "Open")
        self.f.db.commit.assert_not_called()
        self.f.db.set_value.assert_not_called()
        self.assertFalse(any(call.kwargs.get("for_update") for call in self.f.db.get_value.call_args_list))

    def test_session_never_guesses_among_multiple_open_shifts(self):
        self.f.get_list.return_value = [self.shift, frappe._dict(self.shift, name="Another")]
        self.assertEqual(expense_context.get_pos_expense_session.__wrapped__()["status"], "select_shift")
        self.f.get_cached_doc.assert_not_called()

    def test_session_missing_explicit_shift_does_not_fall_back_to_another(self):
        self.f.get_list.return_value = []
        self.assertEqual(expense_context.get_pos_expense_session.__wrapped__("Closed shift")["status"], "no_shift")
        self.assertEqual(self.f.get_list.call_args.kwargs["filters"]["name"], "Closed shift")

    def test_session_respects_register_assignment_and_native_read_scope(self):
        self.f.get_list.return_value = [self.shift]
        self.f.get_hooks.return_value = ["pos-validator"]
        self.f.get_attr.return_value = expense_context.validate_context
        self.profile.applicable_for_users = [frappe._dict(user="another")]
        with self.assertRaises(frappe.PermissionError):
            expense_context.get_pos_expense_session.__wrapped__()

    def test_session_is_view_only_if_register_disabled_or_native_submit_denied(self):
        self.f.get_list.return_value = [self.shift]
        self.f.get_hooks.return_value = ["pos-validator"]
        self.f.get_attr.return_value = expense_context.validate_context
        self.f.has_permission.side_effect = lambda dt, action, **kw: action != "submit"
        self.assertFalse(expense_context.get_pos_expense_session.__wrapped__()["can_record"])
        self.f.has_permission.side_effect = None
        self.f.has_permission.return_value = True
        self.profile.disabled = 1
        self.assertFalse(expense_context.get_pos_expense_session.__wrapped__()["can_record"])
