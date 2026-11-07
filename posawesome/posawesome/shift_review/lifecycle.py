"""Native source cancellation/reversal invalidates allocations in the same transaction."""

from decimal import Decimal

import frappe
from . import snapshot
from .service import save, actions, recompute, _insert_action
from erpnext.accounts.expense_services.commands import fingerprint


def lock_reversal_source(doc, method=None):
    if doc.get("reversal_of"):
        frappe.db.get_value("Journal Entry", doc.reversal_of, "name", for_update=True)


def _posted_capacity(claim):
    total = sum((Decimal(row["signed_amount"]) for row in snapshot.gl_legs(claim.financial_doctype, claim.financial_name,
                frappe.get_cached_value("POS Shift Review", claim.review, "company"), {claim.account})), Decimal(0))
    if claim.financial_doctype != "Journal Entry":
        return total
    seen, frontier = {claim.financial_name}, [claim.financial_name]
    while frontier:
        rows = frappe.db.get_values("Journal Entry", filters={"reversal_of": ["in", frontier], "docstatus": 1}, fieldname=["name", "company"], as_dict=True, for_update=True)
        frontier = []
        for row in rows:
            if row.name in seen:
                continue
            seen.add(row.name)
            frontier.append(row.name)
            total += sum((Decimal(leg["signed_amount"]) for leg in snapshot.gl_legs("Journal Entry", row.name, row.company, {claim.account})), Decimal(0))
    return total


def changed(doc, method=None):
    if not frappe.db.table_exists("POS Shift Source Claim"):
        return  # App upgrade has not installed the additive review schema yet.
    targets = {(doc.doctype, doc.name)}
    if doc.doctype == "Journal Entry" and doc.get("reversal_of"):
        name = doc.reversal_of
        visited = set()
        while name and name not in visited:
            visited.add(name)
            targets.add(("Journal Entry", name))
            name = frappe.db.get_value("Journal Entry", name, "reversal_of")
    for doctype, name in sorted(targets):
        _invalidate(doctype, name, doc, method)


def _invalidate(doctype, name, event, method):
    claims = frappe.db.get_values("POS Shift Source Claim", filters=dict(financial_doctype=doctype, financial_name=name, active=1), fieldname=["name", "review"], as_dict=True, for_update=True)
    affected = sorted({row.review for row in claims})
    for review_name in affected:
        frappe.db.get_value("POS Shift Review", review_name, "name", for_update=True)
        review = frappe.get_doc("POS Shift Review", review_name, for_update=True)
        if review.status == "Voided":
            continue
        reason = f"{event.doctype} {event.name}: {method}"
        transfers = frappe.db.get_values("POS Shift Review Action", filters=dict(review=review_name, financial_doctype=doctype, financial_name=name,
            action=["in", ["Safe transfer", "Payment correction", "Native handoff"]], state="Complete"), fieldname=["name", "review"], as_dict=True, for_update=True)
        for item in [row for row in claims if row.review == review_name]:
            claim = frappe.get_doc("POS Shift Source Claim", item.name, for_update=True)
            if claim.row_key in {"safe-transfer", "payment-correction", "native-handoff"}:
                claim.active = 0
                save(claim)
                continue
            capacity = _posted_capacity(claim)
            original = Decimal(str(claim.capacity))
            usable = min(abs(capacity), abs(original)) if capacity * original > 0 else Decimal(0)
            allocated = abs(Decimal(str(claim.allocated_amount)))
            if usable >= allocated:
                continue
            left = usable
            for row in actions(review):
                if row.state != "Complete" or row.financial_doctype != doctype or row.financial_name != name or row.row_key != claim.row_key:
                    continue
                operation = frappe.get_doc("POS Shift Review Action", row.name, for_update=True)
                value = Decimal(str(operation.signed_amount))
                kept = min(abs(value), left)
                left -= kept
                if kept == abs(value):
                    continue
                operation.state = "Invalidated"
                operation.invalidation_reason = reason
                save(operation)
                if kept:
                    signed = kept if value > 0 else -kept
                    key = "lifecycle:" + fingerprint(dict(event=event.name, method=method, original=operation.name, capacity=str(capacity)))
                    _insert_action(review, "Posting lifecycle", {"reason": reason}, key, fingerprint(dict(key=key)),
                        row=next(r for r in review.accounts if r.row_key == claim.row_key), signed=signed,
                        financial=(doctype, name), evidence={"original_action": operation.name, "posted_capacity": str(capacity)})
            claim.allocated_amount = float((usable if original > 0 else -usable))
            claim.active = int(bool(usable))
            save(claim)
        for row in [row for row in transfers if row.review == review_name]:
            operation = frappe.get_doc("POS Shift Review Action", row.name, for_update=True)
            operation.state = "Invalidated"
            operation.invalidation_reason = reason
            save(operation)
        recompute(review)
