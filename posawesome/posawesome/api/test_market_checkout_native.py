"""Focused controlled fixtures, rolled back; no printer/network requests."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4
import frappe
from frappe.utils import add_days, now_datetime, nowdate
from posawesome.posawesome.api import market_checkout, fiscal, terminal_state
from posawesome.posawesome.api.invoice_processing import creation


class TestMarketCheckoutNative(unittest.TestCase):
    def setUp(self):
        self.user = frappe.session.user
        frappe.set_user("Administrator")
        self.suffix = "MKT-" + uuid4().hex[:10]
        frappe.db.savepoint("market_checkout_test")
        # Guard against accidental commits by linked native code during a fixture run.
        self.commit_guard = patch.object(frappe.db, "commit", side_effect=AssertionError("Fixture attempted to commit"))
        self.commit_guard.start()
        self.previous_sid = frappe.session.get("sid")
        self.addCleanup(self._cleanup)
        profile_name = frappe.db.get_value("POS Profile", {"disabled": 0, "create_pos_invoice_instead_of_sales_invoice": 0}, "name")
        self.profile = frappe.copy_doc(frappe.get_doc("POS Profile", profile_name))
        self.profile.name = self.suffix
        self.profile.set("applicable_for_users", [dict(user="Administrator", default=0)])
        self.profile.posa_allow_credit_sale = 1
        self.profile.posa_allow_partial_payment = 1
        self.profile.posa_allow_return = 1
        self.profile.posa_allow_return_without_invoice = 1
        self.profile.posa_unlimited_cashier_returns = 1
        self.profile.posa_allow_submissions_in_background_job = 0
        self.profile.insert()
        # Disposable invoice names must not depend on or repair live naming counters.
        from frappe.model import naming
        original_autoname = naming.make_autoname
        def fixture_autoname(key="", doctype="", doc="", **kwargs):
            if getattr(doc, "doctype", None) in ("Sales Invoice", "POS Invoice") and doc.get("pos_profile") == self.profile.name:
                return self.suffix + "-" + uuid4().hex[:8]
            return original_autoname(key, doctype, doc, **kwargs)
        name_guard = patch.object(naming, "make_autoname", side_effect=fixture_autoname)
        name_guard.start()
        self.addCleanup(name_guard.stop)
        self.cash_mode = next(p.mode_of_payment for p in self.profile.payments if frappe.get_cached_value("Mode of Payment", p.mode_of_payment, "type") == "Cash")
        self.opening = frappe.get_doc(dict(doctype="POS Opening Shift", pos_profile=self.profile.name,
            company=self.profile.company, user="Administrator", period_start_date=now_datetime(),
            balance_details=[dict(mode_of_payment=self.cash_mode, amount=0)])).insert(set_name=self.suffix).submit()
        frappe.session.sid = self.suffix
        terminal_state.activate_verified_cashier(self.profile, "Administrator")
        self.customer = frappe.get_doc(dict(doctype="Customer", customer_name=self.suffix,
            customer_type="Individual", customer_group=frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
            territory=frappe.db.get_value("Territory", {"is_group": 0}, "name"))).insert()
        self.item = frappe.get_doc(dict(doctype="Item", item_code=self.suffix, item_name="MARKET test item",
            item_group=frappe.db.get_value("Item Group", {"is_group": 0}, "name"), is_stock_item=0,
            stock_uom=frappe.db.get_value("UOM", {"enabled": 1}, "name") or "Nos")).insert()
        frappe.get_doc(dict(doctype="Item Price", item_code=self.item.name, price_list=self.profile.selling_price_list,
            price_list_rate=100, selling=1, currency=self.profile.currency)).insert()

    def _cleanup(self):
        self.commit_guard.stop()
        if getattr(self, "profile", None):
            frappe.cache.delete_value(terminal_state._state_cache_key(self.profile.name))
        frappe.db.rollback(save_point="market_checkout_test")
        frappe.db.after_rollback.run()
        frappe.session.sid = self.previous_sid
        frappe.set_user(self.user)
        if getattr(self, "profile", None):
            frappe.clear_document_cache("POS Profile", self.profile.name)

    def sale(self, pos=0, qty=2, paid=None):
        self.profile.create_pos_invoice_instead_of_sales_invoice = pos
        self.profile.save()
        payload = dict(doctype="POS Invoice" if pos else "Sales Invoice", company=self.profile.company,
            pos_profile=self.profile.name, posa_pos_opening_shift=self.opening.name, customer=self.customer.name,
            is_pos=1, update_stock=1, posting_date=nowdate(), currency=self.profile.currency, selling_price_list=self.profile.selling_price_list,
            items=[dict(item_code=self.item.name, qty=qty, rate=100)],
            taxes_and_charges=self.profile.taxes_and_charges)
        draft = creation.update_invoice(json.dumps(payload))
        draft["payments"] = [dict(mode_of_payment=self.cash_mode, amount=paid if paid is not None else draft["grand_total"], type="Cash")]
        result = creation.submit_invoice(json.dumps(draft, default=str), json.dumps(dict(idempotency_key=uuid4().hex, is_credit_sale=int(paid is not None))), False)
        return frappe.get_doc(result["doctype"], result["name"])

    def refund(self, source, request=None, credit=0):
        return market_checkout.refund(self.profile.name, self.opening.name,
            [dict(name=source.items[0].name, qty=1)], request or uuid4().hex,
            source.name, source.doctype, credit)

    def test_cash_return_replays_and_preserves_remaining_quantity(self):
        source = self.sale(); request = uuid4().hex
        with self.assertRaises(frappe.ValidationError):
            market_checkout.refund(self.profile.name, self.opening.name, [dict(name=source.items[0].name, qty="NaN")], uuid4().hex, source.name, source.doctype)
        result = self.refund(source, request)
        replay = self.refund(source, request)
        self.assertEqual((result["docstatus"], replay["name"]), (1, result["name"]))
        doc = frappe.get_doc(result["doctype"], result["name"])
        self.assertEqual((doc.items[0].qty, doc.return_against), (-1, source.name))
        self.assertLess(doc.paid_amount, 0)
        self.assertEqual(market_checkout.return_items(source.name, source.doctype, self.profile.name)["items"][0]["qty"], 1)
        self.assertTrue(frappe.get_all("GL Entry", filters={"voucher_no": doc.name}))

    def test_registered_customer_credit_return_has_no_cash_payout(self):
        source = self.sale(); result = self.refund(source, credit=1)
        doc = frappe.get_doc(result["doctype"], result["name"])
        self.assertEqual(doc.paid_amount, 0)
        self.assertLess(doc.grand_total, 0)
        self.assertEqual(doc.customer, self.customer.name)
        from posawesome.posawesome.api.stored_value import get_stored_value_summary
        self.assertGreater(get_stored_value_summary(doc.customer, doc.company)["available_amount"], 0)

    def test_inventory_increases_once_for_a_replayed_refund(self):
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
        self.item.is_stock_item = 1
        self.item.save()
        make_stock_entry(item_code=self.item.name, qty=3, company=self.profile.company,
            to_warehouse=self.profile.warehouse, rate=30)
        source = self.sale()
        request = uuid4().hex
        self.refund(source, request)
        self.refund(source, request)
        self.assertEqual(frappe.db.get_value("Bin", dict(item_code=self.item.name, warehouse=self.profile.warehouse), "actual_qty"), 2)

    def test_cash_refunds_cannot_reuse_the_same_original_payment(self):
        source = self.sale(qty=4, paid=200)
        self.refund(source)
        self.refund(source)
        with self.assertRaises(frappe.ValidationError): self.refund(source)

    def test_guest_return_uses_server_price_and_rejects_store_credit(self):
        result = market_checkout.refund(self.profile.name, self.opening.name,
            [dict(item_code=self.item.name, qty=1, rate=9999)], uuid4().hex)
        doc = frappe.get_doc(result["doctype"], result["name"])
        self.assertEqual(doc.items[0].rate, 100)
        self.assertEqual((doc.items[0].qty, doc.customer), (-1, self.profile.customer))
        with self.assertRaises(frappe.ValidationError):
            market_checkout.refund(self.profile.name, self.opening.name, [dict(item_code=self.item.name, qty=1)], uuid4().hex, as_credit=1)

    def test_pos_invoice_return_and_fiscal_unknown_guard(self):
        source = self.sale(pos=1)
        source.custom_fiscal_fd_number = "FORGED"
        with self.assertRaises(frappe.PermissionError): source.save()
        source.reload()
        forged = frappe.new_doc("Sales Invoice")
        forged.custom_fiscal_fd_number = "FORGED"
        with self.assertRaises(frappe.PermissionError): forged.insert(ignore_permissions=True)
        result = self.refund(source)
        self.assertEqual((result["doctype"], result["docstatus"]), ("POS Invoice", 1))
        prepared = fiscal.prepare_fiscal_receipt(source.name, source.doctype)
        self.assertEqual(prepared["payload"]["receiptSum"], sum(p["sum"] for p in prepared["payload"]["products"]))
        self.assertEqual(fiscal.record_fiscal_rejection(source.name, source.doctype, prepared["attempt"], "NO_PAPER")["status"], "Неизвестно")
        with self.assertRaises(frappe.ValidationError): fiscal.prepare_fiscal_receipt(source.name, source.doctype)
        fiscal.record_non_fiscal_sale(source.name, source.doctype)
        self.assertEqual(frappe.db.get_value(source.doctype, source.name, "custom_fiscal_status"), "Неизвестно")
        with self.assertRaises(frappe.ValidationError): fiscal.confirm_unissued_fiscal_attempt(source.name, source.doctype, prepared["attempt"], 0)
        fiscal.confirm_unissued_fiscal_attempt(source.name, source.doctype, prepared["attempt"], 1)
        retry = fiscal.prepare_fiscal_receipt(source.name, source.doctype)
        self.assertNotEqual(retry["attempt"], prepared["attempt"])
        prepared = retry
        response = {"rc": "SUCCESS", "data": {"fdNumber": 999999123, "fpd": "fixture"}}
        fiscal.save_fiscal_data(source.name, source.doctype, response, prepared["attempt"])
        source.reload()
        self.assertFalse(frappe.copy_doc(source, ignore_no_copy=False).get("custom_fiscal_fd_number"))
        self.assertTrue(fiscal.prepare_fiscal_receipt(source.name, source.doctype)["completed"])
        found = market_checkout.find_sales(self.profile.name, "https://ofd.example/receipt?fd=999999123")
        self.assertIn(source.name, [row.name for row in found])
        with self.assertRaises(frappe.PermissionError): fiscal.save_fiscal_data(source.name, source.doctype, response, "wrong")

    def test_receipt_projection_excludes_cost_and_unknown_scope_is_denied(self):
        source = self.sale()
        phone = str(int(uuid4().hex, 16) % 1000000000).zfill(9)
        self.customer.reload()
        self.customer.mobile_no = "+992" + phone
        self.customer.save()
        found = market_checkout.find_sales(self.profile.name, f"+992 ({phone[:2]}) {phone[2:5]}-{phone[5:]}", by_customer=1)
        self.assertIn(source.name, [row.name for row in found])
        receipt = market_checkout.receipt_data(source.name, source.doctype)
        self.assertEqual(receipt["grand_total"], source.grand_total)
        # Two fixture items at the configured list price 100, before native rules.
        self.assertEqual(float(receipt["receipt_totals"]["subtotal"]), 200)
        self.assertEqual(float(receipt["receipt_totals"]["total"]), abs(source.rounded_total or source.grand_total))
        self.assertEqual(receipt["payments"][0]["type"], "Cash")
        self.assertEqual(receipt["payments"][0]["amount"], source.payments[0].amount)
        self.assertEqual(receipt["taxes"][0]["amount"], source.taxes[0].tax_amount_after_discount_amount)
        self.assertNotIn("valuation_rate", receipt["items"][0])
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError): market_checkout.receipt_data(source.name, source.doctype)

    def test_fiscal_preflight_uses_verified_cashier_without_preparing_attempt(self):
        source = self.sale()
        context = fiscal.fiscal_checkout_context(source.name, source.doctype)
        self.assertEqual(context["cashier"], frappe.utils.get_fullname("Administrator"))
        self.assertFalse(frappe.db.get_value(source.doctype, source.name, "custom_fiscal_attempt"))
        terminal_state.lock_authorized_terminal(self.profile)
        with self.assertRaises(frappe.PermissionError): fiscal.fiscal_checkout_context(source.name, source.doctype)
        terminal_state.activate_verified_cashier(self.profile, "Administrator")
        prepared = fiscal.prepare_fiscal_receipt(source.name, source.doctype)
        unknown = fiscal.fiscal_checkout_context(source.name, source.doctype)
        self.assertEqual(unknown["status"], "Неизвестно")
        self.assertNotIn("cashier", unknown)
        self.assertEqual(fiscal.record_fiscal_rejection(source.name, source.doctype, prepared["attempt"], "SHIFT_MUST_BE_OPENED")["status"], "Ошибка")

    def test_purchase_history_unifies_phone_name_receipt_and_older_dates(self):
        source = self.sale()
        phone = str(int(uuid4().hex, 16) % 1000000000).zfill(9)
        fd = "9" + phone + "01"
        # Projection-only fixture: no fiscal API/device is invoked, all writes roll back.
        frappe.db.set_value(source.doctype, source.name, "custom_fiscal_fd_number", fd)
        self.customer.reload()
        self.customer.mobile_no = f"+992 ({phone[:2]}) {phone[2:5]}-{phone[5:]}"
        self.customer.save()
        for query in (self.customer.customer_name, phone, "+992" + phone, source.name, "ФД № " + fd,
                      f"https://example.invalid/receipt?fdNumber={fd}",
                      f"https://example.invalid/receipt?invoice={source.name}", "POSA:" + source.name):
            result = market_checkout.purchase_history(self.profile.name, query)
            self.assertEqual([r.name for r in result["items"]], [source.name])
            self.assertNotIn("valuation_rate", result["items"][0])
            self.assertEqual(result["items"][0].customer_phone, self.customer.mobile_no)
        # Change only the disposable projection fixture, never live ledger dates.
        older = add_days(nowdate(), -3)
        frappe.db.set_value(source.doctype, source.name, "posting_date", older)
        self.assertFalse(market_checkout.purchase_history(self.profile.name, self.suffix)["items"])
        history = market_checkout.purchase_history(self.profile.name, self.suffix, from_date=older, to_date=nowdate())
        self.assertEqual([r.name for r in history["items"]], [source.name])
        for query in ("%", "_", "' OR 1=1 --", "http://["):
            self.assertFalse(market_checkout.purchase_history(self.profile.name, query, older, nowdate())["items"])

    def test_purchase_history_paginates_si_and_pos_together_without_returns(self):
        sale = self.sale()
        pos = self.sale(pos=1)
        self.refund(pos)
        first = market_checkout.purchase_history(self.profile.name, self.suffix, page_length=1)
        second = market_checkout.purchase_history(self.profile.name, self.suffix, start=1, page_length=1)
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        self.assertEqual({r.name for r in first["items"] + second["items"]}, {sale.name, pos.name})
        self.assertEqual({r.doctype for r in first["items"] + second["items"]}, {"Sales Invoice", "POS Invoice"})
        self.assertFalse(market_checkout.purchase_history(self.profile.name, self.suffix, start=2)["items"])
        frappe.db.set_value(pos.doctype, pos.name, "docstatus", 0)
        self.assertEqual([r.name for r in market_checkout.purchase_history(self.profile.name, self.suffix)["items"]], [sale.name])
        frappe.db.set_value(sale.doctype, sale.name, "is_consolidated", 1)
        self.assertFalse(market_checkout.purchase_history(self.profile.name, self.suffix)["items"])

    def test_purchase_history_keeps_register_company_and_session_scope(self):
        source = self.sale()
        # A different cashier's submitted sale remains visible in a permitted register.
        frappe.db.set_value(source.doctype, source.name, "owner", "Guest")
        self.assertIn(source.name, [r.name for r in market_checkout.purchase_history(self.profile.name, self.suffix)["items"]])
        with patch.object(market_checkout, "permitted_profiles", return_value=[self.profile.name]):
            original = frappe.copy_doc(self.profile)
            original.name = self.suffix + "-other"
            original.insert()
            frappe.db.set_value(source.doctype, source.name, "pos_profile", original.name)
            self.assertFalse(market_checkout.purchase_history(self.profile.name, self.suffix)["items"])
            frappe.db.set_value(source.doctype, source.name, "pos_profile", self.profile.name)
            frappe.db.set_value(source.doctype, source.name, "company", "not-this-company")
            self.assertFalse(market_checkout.purchase_history(self.profile.name, self.suffix)["items"])
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError): market_checkout.purchase_history(self.profile.name)

    def test_purchase_history_rejects_invalid_dates(self):
        for start, end in (("2026-11-15", "2026-11-14"), ("2026-13-01", nowdate()), ("yesterday", nowdate())):
            with self.assertRaises(frappe.ValidationError):
                market_checkout.purchase_history(self.profile.name, from_date=start, to_date=end)
