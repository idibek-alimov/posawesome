"""Native documents, GL and permissions. Only run on a migrated disposable test site.

No business company names, mocked ledger rows or controller substitutions. Each case
uses its own accounts/register and rolls back its documents. Concurrent connections
need committed fixtures and are rehearsed separately by the release operator.
"""

import unittest
from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, today

from erpnext.accounts.expense_services import commands
from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.creation import (
    make_closing_shift_from_opening,
    submit_closing_shift,
)
from posawesome.posawesome.shift_review import journey, service, transfers

class TestNativeShiftWorkflow(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(frappe.local, "site", None) or not frappe.conf.get("allow_tests"):
            raise unittest.SkipTest("A disposable migrated site with allow_tests is required")
        from erpnext.accounts.expense_services.native_test_support import ensure_test_company
        ensure_test_company()
        super().setUpClass()

    def setUp(self):
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, "Administrator")
        frappe.db.savepoint("native_shift_workflow")
        self.addCleanup(lambda: frappe.db.rollback(save_point="native_shift_workflow"))
        self.company = "_Test Company"
        self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        self.suffix = uuid4().hex[:8]
        self.cash = self.account("Till", "Cash In Hand - _TC", "Cash")
        self.safe = self.account("Safe", "Cash In Hand - _TC", "Cash")
        self.bank = self.account("Alif", "Bank Accounts - _TC", "Bank")
        self.cost = self.account("Taxi", "Indirect Expenses - _TC")
        self.surplus = self.account("Surplus", "Direct Income - _TC")
        self.cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
        self.category = frappe.get_doc(dict(doctype="Quick Expense Category",
            category_name="_Test Taxi " + self.suffix,
            company_accounts=[dict(company=self.company, expense_account=self.cost)])).insert().name
        self.cash_mode = self.mode("Cash", self.cash, "Cash")
        self.bank_mode = self.mode("Alif", self.bank, "Bank")
        self.profile = frappe.get_doc(dict(doctype="POS Profile", name="_Test Review " + self.suffix,
            company=self.company, currency=self.currency, cost_center=self.cost_center,
            warehouse=frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0}, "name"),
            write_off_account=self.cost, write_off_cost_center=self.cost_center,
            posa_cash_mode_of_payment=self.cash_mode, posa_back_office_cash_account=self.safe,
            payments=[dict(mode_of_payment=self.cash_mode, default=1), dict(mode_of_payment=self.bank_mode)])).insert()
        for account, label in ((self.cash, "Till"), (self.safe, "Safe"), (self.bank, "Alif")):
            frappe.get_doc(dict(doctype="Money Wallet", wallet_name="_Test " + label + self.suffix,
                wallet_type="Safe" if account == self.safe else "Till" if account == self.cash else "Mobile Wallet",
                company=self.company, account=account, enabled=1, accept_in_pos=0,
                allow_desk_expenses=int(account == self.safe),
                expense_profiles=[] if account == self.safe else [dict(pos_profile=self.profile.name)])).insert()
        settings = frappe.db.get_value("POS Shift Review Settings", {"company": self.company}, "name")
        settings = frappe.get_doc("POS Shift Review Settings", settings) if settings else frappe.new_doc("POS Shift Review Settings")
        settings.update(dict(company=self.company, shortage_account=self.cost,
            surplus_account=self.surplus, cost_center=self.cost_center))
        settings.save()
        self.opening = self.open_shift(1000)

    def account(self, label, parent, account_type=None):
        return frappe.get_doc(dict(doctype="Account", account_name="_Test " + label + self.suffix,
            parent_account=parent, company=self.company, is_group=0, account_type=account_type)).insert().name

    def mode(self, label, account, kind):
        return frappe.get_doc(dict(doctype="Mode of Payment", mode_of_payment="_Test " + label + self.suffix,
            type=kind, accounts=[dict(company=self.company, default_account=account)])).insert().name

    def open_shift(self, amount, user=None):
        return frappe.get_doc(dict(doctype="POS Opening Shift", company=self.company,
            pos_profile=self.profile.name, user=user or frappe.session.user, period_start_date=now_datetime(),
            balance_details=[dict(mode_of_payment=self.cash_mode, amount=amount),
                             dict(mode_of_payment=self.bank_mode, amount=0)])).insert().submit()

    def close(self, actual=950):
        closing = make_closing_shift_from_opening({"name": self.opening.name})["closing_shift"]
        for row in closing.payment_reconciliation:
            row.closing_amount = actual if row.mode_of_payment == self.cash_mode else row.expected_amount
        closing.discrepancy_reason = "Native rehearsal count"
        closing.insert().submit()
        review = frappe.get_doc("POS Shift Review", closing.shift_review)
        return closing, review

    def expense(self, account, amount=20, context="POS", shift=None):
        return commands.record(dict(company=self.company, expense_category=self.category,
            amount=amount, paid_from=account, posting_date=today(), entry_context=context,
            pos_profile=self.profile.name if context != "Desk" else None,
            pos_opening_shift=shift or self.opening.name if context != "Desk" else None,
            correction_reason="Native rehearsal", description="Taxi",
            client_request_id=uuid4().hex))

    def action(self, review, action, **args):
        review.reload()
        row = next(row for row in review.accounts if row.account == self.cash)
        return service.act(review.name, action, dict(reason="Native rehearsal", row_key=row.row_key, **args),
            uuid4().hex, review.version)

    def balance(self, account):
        return float(frappe.db.sql("SELECT COALESCE(SUM(debit-credit),0) FROM `tabGL Entry` "
            "WHERE company=%s AND account=%s", (self.company, account))[0][0])

    def test_real_parent_children_and_till_bank_expenses_are_counted_once(self):
        self.expense(self.cash, 20)
        self.expense(self.bank, 50)
        closing, review = self.close(930)
        cash = next(row for row in closing.payment_reconciliation if row.mode_of_payment == self.cash_mode)
        bank = next(row for row in closing.payment_reconciliation if row.mode_of_payment == self.bank_mode)
        self.assertEqual(cash.expected_amount, 980)
        self.assertEqual(bank.expected_amount, -50)
        self.assertEqual(self.balance(self.cash), -20)
        self.assertEqual(self.balance(self.bank), -50)
        self.assertEqual(review.status, "Pending review")
        self.assertEqual(closing.payment_reconciliation[0].doctype, "POS Closing Shift Detail")
        self.assertEqual(self.opening.balance_details[0].doctype, "POS Opening Shift Detail")

    def test_missing_expenses_resolve_partially_retry_and_cancel_without_editing_count(self):
        closing, review = self.close()
        snapshot = review.snapshot_json
        first = self.action(review, "Missing expense", amount=20, signed_amount=-20, category=self.category,
            posting_date=today(), description="Taxi")
        self.assertEqual(first["status"], "Partially resolved")
        self.action(review, "Missing expense", amount=30, signed_amount=-30, category=self.category,
            posting_date=today(), description="Taxi")
        review.reload()
        self.assertEqual(review.status, "Resolved")
        self.assertEqual(self.balance(self.cash), -50)
        self.assertEqual(review.snapshot_json, snapshot)
        expense = frappe.get_doc("Quick Expense", first["operation"]["source_name"])
        commands.cancel(expense.name, "Native reversal rehearsal", str(expense.modified), uuid4().hex)
        review.reload()
        self.assertEqual(review.status, "Partially resolved")
        self.assertEqual(next(row for row in review.accounts if row.account == self.cash).original_difference, -50)
        self.assertEqual(sum(row.remaining_amount for row in review.accounts), -20)
        self.assertEqual(self.balance(self.cash), -30)
        closing.reload()
        self.assertEqual(next(row for row in closing.payment_reconciliation if row.mode_of_payment == self.cash_mode).closing_amount, 950)

    def test_native_loss_and_counted_transfer_reconcile_books_once(self):
        # Establish the example's opening book balance using a real native JE.
        je = frappe.get_doc(dict(doctype="Journal Entry", company=self.company, posting_date=today(),
            accounts=[dict(account=self.cash, debit_in_account_currency=1000),
                      dict(account=self.surplus, credit_in_account_currency=1000, cost_center=self.cost_center)])).insert().submit()
        closing, review = self.close()
        self.action(review, "Cash adjustment", signed_amount=-50, posting_date=today())
        self.assertEqual(self.balance(self.cash), 950)
        first = transfers.transfer(closing.name)
        self.assertTrue(first["success"])
        self.assertEqual(first["transferred_amount"], 950)
        self.assertEqual(self.balance(self.cash), 0)
        self.assertEqual(self.balance(self.safe), 950)
        next_opening = self.open_shift(0)
        retry = transfers.transfer(closing.name)
        self.assertEqual(first["payment_entry"], retry["payment_entry"])
        self.assertEqual(self.balance(self.safe), 950)
        self.assertEqual(next_opening.balance_details[0].amount, 0)
        self.assertEqual(frappe.get_doc("Journal Entry", je.name).docstatus, 1)

    def test_native_cancellation_reopens_loss_and_prevents_repeating_reversed_transfer(self):
        closing, review = self.close()
        result = self.action(review, "Cash adjustment", signed_amount=-50, posting_date=today())
        frappe.get_doc("Journal Entry", result["operation"]["financial_name"]).cancel()
        review.reload()
        self.assertEqual(review.status, "In review")
        self.assertEqual(sum(row.remaining_amount for row in review.accounts), -50)
        transfer = transfers.transfer(closing.name)
        frappe.get_doc("Payment Entry", transfer["payment_entry"]).cancel()
        with self.assertRaises(frappe.ValidationError):
            transfers.transfer(closing.name)

    def test_source_already_in_original_expected_cannot_resolve_again(self):
        original = self.expense(self.cash)
        _, review = self.close(930)
        with self.assertRaises(frappe.ValidationError):
            self.action(review, "Link source", source_doctype="Quick Expense", source_name=original["name"], signed_amount=-20)
        self.assertEqual(self.balance(self.cash), -20)

    def test_native_reversal_reopens_allocated_loss(self):
        from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry

        _, review = self.close()
        result = self.action(review, "Cash adjustment", signed_amount=-50, posting_date=today())
        reversal = make_reverse_journal_entry(result["operation"]["financial_name"])
        reversal.posting_date = today()
        reversal.insert().submit()
        review.reload()
        self.assertEqual(sum(row.remaining_amount for row in review.accounts), -50)
        self.assertEqual(self.balance(self.cash), 0)

    def test_surplus_requires_separate_approved_posting(self):
        _, review = self.close(1050)
        self.action(review, "Cash adjustment", signed_amount=50, posting_date=today())
        review.reload()
        self.assertEqual(review.status, "Resolved")
        self.assertEqual(self.balance(self.cash), 50)
        self.assertEqual(self.balance(self.surplus), -50)

    def test_money_hub_uses_stored_base_gl_and_counts_foreign_wallet_alias_once(self):
        from erpnext.accounts.page.money_hub.money_hub import get_money_hub_data

        before = get_money_hub_data(self.company)["totals"]["total"]
        foreign = frappe.get_doc(dict(doctype="Account", account_name="_Test USD " + self.suffix,
            parent_account="Bank Accounts - _TC", company=self.company, is_group=0,
            account_type="Bank", account_currency="USD")).insert().name
        for label in ("Original", "Alias"):
            frappe.get_doc(dict(doctype="Money Wallet", wallet_name=label + self.suffix,
                wallet_type="Bank", company=self.company, account=foreign, enabled=1, accept_in_pos=0)).insert()
        frappe.get_doc(dict(doctype="Journal Entry", company=self.company, posting_date=today(), multi_currency=1,
            accounts=[dict(account=foreign, debit_in_account_currency=10, exchange_rate=80),
                      dict(account=self.surplus, credit_in_account_currency=800,
                           cost_center=self.cost_center, exchange_rate=1)])).insert().submit()
        hub = get_money_hub_data(self.company)
        wallets = [row for row in hub["wallets"] if row.account == foreign]
        self.assertEqual(len(wallets), 2)
        self.assertEqual({row.account_balance for row in wallets}, {10})
        self.assertEqual({row.balance for row in wallets}, {800})
        self.assertEqual(hub["totals"]["total"] - before, 800)
        self.assertEqual(hub["currency"], self.currency)
        self.assertIn("USD", hub["currency_precisions"])

    def test_unauthorized_safe_or_another_register_cannot_be_spent_from_pos(self):
        with self.assertRaises(frappe.PermissionError):
            self.expense(self.safe)
        payload = dict(company=self.company, expense_category=self.category, amount=20,
            paid_from=self.cash, pos_profile="not-this-register", pos_opening_shift=self.opening.name,
            entry_context="POS", posting_date=today(), client_request_id=uuid4().hex)
        with self.assertRaises(frappe.ValidationError):
            commands.record(payload)
        self.assertEqual(self.balance(self.cash), 0)

    def test_native_retail_manager_reads_balances_but_cannot_approve_genuine_cash_loss(self):
        from erpnext.accounts.page.money_hub.money_hub import get_money_hub_data
        from erpnext.setup.retail_security import can_see_financials

        _, review = self.close()
        manager = frappe.get_doc(dict(doctype="User", email="manager-" + self.suffix + "@example.test",
            first_name="Native manager", enabled=1, send_welcome_email=0,
            roles=[dict(role="Retail Manager")])).insert().name
        frappe.set_user(manager)
        self.assertTrue(frappe.has_permission("Money Wallet", "read"))
        self.assertFalse(frappe.has_permission("Money Wallet", "write"))
        self.assertFalse(frappe.has_permission("Money Wallet", "create"))
        self.assertFalse(can_see_financials(manager))  # Profit/cost visibility remains owner-only.
        data = get_money_hub_data(company=self.company)
        wallet = next(row for row in data["wallets"] if row.account == self.cash)
        self.assertEqual(wallet.balance, 0)
        self.assertEqual(data["company"], self.company)
        with self.assertRaises(frappe.PermissionError):
            self.action(review, "Cash adjustment", signed_amount=-50, posting_date=today())
        self.assertEqual(self.balance(self.cash), 0)

    def test_cashier_api_closes_own_shift_without_general_opening_write_access(self):
        import json
        from frappe.permissions import add_permission

        cashier = frappe.get_doc(dict(doctype="User", email="close-" + self.suffix + "@example.test",
            first_name="Native closing cashier", enabled=1, send_welcome_email=0,
            roles=[dict(role="Retail Cashier")])).insert().name
        add_permission("POS Profile", "Retail Cashier", 0)
        frappe.get_doc(dict(doctype="User Permission", user=cashier, allow="POS Profile",
            for_value=self.profile.name, apply_to_all_doctypes=1)).insert()
        self.opening.cancel()
        self.opening = self.open_shift(1000, user=cashier)
        frappe.set_user(cashier)
        self.assertFalse(frappe.has_permission("Money Wallet", "read"))
        self.assertFalse(frappe.has_permission("POS Opening Shift", "write", doc=self.opening))
        draft = make_closing_shift_from_opening({"name": self.opening.name})["closing_shift"]
        for row in draft.payment_reconciliation:
            row.closing_amount = 950 if row.mode_of_payment == self.cash_mode else row.expected_amount
        draft.discrepancy_reason = "Cashier native closing regression"
        name = submit_closing_shift(json.dumps(draft.as_dict(), default=str))
        self.opening.reload()
        self.assertEqual(self.opening.status, "Closed")
        self.assertEqual(self.opening.pos_closing_shift, name)
        self.assertEqual(frappe.db.get_value("POS Closing Shift", name, "review_status"), "Pending review")
        self.assertFalse(frappe.has_permission("POS Opening Shift", "write", doc=self.opening))

    def test_following_opening_refuses_first_old_count_transfer(self):
        closing, review = self.close()
        self.open_shift(0)
        with self.assertRaises(frappe.ValidationError):
            transfers.transfer(closing.name)
        self.assertEqual(self.balance(self.safe), 0)
        self.assertEqual(journey.get_register_context(self.profile.name)["latest"]["review"], review.name)

    def test_office_spending_does_not_reduce_shift_and_zero_count_posts_no_transfer(self):
        self.expense(self.safe, 100, "Desk")
        closing, _ = self.close(0)
        self.assertEqual(next(row for row in closing.payment_reconciliation if row.mode_of_payment == self.cash_mode).expected_amount, 1000)
        self.assertFalse(transfers.transfer(closing.name)["success"])
        self.assertEqual(self.balance(self.cash), 0)
        self.assertEqual(self.balance(self.safe), -100)

    def test_cashier_native_read_redacts_snapshot_and_denies_other_users_and_actions(self):
        from frappe.client import get
        from frappe.desk.form.load import getdoc

        cashier = frappe.get_doc(dict(doctype="User", email="native-" + self.suffix + "@example.test",
            first_name="Native cashier", enabled=1, send_welcome_email=0,
            roles=[dict(role="Retail Cashier")])).insert().name
        # Explicit deployment setup, not an Accounts User role bundle: allow
        # native register read and restrict this user's profile through User Permission.
        from frappe.permissions import add_permission
        add_permission("POS Profile", "Retail Cashier", 0)
        frappe.get_doc(dict(doctype="User Permission", user=cashier, allow="POS Profile",
            for_value=self.profile.name, apply_to_all_doctypes=1)).insert()
        self.opening.cancel()
        self.opening = self.open_shift(1000, user=cashier)
        from frappe.utils.file_manager import save_file
        inaccessible = save_file("private-manager-" + self.suffix + ".txt", b"Manager private receipt",
            None, None, is_private=1)
        frappe.set_user(cashier)
        own = save_file("private-cashier-" + self.suffix + ".txt", b"Cashier taxi receipt", None, None, is_private=1)
        payload = dict(company=self.company, expense_category=self.category, amount=20,
            paid_from=self.cash, pos_profile=self.profile.name, pos_opening_shift=self.opening.name,
            entry_context="POS", posting_date=today(), description="Taxi", client_request_id=uuid4().hex)
        with self.assertRaises(frappe.PermissionError):
            commands.record(dict(payload, receipt_attachment=inaccessible.file_url))
        recorded = commands.record(dict(payload, receipt_attachment=own.file_url))
        expense = frappe.get_doc("Quick Expense", recorded["name"])
        with self.assertRaises(frappe.PermissionError):
            commands.cancel(expense.name, "Cashier cannot cancel", str(expense.modified), uuid4().hex)
        self.assertEqual(frappe.db.count("File", {"file_url": own.file_url, "is_private": 1,
            "attached_to_doctype": "Quick Expense", "attached_to_name": recorded["name"]}), 1)
        self.assertEqual(frappe.db.count("File", {"file_url": own.file_url, "is_private": 1,
            "attached_to_doctype": "Journal Entry", "attached_to_name": recorded["journal_entry"]}), 1)
        frappe.set_user("Administrator")
        closing, review = self.close()
        frappe.set_user(cashier)
        doc = get("POS Shift Review", review.name)
        self.assertFalse(doc.get("snapshot_json"))
        self.assertFalse(doc.get("snapshot_hash"))
        self.assertTrue(doc["accounts"])
        frappe.local.response.docs = []
        getdoc("POS Shift Review", review.name)
        self.assertFalse(frappe.local.response.docs[0].get("snapshot_json"))
        rows = frappe.get_list("POS Shift Review", fields=["name", "snapshot_json", "snapshot_hash"])
        self.assertTrue(rows)
        self.assertFalse(any(row.get("snapshot_json") or row.get("snapshot_hash") for row in rows))
        self.assertFalse(frappe.has_permission("POS Shift Review", "export"))
        printed = frappe.get_print("POS Shift Review", review.name)
        self.assertNotIn(review.snapshot_hash, printed)
        self.assertNotIn("snapshot_json", printed)
        with self.assertRaises(frappe.PermissionError):
            self.action(review, "Investigate")
        self.assertFalse(frappe.has_permission("POS Shift Review Action", "read"))
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            get("POS Shift Review", review.name)
