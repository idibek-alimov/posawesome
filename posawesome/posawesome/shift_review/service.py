"""Serialized, idempotent review commands. All financial effects share the transaction."""

import hashlib
import json
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, today
from erpnext.accounts.expense_services import commands as expenses
from . import SERVICE, arithmetic, policy, snapshot

SOURCE_TYPES = {"Quick Expense", "POS Cash Movement", "Payment Entry", "Journal Entry", "Sales Invoice", "POS Invoice"}
REQUEST_TYPES = {"Investigate", "Payment correction request", "Refund request", "Transfer request", "Recovery request", "Bank reconciliation request"}


def save(doc, insert=False):
    doc.flags.shift_review_service = SERVICE
    return doc.insert(ignore_permissions=True) if insert else doc.save(ignore_permissions=True)


def load(name, lock=False, write=False):
    policy.require_schema()
    if lock:
        frappe.db.get_value("POS Shift Review", name, "name", for_update=True)
    doc = frappe.get_doc("POS Shift Review", name, for_update=lock)
    policy.scope(doc, write=write)
    doc.check_permission("read")
    snapshot.read(doc)
    return doc


def actions(review):
    return frappe.db.get_values("POS Shift Review Action", filters={"review": review.name}, fieldname=["name", "action", "state", "row_key", "signed_amount", "evidence_json", "source_doctype", "source_name", "financial_doctype", "financial_name"], order_by="creation asc, name asc", as_dict=True, for_update=True)


def recompute(review, bump=True):
    rows = actions(review)
    for row in review.accounts:
        values = [action.signed_amount for action in rows if action.state == "Complete" and action.row_key == row.row_key]
        values.extend(entry["signed_amount"] for action in rows if action.state == "Complete" and action.action == "Payment correction"
                      for entry in json.loads(action.evidence_json)["allocations"] if entry["row_key"] == row.row_key)
        try:
            rest = arithmetic.remaining(row.original_difference, values, review.currency_precision)
        except ValueError as error:
            frappe.throw(_(str(error)))
        row.remaining_amount = float(rest)
        row.allocated_amount = float(Decimal(str(row.original_difference)) - rest)
    review.status = arithmetic.status([dict(remaining_amount=row.remaining_amount, allocated_amount=row.allocated_amount) for row in review.accounts], started=bool(review.reviewer), voided=review.status == "Voided")
    if bump:
        review.version += 1
    save(review)
    frappe.db.set_value("POS Closing Shift", review.closing_shift, "review_status", review.status, update_modified=False)
    return review


def result(review, operation=None):
    response = dict(review=review.name, status=review.status, version=review.version, currency=review.currency,
        accounts=[{key: row.get(key) for key in ("row_key", "account", "expected_amount", "actual_amount", "original_difference", "allocated_amount", "remaining_amount")} for row in review.accounts])
    if operation:
        response["operation"] = dict(name=operation.name, action=operation.action, state=operation.state,
            client_request_id=operation.client_request_id, source_doctype=operation.source_doctype,
            source_name=operation.source_name, financial_doctype=operation.financial_doctype, financial_name=operation.financial_name)
    return response


def _row(review, key):
    row = next((row for row in review.accounts if row.row_key == key), None)
    if not row:
        frappe.throw(_("Select an account difference in this review."))
    return row


def _amount(review, row, proposed):
    try:
        proposed = arithmetic.amount(proposed, review.currency_precision)
        arithmetic.allocate(row.original_difference, [row.allocated_amount], proposed, review.currency_precision)
    except ValueError as error:
        frappe.throw(_(str(error)))
    return proposed


def _source(doctype, name, allow_cancelled=False):
    if doctype not in SOURCE_TYPES or not name:
        frappe.throw(_("Select a supported native correction document."))
    frappe.db.get_value(doctype, name, "name", for_update=True)
    doc = frappe.get_doc(doctype, name, for_update=True)
    doc.check_permission("read")
    if doc.docstatus != 1 and not (allow_cancelled and doc.docstatus == 2):
        frappe.throw(_("Only a submitted correction document can resolve money."))
    return doc


def _effect(review, row, source, explicit_attribution=False):
    original = snapshot.read(review)
    if not row.account or row.account_currency != review.currency:
        frappe.throw(_("Unmapped or foreign-currency sources need the native accountant workflow."))
    if source.company != review.company:
        frappe.throw(_("The source must belong to the review company."))
    stored_shift = source.get("pos_opening_shift") or source.get("posa_pos_opening_shift")
    if source.doctype == "Payment Entry" and source.get("reference_no") and frappe.db.exists("POS Opening Shift", source.reference_no):
        stored_shift = source.reference_no
    if stored_shift and stored_shift != review.pos_opening_shift:
        frappe.throw(_("This source belongs to another shift."), frappe.PermissionError)
    if not stored_shift and not explicit_attribution:
        frappe.throw(_("Explicit manager attribution to the original shift is required for an unassigned source."))
    if source.get("posting_date") and getdate(source.posting_date) > getdate(today()):
        frappe.throw(_("Use a posting date between the shift opening date and today."))
    if not stored_shift and get_datetime(source.creation) < get_datetime(original["period_start"]):
        frappe.throw(_("The source predates this shift. Use the native accountant workflow."))
    if not source.get("posting_date") or getdate(source.posting_date) < getdate(original["period_start"]):
        frappe.throw(_("The source predates this shift. Use the native accountant workflow."))
    if source.get("amended_from"):
        frappe.throw(_("Confirm a native payment correction through its original and replacement documents."))
    financial = snapshot.vouchers(source)
    if len(financial) != 1:
        frappe.throw(_("This source needs native accounting review; a single paid effect is required."))
    doctype, name = financial[0]
    if (source.doctype, source.name) in {(s["doctype"], s["name"]) for s in original["sources"]} or (doctype, name) in {(v["doctype"], v["name"]) for s in original["sources"] for v in s["vouchers"]}:
        frappe.throw(_("This source was already included in the original closing expectations."))
    if frappe.db.get_value("POS Shift Review Action", {"action": "Safe transfer", "financial_doctype": doctype, "financial_name": name}, "name", for_update=True):
        frappe.throw(_("A counted-cash safe transfer does not resolve a closing difference."))
    voucher = source if source.doctype == doctype and source.name == name else _source(doctype, name)
    if voucher.company != review.company:
        frappe.throw(_("The accounting source must belong to the review company."))
    reversal = voucher.get("reversal_of")
    if reversal and frappe.db.get_value("POS Shift Source Claim", {"financial_doctype": "Journal Entry", "financial_name": reversal}, "name", for_update=True):
        frappe.throw(_("A reversal reopens its original review; do not allocate it as a new explanation."))
    if doctype == "Journal Entry" and frappe.db.get_value("Journal Entry", {"reversal_of": name, "docstatus": 1}, "name", for_update=True):
        frappe.throw(_("This accounting source has a submitted reversal."))
    legs = snapshot.gl_legs(doctype, name, review.company, {row.account})
    if any(leg["account_currency"] != review.currency for leg in legs):
        frappe.throw(_("Use the native workflow for foreign-currency settlement."))
    capacity = arithmetic.amount(sum((Decimal(leg["signed_amount"]) for leg in legs), Decimal(0)), review.currency_precision)
    if not capacity:
        frappe.throw(_("This source has no net posted effect on the reviewed account."))
    return doctype, name, capacity, legs


def _claim(review, row, financial_doctype, financial_name, capacity, proposed, evidence):
    key = hashlib.sha256(f"{financial_doctype}|{financial_name}|{row.account}".encode()).hexdigest()
    name = frappe.db.get_value("POS Shift Source Claim", {"claim_key": key}, "name", for_update=True)
    if name:
        claim = frappe.get_doc("POS Shift Source Claim", name, for_update=True)
        if claim.review != review.name or claim.row_key != row.row_key:
            frappe.throw(_("This posted account effect is already attributed to another difference."))
        allocated = Decimal(str(claim.allocated_amount or 0)) if claim.active else Decimal(0)
        if Decimal(str(claim.capacity)) != capacity:
            frappe.throw(_("The source accounting effect changed. Investigate before reallocating it."))
    else:
        claim = frappe.get_doc(dict(doctype="POS Shift Source Claim", claim_key=key, review=review.name,
            row_key=row.row_key, financial_doctype=financial_doctype, financial_name=financial_name,
            account=row.account, capacity=float(capacity), currency=review.currency, evidence_json=snapshot.encode(evidence)))
        allocated = Decimal(0)
    try:
        arithmetic.allocate(capacity, [allocated], proposed, review.currency_precision)
    except ValueError as error:
        frappe.throw(_(str(error)))
    claim.allocated_amount = float(allocated + proposed)
    claim.active = 1
    save(claim, insert=not name)


def _insert_action(review, action, args, key, digest, *, state="Complete", row=None, signed=0, source=None, financial=None, evidence=None):
    operation = frappe.get_doc(dict(doctype="POS Shift Review Action", review=review.name, client_request_id=key,
        request_fingerprint=digest, actor=frappe.session.user, action=action, state=state,
        row_key=row.row_key if row else None, signed_amount=float(signed), currency=review.currency, reason=args["reason"],
        source_doctype=source.doctype if source else None, source_name=source.name if source else None,
        financial_doctype=financial[0] if financial else None, financial_name=financial[1] if financial else None,
        evidence_json=snapshot.encode(evidence or {})))
    save(operation, insert=True)
    return operation


@frappe.whitelist(methods=["POST"])
def act(review_name, action, args, client_request_id, expected_version):
    policy.require_schema()
    args = json.loads(args) if isinstance(args, str) else args
    if not isinstance(args, dict) or not (args.get("reason") or "").strip():
        frappe.throw(_("A review reason is required."))
    key = expenses.request_id(client_request_id)
    digest = expenses.fingerprint(dict(review=review_name, actor=frappe.session.user, action=action, args=args, version=str(expected_version)))
    expenses.lock_actor()
    review = load(review_name, write=True)
    # Actor serialization and the unique request key protect retry identity. Do not
    # hold an action lock before the review: recompute locks them in the other order.
    old = frappe.db.get_value("POS Shift Review Action", {"client_request_id": key}, "name")
    if old:
        operation = frappe.get_doc("POS Shift Review Action", old)
        if operation.actor != frappe.session.user or operation.request_fingerprint != digest or operation.review != review_name:
            frappe.throw(_("This request ID belongs to another review operation."), frappe.PermissionError)
        review = load(review_name, lock=True, write=True)
        operation = frappe.get_doc("POS Shift Review Action", old, for_update=True)
        return result(review, operation)
    # Existing source first, review second: the same order native cancellation hooks
    # use. Newly posted documents are not visible to another transaction until commit.
    source = _source(args.get("source_doctype"), args.get("source_name"), allow_cancelled=action == "Confirm native handoff") if action in {"Link source", "Confirm payment correction", "Confirm native handoff"} else None
    if source and source.docstatus == 1:
        for financial_doctype, financial_name in snapshot.vouchers(source):
            _source(financial_doctype, financial_name)
    frappe.db.savepoint("shift_review_action")
    try:
        if action == "Missing expense":
            _row(review, args.get("row_key"))
            # Expense commands perform current source/category/role/shift validation.
            expense = expenses.record(dict(company=review.company, pos_profile=review.pos_profile,
                pos_opening_shift=review.pos_opening_shift, entry_context="POS Correction", correction_reason=args["reason"],
                expense_category=args.get("category"), amount=args.get("amount"), paid_from=_row(review, args.get("row_key")).account,
                description=args.get("description"), beneficiary_name=args.get("beneficiary_name"), receipt_attachment=args.get("receipt_attachment"),
                posting_date=args.get("posting_date"), client_request_id="review-expense:" + hashlib.sha256(key.encode()).hexdigest()))
            source = _source("Quick Expense", expense["name"])
        review = load(review_name, lock=True, write=True)
        if review.status == "Voided" or str(review.version) != str(expected_version):
            frappe.throw(_("The review changed. Refresh it before applying a correction."), frappe.TimestampMismatchError)
        review.reviewer = frappe.session.user
        if action in REQUEST_TYPES:
            operation = _insert_action(review, action, args, key, digest, state="Requested", evidence={"requested_source": args.get("source_name")})
        elif action in {"Withdraw request", "Confirm native handoff"}:
            requested = frappe.get_doc("POS Shift Review Action", args.get("request_action_name"), for_update=True)
            if requested.review != review.name or requested.action not in REQUEST_TYPES or requested.state != "Requested":
                frappe.throw(_("Select an open non-financial investigation request in this review."))
            if action == "Withdraw request":
                requested.state = "Withdrawn"
                operation = _insert_action(review, action, args, key, digest, state="Recorded", evidence={"request_action": requested.name})
            else:
                if source.company != review.company:
                    frappe.throw(_("The source must belong to the review company."))
                stored_shift = source.get("pos_opening_shift") or source.get("posa_pos_opening_shift")
                if stored_shift and stored_shift != review.pos_opening_shift:
                    frappe.throw(_("This source belongs to another shift."), frappe.PermissionError)
                if not stored_shift and not args.get("attribute_to_shift"):
                    frappe.throw(_("Explicit manager attribution to the original shift is required for an unassigned source."))
                financial = snapshot.vouchers(source)
                if len(financial) != 1:
                    frappe.throw(_("A single native accounting replacement is required."))
                financial_doctype, financial_name = financial[0]
                baseline = {(v["doctype"], v["name"]) for item in snapshot.read(review)["sources"] for v in item["vouchers"]}
                new_effect = source.docstatus == 1 and financial[0] not in baseline
                if new_effect:
                    claim_key = hashlib.sha256(f"handoff|{financial_doctype}|{financial_name}".encode()).hexdigest()
                    if frappe.db.get_value("POS Shift Source Claim", {"claim_key": claim_key}, "name", for_update=True):
                        frappe.throw(_("This posted account effect is already attributed to another difference."))
                    claim = frappe.get_doc(dict(doctype="POS Shift Source Claim", claim_key=claim_key, review=review.name,
                        row_key="native-handoff", financial_doctype=financial_doctype, financial_name=financial_name,
                        capacity=0, allocated_amount=0, currency=review.currency, active=1, evidence_json="{}"))
                    save(claim, insert=True)
                operation = _insert_action(review, "Native handoff", args, key, digest,
                    state="Complete" if new_effect else "Recorded", source=source,
                    financial=financial[0], evidence={"request_action": requested.name, "native_docstatus": source.docstatus})
                requested.state = "Handled"
            save(requested)
        elif action in {"Link source", "Missing expense", "Cash adjustment"}:
            row = _row(review, args.get("row_key"))
            signed = _amount(review, row, args.get("signed_amount"))
            if action == "Cash adjustment":
                policy.require_approver()
                if any(other.account == row.account and other.row_key != row.row_key and other.remaining_amount for other in review.accounts):
                    frappe.throw(_("Opposite differences share this account. Investigate payment attribution before any cash adjustment."))
                from erpnext.accounts.expense_services.shift_adjustments import post_cash_adjustment
                setup = frappe.db.get_value("POS Shift Review Settings", {"company": review.company}, "name")
                if not setup:
                    frappe.throw(_("Configure company shift review accounts before posting an adjustment."))
                settings = frappe.get_doc("POS Shift Review Settings", setup)
                counterpart = settings.get("shortage_account" if signed < 0 else "surplus_account")
                if "expected_adjustment_account" in args and args["expected_adjustment_account"] != counterpart:
                    frappe.throw(_("Adjustment accounts changed. Refresh and confirm the proposed accounts again."), frappe.TimestampMismatchError)
                source = post_cash_adjustment(review.company, row.account, signed, args.get("posting_date"), settings.as_dict(), review.name, args["reason"])
            if action == "Missing expense" and signed != -Decimal(str(source.amount)):
                frappe.throw(_("A missing expense must explain exactly its own posted amount."))
            financial_doctype, financial_name, capacity, legs = _effect(review, row, source, explicit_attribution=bool(args.get("attribute_to_shift")) or action == "Cash adjustment")
            _claim(review, row, financial_doctype, financial_name, capacity, signed, legs)
            operation = _insert_action(review, action, args, key, digest, row=row, signed=signed, source=source,
                                       financial=(financial_doctype, financial_name), evidence={"legs": legs, "attributed_shift": review.pos_opening_shift})
        elif action == "Confirm payment correction":
            operation = _payment_correction(review, source, args, key, digest)
        elif action == "Count correction":
            row = _row(review, args.get("row_key"))
            original = snapshot.read(review)
            mode = args.get("mode_of_payment")
            methods = json.loads(row.methods_json)
            detail = next((detail for detail in original["methods"] if detail["mode_of_payment"] == mode and mode in methods), None)
            if not detail:
                frappe.throw(_("Select an original payment method in this account difference."))
            previous = Decimal(detail["actual"])
            for item in actions(review):
                if item.action == "Count correction" and item.state == "Complete":
                    evidence = json.loads(item.evidence_json)
                    if evidence["mode_of_payment"] == mode:
                        previous = Decimal(evidence["new_actual"])
            corrected = arithmetic.amount(args.get("new_actual"), review.currency_precision)
            # A grouped account may contain several methods with the same sign.
            # Its remaining amount must not permit repeated edits to overshoot one
            # method's original expected count.
            lower, upper = sorted((Decimal(detail["actual"]), Decimal(detail["expected_amount"])))
            if not lower <= corrected <= upper:
                frappe.throw(_("A count correction cannot move this method beyond its original difference."))
            signed = _amount(review, row, previous - corrected)
            if Decimal(detail["difference"]) * signed <= 0 or abs(signed) > abs(Decimal(detail["difference"])):
                frappe.throw(_("A count correction cannot move this method beyond its original difference."))
            if row.account_type == "Cash" and corrected < 0:
                frappe.throw(_("A physical cash count cannot be negative."))
            operation = _insert_action(review, action, args, key, digest, row=row, signed=signed,
                evidence=dict(mode_of_payment=mode, previous_actual=str(previous), new_actual=str(corrected)))
        elif action == "Withdraw count correction":
            original = frappe.get_doc("POS Shift Review Action", args.get("action_name"), for_update=True)
            if original.review != review.name or original.action != "Count correction" or original.state != "Complete":
                frappe.throw(_("Select an active count correction in this review."))
            later = [item for item in actions(review) if item.action == "Count correction" and item.state == "Complete" and item.row_key == original.row_key]
            if later[-1].name != original.name:
                frappe.throw(_("Withdraw later count corrections first."))
            original.state = "Withdrawn"
            save(original)
            operation = _insert_action(review, action, args, key, digest, state="Recorded", evidence={"withdrawn_action": original.name})
        else:
            frappe.throw(_("Unsupported review action."))
        recompute(review)
        return result(review, operation)
    except ValueError as error:
        frappe.db.rollback(save_point="shift_review_action")
        frappe.throw(_(str(error)))
    except Exception:
        frappe.db.rollback(save_point="shift_review_action")
        raise


@frappe.whitelist()
def get_outcome(client_request_id):
    policy.require_schema()
    key = expenses.request_id(client_request_id)
    expenses.lock_actor()
    name = frappe.db.get_value("POS Shift Review Action", {"client_request_id": key}, "name")
    if not name:
        return dict(status="not_found", client_request_id=key)
    operation = frappe.get_doc("POS Shift Review Action", name)
    if operation.actor != frappe.session.user:
        frappe.throw(_("This review request belongs to another user."), frappe.PermissionError)
    review = load(operation.review, lock=True)
    operation = frappe.get_doc("POS Shift Review Action", name, for_update=True)
    return result(review, operation)


def _payment_correction(review, source, args, key, digest):
    original = snapshot.read(review)
    if source.doctype not in {"Sales Invoice", "POS Invoice"} or not source.get("amended_from"):
        frappe.throw(_("Select the submitted native amendment of an original shift invoice."))
    old = next((row for row in original["sources"] if row["doctype"] == source.doctype and row["name"] == source.amended_from), None)
    if not old or not old.get("invoice") or source.company != review.company or source.get("posa_pos_opening_shift") != review.pos_opening_shift:
        frappe.throw(_("The amendment must replace an invoice in this original shift snapshot."))
    original_doc = frappe.get_doc(source.doctype, source.amended_from)
    original_doc.check_permission("read")
    if original_doc.docstatus != 2:
        frappe.throw(_("The original invoice must be cancelled through its native workflow."))
    before = old["invoice"]
    for field in ("base_grand_total", "base_net_total"):
        if Decimal(str(before.get(field) or 0)) != Decimal(str(source.get(field) or 0)):
            frappe.throw(_("Changes to sales totals need the native accountant workflow, not a payment-attribution correction."))
    if before.get("change_amount") or source.get("change_amount"):
        frappe.throw(_("Payment corrections involving change or overpayments require native accountant investigation."))
    before_modes = arithmetic.payment_totals(before, original["cash_mode"], review.currency_precision)
    after_modes = arithmetic.payment_totals(source.as_dict(), original["cash_mode"], review.currency_precision)
    allocations, account_deltas = [], {}
    for mode in sorted(set(before_modes) | set(after_modes)):
        delta = after_modes[mode] - before_modes[mode]
        if not delta:
            continue
        row = next((row for row in review.accounts if mode in json.loads(row.methods_json)), None)
        if not row:
            frappe.throw(_("The amendment changes a method without an original unresolved difference."))
        _amount(review, row, delta)
        mapped = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": review.company}, "default_account")
        if mapped != row.account or row.account_currency != review.currency:
            frappe.throw(_("Payment account mapping or currency changed. Use the native accountant workflow."))
        allocations.append(dict(row_key=row.row_key, mode_of_payment=mode, signed_amount=str(delta)))
        account_deltas[row.account] = account_deltas.get(row.account, Decimal(0)) + delta
    if not allocations:
        frappe.throw(_("The amendment contains no payment-attribution correction."))
    for row in review.accounts:
        proposed = sum((Decimal(entry["signed_amount"]) for entry in allocations if entry["row_key"] == row.row_key), Decimal(0))
        if proposed:
            _amount(review, row, proposed)
    financial = snapshot.vouchers(source)
    if len(financial) != 1:
        frappe.throw(_("A single native accounting replacement is required."))
    doctype, name = financial[0]
    _source(doctype, name)
    for account, delta in account_deltas.items():
        old_gl = sum((Decimal(leg["signed_amount"]) for voucher in old["vouchers"] for leg in voucher["legs"] if leg["account"] == account), Decimal(0))
        new_legs = snapshot.gl_legs(doctype, name, review.company, {account})
        new_gl = sum((Decimal(leg["signed_amount"]) for leg in new_legs), Decimal(0))
        if arithmetic.amount(new_gl - old_gl, review.currency_precision, rounded=True) != delta:
            frappe.throw(_("The native GL change does not match the payment-attribution change."))
        claim_key = hashlib.sha256(f"{doctype}|{name}|{account}".encode()).hexdigest()
        if frappe.db.get_value("POS Shift Source Claim", {"claim_key": claim_key}, "name", for_update=True):
            frappe.throw(_("This replacement accounting effect is already allocated."))
        claim = frappe.get_doc(dict(doctype="POS Shift Source Claim", claim_key=claim_key, review=review.name,
            row_key="payment-correction", financial_doctype=doctype, financial_name=name, account=account,
            capacity=float(delta), allocated_amount=0, currency=review.currency, active=1, evidence_json=snapshot.encode(new_legs)))
        save(claim, insert=True)
    return _insert_action(review, "Payment correction", args, key, digest, source=source,
                          financial=(doctype, name), evidence=dict(original_invoice=source.amended_from, allocations=allocations))
