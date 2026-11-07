"""Read-only manager projections. Commands remain owned by service.act."""

import json
from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, getdate
from erpnext.accounts.expense_services import policy as expense_policy
from erpnext.accounts.page.expense_desk.expense_desk import get_expense_options
from . import policy, service, snapshot

UNRESOLVED = ("Pending review", "In review", "Partially resolved")
STATUSES = (*UNRESOLVED, "Resolved", "Voided")
ACCOUNT_FIELDS = ("row_key", "account", "account_currency", "account_type", "expected_amount", "actual_amount",
                  "original_difference", "allocated_amount", "remaining_amount")


def require_manager():
    policy.require_schema()
    if not policy.is_manager():
        frappe.throw(_("An authorized manager is required to open Shift Review."), frappe.PermissionError)
    if not frappe.has_permission("POS Shift Review", "read"):
        frappe.throw(_("Shift review read permission is required."), frappe.PermissionError)


@frappe.whitelist()
def navigation():
    # Discovery is safe before migration and when ERPNext is installed without POS.
    return dict(available=policy.is_manager() and frappe.db.table_exists("POS Shift Review")
                and frappe.db.table_exists("POS Shift Review Action")
                and frappe.db.has_column("POS Closing Shift", "shift_review")
                and frappe.has_permission("POS Shift Review", "read"))


@frappe.whitelist()
def get_list(company=None, pos_profile=None, cashier=None, status="unresolved", search=None,
             from_date=None, to_date=None, limit_start=0, page_length=40):
    require_manager()
    filters = {}
    for field, value in (("company", company), ("pos_profile", pos_profile), ("cashier", cashier)):
        if value:
            filters[field] = value
    if status == "unresolved":
        filters["status"] = ["in", UNRESOLVED]
    elif status != "all":
        if status not in STATUSES:
            frappe.throw(_("Select a valid review status."))
        filters["status"] = status
    # Unresolved statuses and All always include old money, even with dates in a saved URL.
    if status in {"Resolved", "Voided"}:
        if from_date and to_date and getdate(from_date) > getdate(to_date):
            frappe.throw(_("The start date must not be after the end date."))
        if from_date and to_date:
            filters["creation"] = ["between", [str(getdate(from_date)), str(getdate(to_date)) + " 23:59:59.999999"]]
        elif from_date:
            filters["creation"] = [">=", str(getdate(from_date))]
        elif to_date:
            filters["creation"] = ["<=", str(getdate(to_date)) + " 23:59:59.999999"]
    or_filters = None
    if search and search.strip():
        value = "%" + search.strip()[:140] + "%"
        or_filters = [["POS Shift Review", field, "like", value] for field in
                      ("name", "closing_shift", "pos_opening_shift", "pos_profile", "cashier")]
    # get_list compiles native permissions plus the Phase 6 child-account scope hook.
    parents = frappe.get_list("POS Shift Review", filters=filters, or_filters=or_filters,
        fields=["name", "company", "pos_profile", "pos_opening_shift", "closing_shift", "cashier", "creation", "status", "currency", "currency_precision"],
        order_by="creation asc, name asc" if status == "unresolved" else "creation desc, name desc", limit_page_length=0)
    children = defaultdict(list)
    for offset in range(0, len(parents), 200):
        names = [row.name for row in parents[offset:offset + 200]]
        for row in frappe.get_all("POS Shift Review Account", filters={"parent": ["in", names], "parenttype": "POS Shift Review"},
                                  fields=["parent", "idx", "methods_json", *ACCOUNT_FIELDS], order_by="idx asc"):
            children[row.parent].append(row)
    rows, currencies, needing_review = [], {}, set()
    for parent in parents:
        for child in children[parent.name]:
            remaining = Decimal(str(child.remaining_amount or 0))
            if status == "unresolved" and not remaining:
                continue
            rows.append(dict(parent, methods=json.loads(child.methods_json or "[]"), **{field: child.get(field) for field in ACCOUNT_FIELDS}))
            if parent.status in UNRESOLVED and remaining:
                needing_review.add(parent.name)
                totals = currencies.setdefault(parent.currency, dict(shortage=Decimal(0), surplus=Decimal(0)))
                totals["shortage" if remaining < 0 else "surplus"] += abs(remaining)
    start, length = max(0, cint(limit_start)), max(1, min(100, cint(page_length)))
    return dict(rows=rows[start:start + length], total=len(rows), has_more=start + length < len(rows),
                shifts_needing_review=len(needing_review),
                currencies=[dict(currency=currency, **{key: str(value) for key, value in totals.items()}) for currency, totals in sorted(currencies.items())])


def capabilities(review):
    options, expense_error = {}, None
    try:
        with expense_policy.quiet_setup_checks():
            options = get_expense_options(review.company, review.pos_profile, review.pos_opening_shift, "POS Correction")
    except (frappe.PermissionError, frappe.ValidationError) as error:
        expense_error = str(error)
    allowed_sources = {source["account"] for source in options.get("payment_sources", [])}
    can_expense = all(frappe.has_permission("Quick Expense", action) for action in ("create", "submit"))
    can_approve = frappe.session.user == "Administrator" or bool(policy.APPROVERS.intersection(frappe.get_roles()))
    setup, setup_error = None, None
    if can_approve and all(frappe.has_permission("Journal Entry", action) for action in ("create", "submit")):
        name = frappe.db.get_value("POS Shift Review Settings", {"company": review.company}, "name")
        if name:
            setup = frappe.get_doc("POS Shift Review Settings", name)
            try:
                from erpnext.accounts.expense_services.shift_adjustments import validate_setup
                with expense_policy.quiet_setup_checks():
                    validate_setup(setup.as_dict())
            except (frappe.PermissionError, frappe.ValidationError) as error:
                setup, setup_error = None, str(error)
    rows = {}
    for row in review.accounts:
        remaining = Decimal(str(row.remaining_amount or 0))
        supported = bool(row.account and row.account_currency == review.currency and remaining and review.status != "Voided")
        counterpart = setup.get("shortage_account" if remaining < 0 else "surplus_account") if setup else None
        opposite = any(other.row_key != row.row_key and other.account == row.account and other.remaining_amount for other in review.accounts)
        adjustment_reason = None
        if supported and row.account_type == "Cash":
            if not can_approve:
                adjustment_reason = _("Only the owner or Accounts Manager can approve a loss or surplus.")
            elif not all(frappe.has_permission("Journal Entry", action) for action in ("create", "submit")):
                adjustment_reason = _("Native Journal Entry create and submit permissions are required.")
            elif opposite:
                adjustment_reason = _("Opposite differences share this account. Investigate payment attribution before any cash adjustment.")
            elif not counterpart:
                adjustment_reason = _("Configure company shift review accounts before posting an adjustment.")
        rows[row.row_key] = dict(adjustment_reason=adjustment_reason,
link_source=supported, count_correction=bool(remaining and review.status != "Voided"),
            missing_expense=bool(supported and remaining < 0 and can_expense and row.account in allowed_sources and options.get("categories")),
            cash_adjustment=bool(supported and row.account_type == "Cash" and counterpart and not opposite),
            adjustment_account=counterpart if supported and row.account_type == "Cash" and not opposite else None)
    return dict(rows=rows, expense_options=options, expense_setup_error=expense_error, adjustment_setup_error=setup_error,
                can_investigate=review.status != "Voided", source_types=sorted(service.SOURCE_TYPES))


@frappe.whitelist()
def get_detail(review_name):
    require_manager()
    review = service.load(review_name)
    original = snapshot.read(review)
    history = frappe.get_all("POS Shift Review Action", filters={"review": review.name},
        fields=["name", "creation", "actor", "action", "state", "row_key", "signed_amount", "currency", "reason",
                "source_doctype", "source_name", "financial_doctype", "financial_name", "invalidation_reason", "evidence_json"],
        order_by="creation asc, name asc")
    # Do not return raw financial evidence or source fields denied by native permission.
    for item in history:
        evidence = json.loads(item.pop("evidence_json") or "{}")
        item["count"] = {key: evidence.get(key) for key in ("mode_of_payment", "previous_actual", "new_actual")} if item.action == "Count correction" else None
        for prefix in ("source", "financial"):
            dt, name = item.get(prefix + "_doctype"), item.get(prefix + "_name")
            if dt and name:
                try:
                    permitted = frappe.has_permission(dt, "read", doc=name)
                except (frappe.PermissionError, frappe.DoesNotExistError):
                    permitted = False
                if not permitted:
                    item[prefix + "_doctype"] = item[prefix + "_name"] = None
    sources = []
    grouped = defaultdict(list)
    for source in original["sources"]:
        grouped[source["doctype"]].append(source)
    for doctype, items in grouped.items():
        # Native get_list scopes documents without disclosing their contents individually.
        if not frappe.has_permission(doctype, "read"):
            sources.extend(dict(restricted=True) for _ in items)
            continue
        current = {}
        for offset in range(0, len(items), 200):
            current.update({row.name: row for row in frappe.get_list(doctype,
                filters={"name": ["in", [item["name"] for item in items[offset:offset + 200]]]},
                fields=["name", "modified", "docstatus"], limit_page_length=0)})
        for source in items:
            row = current.get(source["name"])
            if not row:
                sources.append(dict(restricted=True))
                continue
            sources.append(dict(doctype=doctype, name=row.name, posting_date=source["posting_date"],
                docstatus=row.docstatus, changed=str(row.modified) != source["modified"],
                amount=source.get("invoice", {}).get("base_grand_total", source.get("document", {}).get("amount")),
                original_amount=source.get("invoice", {}).get("grand_total"),
                original_currency=source.get("invoice", {}).get("currency"),
                document=source.get("document", {})))
    financial_states = {}
    financial_groups = defaultdict(set)
    for source in original["sources"]:
        for voucher in source.get("vouchers", []):
            financial_groups[voucher["doctype"]].add(voucher["name"])
    for doctype, names in financial_groups.items():
        if not frappe.has_permission(doctype, "read"):
            continue
        names = sorted(names)
        for offset in range(0, len(names), 200):
            for row in frappe.get_list(doctype, filters={"name": ["in", names[offset:offset + 200]]}, fields=["name", "docstatus"], limit_page_length=0):
                financial_states[(doctype, row.name)] = dict(doctype=doctype, name=row.name, docstatus=row.docstatus)
            if doctype == "Journal Entry":
                for row in frappe.get_list(doctype, filters={"reversal_of": ["in", names[offset:offset + 200]], "docstatus": 1}, fields=["name", "reversal_of"], limit_page_length=0):
                    if (doctype, row.reversal_of) in financial_states:
                        financial_states[(doctype, row.reversal_of)]["reversed"] = True
    originals = {(item["doctype"], item["name"]): item for item in original["sources"]}
    for source in sources:
        if source.get("restricted"):
            continue
        original_source = originals[(source["doctype"], source["name"])]
        source["financial"] = [financial_states.get((voucher["doctype"], voucher["name"]), dict(restricted=True)) for voucher in original_source.get("vouchers", [])]
    response = service.result(review)
    for target, row in zip(response["accounts"], review.accounts):
        target["methods"] = json.loads(row.methods_json or "[]")
    return dict(**response, company=review.company, pos_profile=review.pos_profile,
        pos_opening_shift=review.pos_opening_shift, closing_shift=review.closing_shift, cashier=review.cashier,
        cashier_reason=review.cashier_reason, reviewer=review.reviewer, period_start=original["period_start"], period_end=original["period_end"],
        currency_precision=review.currency_precision, methods=original["methods"], history=history, sources=sources,
        capabilities=capabilities(review))
