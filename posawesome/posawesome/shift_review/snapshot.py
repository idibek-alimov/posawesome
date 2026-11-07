"""Immutable evidence at close; later read endpoints never reconstruct the original."""

import json
from decimal import Decimal

import frappe
from frappe import _
from erpnext.accounts.expense_services.commands import fingerprint
from erpnext.accounts.expense_services.policy import currency_precision
from . import arithmetic

INVOICE_FIELDS = ("doctype", "name", "posting_date", "currency", "conversion_rate", "grand_total", "base_grand_total",
                  "net_total", "base_net_total", "change_amount", "base_change_amount", "posa_pos_opening_shift")
SOURCE_FIELDS = ("pos_opening_shift", "posa_pos_opening_shift", "pos_profile", "currency", "conversion_rate",
                 "paid_from", "paid_to", "paid_amount", "received_amount", "base_paid_amount", "base_received_amount",
                 "paid_from_account_currency", "paid_to_account_currency", "source_exchange_rate", "target_exchange_rate",
                 "amount", "source_account", "target_account", "movement_type", "entry_context", "reference_no")


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def gl_legs(doctype, name, company, accounts):
    if not accounts:
        return []
    rows = frappe.db.get_values("GL Entry", filters=dict(voucher_type=doctype, voucher_no=name, company=company,
                        account=["in", sorted(accounts)], is_cancelled=0),
                        fieldname=["name", "account", "account_currency", "debit", "credit", "posting_date", "voucher_detail_no"], as_dict=True, for_update=True, order_by="name")
    return [dict(row, signed_amount=str(Decimal(str(row.debit or 0)) - Decimal(str(row.credit or 0)))) for row in rows]


def vouchers(doc):
    if doc.doctype in {"Quick Expense", "POS Cash Movement"}:
        return [(doctype, doc.get(field)) for doctype, field in (("Journal Entry", "journal_entry"),
                ("Payment Entry", "payment_entry")) if doc.get(field)]
    if doc.doctype == "POS Invoice" and doc.get("consolidated_invoice"):
        return [("Sales Invoice", doc.consolidated_invoice)]
    return [(doc.doctype, doc.name)]


def build(closing, opening, overview, invoices, entries):
    precision = currency_precision(opening.company)
    currency = frappe.get_cached_value("Company", opening.company, "default_currency")
    counts = {row.mode_of_payment: row.closing_amount for row in closing.payment_reconciliation}
    try:
        methods, groups = arithmetic.group_counts(overview["reconciliation"], counts, precision)
    except (ValueError, KeyError) as error:
        frappe.throw(_("Enter actual counts using the company currency precision: {0}").format(str(error)))
    accounts = {}
    for method in methods:
        name = method.get("account")
        if name and name not in accounts:
            doc = frappe.get_cached_doc("Account", name)
            if doc.company != opening.company or doc.is_group:
                frappe.throw(_("The closing payment account does not belong to the stored shift company."))
            accounts[name] = dict(account_type=doc.account_type, account_currency=doc.account_currency or currency)
    for group in groups:
        group.update(accounts.get(group["account"], dict(account_type="Unmapped", account_currency=None)))
        group["currency"] = currency
    sources = []
    source_ids = {(doc.get("doctype") or ("POS Invoice" if doc.get("is_pos") and doc.get("consolidated_invoice") else "Sales Invoice"), doc["name"]) for doc in invoices}
    source_ids.update(("Payment Entry", row["name"]) for row in entries)
    source_ids.update((row["doctype"], row["name"]) for row in overview.get("movements", []))
    for doctype, name in sorted(source_ids):
        doc = frappe.get_doc(doctype, name)
        if doc.company != opening.company or doc.docstatus != 1:
            frappe.throw(_("The source must belong to the review company."))
        evidence = dict(doctype=doctype, name=name, creation=str(doc.creation), modified=str(doc.modified),
                        posting_date=str(doc.get("posting_date")), vouchers=[],
                        document={field: doc.get(field) for field in SOURCE_FIELDS if doc.get(field) is not None})
        if doctype in {"Sales Invoice", "POS Invoice"}:
            original = next((row for row in invoices if row["name"] == name and (row.get("doctype") or doctype) == doctype), None) or doc.as_dict()
            evidence["invoice"] = {field: original.get(field) for field in INVOICE_FIELDS}
            evidence["invoice"]["payments"] = [{field: row.get(field) for field in ("mode_of_payment", "amount", "base_amount")} for row in original.get("payments", [])]
        for financial_doctype, financial_name in vouchers(doc):
            evidence["vouchers"].append(dict(doctype=financial_doctype, name=financial_name,
                legs=gl_legs(financial_doctype, financial_name, opening.company, accounts)))
        sources.append(evidence)
    return dict(version=1, company=opening.company, currency=currency, precision=precision,
                opening_shift=opening.name, closing_shift=closing.name, period_start=str(opening.period_start_date),
                period_end=str(closing.period_end_date), cash_mode=overview.get("cash_expected", {}).get("mode_of_payment"),
                methods=methods, groups=groups, sources=sources)


def read(review):
    try:
        result = json.loads(review.get("snapshot_json"))
        valid = isinstance(result, dict) and fingerprint(result) == review.get("snapshot_hash")
    except (ValueError, TypeError):
        valid = False
    if not valid:
        frappe.throw(_("Shift review evidence failed its integrity check."))
    return result
