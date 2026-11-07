"""Controlled permissions/posting fixtures for the connected journey; no site writes."""
import copy
from inspect import unwrap
from unittest.mock import patch

import frappe
from . import journey, transfers, snapshot
from .test_desk import DeskFixture


class JourneyTests(DeskFixture):
    def setUp(self):
        super().setUp()
        self.review.cashier = "owner"
        self.stack.enter_context(patch.object(journey, "frappe", self.f))
        self.profile_access = self.stack.enter_context(patch.object(journey, "authorized_profile"))
        self.add("POS Profile", "Register", company="Test")
        self.f.get_list.side_effect = self.list_records
        self.f.get_all.side_effect = self.all_records

    def list_records(self, doctype, filters=None, fields=None, **kwargs):
        rows = super().get_all(doctype, filters, fields, **kwargs)
        if doctype == "POS Shift Review":
            rows.sort(key=lambda row: str(row.creation), reverse="desc" in kwargs.get("order_by", ""))
        length = kwargs.get("limit_page_length", 0)
        return rows[:length] if length else rows

    def all_records(self, doctype, filters=None, fields=None, **kwargs):
        if doctype == "POS Shift Review Account":
            return [frappe._dict(row, parent=review.name) for (dt, name), review in self.docs.items()
                    if dt == "POS Shift Review" and name in filters["parent"][1] for row in review.accounts]
        return super().get_all(doctype, filters, fields, **kwargs)

    def register(self, **kwargs):
        return unwrap(journey.get_register_context)("Register", **kwargs)

    def test_cashier_projection_has_original_remaining_reason_and_no_accounting_evidence(self):
        self.roles = ["Retail Cashier"]
        result = self.register()
        self.assertEqual(result["total"], 1)
        row = result["reviews"][0]
        self.assertEqual(row["accounts"][0]["remaining_amount"], -50)
        self.assertEqual(row["cashier_reason"], "Missing taxi")
        self.assertIsNone(row["url"])
        self.assertNotIn("snapshot_json", row)
        self.assertNotIn("account", row["accounts"][0])
        self.assertNotIn("capabilities", row)
        self.profile_access.assert_called_with("Test", "Register", "owner")
        self.f.db.set_value.assert_not_called(); self.f.db.commit.assert_not_called()

    def test_pending_history_uses_all_dates_and_only_own_same_company_register(self):
        for field, value in (("cashier", "other"), ("company", "Other"), ("pos_profile", "Elsewhere")):
            values = dict(self.review.as_dict(), name=field, closing_shift=field)
            values[field] = value
            self.add("POS Shift Review", **{key: value for key, value in values.items() if key != "doctype"})
        result = self.register()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["reviews"][0]["review"], "REVIEW")

    def test_full_count_survives_paging_and_child_reads_are_bounded(self):
        # Use distinct closing IDs while retaining an old unresolved origin.
        for index in range(205):
            self.add("POS Shift Review", str(index), company="Test", pos_profile="Register", cashier="owner",
                status="Pending review", accounts=copy.deepcopy(self.review.accounts), closing_shift=str(index))
        result = self.register(page_length=1)
        self.assertEqual(result["total"], 206)
        self.assertEqual(len(result["reviews"]), 1)
        self.assertTrue(result["has_more"])
        batches = [call.kwargs["filters"]["parent"][1] for call in self.f.get_all.call_args_list if call.args[0] == "POS Shift Review Account"]
        self.assertEqual([len(batch) for batch in batches], [200, 6])

    def test_unmigrated_or_denied_schema_does_not_expose_history(self):
        self.f.db.table_exists.return_value = False
        self.assertEqual(self.register(), dict(available=False))
        self.profile_access.assert_not_called(); self.f.get_list.assert_not_called()

    def test_changed_register_scope_is_denied_before_reading_reviews(self):
        self.profile_access.side_effect = frappe.PermissionError("Not assigned")
        with self.assertRaises(frappe.PermissionError): self.register()
        self.f.get_list.assert_not_called()

    def test_generic_sales_role_does_not_bypass_the_cashier_read_contract(self):
        self.roles = ["Sales User"]
        with patch.object(journey, "_", lambda value: value):
            with self.assertRaises(frappe.PermissionError): self.register()
        self.f.get_list.assert_not_called()

    def test_closed_review_does_not_expose_other_cashier_or_sources(self):
        self.roles = ["Retail Cashier"]
        self.f.session.user = "cashier"
        # scope() protects this direct endpoint independently of the list filters.
        with self.assertRaises(frappe.PermissionError): unwrap(journey.get_closing_status)("CLOSE")

    def test_partial_then_full_missing_expense_keeps_original_and_next_opening_separate(self):
        original = self.review.snapshot_json
        self.act("Missing expense", dict(row_key=self.review.accounts[0].row_key, signed_amount=-20, amount=20,
            category="Taxi", posting_date="2026-11-06"))
        self.assertEqual(self.register()["reviews"][0]["accounts"][0]["remaining_amount"], -30)
        next_opening = self.add("POS Opening Shift", "NEXT", pos_profile="Register", company="Test", docstatus=1,
            user="owner", status="Open", period_start_date="2026-11-07 08:00:00", balance_details=[frappe._dict(amount=0)])
        self.act("Missing expense", dict(row_key=self.review.accounts[0].row_key, signed_amount=-30, amount=30,
            category="Taxi", posting_date="2026-11-06"), key="second-expense")
        result = self.register()
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["latest"]["status"], "Resolved")
        self.assertEqual(result["latest"]["accounts"][0]["original_difference"], "-50.00")
        self.assertEqual(next_opening.balance_details[0].amount, 0)
        self.assertEqual(self.review.snapshot_json, original)
        self.assertEqual(sum(row.credit for row in self.ledger if row.account == "Till"), 50)

    def test_expense_links_use_native_opening_closing_permissions_and_review_scope(self):
        doc = self.add("Quick Expense", "EXP", pos_opening_shift="OPEN")
        result = journey.expense_links(doc)
        self.assertEqual(result["reviews"][0]["url"], "/app/shift-review/REVIEW")
        self.denied.update({("POS Opening Shift", "read"), ("POS Closing Shift", "read")})
        result = journey.expense_links(doc)
        self.assertIsNone(result["opening_shift"])
        self.assertIsNone(result["reviews"][0]["closing_shift"])
        self.denied.add(("POS Shift Review", "read"))
        self.assertEqual(journey.expense_links(doc), {})

    def test_unassigned_expense_finds_only_its_native_permitted_review_action(self):
        doc = self.add("Quick Expense", "EXP", pos_opening_shift=None)
        self.add("POS Shift Review Action", "ACTION", review="REVIEW", source_doctype=doc.doctype, source_name=doc.name, client_request_id="action")
        self.assertEqual(journey.expense_links(doc)["reviews"][0]["name"], "REVIEW")

    def test_late_old_count_transfer_is_refused_after_next_shift_without_posting(self):
        self.add("POS Opening Shift", "NEXT", pos_profile="Register", docstatus=1, status="Open",
            period_start_date="2026-11-07 08:00:00")
        with self.assertRaises(frappe.ValidationError): transfers.transfer("CLOSE")
        self.assertEqual(self.ledger, [])
        self.assertIn(("POS Profile", "Register"), self.locks)
        self.assertTrue(any(call.args[0] == "POS Opening Shift" and isinstance(call.args[1], dict)
            and call.kwargs.get("for_update") for call in self.f.db.get_value.call_args_list))

    def test_transfer_capability_needs_native_role_permissions_currency_and_no_later_opening(self):
        from erpnext.accounts.expense_services.commands import fingerprint
        original = snapshot.read(self.review)
        original["groups"][0]["account_currency"] = "TJS"
        self.review.snapshot_json = snapshot.encode(original); self.review.snapshot_hash = fingerprint(original)
        self.assertTrue(unwrap(journey.get_closing_status)("CLOSE")["can_transfer"])
        self.denied.add(("Payment Entry", "submit"))
        self.assertFalse(unwrap(journey.get_closing_status)("CLOSE")["can_transfer"])
        self.denied.clear()
        self.add("POS Shift Review Action", "COUNT", review="REVIEW", action="Count correction", state="Complete", client_request_id="count")
        self.assertFalse(unwrap(journey.get_closing_status)("CLOSE")["can_transfer"])
        self.docs.pop(("POS Shift Review Action", "COUNT"))
        self.add("POS Opening Shift", "NEXT", pos_profile="Register", docstatus=2,
            period_start_date="2026-11-07 08:00:00", status="Cancelled")
        self.assertFalse(unwrap(journey.get_closing_status)("CLOSE")["can_transfer"])
        with self.assertRaises(frappe.ValidationError): transfers.transfer("CLOSE")

    def test_completed_transfer_replay_remains_available_after_next_opening(self):
        import hashlib
        self.add("POS Shift Review Action", "TRANSFER", review="REVIEW", action="Safe transfer", state="Complete",
            client_request_id="safe-transfer:" + hashlib.sha256(b"CLOSE").hexdigest(), financial_name="SAFE-PE",
            evidence_json='{"amount":"950.00","target_label":"Safe"}')
        self.add("POS Opening Shift", "NEXT", pos_profile="Register", docstatus=1, status="Open")
        result = transfers.transfer("CLOSE")
        self.assertTrue(result["success"])
        self.assertEqual(result["payment_entry"], "SAFE-PE")
        self.assertEqual(self.ledger, [])

    def test_source_invoice_keeps_original_currency_beside_company_amount(self):
        from . import desk
        original = snapshot.read(self.review)
        self.add("Sales Invoice", "USD-SALE", company="Test", docstatus=1)
        original["sources"] = [dict(doctype="Sales Invoice", name="USD-SALE", posting_date="2026-11-06", modified="old",
            invoice=dict(base_grand_total=1100, grand_total=100, currency="USD"), vouchers=[])]
        from erpnext.accounts.expense_services.commands import fingerprint
        self.review.snapshot_json = snapshot.encode(original); self.review.snapshot_hash = fingerprint(original)
        data = unwrap(desk.get_detail)("REVIEW")
        self.assertEqual(data["sources"][0]["amount"], 1100)
        self.assertEqual(data["sources"][0]["original_amount"], 100)
        self.assertEqual(data["sources"][0]["original_currency"], "USD")

    def test_opening_counts_use_company_currency_independently_of_sales_profile_currency(self):
        from posawesome.posawesome.api import shifts
        self.f.db.sql.return_value = [frappe._dict(name="Register", company="Test", currency="USD")]
        modes = [frappe._dict(parent="Register", mode_of_payment="Cash")]
        self.f.get_list.side_effect = lambda doctype, **kwargs: modes
        with patch.object(shifts, "frappe", self.f), patch.object(shifts, "get_version", return_value=15):
            data = unwrap(shifts.get_opening_dialog_data)()
        self.assertEqual(data["payments_method"][0]["currency"], "TJS")
        self.assertEqual(data["count_currency_basis"], "company")
        self.f.db.commit.assert_not_called(); self.f.db.set_value.assert_not_called()
