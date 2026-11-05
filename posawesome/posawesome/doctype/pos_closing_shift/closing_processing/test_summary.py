from inspect import unwrap
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from . import overview, creation, data, summary
from posawesome.posawesome.api import fiscal
from posawesome.posawesome.doctype.pos_opening_shift_detail.pos_opening_shift_detail import (
    POSOpeningShiftDetail,
)


def opening_detail(mode, amount):
    # Retain the actual Document API; only metadata loading is isolated from the site.
    with patch("frappe.get_meta", return_value=SimpleNamespace(get_table_fields=lambda: [])), patch.object(
        POSOpeningShiftDetail, "get_valid_columns", return_value=["doctype", "mode_of_payment", "amount"]
    ):
        return POSOpeningShiftDetail({
            "doctype": "POS Opening Shift Detail", "mode_of_payment": mode, "amount": amount,
        })


class TestClosingSummary(unittest.TestCase):
    def setUp(self):
        self.opening = frappe._dict(name="OPEN-1", doctype="POS Opening Shift", pos_profile="Till", company="Company", user="cashier",
                                    balance_details=[opening_detail("Cash", 500), opening_detail("Card", 0)])
        self.invoices = []
        self.entries = []
        self.movements = []
        self.expenses = []
        self.fake = Mock()
        self.fake._dict = frappe._dict
        self.fake.get_cached_value.return_value = "TJS"
        self.fake.db.get_value.side_effect = lambda dt, name, field: (
            0 if field == "create_pos_invoice_instead_of_sales_invoice" else
            "Cash" if field == "posa_cash_mode_of_payment" else
            {"Cash": "Till Cash", "Card": "Bank"}.get(name.get("parent")) if isinstance(name, dict) else None)
        self.fake.get_meta.return_value = frappe._dict(fields=[])
        self.fake.get_all.side_effect = self.query
        for target, name, value in [(overview, "frappe", self.fake),
                                    (overview, "get_pos_invoices", lambda *a, **kw: self.invoices),
                                    (overview, "get_payments_entries", lambda *a, **kw: self.entries)]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def query(self, doctype, **kwargs):
        if doctype == "POS Cash Movement": return self.movements
        if doctype == "Quick Expense": return self.expenses
        if doctype == "POS Payment Method": return [{"mode_of_payment": "Cash"}, {"mode_of_payment": "Card"}]
        if doctype == "Payment Entry Reference":
            return [{"parent": entry["name"], **ref} for entry in self.entries for ref in entry.get("references", [])]
        return []

    def invoice(self, amount, payments=None, **kwargs):
        return frappe._dict(name="INV-1", currency="TJS", conversion_rate=1, grand_total=amount,
                            base_grand_total=amount, rounded_total=amount, payments=payments or [], **kwargs)

    def snapshot(self):
        return overview.build_closing_overview(self.opening, self.invoices, self.entries)

    def cash(self):
        return next(row for row in self.snapshot()["reconciliation"] if row["mode_of_payment"] == "Cash")

    def test_opening_float_is_included_even_without_sales(self):
        result = self.snapshot()
        self.assertEqual(self.cash()["expected_amount"], 500)
        self.assertEqual(result["cash_expected"]["company_currency_total"], 500)
        self.assertEqual(result["salespeople"], [])

    def test_submission_recalculates_totals_with_real_opening_child_documents(self):
        self.assertIsInstance(self.opening.balance_details[0], POSOpeningShiftDetail)
        payments = [
            frappe._dict(mode_of_payment="Cash", expected_amount=500, closing_amount=450),
            frappe._dict(mode_of_payment="Card", expected_amount=0, closing_amount=0),
        ]
        closing = Mock(pos_opening_shift=self.opening.name, pos_profile=self.opening.pos_profile,
                       company=self.opening.company, user=self.opening.user)
        closing.name = "CLOSE-1"
        closing.get.side_effect = lambda key, default=None: {
            "payment_reconciliation": payments, "pos_transactions": [], "pos_payments": [],
        }.get(key, default)
        self.fake.get_doc.return_value = closing
        self.fake.get_cached_value.side_effect = lambda doctype, *args: 3 if doctype == "System Settings" else "TJS"
        with patch.object(creation, "frappe", self.fake), patch.object(
            creation, "get_authorized_opening_shift", return_value=self.opening
        ), patch.object(creation, "get_pos_invoices", return_value=[]), patch.object(
            creation, "get_payments_entries", return_value=[]
        ), patch.object(creation, "flt", side_effect=lambda value, precision=None: frappe.utils.flt(
            value, precision, rounding_method="Banker's Rounding"
        )):
            self.assertEqual(unwrap(creation.submit_closing_shift)(
                json.dumps({"doctype": "POS Closing Shift"})
            ), "CLOSE-1")
        closing.submit.assert_called_once()
        self.assertEqual(payments[0].opening_amount, 500)
        self.assertEqual(payments[0].expected_amount, 500)
        self.assertEqual(payments[0].closing_amount, 450)

    def test_change_expenses_safe_transfer_and_card_expense_reconcile(self):
        self.invoices = [self.invoice(6000, [{"mode_of_payment": "Cash", "amount": 4100}, {"mode_of_payment": "Card", "amount": 2000}], change_amount=100)]
        self.movements = [{"name": "MOVE-1", "movement_type": "Deposit", "amount": 500, "source_account": "Till Cash"}]
        self.expenses = [{"name": "EXP-1", "amount": 200, "paid_from": "Till Cash", "mode_of_payment": "Card"},
                         {"name": "EXP-2", "amount": 50, "paid_from": "Bank", "mode_of_payment": "Card"}]
        cash = self.cash()
        self.assertEqual((cash["opening_amount"], cash["net_received"], cash["taken_out"], cash["expected_amount"]), (500, 4000, 700, 3800))
        card = next(row for row in self.snapshot()["reconciliation"] if row["mode_of_payment"] == "Card")
        self.assertEqual(card["expected_amount"], 1950)
        self.assertEqual(card["taken_out"], 50)

    def test_expense_from_another_till_does_not_reduce_this_till(self):
        self.movements = [{"name": "MOVE-2", "amount": 200, "source_account": "Another Till"}]
        self.assertEqual(self.cash()["expected_amount"], 500)
        self.assertIsNone(self.snapshot()["movements"][0]["mode_of_payment"])

    def test_refund_payment_entry_and_invoice_change_are_not_counted_twice(self):
        self.invoices = [self.invoice(100, [{"mode_of_payment": "Cash", "amount": 120}], change_amount=20)]
        self.entries = [frappe._dict(name="PAY-1", payment_type="Pay", mode_of_payment="Cash", paid_amount=20, base_paid_amount=20,
                                    paid_from_account_currency="TJS", references=[{"reference_doctype": "Sales Invoice", "reference_name": "INV-1", "allocated_amount": 20}])]
        self.assertEqual(self.cash()["net_received"], 100)

    def test_unrelated_refund_does_not_suppress_invoice_change(self):
        self.invoices = [self.invoice(100, [{"mode_of_payment": "Cash", "amount": 120}], change_amount=20)]
        self.entries = [frappe._dict(name="PAY-1", payment_type="Pay", mode_of_payment="Cash", paid_amount=30, base_paid_amount=30,
                                    paid_from_account_currency="TJS", references=[])]
        self.assertEqual(self.cash()["net_received"], 70)

    def test_return_reduces_sales_and_receipts_once(self):
        self.invoices = [self.invoice(-100, [{"mode_of_payment": "Cash", "amount": -100}], is_return=1, custom_sales_person="Ali")]
        snapshot = self.snapshot()
        self.assertEqual(self.cash()["expected_amount"], 400)
        self.assertEqual(snapshot["returns"]["company_currency_total"], 100)
        self.assertEqual(snapshot["salespeople"][0]["total"], -100)

    def test_currency_conversion_uses_company_amounts_for_closing(self):
        invoice = self.invoice(10, [{"mode_of_payment": "Cash", "amount": 10, "base_amount": 110}])
        invoice.update(currency="USD", conversion_rate=11, base_grand_total=110)
        self.invoices = [invoice]
        self.assertEqual(self.cash()["expected_amount"], 610)
        self.assertEqual(self.snapshot()["salespeople"][0]["total"], 110)
        currencies = {row["currency"]: row for row in self.snapshot()["cash_expected"]["by_currency"]}
        self.assertEqual(currencies["USD"]["total"], 10)
        self.assertEqual(currencies["TJS"]["total"], 500)
        self.assertEqual(sum(row["company_currency_total"] for row in currencies.values()), 610)

    def test_payment_entry_uses_receiving_account_amount_not_customer_currency(self):
        self.entries = [frappe._dict(name="PAY-2", payment_type="Receive", mode_of_payment="Cash", paid_amount=10, base_paid_amount=110,
                                    received_amount=110, base_received_amount=110, paid_from_account_currency="USD", paid_to_account_currency="TJS")]
        self.assertEqual(self.cash()["net_received"], 110)
        self.assertEqual(self.snapshot()["payments_by_mode"][0]["total"], 110)

    def test_loyalty_and_credit_sales_do_not_inflate_cash(self):
        self.invoices = [self.invoice(100, [{"mode_of_payment": "Cash", "amount": 70}], loyalty_amount=10, outstanding_amount=20)]
        self.assertEqual(self.cash()["net_received"], 70)
        self.assertEqual(self.snapshot()["sales_summary"]["net_company_currency_total"], 100)

    def test_salespeople_split_returns_and_unassigned_reconcile(self):
        self.invoices = [self.invoice(100, sales_team=[{"sales_person": "Ali", "allocated_percentage": 60}, {"sales_person": "Zebo", "allocated_percentage": 40}]),
                         self.invoice(-20, custom_sales_person="Ali"), self.invoice(30)]
        people = {row["sales_person"]: row for row in self.snapshot()["salespeople"]}
        self.assertEqual(people["Ali"]["total"], 40)
        self.assertEqual(people["Zebo"]["total"], 40)
        self.assertEqual(people[""]["total"], 30)
        self.assertEqual(sum(row["total"] for row in people.values()), 110)

    def test_incomplete_and_overallocated_teams_cannot_lose_or_double_sales(self):
        for percentages in [(50, 25), (100, 100), (0, 0)]:
            rows = summary.salesperson_totals([self.invoice(100, sales_team=[{"sales_person": person, "allocated_percentage": share} for person, share in zip(["Ali", "Zebo"], percentages)])])
            self.assertEqual(sum(row["total"] for row in rows), 100)

    def test_supplier_payment_is_taken_out_instead_of_negative_receipts(self):
        self.entries = [frappe._dict(name="SUP-PAY", payment_type="Pay", party_type="Supplier",
                                    mode_of_payment="Cash", paid_amount=100, base_paid_amount=100,
                                    paid_from_account_currency="TJS")]
        cash = self.cash()
        self.assertEqual((cash["net_received"], cash["taken_out"], cash["expected_amount"]), (0, 100, 400))
        self.assertEqual(self.snapshot()["payments_by_mode"][0]["company_currency_total"], -100)

    def test_other_cashier_cannot_read_the_shift(self):
        with patch.object(data, "frappe") as fake:
            fake.get_doc.return_value = self.opening
            fake.session.user = "other-cashier"
            fake.has_role.return_value = False
            fake.PermissionError = PermissionError
            fake._ = lambda text: text
            fake.throw.side_effect = PermissionError
            with self.assertRaises(PermissionError): data.get_authorized_opening_shift("OPEN-1")


class TestClosingSubmission(unittest.TestCase):
    def setUp(self):
        self.opening = frappe._dict(name="OPEN-1", pos_profile="Till", company="Company", user="cashier")
        self.row = frappe._dict(mode_of_payment="Cash", opening_amount=0, expected_amount=100, closing_amount=90)
        self.doc = Mock(pos_opening_shift="OPEN-1", pos_profile="Till", company="Company", user="cashier")
        self.doc.name = "CLOSE-1"
        self.doc.get.side_effect = lambda key, default=None: {"payment_reconciliation": [self.row], "pos_transactions": [], "pos_payments": []}.get(key, default)
        self.fake = Mock()
        self.fake.get_doc.return_value = self.doc
        self.fake.get_cached_value.return_value = 3
        self.fake.db.get_value.return_value = 0
        self.fake.throw.side_effect = ValueError
        self.snapshot = {"reconciliation": [{"mode_of_payment": "Cash", "opening_amount": 50, "expected_amount": 100}]}
        for name, value in [("frappe", self.fake), ("get_authorized_opening_shift", lambda name: self.opening),
                            ("get_pos_invoices", lambda *a, **kw: []), ("get_payments_entries", lambda *a, **kw: []),
                            ("build_closing_overview", lambda *a, **kw: self.snapshot), ("normalize_pos_payment_references", lambda doc: None),
                            ("_", lambda text: text),
                            ("flt", lambda value, precision=None: frappe.utils.flt(value, precision, rounding_method="Banker's Rounding"))]:
            patcher = patch.object(creation, name, value); patcher.start(); self.addCleanup(patcher.stop)

    def submit(self):
        return unwrap(creation.submit_closing_shift)(json.dumps({"doctype": "POS Closing Shift"}))

    def test_saved_expectations_and_opening_amount_come_from_server(self):
        self.assertEqual(self.submit(), "CLOSE-1")
        self.assertEqual(self.row.opening_amount, 50)
        self.assertEqual(self.row.closing_amount, 90)
        self.doc.submit.assert_called_once()

    def test_changed_totals_require_a_refresh_without_submitting(self):
        self.row.expected_amount = 110
        with self.assertRaises(ValueError): self.submit()
        self.doc.submit.assert_not_called()

    def test_missing_or_invalid_actual_amounts_cannot_close(self):
        for actual in [None, "", "nan", "inf", "abc"]:
            self.row.closing_amount = actual
            with self.assertRaises(ValueError): self.submit()
        self.doc.submit.assert_not_called()

    def test_new_credit_invoice_requires_refresh_even_if_cash_total_is_unchanged(self):
        with patch.object(creation, "get_pos_invoices", return_value=[frappe._dict(name="NEW-CREDIT")]):
            with self.assertRaises(ValueError): self.submit()
        self.doc.submit.assert_not_called()

    def test_client_cannot_switch_company_or_profile(self):
        self.doc.company = "Other Company"
        with self.assertRaises(ValueError): self.submit()
        self.doc.submit.assert_not_called()


class TestClosingSafeTransfer(unittest.TestCase):
    def setUp(self):
        self.row = frappe._dict(mode_of_payment="Наличные", closing_amount=80, expected_amount=100)
        self.doc = frappe._dict(pos_opening_shift="OPEN-1", docstatus=1, company="Company", pos_profile="Till", payment_reconciliation=[self.row])
        self.fake = Mock()
        self.fake.get_doc.return_value = self.doc
        self.fake.db.exists.return_value = True
        self.fake.get_cached_value.return_value = "TJS"
        self.fake.throw.side_effect = ValueError
        self.fake.db.get_value.side_effect = self.lookup
        for module, name, value in [(fiscal, "frappe", self.fake), (fiscal, "_", lambda text: text),
                                    (data, "get_authorized_opening_shift", lambda name: self.doc)]:
            patcher = patch.object(module, name, value); patcher.start(); self.addCleanup(patcher.stop)
        self.transfer = patch("erpnext.accounts.page.money_hub.money_hub.transfer_money")
        self.mock_transfer = self.transfer.start(); self.addCleanup(self.transfer.stop)

    def lookup(self, doctype, name, field, **kwargs):
        if doctype == "POS Profile": return "Наличные"
        if doctype == "Mode of Payment Account": return "Till Cash"
        if doctype == "Account": return "TJS"
        if doctype == "Money Wallet":
            if name.get("wallet_type") == "Safe": return {"name": "SAFE-1", "wallet_name": "Safe", "account": "Safe Cash"}
            if name.get("account") == "Till Cash": return {"name": "TILL-1", "wallet_name": "Till", "account": "Till Cash"}
        return None

    def test_zero_cash_never_falls_back_to_expected_amount(self):
        self.row.closing_amount = 0
        result = unwrap(fiscal.transfer_shift_cash_to_safe)("CLOSE-1")
        self.assertFalse(result["success"])
        self.mock_transfer.assert_not_called()

    def test_uses_configured_cash_mode_and_exact_counted_amount(self):
        result = unwrap(fiscal.transfer_shift_cash_to_safe)("CLOSE-1")
        self.assertTrue(result["success"])
        self.assertEqual(self.mock_transfer.call_args.kwargs["from_wallet"], "TILL-1")
        self.assertEqual(self.mock_transfer.call_args.kwargs["amount"], 80)

    def test_cannot_transfer_more_than_counted_cash(self):
        with self.assertRaises(ValueError): unwrap(fiscal.transfer_shift_cash_to_safe)("CLOSE-1", amount=100)
        self.mock_transfer.assert_not_called()

    def test_does_not_fall_back_to_an_unrelated_till(self):
        original = self.lookup
        self.fake.db.get_value.side_effect = lambda doctype, name, field, **kw: None if doctype == "Money Wallet" and name.get("account") else original(doctype, name, field, **kw)
        self.assertFalse(unwrap(fiscal.transfer_shift_cash_to_safe)("CLOSE-1")["success"])
        self.mock_transfer.assert_not_called()

    def test_foreign_currency_transfer_requires_money_hub(self):
        original = self.lookup
        self.fake.db.get_value.side_effect = lambda doctype, name, field, **kw: "USD" if doctype == "Account" else original(doctype, name, field, **kw)
        self.assertFalse(unwrap(fiscal.transfer_shift_cash_to_safe)("CLOSE-1")["success"])
        self.mock_transfer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
