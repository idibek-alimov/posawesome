"""Read projections/capability guards with controlled data; no live site writes."""
import copy
import unittest
from inspect import unwrap
from unittest.mock import Mock, patch

import frappe
from posawesome.posawesome.shift_review import desk
from posawesome.posawesome.shift_review.test_review import ReviewFixture


class ListTests(unittest.TestCase):
    def setUp(self):
        self.f = Mock(PermissionError=frappe.PermissionError, ValidationError=frappe.ValidationError)
        self.f.throw.side_effect = lambda message, exception=frappe.ValidationError: (_ for _ in ()).throw(exception(message))
        self.patch = patch.object(desk, "frappe", self.f); self.patch.start(); self.addCleanup(self.patch.stop)
        self.guard = patch.object(desk, "require_manager"); self.guard.start(); self.addCleanup(self.guard.stop)
        self.parents = [frappe._dict(name="old", company="Test", pos_profile="Register", cashier="Cashier", closing_shift="Close", creation="2020-01-01", status="Pending review", currency="TJS"),
                        frappe._dict(name="second", company="Other", pos_profile="Other", cashier="Cashier", closing_shift="Other close", creation="2026-11-06", status="Partially resolved", currency="USD")]
        self.f.get_list.return_value = self.parents
        self.f.get_all.return_value = [frappe._dict(parent="old", account="Till", remaining_amount=-50, original_difference=-50),
                                       frappe._dict(parent="old", account="Till", remaining_amount=50, original_difference=50),
                                       frappe._dict(parent="second", account="Bank", remaining_amount=-20, original_difference=-30)]

    def test_all_dates_unresolved_separate_sign_currency_full_summary_before_paging(self):
        result = unwrap(desk.get_list)(from_date="2026-01-01", to_date="2026-11-01", page_length=1)
        self.assertNotIn("creation", self.f.get_list.call_args.kwargs["filters"])
        self.assertEqual(self.f.get_list.call_args.kwargs["limit_page_length"], 0)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["shifts_needing_review"], 2)
        self.assertEqual(result["currencies"], [dict(currency="TJS", shortage="50", surplus="50"), dict(currency="USD", shortage="20", surplus="0")])
        self.assertEqual(len(result["rows"]), 1)
        self.assertTrue(result["has_more"])
        self.f.db.commit.assert_not_called(); self.f.db.set_value.assert_not_called()

    def test_every_unresolved_status_and_all_preserve_older_unresolved_money(self):
        for status in (*desk.UNRESOLVED, "all"):
            unwrap(desk.get_list)(status=status, from_date="2026-01-01", to_date="2026-11-01")
            self.assertNotIn("creation", self.f.get_list.call_args.kwargs["filters"])

    def test_history_dates_are_inclusive_and_search_scope_uses_native_get_list(self):
        unwrap(desk.get_list)(company="Test", status="Resolved", from_date="2026-01-01", to_date="2026-02-01", search="cashier")
        args = self.f.get_list.call_args.kwargs
        self.assertEqual(args["filters"]["creation"], ["between", ["2026-01-01", "2026-02-01 23:59:59.999999"]])
        self.assertEqual(args["filters"]["company"], "Test")
        self.assertTrue(args["or_filters"])
        self.assertEqual(self.f.get_all.call_args.kwargs["filters"]["parent"], ["in", ["old", "second"]])

    def test_unsupported_status_and_bad_history_dates_rejected(self):
        for values in (dict(status="forged"), dict(status="Resolved", from_date="2026-02-01", to_date="2026-01-01")):
            with self.assertRaises(frappe.ValidationError): unwrap(desk.get_list)(**values)
        self.f.get_list.assert_not_called()

    def test_parent_scoped_child_queries_are_bounded(self):
        self.f.get_list.return_value = [frappe._dict(self.parents[0], name=str(i)) for i in range(451)]
        self.f.get_all.return_value = []
        unwrap(desk.get_list)()
        self.assertEqual([len(call.kwargs["filters"]["parent"][1]) for call in self.f.get_all.call_args_list], [200, 200, 51])

    def test_navigation_hides_unavailable_schema_and_unauthorized_role(self):
        with patch.object(desk.policy, "is_manager", return_value=False):
            self.assertFalse(unwrap(desk.navigation)()["available"])
        self.f.db.table_exists.side_effect = lambda dt: dt != "POS Shift Review Action"
        with patch.object(desk.policy, "is_manager", return_value=True):
            self.assertFalse(unwrap(desk.navigation)()["available"])
        self.f.db.table_exists.side_effect = None
        self.f.db.table_exists.return_value = True
        self.f.has_permission.return_value = False
        with patch.object(desk.policy, "is_manager", return_value=True):
            self.assertFalse(unwrap(desk.navigation)()["available"])

    def test_manager_and_native_permission_are_required(self):
        self.guard.stop()
        with patch.object(desk.policy, "require_schema"), patch.object(desk.policy, "is_manager", return_value=False):
            with self.assertRaises(frappe.PermissionError): unwrap(desk.get_list)()
        self.f.get_list.assert_not_called()


class DeskFixture(ReviewFixture):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(desk, "frappe", self.f))
        self.stack.enter_context(patch.object(desk, "_", lambda text: text))
        self.f.get_list.side_effect = self.get_all
        self.expense_options = dict(categories=[dict(name="Taxi", category_name="Taxi")], payment_sources=[dict(account="Till")])
        self.stack.enter_context(patch.object(desk, "get_expense_options", return_value=self.expense_options))
        self.stack.enter_context(patch.object(desk.expense_policy, "quiet_setup_checks"))
        self.review.cashier_reason = "Missing taxi"


class DetailTests(DeskFixture):
    def test_detail_is_read_only_and_preserves_original_after_partial_resolution(self):
        self.act("Missing expense", dict(row_key=self.review.accounts[0].row_key, signed_amount=-20, amount=20, category="Taxi", posting_date="2026-11-06"))
        before = copy.deepcopy(self.review.snapshot_json)
        self.f.db.set_value.reset_mock(); self.f.db.commit.reset_mock()
        data = unwrap(desk.get_detail)("REVIEW")
        self.assertEqual(data["accounts"][0]["original_difference"], "-50.00")
        self.assertEqual(data["accounts"][0]["remaining_amount"], -30)
        self.assertEqual(self.review.snapshot_json, before)
        self.assertEqual(data["cashier_reason"], "Missing taxi")
        self.assertNotIn("evidence_json", data["history"][0])
        self.f.db.set_value.assert_not_called(); self.f.db.commit.assert_not_called()

    def test_changed_adjustment_account_requires_new_confirmation_before_posting(self):
        with self.assertRaises(frappe.TimestampMismatchError):
            self.act("Cash adjustment", dict(row_key=self.review.accounts[0].row_key, signed_amount=-50,
                posting_date="2026-11-06", expected_adjustment_account="Changed account"))
        self.assertEqual(self.ledger, [])
        self.assertEqual(self.review.accounts[0].remaining_amount, -50)

    def test_manager_without_approval_role_cannot_get_adjustment_capability(self):
        self.roles = ["Retail Manager"]
        caps = desk.capabilities(self.review)["rows"][self.review.accounts[0].row_key]
        self.assertTrue(caps["missing_expense"])
        self.assertFalse(caps["cash_adjustment"])
        self.assertIsNone(caps["adjustment_account"])

    def test_native_permissions_and_sources_gate_expense_and_adjustment(self):
        self.denied.update({("Quick Expense", "submit"), ("Journal Entry", "submit")})
        caps = desk.capabilities(self.review)["rows"][self.review.accounts[0].row_key]
        self.assertFalse(caps["missing_expense"]); self.assertFalse(caps["cash_adjustment"])
        self.denied.clear(); self.expense_options["payment_sources"] = []
        caps = desk.capabilities(self.review)["rows"][self.review.accounts[0].row_key]
        self.assertFalse(caps["missing_expense"]); self.assertTrue(caps["cash_adjustment"])

    def test_bank_foreign_currency_opposite_and_void_cases_fail_closed(self):
        self.build_review([dict(mode_of_payment="Cash", account="Till", expected_amount=1000), dict(mode_of_payment="Card", account="Till", expected_amount=0)], {"Cash":950,"Card":50})
        self.assertFalse(any(row["cash_adjustment"] for row in desk.capabilities(self.review)["rows"].values()))
        self.build_review([dict(mode_of_payment="Bank", account="Alif", expected_amount=1000)], {"Bank":950})
        self.assertFalse(desk.capabilities(self.review)["rows"][self.review.accounts[0].row_key]["cash_adjustment"])
        self.review.accounts[0].account_currency = "USD"
        self.assertFalse(desk.capabilities(self.review)["rows"][self.review.accounts[0].row_key]["link_source"])
        self.review.status = "Voided"
        self.assertFalse(desk.capabilities(self.review)["can_investigate"])

    def test_history_denied_source_links_do_not_leak_document_ids(self):
        self.act("Missing expense", dict(row_key=self.review.accounts[0].row_key, signed_amount=-20, amount=20, category="Taxi", posting_date="2026-11-06"))
        self.denied.update({("Quick Expense", "read"), ("Journal Entry", "read")})
        data = unwrap(desk.get_detail)("REVIEW")
        self.assertIsNone(data["history"][0]["source_name"])
        self.assertIsNone(data["history"][0]["financial_name"])



class SourceProjectionTests(DeskFixture):
    def original_source(self):
        from posawesome.posawesome.shift_review import snapshot
        from erpnext.accounts.expense_services import commands
        import json
        self.add("Quick Expense", "ORIGINAL", company="Test", docstatus=1, amount=20)
        self.add("Journal Entry", "ORIGINAL-JE", company="Test", docstatus=2)
        original = json.loads(self.review.snapshot_json)
        original["sources"] = [dict(doctype="Quick Expense", name="ORIGINAL", posting_date="2026-11-06",
            modified="2026-11-06 09:00:00", document=dict(amount=20, paid_from="Till"),
            vouchers=[dict(doctype="Journal Entry", name="ORIGINAL-JE", legs=[])])]
        self.review.snapshot_json = snapshot.encode(original)
        self.review.snapshot_hash = commands.fingerprint(original)

    def test_changed_original_source_and_cancelled_accounting_are_visible_without_rewriting_snapshot(self):
        self.original_source()
        original = self.review.snapshot_json
        data = unwrap(desk.get_detail)("REVIEW")
        source = data["sources"][0]
        self.assertTrue(source["changed"])
        self.assertEqual(source["financial"][0]["docstatus"], 2)
        self.assertEqual(self.review.snapshot_json, original)

    def test_original_journal_reversal_is_visible(self):
        self.original_source()
        self.add("Journal Entry", "REVERSAL", company="Test", docstatus=1, reversal_of="ORIGINAL-JE")
        data = unwrap(desk.get_detail)("REVIEW")
        self.assertTrue(data["sources"][0]["financial"][0]["reversed"])

    def test_denied_original_source_is_redacted(self):
        self.original_source()
        self.denied.add(("Quick Expense", "read"))
        data = unwrap(desk.get_detail)("REVIEW")
        self.assertEqual(data["sources"], [dict(restricted=True)])

    def test_denied_original_financial_source_is_redacted(self):
        self.original_source()
        self.denied.add(("Journal Entry", "read"))
        data = unwrap(desk.get_detail)("REVIEW")
        self.assertEqual(data["sources"][0]["financial"], [dict(restricted=True)])


class OptionalNavigationTests(unittest.TestCase):
    def test_erpnext_without_pos_has_no_import_or_link(self):
        from erpnext.accounts.page.expense_desk import expense_desk
        with patch.object(expense_desk.frappe, "get_installed_apps", return_value=["frappe", "erpnext"]), patch.object(expense_desk.frappe, "get_attr") as resolve:
            self.assertEqual(unwrap(expense_desk.get_shift_review_navigation)(), dict(available=False))
            resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
