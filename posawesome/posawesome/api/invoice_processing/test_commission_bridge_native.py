"""Enabled private bridge on a disposable installed-POS database.

Worker functions here execute in-process. The separate RQ harness proves real
worker transactions and committed replay/failure behavior.
"""
import json
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.utils import add_days, get_first_day, get_datetime, today

from erpnext.setup import staff_commission_capture as capture, staff_commission_snapshots as snapshots
from erpnext.setup.doctype.staff_commission_assignment import staff_commission_assignment as terms
from posawesome.posawesome.api.invoice_processing import creation, commission_capture as bridge
from posawesome.posawesome.api.invoice_processing.test_commission_capture_native import TestCommissionCaptureAdoptionNative
from posawesome.posawesome.api.offline_sync.invoices import submit_invoice_outbox_entry


class TestCommissionPOSBridgeNative(TestCommissionCaptureAdoptionNative):
    def setUp(self):
        super().setUp()
        if not frappe.db.exists("Gender", "Male"):
            frappe.get_doc(dict(doctype="Gender", gender="Male")).insert()
        self.scheme = frappe.get_doc(dict(doctype="Staff Commission Scheme", scheme_name="S2e4 " + self.suffix,
            is_active=1, basis="Gross Profit Margin", calculation_type="Fixed Percentage", fixed_rate=10)).insert()
        self.person, self.employee = self.member()
        frappe.get_doc(dict(doctype=capture.SETTINGS, company=self.company, enabled=1, capture_version=1)).insert()

    def member(self):
        employee = frappe.get_doc(dict(doctype="Employee", first_name="S2e4 " + uuid4().hex[:8],
            company=self.company, gender="Male", date_of_birth="1995-02-03", date_of_joining="2020-01-01",
            status="Active", create_user_permission=0)).insert()
        person = frappe.get_doc(dict(doctype="Sales Person", sales_person_name=employee.employee_name,
            employee=employee.name, is_group=0)).insert()
        month = str(get_first_day(today()))
        with patch.object(terms, "today", return_value=add_days(month, -1)), \
                patch.object(terms, "now_datetime", return_value=get_datetime(add_days(month, -1))):
            frappe.get_doc(dict(doctype="Staff Commission Assignment", company=self.company,
                employee=employee.name, scheme=self.scheme.name, effective_from=month)).insert().submit()
        return person, employee

    def payload(self, **changes):
        return super().payload(**dict(dict(sales_team=[dict(sales_person=self.person.name,
            allocated_percentage=100)]), **changes))

    def outcome(self, result, state="Captured", reason=None):
        row = frappe.get_doc(capture.OUTCOME, frappe.db.get_value(capture.OUTCOME,
            dict(source_type=result["doctype"], source_name=result["name"]), "name"))
        self.assertEqual(row.state, state)
        if reason:
            self.assertEqual(row.reason, reason)
        manifest = json.loads(row.manifest)
        self.assertEqual(snapshots.digest(row.manifest), row.manifest_hash)
        return manifest

    def test_s2e4_foreground_si_pos_split_and_replay_seal_once(self):
        other, _ = self.member()
        for pos in (0, 1):
            self.profile.create_pos_invoice_instead_of_sales_invoice = pos; self.profile.save()
            team = [dict(sales_person=self.person.name, allocated_percentage=0),
                    dict(sales_person=other.name, allocated_percentage=100)]
            payload = self.payload(sales_team=team); request = uuid4().hex
            result = self.submit(payload, request)
            manifest = self.outcome(result)
            self.assertEqual(len(manifest["members"]), 2)
            self.assertEqual(self.submit(payload, request)["name"], result["name"])
            self.assertEqual(frappe.db.count(capture.OUTCOME, dict(source_name=result["name"])), 1)
            self.assertFalse(set(result) & {"employee", "manifest", "cost", "evidence", "commission"})
            self.assertIsNone(bridge._submission.get()); self.assertIsNone(capture.current_operation())

    def test_s2e4_both_workers_mint_fresh_authority(self):
        self.profile.posa_allow_submissions_in_background_job = 1; self.profile.save()
        for existing in (False, True):
            payload = self.payload()
            if existing:
                payload["name"] = creation.update_invoice(json.dumps(payload))["name"]
            queued = []
            with patch.object(creation, "enqueue", side_effect=lambda **kw: queued.append(kw)):
                result = self.submit(payload, background=1)
            self.assertEqual(result["docstatus"], 0)
            self.assertEqual(frappe.db.count(capture.OUTCOME, dict(source_name=result["name"])), 0)
            self.assertFalse(any("capability" in key or "capture" in key for key in queued[0]["kwargs"]))
            queued[0]["method"](queued[0]["kwargs"])
            self.assertEqual(frappe.get_doc(result["doctype"], result["name"]).docstatus, 1)
            self.outcome(result)
            ledger = frappe.get_doc(creation.LEDGER_DOCTYPE, queued[0]["kwargs"]["ledger_name"])
            self.assertEqual(ledger.state, creation.STATE_POST_SUBMIT_DONE)
            queued[0]["method"](queued[0]["kwargs"])
            self.assertEqual(ledger.reload().state, creation.STATE_POST_SUBMIT_DONE)
            self.assertIsNone(bridge._worker.get()); self.assertIsNone(bridge._submission.get())
            self.assertIsNone(capture.current_operation())

    def test_s2e4_outbox_backdated_preserves_date_and_unavailable_outcome(self):
        request = uuid4().hex; date = add_days(today(), -1)
        payload = self.payload(posting_date=date)
        result = submit_invoice_outbox_entry(request, payload, dict(client_request_id=request))
        self.assertTrue(result["acknowledged"])
        self.outcome(result["invoice"], "Unavailable", "unsupported_date")
        self.assertEqual(str(frappe.get_doc(result["invoice"]["doctype"], result["invoice"]["name"]).posting_date), date)
        replay = submit_invoice_outbox_entry(request, payload, dict(client_request_id=request))
        self.assertEqual(replay["invoice"]["name"], result["invoice"]["name"])

    def test_s2e4_absent_private_attestation_and_client_flags_never_authorize(self):
        payload = self.payload(); draft = creation.update_invoice(json.dumps(payload))
        doc = frappe.get_doc(draft["doctype"], draft["name"])
        doc.flags.ignore_permissions = True; doc.flags.posa_commission_capture = True
        doc.submit()
        self.outcome(doc.as_dict(), "Unavailable", "source_authority_required")

    def test_s2e4_changed_persisted_ledger_or_actor_withholds_originals(self):
        original = bridge.authorized_source
        for key, value in [("owner", "Guest"), ("invoice_name", "wrong"), ("client_request_id", "wrong")]:
            def changed(doc):
                grant = bridge._submission.get()
                previous = frappe.db.get_value(creation.LEDGER_DOCTYPE, grant.ledger_name, key)
                frappe.db.set_value(creation.LEDGER_DOCTYPE, grant.ledger_name, key, value, update_modified=False)
                try:
                    return original(doc)
                finally:
                    frappe.db.set_value(creation.LEDGER_DOCTYPE, grant.ledger_name, key, previous, update_modified=False)
            with patch.object(bridge, "authorized_source", side_effect=changed):
                result = self.submit(self.payload())
            self.outcome(result, "Unavailable", "source_authority_required")
            self.assertEqual(frappe.db.count(snapshots.DOCTYPE, dict(source_name=result["name"])), 0)

    def test_s2e4_private_failure_rolls_back_native_source_and_resets_authority(self):
        with patch.object(capture, "_insert", side_effect=RuntimeError("private Employee/cost/hash")):
            with self.assertRaises(capture.CaptureSubmissionError) as error:
                self.submit(self.payload())
        self.assertNotIn("private", str(error.exception))
        self.assertEqual(frappe.db.count(capture.OUTCOME), 0)
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE), 0)
        self.assertEqual(frappe.db.count("Sales Invoice", dict(company=self.company, docstatus=1)), 0)
        self.assertIsNone(bridge._submission.get()); self.assertIsNone(capture.current_operation())

    def test_s2e4_return_uses_original_members_and_cancel_keeps_private_identity(self):
        for pos in (0, 1):
            self.profile.create_pos_invoice_instead_of_sales_invoice = pos; self.profile.save()
            sale = self.submit(self.payload())
            source = frappe.get_doc(sale["doctype"], sale["name"])
            other, _ = self.member()
            payload = self.payload(is_return=1, return_against=source.name,
                sales_team=[dict(sales_person=other.name, allocated_percentage=100)])
            payload["items"][0].update(qty=-1,
                **{"pos_invoice_item" if pos else "sales_invoice_item": source.items[0].name})
            payload["payments"][0]["amount"] = -100
            result = self.submit(payload); manifest = self.outcome(result)
            self.assertEqual([m["employee"] for m in manifest["members"]], [self.employee.name])
            frappe.get_doc(result["doctype"], result["name"]).cancel()
            self.outcome(result)
            self.assertEqual(frappe.db.count(snapshots.DOCTYPE, dict(source_name=result["name"])), 1)
            self.assertFalse(frappe.db.exists(creation.LEDGER_DOCTYPE, dict(invoice_name=result["name"])))

    def test_s2e4_explicit_payment_repair_reuses_original_without_recapture(self):
        request = uuid4().hex
        result = self.submit(self.payload(), request=request)
        manifest = self.outcome(result)
        ledger = creation._get_submission_ledger(request, self.company, self.profile.name, result["doctype"])
        creation._update_submission_ledger(ledger, creation.STATE_FAILED, error_message="Disposable payment failure")
        repaired = creation.repair_invoice_submission(request, company=self.company,
            pos_profile=self.profile.name, document_type=result["doctype"])
        self.assertTrue(repaired["repaired"])
        self.assertEqual(repaired["ledger_state"], creation.STATE_POST_SUBMIT_DONE)
        self.assertEqual(self.outcome(result), manifest)
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE, dict(source_name=result["name"])), 1)

    def test_s2e4_native_source_actor_without_hr_can_capture_but_cannot_observe(self):
        from posawesome.posawesome.api import terminal_state
        user = frappe.get_doc(dict(doctype="User", email=f"s2e4-{self.suffix}@example.test", first_name="POS actor",
            enabled=1, send_welcome_email=0, roles=[dict(role=r) for r in
                ("Sales Manager", "Accounts Manager", "Stock Manager", "Stock User")])).insert()
        self.profile.append("applicable_for_users", dict(user=user.name)); self.profile.save()
        opening = self.open_shift(0, user=user.name)
        frappe.set_user(user.name)
        terminal_state.activate_verified_cashier(self.profile, user.name)
        self.assertFalse(frappe.has_permission("Employee", "read"))
        result = self.submit(self.payload(posa_pos_opening_shift=opening.name))
        from erpnext.setup.staff_payroll_data import Unavailable
        with self.assertRaises((frappe.PermissionError, Unavailable)):
            snapshots.observe_captured_source(result["doctype"], result["name"])
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list(capture.OUTCOME, fields=["manifest"])
        frappe.set_user("Administrator"); self.outcome(result)

    def test_s2e4_capture_all_member_observation_is_atomic_idempotent_and_keeps_original(self):
        other, _ = self.member()
        result = self.submit(self.payload(sales_team=[dict(sales_person=self.person.name, allocated_percentage=50),
            dict(sales_person=other.name, allocated_percentage=50)]))
        manifest = self.outcome(result)
        originals = {m["evidence"]: frappe.get_doc(snapshots.DOCTYPE, m["evidence"]).payload for m in manifest["members"]}
        names = snapshots.observe_captured_source(result["doctype"], result["name"])
        self.assertEqual(len(names), 2)
        self.assertEqual(names, snapshots.observe_captured_source(result["doctype"], result["name"]))
        for name, payload in originals.items():
            self.assertEqual(frappe.get_doc(snapshots.DOCTYPE, name).payload, payload)
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE, dict(kind="Observation")), 2)

    def test_s2e4_unavailable_or_old_source_cannot_be_promoted_by_observation(self):
        from erpnext.setup.staff_payroll_data import Unavailable
        result = self.submit(self.payload(posting_date=add_days(today(), -1)))
        with self.assertRaises(Unavailable):
            snapshots.observe_captured_source(result["doctype"], result["name"])
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE), 0)

    def test_s2e4_serialized_proof_budget_preserves_sale_with_no_partial_originals(self):
        with patch.object(capture, "MAX_ORIGINAL_BYTES", 1):
            result = self.submit(self.payload())
        self.outcome(result, "Unavailable", "source_limit")
        self.assertEqual(result["docstatus"], 1)
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE), 0)

    def test_s2e4_observation_budget_or_second_member_failure_rolls_back_entire_batch(self):
        from erpnext.setup.staff_payroll_data import Unavailable
        other, _ = self.member()
        result = self.submit(self.payload(sales_team=[dict(sales_person=self.person.name, allocated_percentage=50),
            dict(sales_person=other.name, allocated_percentage=50)]))
        with patch.object(snapshots, "MAX_OBSERVATION_BYTES", 1):
            with self.assertRaises(Unavailable):
                snapshots.observe_captured_source(result["doctype"], result["name"])
        original = snapshots._append; calls = []
        def append(*args, **kwargs):
            calls.append(args)
            if len(calls) == 2:
                raise Unavailable()
            return original(*args, **kwargs)
        with patch.object(snapshots, "_append", side_effect=append):
            with self.assertRaises(Unavailable):
                snapshots.observe_captured_source(result["doctype"], result["name"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE, dict(kind="Observation")), 0)

    def test_s2e4_return_original_graph_budget_withholds_without_blocking_valid_return(self):
        sale = self.submit(self.payload())
        source = frappe.get_doc(sale["doctype"], sale["name"])
        payload = self.payload(is_return=1, return_against=source.name)
        payload["items"][0].update(qty=-1, sales_invoice_item=source.items[0].name)
        payload["payments"][0]["amount"] = -100
        with patch.object(capture, "MAX_ORIGINAL_RECORDS", 0):
            result = self.submit(payload)
        self.outcome(result, "Unavailable", "source_limit")
        self.assertEqual(result["docstatus"], 1)
        self.assertEqual(frappe.db.count(snapshots.DOCTYPE, dict(source_name=result["name"])), 0)
