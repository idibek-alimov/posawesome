"""One counted-cash transfer per closing, independently retrievable after a timeout."""

import hashlib
import json
from decimal import Decimal

import frappe
from frappe import _
from erpnext.accounts.expense_services.commands import lock_actor, fingerprint
from . import arithmetic, policy, snapshot
from .service import load, save, _insert_action, recompute


def following_shift(review, original, lock=False):
    scope = {"pos_profile": review.pos_profile, "docstatus": ["in", [1, 2]], "name": ["!=", review.pos_opening_shift]}
    def found(filters):
        # Posting needs a current read after the register lock, even if this
        # transaction established a repeatable-read snapshot before the new opening.
        return (frappe.db.get_value("POS Opening Shift", filters, "name", for_update=True)
                if lock else frappe.db.exists("POS Opening Shift", filters))
    return (found(dict(scope, status="Open"))
            or found(dict(scope, period_start_date=[">=", original["period_end"]])))


def lock_register_opening(doc, method=None):
    # The same register lock prevents a late original-count transfer racing a new opening.
    frappe.db.get_value("POS Profile", doc.pos_profile, "name", for_update=True)


def transfer(closing_name, requested=None):
    policy.require_schema()
    lock_actor()
    name = frappe.db.get_value("POS Shift Review", {"closing_shift": closing_name}, "name")
    if not name:
        frappe.throw(_("This historical closing has no transfer provenance. Investigate existing transfers in the native workflow."))
    review = load(name, lock=True)
    closing = frappe.get_doc("POS Closing Shift", closing_name)
    if closing.docstatus != 1 or review.status == "Voided":
        frappe.throw(_("Only a submitted closing shift can transfer cash to the safe."))
    original = snapshot.read(review)
    cash_mode = original["cash_mode"]
    cash = next((row for row in original["methods"] if row["mode_of_payment"] == cash_mode), None)
    if not cash or not cash.get("account"):
        frappe.throw(_("The closing has no mapped cash count."))
    counted = arithmetic.amount(cash["actual"], review.currency_precision)
    amount = counted if requested in (None, "") else arithmetic.amount(requested, review.currency_precision)
    if amount <= 0:
        return dict(success=False, message=_("No counted cash to transfer to the safe."))
    if amount > counted:
        frappe.throw(_("Transfer amount cannot exceed the counted cash."))
    key = "safe-transfer:" + hashlib.sha256(closing_name.encode()).hexdigest()
    previous = frappe.db.get_value("POS Shift Review Action", {"client_request_id": key}, "name", for_update=True)
    if previous:
        operation = frappe.get_doc("POS Shift Review Action", previous)
        data = json.loads(operation.evidence_json)
        if Decimal(data["amount"]) != amount:
            frappe.throw(_("This closing already has a different transfer request. Investigate its outcome before moving more cash."))
        if operation.state != "Complete":
            frappe.throw(_("The original safe transfer was reversed or changed. Investigate its native document; do not repeat it."))
        return dict(success=True, transferred_amount=float(amount), payment_entry=operation.financial_name,
                    target_wallet=data["target_label"], message=_("The original safe transfer is confirmed."))
    lock_register_opening(review)
    if following_shift(review, original, lock=True):
        frappe.throw(_("Another shift has opened on this register. Check the current physical cash and use the native transfer workflow; do not transfer an old count."))
    if frappe.db.get_value("POS Shift Review Action", {"review": name, "action": "Count correction", "state": "Complete"}, "name", for_update=True):
        frappe.throw(_("The count was corrected after closing. Use the native transfer workflow with the revised evidence."))
    if frappe.get_cached_value("Account", cash["account"], "account_currency") != review.currency:
        frappe.throw(_("Use the native transfer workflow for foreign-currency counted cash."))
    sources = frappe.get_all("Money Wallet", filters={"company": review.company, "account": cash["account"], "enabled": 1}, fields=["name", "wallet_name", "account"], order_by="name")
    configured = frappe.get_cached_value("POS Profile", review.pos_profile, "posa_back_office_cash_account")
    safe_filters = dict(company=review.company, wallet_type="Safe", enabled=1)
    if configured:
        safe_filters["account"] = configured
    targets = frappe.get_all("Money Wallet", filters=safe_filters, fields=["name", "wallet_name", "account"], order_by="name")
    if not sources or len({row.account for row in targets}) != 1:
        frappe.throw(_("Configure one explicit Safe destination and an enabled wallet for the original till account."))
    target = targets[0]
    frappe.db.savepoint("shift_safe_transfer")
    try:
        from erpnext.accounts.expense_services.shift_adjustments import post_shift_transfer
        doc = post_shift_transfer(review.company, sources[0].name, target.name, amount, closing_name)
        claim = frappe.get_doc(dict(doctype="POS Shift Source Claim",
            claim_key=hashlib.sha256(f"Payment Entry|{doc.name}|{cash['account']}".encode()).hexdigest(),
            review=review.name, row_key="safe-transfer", financial_doctype="Payment Entry", financial_name=doc.name,
            account=cash["account"], capacity=0, allocated_amount=0, currency=review.currency, active=1, evidence_json="{}"))
        save(claim, insert=True)
        _insert_action(review, "Safe transfer", {"reason": "Counted cash after closing"}, key,
            fingerprint(dict(closing=closing_name, amount=str(amount))), source=doc, financial=("Payment Entry", doc.name),
            evidence=dict(amount=str(amount), target_label=target.wallet_name, target_account=target.account, source_account=cash["account"]))
        recompute(review)
        return dict(success=True, transferred_amount=float(amount), target_wallet=target.wallet_name,
                    payment_entry=doc.name, message=_("Counted cash transfer completed. Any shift difference remains under review."))
    except Exception:
        frappe.db.rollback(save_point="shift_safe_transfer")
        raise
