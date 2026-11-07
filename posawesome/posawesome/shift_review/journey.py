"""Read-only links and cashier projections. Never carry a difference into a new float."""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint
from erpnext.accounts.expense_services import policy as expense_policy
from posawesome.posawesome.api.expense_context import authorized_profile
from . import policy, service, snapshot

UNRESOLVED = ("Pending review", "In review", "Partially resolved")
PARENT_FIELDS = ["name", "closing_shift", "pos_opening_shift", "pos_profile", "company",
                 "cashier", "creation", "status", "currency", "currency_precision", "cashier_reason"]


def available():
    return (frappe.db.table_exists("POS Shift Review") and frappe.db.table_exists("POS Shift Review Action")
            and frappe.db.has_column("POS Closing Shift", "shift_review")
            and frappe.has_permission("POS Shift Review", "read"))


def review_url(name):
    from urllib.parse import quote
    return "/app/shift-review/" + quote(name, safe="") if policy.is_manager() else None


def projection(review, accounts):
    # No original source/GL snapshots, reviewer notes or accounting capabilities in POS.
    return dict(review=review.name, closing_shift=review.closing_shift,
        pos_opening_shift=review.pos_opening_shift, creation=str(review.creation), status=review.status,
        cashier_reason=review.cashier_reason, currency=review.currency,
        currency_precision=review.currency_precision, url=review_url(review.name),
        accounts=[dict(methods=json.loads(row.methods_json or "[]"),
            **{field: row.get(field) for field in ("expected_amount", "actual_amount", "original_difference", "remaining_amount")})
            for row in accounts])


@frappe.whitelist()
def get_register_context(pos_profile, limit_start=0, page_length=10):
    if not available():
        return dict(available=False)
    if not policy.is_manager() and not expense_policy.CASHIER_ROLES.intersection(frappe.get_roles()):
        frappe.throw(_("You do not have access to this shift review."), frappe.PermissionError)
    company = frappe.get_cached_value("POS Profile", pos_profile, "company")
    expense_policy.check_company(company)
    authorized_profile(company, pos_profile, frappe.session.user)
    # Even a manager at a cashier terminal sees only their own closing history here.
    filters = dict(company=company, pos_profile=pos_profile, cashier=frappe.session.user)
    parents = frappe.get_list("POS Shift Review", filters=dict(filters, status=["in", UNRESOLVED]),
        fields=PARENT_FIELDS, order_by="creation asc, name asc", limit_page_length=0)
    latest = frappe.get_list("POS Shift Review", filters=dict(filters, status=["!=", "Voided"]),
        fields=PARENT_FIELDS, order_by="creation desc, name desc", limit_page_length=1)
    selected = {row.name: row for row in parents + latest}
    children = defaultdict(list)
    names = list(selected)
    for offset in range(0, len(names), 200):
        for row in frappe.get_all("POS Shift Review Account",
                filters={"parent": ["in", names[offset:offset + 200]], "parenttype": "POS Shift Review"},
                fields=["parent", "methods_json", "expected_amount", "actual_amount", "original_difference", "remaining_amount"],
                order_by="idx asc"):
            children[row.parent].append(row)
    start, length = max(0, cint(limit_start)), min(50, max(1, cint(page_length)))
    return dict(available=True, total=len(parents), has_more=start + length < len(parents),
        reviews=[projection(row, children[row.name]) for row in parents[start:start + length]],
        latest=projection(latest[0], children[latest[0].name]) if latest else None)


@frappe.whitelist()
def get_closing_status(closing_shift):
    policy.require_schema()
    name = frappe.db.get_value("POS Shift Review", {"closing_shift": closing_shift}, "name")
    if not name:
        return dict(available=False)
    review = service.load(name)
    response = projection(review, review.accounts)
    original = snapshot.read(review)
    cash = next((row for row in original["methods"] if row["mode_of_payment"] == original.get("cash_mode")), None)
    response["counted_cash"] = cash["actual"] if cash else None
    operations = frappe.get_all("POS Shift Review Action", filters={"review": name, "action": "Safe transfer"},
        fields=["state"], limit_page_length=1)
    response["transfer_state"] = operations[0].state if operations else "Not recorded"
    from erpnext.accounts.page.money_hub.money_hub import ALLOWED_ROLES
    from .transfers import following_shift
    cash_group = next((row for row in original["groups"] if cash and row["account"] == cash.get("account")), {})
    corrected = frappe.db.exists("POS Shift Review Action", {"review": name, "action": "Count correction", "state": "Complete"})
    response["can_transfer"] = (bool(ALLOWED_ROLES.intersection(frappe.get_roles()))
        and all(frappe.has_permission("Payment Entry", action) for action in ("create", "submit"))
        and review.status != "Voided" and cash is not None and cash_group.get("account_currency") == review.currency
        and float(cash["actual"]) > 0 and not corrected and not following_shift(review, original))
    response["available"] = True
    return response


def expense_links(doc):
    """Optional ERPNext detail hook; the caller already authorized the expense itself."""
    if not available():
        return {}
    shift = doc.get("pos_opening_shift")
    review_filters = {"pos_opening_shift": shift} if shift else None
    if not shift and policy.is_manager():
        # A linked omitted legacy source may deliberately retain its original empty shift.
        actions = frappe.get_list("POS Shift Review Action",
            filters={"source_doctype": doc.doctype, "source_name": doc.name}, fields=["review"], limit_page_length=0)
        review_filters = {"name": ["in", sorted({row.review for row in actions})]} if actions else None
    reviews = frappe.get_list("POS Shift Review", filters=review_filters,
        fields=["name", "closing_shift", "status"], limit_page_length=0) if review_filters else []
    opening = shift if shift and frappe.has_permission("POS Opening Shift", "read", doc=shift) else None
    return dict(opening_shift=opening, reviews=[dict(name=row.name, status=row.status, url=review_url(row.name),
        closing_shift=row.closing_shift if frappe.has_permission("POS Closing Shift", "read", doc=row.closing_shift) else None)
        for row in reviews])
