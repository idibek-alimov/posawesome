"""Shared shift summaries. All amounts here are in company currency."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from .utils import get_base_value


def salesperson_totals(invoices):
    totals = {}
    for invoice in invoices:
        amount = get_base_value(invoice, "grand_total", "base_grand_total", invoice.get("conversion_rate"))
        team = [row for row in (invoice.get("sales_team") or []) if row.get("sales_person")]
        allocations = defaultdict(float)
        for row in team:
            allocations[row["sales_person"]] += max(0, flt(row.get("allocated_percentage"))) / 100
        if not allocations and invoice.get("custom_sales_person"):
            allocations[invoice["custom_sales_person"]] = 1
        # Keep incomplete allocations visible and never count an invoice twice.
        allocated = sum(allocations.values())
        if allocated > 1:
            allocations = {person: share / allocated for person, share in allocations.items()}
        elif allocated < 1:
            allocations[""] += 1 - allocated
        for person, share in allocations.items():
            if not share:
                continue
            row = totals.setdefault(person, {"sales_person": person, "sales": 0, "returns": 0, "total": 0})
            value = amount * share
            row["sales" if value >= 0 else "returns"] += abs(value)
            row["total"] += value
    return sorted(totals.values(), key=lambda row: (-row["total"], row["sales_person"]))


def shift_outflows(opening, cash_mode, mode_accounts, query=None):
    """Attribute withdrawals by the account actually credited, not just its label."""
    query = query or frappe.get_all
    details = []
    account_modes = defaultdict(list)
    for mode, account in mode_accounts.items():
        if account:
            account_modes[account].append(mode)

    def add(row, doctype, account, preferred, label):
        candidates = account_modes.get(account, []) if account else []
        mode = preferred if preferred in candidates else (candidates[0] if candidates else None)
        if not account:
            mode = preferred or cash_mode  # Legacy records without an account.
        amount = abs(flt(row.get("amount")))
        if amount:
            details.append({
                "doctype": doctype,
                "name": row.get("name"),
                "mode_of_payment": mode,
                "account": account,
                "amount": amount,
                "label": label,
            })

    filters = {"pos_opening_shift": opening.name, "docstatus": 1}
    for row in query(
        "POS Cash Movement", filters=filters,
        fields=["name", "movement_type", "amount", "source_account"],
    ):
        add(
            row, "POS Cash Movement", row.get("source_account"), cash_mode,
            "Transfer out" if row.get("movement_type") == "Deposit" else "Expense",
        )
    for row in query(
        "Quick Expense", filters=filters,
        fields=["name", "expense_category", "amount", "paid_from", "mode_of_payment"],
    ):
        add(
            row, "Quick Expense", row.get("paid_from"), row.get("mode_of_payment") or cash_mode,
            row.get("expense_category") or "Expense",
        )
    return details


def reconciliation_rows(opening, payments, outflows, mode_accounts):
    rows = {}

    def row_for(mode):
        return rows.setdefault(mode, {
            "mode_of_payment": mode,
            "account": mode_accounts.get(mode),
            "opening_amount": 0,
            "net_received": 0,
            "taken_out": 0,
            "expected_amount": 0,
        })

    for mode in mode_accounts:
        row_for(mode)
    for detail in getattr(opening, "balance_details", None) or []:
        row_for(detail.get("mode_of_payment"))["opening_amount"] += flt(detail.get("amount"))
    for payment in payments:
        row_for(payment["mode_of_payment"])["net_received"] += flt(payment["company_currency_total"])
    for movement in outflows:
        if movement["mode_of_payment"]:
            row = row_for(movement["mode_of_payment"])
            row["taken_out"] += movement["amount"]
            if movement.get("included_in_receipts"):
                row["net_received"] += movement["amount"]
    for row in rows.values():
        row["expected_amount"] = row["opening_amount"] + row["net_received"] - row["taken_out"]
    return list(rows.values())


def payment_entry_receipt(entry, company_currency):
    """Read the till side of a receipt/refund, which can differ from customer currency."""
    refund = entry.get("payment_type") == "Pay"
    currency = entry.get("paid_from_account_currency" if refund else "paid_to_account_currency")
    field = "paid_amount" if refund or entry.get("received_amount") in (None, "") else "received_amount"
    rate = entry.get("source_exchange_rate" if refund else "target_exchange_rate") or entry.get("exchange_rate") or 1
    sign = -1 if refund else 1
    return {
        "currency": currency or company_currency,
        "amount": sign * abs(flt(entry.get(field))),
        "base_amount": sign * abs(get_base_value(entry, field, "base_" + field, rate)),
        "rate": rate,
    }
