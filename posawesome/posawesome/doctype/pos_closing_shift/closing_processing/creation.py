import math

import frappe
from frappe import _
from frappe.utils import flt, json
from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.utils import get_base_value
from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.data import (
    get_pos_invoices,
    get_payments_entries,
    get_authorized_opening_shift,
)
from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.invoices import (
    submit_printed_invoices,
)

from .overview import build_closing_overview


def build_pos_payment_reference(payment_entry):
    party_type = payment_entry.get("party_type")
    party = payment_entry.get("party")
    row = frappe._dict(
        {
            "payment_entry": payment_entry.name,
            "mode_of_payment": payment_entry.mode_of_payment,
            "paid_amount": payment_entry.paid_amount,
            "posting_date": payment_entry.posting_date,
            "party_type": party_type,
            "party": party,
        }
    )

    if party_type == "Customer":
        row.customer = party

    return row


def _get_payment_entry_party(payment_entry):
    if not payment_entry:
        return {}

    return (
        frappe.db.get_value(
            "Payment Entry",
            payment_entry,
            ["party_type", "party"],
            as_dict=True,
        )
        or {}
    )


def _is_legacy_customer_required():
    customer_field = frappe.get_meta("POS Payment Entry Reference").get_field("customer")
    return bool(customer_field and customer_field.reqd)


def normalize_pos_payment_references(closing_shift_doc):
    has_non_customer_payment = False

    for row in closing_shift_doc.get("pos_payments", []):
        party_type = row.get("party_type")
        party = row.get("party")

        if row.get("payment_entry") and (not party_type or not party):
            payment_party = _get_payment_entry_party(row.get("payment_entry"))
            party_type = party_type or payment_party.get("party_type")
            party = party or payment_party.get("party")
            row.party_type = party_type
            row.party = party

        if party_type == "Customer":
            if party and not row.get("customer"):
                row.customer = party
            continue

        has_non_customer_payment = True
        if row.get("customer"):
            row.customer = None

    if has_non_customer_payment and _is_legacy_customer_required():
        closing_shift_doc.flags.ignore_mandatory = True


@frappe.whitelist()
def make_closing_shift_from_opening(opening_shift):
    opening_shift = json.loads(opening_shift) if isinstance(opening_shift, str) else opening_shift
    opening_shift = get_authorized_opening_shift(opening_shift.get("name")).as_dict()
    use_pos_invoice = frappe.db.get_value(
        "POS Profile",
        opening_shift.get("pos_profile"),
        "create_pos_invoice_instead_of_sales_invoice",
    )
    doctype = "POS Invoice" if use_pos_invoice else "Sales Invoice"
    skipped_printed_invoices = submit_printed_invoices(opening_shift.get("name"), doctype)
    closing_shift = frappe.new_doc("POS Closing Shift")
    closing_shift.pos_opening_shift = opening_shift.get("name")
    closing_shift.period_start_date = opening_shift.get("period_start_date")
    closing_shift.period_end_date = frappe.utils.get_datetime()
    closing_shift.pos_profile = opening_shift.get("pos_profile")
    closing_shift.user = opening_shift.get("user")
    closing_shift.company = opening_shift.get("company")
    closing_shift.grand_total = 0
    closing_shift.net_total = 0
    closing_shift.total_quantity = 0

    company_currency = frappe.get_cached_value("Company", closing_shift.company, "default_currency")
    invoices = get_pos_invoices(opening_shift.get("name"), doctype, submit_printed=0)

    pos_transactions = []
    taxes = []
    invoice_field = "pos_invoice" if doctype == "POS Invoice" else "sales_invoice"

    for d in invoices:
        conversion_rate = d.get("conversion_rate")
        pos_transactions.append(
            frappe._dict(
                {
                    invoice_field: d.name,
                    "posting_date": d.posting_date,
                    "grand_total": get_base_value(d, "grand_total", "base_grand_total", conversion_rate),
                    "transaction_currency": d.get("currency") or company_currency,
                    "transaction_amount": flt(d.get("grand_total")),
                    "customer": d.customer,
                }
            )
        )
        base_grand_total = get_base_value(d, "grand_total", "base_grand_total", conversion_rate)
        base_net_total = get_base_value(d, "net_total", "base_net_total", conversion_rate)
        closing_shift.grand_total += base_grand_total
        closing_shift.net_total += base_net_total
        closing_shift.total_quantity += flt(d.total_qty)

        for t in d.taxes:
            existing_tax = [tx for tx in taxes if tx.account_head == t.account_head and tx.rate == t.rate]
            if existing_tax:
                existing_tax[0].amount += get_base_value(
                    t, "tax_amount", "base_tax_amount", d.get("conversion_rate")
                )
            else:
                taxes.append(
                    frappe._dict(
                        {
                            "account_head": t.account_head,
                            "rate": t.rate,
                            "amount": get_base_value(
                                t, "tax_amount", "base_tax_amount", d.get("conversion_rate")
                            ),
                        }
                    )
                )

    pos_payments = get_payments_entries(opening_shift.get("name"))
    pos_payments_table = [build_pos_payment_reference(py) for py in pos_payments]
    snapshot = build_closing_overview(frappe._dict(opening_shift), invoices, pos_payments)
    payments = [
        frappe._dict({
            "mode_of_payment": row["mode_of_payment"],
            "opening_amount": row["opening_amount"],
            "expected_amount": row["expected_amount"],
        })
        for row in snapshot["reconciliation"]
    ]

    closing_shift.set("pos_transactions", pos_transactions)
    closing_shift.set("payment_reconciliation", payments)
    closing_shift.set("taxes", taxes)
    closing_shift.set("pos_payments", pos_payments_table)

    return {
        "closing_shift": closing_shift,
        "skipped_printed_invoices": skipped_printed_invoices,
        "overview": snapshot,
    }


@frappe.whitelist()
def submit_closing_shift(closing_shift):
    closing_shift = json.loads(closing_shift)
    if closing_shift.get("doctype") != "POS Closing Shift":
        frappe.throw(_("Closing shift does not match the opening shift."))
    closing_shift_doc = frappe.get_doc(closing_shift)
    opening = get_authorized_opening_shift(closing_shift_doc.pos_opening_shift)
    if (
        closing_shift_doc.company != opening.company
        or closing_shift_doc.pos_profile != opening.pos_profile
        or closing_shift_doc.user != opening.user
    ):
        frappe.throw(_("Closing shift does not match the opening shift."))
    use_pos_invoice = frappe.db.get_value(
        "POS Profile", opening.pos_profile, "create_pos_invoice_instead_of_sales_invoice"
    )
    doctype = "POS Invoice" if use_pos_invoice else "Sales Invoice"
    invoices = get_pos_invoices(opening.name, doctype, submit_printed=0)
    entries = get_payments_entries(opening.name)
    invoice_names = {
        row.get("sales_invoice") or row.get("pos_invoice")
        for row in closing_shift_doc.get("pos_transactions", [])
    }
    payment_names = {row.get("payment_entry") for row in closing_shift_doc.get("pos_payments", [])}
    if invoice_names != {row["name"] for row in invoices} or payment_names != {row["name"] for row in entries}:
        frappe.throw(_("Shift totals changed. Reload the closing summary before closing."))
    current = build_closing_overview(opening, invoices, entries)["reconciliation"]
    expected = {row["mode_of_payment"]: row for row in current}
    submitted = closing_shift_doc.get("payment_reconciliation", [])
    if len(submitted) != len(expected) or {row.mode_of_payment for row in submitted} != set(expected):
        frappe.throw(_("Shift totals changed. Reload the closing summary before closing."))
    precision = int(frappe.get_cached_value("System Settings", None, "currency_precision") or 3)
    for row in submitted:
        actual = row.get("closing_amount")
        try:
            valid = actual not in (None, "") and math.isfinite(float(actual))
        except (ValueError, TypeError):
            valid = False
        if not valid:
            frappe.throw(_("Enter an actual amount for every payment method."))
        fresh = expected[row.mode_of_payment]
        if flt(row.expected_amount, precision) != flt(fresh["expected_amount"], precision):
            frappe.throw(_("Shift totals changed. Reload the closing summary before closing."))
        row.expected_amount = fresh["expected_amount"]
        row.opening_amount = fresh["opening_amount"]
    closing_shift_doc.grand_total = sum(get_base_value(row, "grand_total", "base_grand_total") for row in invoices)
    closing_shift_doc.net_total = sum(get_base_value(row, "net_total", "base_net_total") for row in invoices)
    closing_shift_doc.total_quantity = sum(flt(row.get("total_qty")) for row in invoices)
    closing_shift_doc.period_start_date = opening.period_start_date
    closing_shift_doc.period_end_date = frappe.utils.get_datetime()
    closing_shift_doc.flags.ignore_permissions = True
    normalize_pos_payment_references(closing_shift_doc)
    closing_shift_doc.save()
    closing_shift_doc.submit()
    return closing_shift_doc.name
