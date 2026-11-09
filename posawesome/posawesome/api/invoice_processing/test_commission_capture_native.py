"""S2e1 route contracts and S2e2 split regressions on a disposable POS site.

These assert the current checkout contract, not a live commission integration.
Worker enqueue is intercepted; its real function is executed explicitly in-process.
"""
import json
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.utils import add_days, today, flt

from posawesome.posawesome.api import terminal_state
from posawesome.posawesome.api.invoice_processing import creation
from posawesome.posawesome.api.offline_sync.invoices import submit_invoice_outbox_entry
from posawesome.posawesome.shift_review.test_native_workflow import TestNativeShiftWorkflow


class TestCommissionCaptureAdoptionNative(TestNativeShiftWorkflow):
    def setUp(self):
        super().setUp()
        frappe.db.set_value("Company", self.company, dict(round_off_account=self.cost,
            round_off_cost_center=self.cost_center))
        frappe.clear_document_cache("Company", self.company)
        self.addCleanup(lambda: frappe.clear_document_cache("Company", self.company))
        self.profile.append("applicable_for_users", dict(user="Administrator"))
        self.tax_template = frappe.get_doc(dict(doctype="Sales Taxes and Charges Template",
            title="S2e1 " + self.suffix, company=self.company, taxes=[dict(charge_type="On Net Total",
            account_head=self.cost, rate=0, description="Disposable zero tax")])).insert().name
        self.profile.taxes_and_charges = self.tax_template
        self.profile.save()
        previous = frappe.session.get("sid")
        frappe.session.sid = "s2e1-" + self.suffix
        self.addCleanup(lambda: frappe.session.update(sid=previous))
        terminal_state.activate_verified_cashier(self.profile, "Administrator")
        key = terminal_state._state_cache_key(self.profile.name)
        self.addCleanup(lambda: frappe.cache.delete_value(key))
        self.customer = frappe.get_doc(dict(doctype="Customer", customer_name="S2e1 " + self.suffix,
            customer_type="Individual", customer_group=frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
            territory=frappe.db.get_value("Territory", {"is_group": 0}, "name"))).insert().name
        group = frappe.get_doc(dict(doctype="Item Group", item_group_name="S2e1 " + self.suffix,
            is_group=0)).insert().name
        uom = frappe.get_doc(dict(doctype="UOM", uom_name="S2e1 " + self.suffix)).insert().name
        self.price_list = frappe.get_doc(dict(doctype="Price List", price_list_name="S2e1 " + self.suffix,
            selling=1, enabled=1, currency=self.currency)).insert().name
        self.item = frappe.get_doc(dict(doctype="Item", item_code="S2e1 " + self.suffix,
            item_name="Capture diagnostic", item_group=group, stock_uom=uom,
            is_stock_item=0)).insert().name

    def payload(self, **changes):
        return dict(dict(doctype="Sales Invoice", company=self.company, pos_profile=self.profile.name,
            posa_pos_opening_shift=self.opening.name, customer=self.customer, is_pos=1,
            posting_date=today(), currency=self.currency, conversion_rate=1,
            taxes_and_charges=self.tax_template, taxes=[dict(charge_type="On Net Total",
                account_head=self.cost, rate=0, description="Disposable zero tax")],
            selling_price_list=self.price_list, price_list_currency=self.currency,
            plc_conversion_rate=1, update_stock=0, items=[dict(item_code=self.item, qty=1,
            rate=100, income_account="Sales - _TC", cost_center=self.cost_center)],
            payments=[dict(mode_of_payment=self.cash_mode, amount=100, account=self.cash, type="Cash")]), **changes)

    def submit(self, payload, request=None, background=0):
        request = request or uuid4().hex
        data = dict(client_request_id=request, company=self.company, pos_profile=self.profile.name,
            posa_pos_opening_shift=payload.get("posa_pos_opening_shift"), paid_amount=100)
        return creation.submit_invoice(json.dumps(payload), json.dumps(data), submit_in_background=background)

    def test_s2e1_native_foreground_replay_keeps_one_invoice_and_private_response(self):
        request = uuid4().hex; payload = self.payload()
        result = self.submit(payload, request); replay = self.submit(payload, request)
        self.assertEqual(result["docstatus"], 1); self.assertEqual(replay["name"], result["name"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(result["posa_cashier"], "Administrator")
        self.assertFalse(set(result) & {"employee", "commission", "cost", "evidence", "snapshot"})
        self.assertEqual(frappe.db.count(creation.LEDGER_DOCTYPE, {"client_request_id": request}), 1)
        self.assertEqual(frappe.get_doc(result["doctype"], result["name"]).base_grand_total, 100)

    def test_s2e1_native_profile_selects_pos_invoice(self):
        self.profile.create_pos_invoice_instead_of_sales_invoice = 1; self.profile.save()
        result = self.submit(self.payload())
        self.assertEqual((result["doctype"], result["docstatus"]), ("POS Invoice", 1))
        self.assertFalse(frappe.get_doc("POS Invoice", result["name"]).consolidated_invoice)

    def test_s2e1_native_manual_previous_day_is_not_rewritten_to_today(self):
        date = add_days(today(), -1)
        result = self.submit(self.payload(posting_date=date))
        self.assertEqual(str(frappe.get_doc(result["doctype"], result["name"]).posting_date), date)
        self.assertEqual(result["docstatus"], 1)

    def test_s2e1_native_background_transition_and_replay(self):
        self.profile.posa_allow_submissions_in_background_job = 1; self.profile.save()
        queued = []; request = uuid4().hex; payload = self.payload()
        with patch.object(creation, "enqueue", side_effect=lambda **kw: queued.append(kw)):
            result = self.submit(payload, request=request, background=1)
        self.assertEqual(result["docstatus"], 0); self.assertEqual(len(queued), 1)
        self.assertTrue(queued[0]["enqueue_after_commit"])
        creation.submit_in_background_job(queued[0]["kwargs"])
        self.assertEqual(frappe.get_doc(result["doctype"], result["name"]).docstatus, 1)
        ledger = creation._get_submission_ledger_by_name(queued[0]["kwargs"]["ledger_name"])
        self.assertEqual(ledger.state, creation.STATE_POST_SUBMIT_DONE)
        self.assertIsNone(frappe.flags.get("posa_owned_submission_ledger"))
        self.assertEqual(self.submit(payload, request=request)["name"], result["name"])

    def test_s2e1_native_existing_draft_payload_worker_uses_same_submit_path(self):
        self.profile.posa_allow_submissions_in_background_job = 1; self.profile.save()
        payload = self.payload(); draft = creation.update_invoice(json.dumps(payload))
        payload["name"] = draft["name"]; queued = []
        with patch.object(creation, "enqueue", side_effect=lambda **kw: queued.append(kw)):
            result = self.submit(payload, background=1)
        self.assertEqual(result["docstatus"], 0); self.assertTrue(result["queued"])
        self.assertEqual(len(queued), 1)
        self.assertIs(queued[0]["method"], creation.submit_payload_in_background_job)
        self.assertTrue(queued[0]["enqueue_after_commit"])
        queued[0]["method"](queued[0]["kwargs"])
        self.assertEqual(frappe.get_doc(result["doctype"], result["name"]).docstatus, 1)
        self.assertIsNone(frappe.flags.get("posa_owned_submission_ledger"))
        self.assertIsNone(frappe.flags.get("posa_background_authoritative_cashier"))

    def test_s2e1_native_offline_outbox_keeps_date_and_request_identity(self):
        request = uuid4().hex; date = add_days(today(), -1); payload = self.payload(posting_date=date)
        result = submit_invoice_outbox_entry(request, payload, dict(client_request_id=request))
        replay = submit_invoice_outbox_entry(request, payload, dict(client_request_id=request))
        self.assertTrue(result["acknowledged"]); self.assertTrue(replay["replayed"])
        self.assertEqual(result["invoice"]["name"], replay["invoice"]["name"])
        self.assertEqual(str(frappe.get_doc(result["invoice"]["doctype"], result["invoice"]["name"]).posting_date), date)

    def test_s2e2_native_zero_share_has_zero_allocated_amount(self):
        from posawesome.posawesome.api.invoice import sync_sales_person
        person = frappe.get_doc(dict(doctype="Sales Person", sales_person_name="S2e1 " + self.suffix,
            is_group=0)).insert()
        doc = frappe.get_doc(dict(doctype="Sales Invoice", grand_total=100, sales_team=[
            dict(sales_person=person.name, allocated_percentage=0, allocated_amount=0)]))
        sync_sales_person(doc)
        self.assertEqual(doc.sales_team[0].allocated_percentage, 0)
        self.assertEqual(doc.sales_team[0].allocated_amount, 0)

    def team(self, shares):
        return [dict(sales_person=frappe.get_doc(dict(doctype="Sales Person",
            sales_person_name=f"S2e2 {self.suffix} {uuid4().hex[:6]}", is_group=0)).insert().name,
            allocated_percentage=share) for share in shares]

    def assert_team(self, doc, shares):
        # Native field precision remains authoritative after submission (3 here).
        expected = [flt(share, doc.precision("allocated_percentage", doc.sales_team[0])) for share in shares]
        self.assertEqual([row.allocated_percentage for row in doc.sales_team], expected)
        self.assertAlmostEqual(sum(row.allocated_percentage for row in doc.sales_team), 100)
        self.assertEqual(doc.sales_team[0].allocated_amount, 0)
        self.assertAlmostEqual(sum(row.allocated_amount for row in doc.sales_team), doc.amount_eligible_for_commission)

    def test_s2e2_native_si_and_pos_sales_and_returns_keep_source_splits(self):
        for pos in [0, 1]:
            self.profile.create_pos_invoice_instead_of_sales_invoice = pos; self.profile.save()
            team = self.team([0, 33.3333, 66.6667])
            payload = self.payload(sales_team=team)
            payload["items"][0]["grant_commission"] = 1
            result = self.submit(payload)
            sale = frappe.get_doc(result["doctype"], result["name"])
            self.assert_team(sale, [0, 33.3333, 66.6667])
            self.assertEqual(sale.base_grand_total, 100)
            self.assertEqual(sale.paid_amount, 100)
            returned = self.payload(is_return=1, return_against=sale.name, sales_team=team)
            returned["items"][0].update(qty=-1, grant_commission=1,
                **{"pos_invoice_item" if pos else "sales_invoice_item": sale.items[0].name})
            returned["payments"][0]["amount"] = -100
            result = self.submit(returned)
            credit = frappe.get_doc(result["doctype"], result["name"])
            self.assert_team(credit, [0, 33.3333, 66.6667])
            self.assertEqual(credit.base_grand_total, -100)
            self.assertEqual(credit.return_against, sale.name)
            self.assertEqual(credit.paid_amount, -100)

    def test_s2e2_native_both_workers_preserve_split_after_draft_hydration(self):
        self.profile.posa_allow_submissions_in_background_job = 1; self.profile.save()
        for existing in [False, True]:
            team=self.team([0, 100]); payload=self.payload(sales_team=team)
            payload["items"][0]["grant_commission"]=1
            if existing:
                payload["name"]=creation.update_invoice(json.dumps(payload))["name"]
            queued=[]
            with patch.object(creation, "enqueue", side_effect=lambda **kw: queued.append(kw)):
                result=self.submit(payload, background=1)
            draft=frappe.get_doc(result["doctype"], result["name"])
            self.assert_team(draft, [0, 100])
            queued[0]["method"](queued[0]["kwargs"])
            sale=frappe.get_doc(result["doctype"], result["name"])
            self.assertEqual(sale.docstatus, 1)
            self.assert_team(sale, [0, 100])

    def test_s2e2_native_outbox_replay_keeps_decimal_split(self):
        request=uuid4().hex; team=self.team([0, 33.3333, 66.6667])
        payload=self.payload(sales_team=team); payload["items"][0]["grant_commission"]=1
        result=submit_invoice_outbox_entry(request, payload, dict(client_request_id=request))
        replay=submit_invoice_outbox_entry(request, payload, dict(client_request_id=request))
        self.assertTrue(replay["replayed"])
        self.assertEqual(result["invoice"]["name"], replay["invoice"]["name"])
        self.assert_team(frappe.get_doc(result["invoice"]["doctype"], result["invoice"]["name"]), [0, 33.3333, 66.6667])

    def test_s2e2_native_partial_team_is_rejected_without_inventing_a_share(self):
        payload=self.payload(sales_team=self.team([0, 40]))
        with self.assertRaisesRegex(frappe.ValidationError, "Total allocated percentage"):
            self.submit(payload)

    def test_s2e2_native_helper_never_promotes_absent_or_malformed_percent_to_full_amount(self):
        from posawesome.posawesome.api.invoice import sync_sales_person
        for value in [None, "", "bad", 0, "0", 33.3333]:
            for total in [100, -100]:
                row=frappe._dict(sales_person="Recorded", allocated_percentage=value, allocated_amount=0)
                doc=frappe._dict(sales_team=[row], grand_total=total)
                sync_sales_person(doc)
                self.assertEqual(row.allocated_percentage, value)
                expected=total*33.3333/100 if value==33.3333 else 0
                self.assertAlmostEqual(row.allocated_amount, expected)

    def test_s2e2_native_legacy_single_person_remains_compatible(self):
        person=self.team([100])[0]["sales_person"]
        payload=self.payload(custom_sales_person=person)
        result=self.submit(payload)
        sale=frappe.get_doc(result["doctype"], result["name"])
        self.assertEqual([(row.sales_person, row.allocated_percentage) for row in sale.sales_team], [(person, 100)])
