"""Shared submission invariant for POS, Desk and direct Document submission."""

import json

import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.expense_services import policy as expense_policy
from . import SERVICE, arithmetic, policy, snapshot


def validate(closing):
    policy.require_schema()
    from posawesome.posawesome.doctype.pos_closing_shift.closing_processing import creation
    from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.overview import build_closing_overview
    frappe.db.get_value("POS Opening Shift", closing.pos_opening_shift, "name", for_update=True)
    opening = creation.get_authorized_opening_shift(closing.pos_opening_shift)
    if opening.docstatus != 1 or opening.status != "Open" or opening.get("pos_closing_shift"):
        frappe.throw(_("An active submitted opening shift is required."))
    if (closing.company, closing.pos_profile, closing.user) != (opening.company, opening.pos_profile, opening.user):
        frappe.throw(_("Closing shift does not match the opening shift."))
    expense_policy.check_company(opening.company)
    expense_policy.check_user_scope("POS Profile", opening.pos_profile)
    if not frappe.has_permission("POS Profile", "read", doc=opening.pos_profile):
        frappe.throw(_("You do not have access to this register."), frappe.PermissionError)
    use_pos = frappe.db.get_value("POS Profile", opening.pos_profile, "create_pos_invoice_instead_of_sales_invoice")
    doctype = "POS Invoice" if use_pos else "Sales Invoice"
    invoices = creation.get_pos_invoices(opening.name, doctype, submit_printed=0)
    entries = creation.get_payments_entries(opening.name)
    if any(row.get("company") != opening.company for row in [*invoices, *entries]):
        frappe.throw(_("The source must belong to the review company."))
    overview = build_closing_overview(opening, invoices, entries)
    expected = {row["mode_of_payment"]: row for row in overview["reconciliation"]}
    for row in overview["reconciliation"]:
        if row.get("account"):
            expense_policy.check_user_scope("Account", row["account"])
    rows = closing.get("payment_reconciliation", [])
    invoice_names = {row.get("sales_invoice") or row.get("pos_invoice") for row in closing.get("pos_transactions", [])}
    payment_names = {row.get("payment_entry") for row in closing.get("pos_payments", [])}
    if len(closing.get("pos_transactions", [])) != len(invoices) or len(closing.get("pos_payments", [])) != len(entries) or invoice_names != {row["name"] for row in invoices} or payment_names != {row["name"] for row in entries} or len(rows) != len(expected) or {row.mode_of_payment for row in rows} != set(expected):
        frappe.throw(_("Shift totals changed. Reload the closing summary before closing."))
    originals = {row["name"]: row for row in invoices}
    invoice_field = "pos_invoice" if use_pos else "sales_invoice"
    other_field = "sales_invoice" if use_pos else "pos_invoice"
    for row in closing.get("pos_transactions", []):
        if row.get(other_field) or not row.get(invoice_field):
            frappe.throw(_("The invoice type does not match this register."))
        source = originals[row.get(invoice_field)]
        for field, value in dict(posting_date=source.get("posting_date"),
            grand_total=creation.get_base_value(source, "grand_total", "base_grand_total"),
            transaction_currency=source.get("currency"), transaction_amount=source.get("grand_total"), customer=source.get("customer")).items():
            row.set(field, value)
    payments = {row["name"]: row for row in entries}
    for row in closing.get("pos_payments", []):
        original = creation.build_pos_payment_reference(payments[row.payment_entry])
        for field, value in original.items():
            row.set(field, value)
    taxes = {}
    for invoice in invoices:
        for tax in invoice.get("taxes", []):
            key = (tax.get("account_head"), tax.get("rate"))
            taxes[key] = taxes.get(key, 0) + creation.get_base_value(tax, "tax_amount", "base_tax_amount", invoice.get("conversion_rate"))
    closing.set("taxes", [dict(account_head=account, rate=rate, amount=value) for (account, rate), value in taxes.items()])
    precision = expense_policy.currency_precision(opening.company)
    differences = []
    for row in rows:
        fresh = expected[row.mode_of_payment]
        try:
            actual = arithmetic.amount(row.closing_amount, precision)
            fresh_expected = arithmetic.amount(flt(fresh["expected_amount"], precision), precision)
            stale = arithmetic.amount(flt(row.expected_amount, precision), precision) != fresh_expected
        except ValueError:
            frappe.throw(_("Enter actual counts using the company currency precision."))
        if stale:
            frappe.throw(_("Shift totals changed. Reload the closing summary before closing."))
        fresh["expected_amount"] = float(fresh_expected)
        row.expected_amount = float(fresh_expected)
        row.opening_amount = fresh["opening_amount"]
        row.difference = float(actual - fresh_expected)
        if fresh.get("account") and frappe.get_cached_value("Account", fresh["account"], "account_type") == "Cash" and actual < 0:
            frappe.throw(_("A physical cash count cannot be negative."))
        differences.append(row.difference)
    if any(differences) and not (closing.get("discrepancy_reason") or "").strip():
        frappe.throw(_("Explain the difference before closing. The shift can close with Pending review."))
    closing.period_start_date = opening.period_start_date
    closing.period_end_date = frappe.utils.now_datetime()
    closing.grand_total = sum(creation.get_base_value(row, "grand_total", "base_grand_total") for row in invoices)
    closing.net_total = sum(creation.get_base_value(row, "net_total", "base_net_total") for row in invoices)
    closing.total_quantity = sum(flt(row.get("total_qty")) for row in invoices)
    creation.normalize_pos_payment_references(closing)
    closing.flags.shift_review_context = (opening, overview, invoices, entries)


def create_review(closing):
    context = closing.flags.get("shift_review_context")
    if not context:
        frappe.throw(_("Validated closing evidence is required to create a shift review."))
    data = snapshot.build(closing, *context)
    canonical = snapshot.encode(data)
    doc = frappe.get_doc(dict(doctype="POS Shift Review", company=closing.company, pos_profile=closing.pos_profile,
        pos_opening_shift=closing.pos_opening_shift, closing_shift=closing.name, cashier=closing.user,
        cashier_reason=closing.get("discrepancy_reason"), currency=data["currency"], currency_precision=data["precision"],
        snapshot_json=canonical, snapshot_hash=snapshot.fingerprint(json.loads(canonical)),
        version=1, status="Pending review" if any(float(row["original_difference"]) for row in data["groups"]) else "Resolved"))
    for group in data["groups"]:
        doc.append("accounts", dict(row_key=group["row_key"], account=group["account"], currency=group["currency"],
            account_currency=group["account_currency"], account_type=group["account_type"], methods_json=snapshot.encode(group["methods"]),
            expected_amount=float(group["expected_amount"]), actual_amount=float(group["actual_amount"]),
            original_difference=float(group["original_difference"]), allocated_amount=0, remaining_amount=float(group["original_difference"])))
    doc.flags.shift_review_service = SERVICE
    doc.insert(ignore_permissions=True)
    closing.db_set({"shift_review": doc.name, "review_status": doc.status}, update_modified=False)
    return doc


def before_cancel(closing):
    policy.require_schema()
    # The same shift lock guards submission of new invoices and expenses. Keep it
    # until cancellation has reopened the shift and finished native unconsolidation.
    frappe.db.get_value("POS Opening Shift", closing.pos_opening_shift, "name", for_update=True)
    name = frappe.db.get_value("POS Shift Review", {"closing_shift": closing.name}, "name", for_update=True)
    if not name:
        return  # Historical closing without new provenance: preserve native behavior.
    doc = frappe.get_doc("POS Shift Review", name, for_update=True)
    policy.scope(doc, write=True)
    if frappe.db.get_value("POS Shift Review Action", {"review": name, "state": "Complete"}, "name", for_update=True):
        frappe.throw(_("Reverse or withdraw completed review resolutions before cancelling this closing."))
    if frappe.db.get_value("POS Shift Review Action", {"review": name, "action": "Transfer request", "state": ["in", ["Requested", "Complete"]]}, "name", for_update=True):
        frappe.throw(_("Investigate the transfer outcome before cancelling this closing."))
    doc.status = "Voided"
    doc.version += 1
    doc.flags.shift_review_service = SERVICE
    doc.save(ignore_permissions=True)
    closing.ignore_linked_doctypes = list(set(closing.get("ignore_linked_doctypes") or []) | {"POS Shift Review"})
    closing.review_status = "Voided"


def before_update_after_submit(closing):
    frappe.throw(_("Original closing counts and evidence cannot be changed after submission. Use shift review."))


def guard_shift_source(doc, method=None):
    """Serialize new invoice/payment/movement submission with closing's shift lock."""
    shift = doc.get("posa_pos_opening_shift") or doc.get("pos_opening_shift")
    if not shift and doc.doctype == "Payment Entry":
        reference = doc.get("reference_no")
        if reference and frappe.db.exists("POS Opening Shift", reference):
            shift = reference
    if not shift:
        return
    stored = frappe.db.get_value("POS Opening Shift", shift, ["company", "status", "docstatus"], as_dict=True, for_update=True)
    if not stored or stored.company != doc.company or stored.docstatus != 1:
        frappe.throw(_("The source does not belong to a submitted opening shift in its company."))
    if stored.status != "Open" and not (doc.doctype == "Quick Expense" and doc.get("entry_context") == "POS Correction" and policy.is_manager()):
        frappe.throw(_("This shift is closed. Use the authorized correction workflow."))


def lock_shift_source_cancellation(doc, method=None):
    """A cancellation cannot change the expectation while closing snapshots it."""
    shift = doc.get("posa_pos_opening_shift") or doc.get("pos_opening_shift")
    if not shift and doc.doctype == "Payment Entry" and doc.get("reference_no"):
        if frappe.db.exists("POS Opening Shift", doc.reference_no):
            shift = doc.reference_no
    if shift:
        frappe.db.get_value("POS Opening Shift", shift, "name", for_update=True)
