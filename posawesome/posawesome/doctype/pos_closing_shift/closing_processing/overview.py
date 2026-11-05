import frappe
from frappe.utils import flt, json
from collections import defaultdict
from frappe import _
from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.utils import get_base_value
from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.data import (
    get_pos_invoices,
    get_payments_entries,
    get_authorized_opening_shift,
)

from .summary import salesperson_totals, shift_outflows, reconciliation_rows, payment_entry_receipt


@frappe.whitelist()
def get_closing_shift_overview(pos_opening_shift):
    """Return invoice and payment totals for the provided POS Opening Shift."""

    if not pos_opening_shift:
        frappe.throw(_("POS Opening Shift is required to compute the overview."))

    opening_shift_doc = None
    opening_shift_name = None
    payload = pos_opening_shift

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except ValueError:
            opening_shift_name = payload
        else:
            payload = parsed if isinstance(parsed, dict) else payload

    if isinstance(payload, dict):
        opening_shift_name = payload.get("name") or opening_shift_name
    elif getattr(payload, "doctype", None) == "POS Opening Shift":
        opening_shift_doc = payload
        opening_shift_name = payload.name
    elif opening_shift_name is None:
        opening_shift_name = getattr(payload, "name", None)

    if not opening_shift_doc:
        if not opening_shift_name:
            frappe.throw(_("Invalid POS Opening Shift data provided."))
        opening_shift_doc = get_authorized_opening_shift(opening_shift_name)

    if opening_shift_doc.doctype != "POS Opening Shift":
        frappe.throw(_("Unable to resolve POS Opening Shift."))

    return build_closing_overview(opening_shift_doc)


def build_closing_overview(opening_shift_doc, invoices=None, payment_entries=None):
    pos_profile = opening_shift_doc.pos_profile
    company = opening_shift_doc.company
    company_currency = frappe.get_cached_value("Company", company, "default_currency")

    use_pos_invoice = frappe.db.get_value(
        "POS Profile",
        pos_profile,
        "create_pos_invoice_instead_of_sales_invoice",
    )
    doctype = "POS Invoice" if use_pos_invoice else "Sales Invoice"
    if invoices is None:
        invoices = get_pos_invoices(opening_shift_doc.name, doctype, submit_printed=0)

    total_invoices = len(invoices)
    company_currency_total = 0
    multi_currency_totals = {}
    payments_by_mode = {}
    credit_company_currency_total = 0
    credit_invoices_count = 0
    credit_totals_by_currency = {}
    gross_company_currency_total = 0
    sale_invoices_count = 0
    returns_company_currency_total = 0
    returns_count = 0
    returns_totals_by_currency = {}
    change_company_currency_total = 0
    change_totals_by_currency = {}
    overpayment_change_company_currency_total = 0
    overpayment_change_totals_by_currency = {}
    total_change_totals_by_currency = {}
    loyalty_redeemed_company_currency_total = 0
    loyalty_redeemed_points = 0
    loyalty_redeemed_invoice_count = 0
    loyalty_redeemed_totals_by_currency = {}
    customer_credit_redeemed_company_currency_total = 0
    customer_credit_redeemed_invoice_count = 0
    customer_credit_redeemed_totals_by_currency = {}
    cash_movement_count = 0
    cash_movement_company_currency_total = 0
    cash_movement_totals_by_type = {}
    cash_movement_totals_by_currency = {}

    cash_mode_of_payment = frappe.db.get_value("POS Profile", pos_profile, "posa_cash_mode_of_payment")
    if not cash_mode_of_payment:
        cash_mode_of_payment = "Cash"

    def accumulate_payment(container, mode, currency, amount, base_amount=0, conversion_rate=None):
        if not mode:
            return
        currency = currency or company_currency
        key = (mode, currency)
        if key not in container:
            container[key] = {
                "mode_of_payment": mode,
                "currency": currency,
                "total": 0,
                "company_currency_total": 0,
                "exchange_rates": set(),
            }
        container[key]["total"] += flt(amount)
        container[key]["company_currency_total"] += flt(base_amount)

        if currency != company_currency:
            rate = None
            if flt(amount):
                rate = abs(flt(base_amount)) / abs(flt(amount)) if base_amount else None
            if not rate and conversion_rate:
                rate = flt(conversion_rate)
            if rate:
                container[key]["exchange_rates"].add(rate)

    def resolve_payment_currency(payment_row, invoice_currency):
        for fieldname in (
            "currency",
            "account_currency",
            "payment_currency",
        ):
            value = payment_row.get(fieldname)
            if value:
                return value
        return invoice_currency or company_currency

    shift_invoice_names = {invoice.get("name") for invoice in invoices}
    invoice_shift_link_field_cache = {}
    invoice_membership_cache = {}
    overpayment_invoice_names = set()

    def resolve_shift_link_field(doctype_name):
        if doctype_name in invoice_shift_link_field_cache:
            return invoice_shift_link_field_cache[doctype_name]

        link_field = None
        try:
            meta = frappe.get_meta(doctype_name)
        except frappe.DoesNotExistError:
            meta = None

        if meta:
            for df in meta.get("fields", []):
                if df.fieldtype == "Link" and df.options == "POS Opening Shift":
                    link_field = df.fieldname
                    break

        invoice_shift_link_field_cache[doctype_name] = link_field
        return link_field

    def reference_belongs_to_shift(doctype_name, docname):
        key = (doctype_name, docname)
        if key in invoice_membership_cache:
            return invoice_membership_cache[key]

        if doctype_name == doctype and docname in shift_invoice_names:
            invoice_membership_cache[key] = True
            return True

        link_field = resolve_shift_link_field(doctype_name)
        if not link_field:
            invoice_membership_cache[key] = False
            return False

        value = frappe.db.get_value(doctype_name, docname, link_field)
        invoice_membership_cache[key] = bool(value and value == opening_shift_doc.name)
        return invoice_membership_cache[key]

    if payment_entries is None:
        payment_entries = get_payments_entries(opening_shift_doc.name)

    payment_entry_names = [row.get("name") for row in payment_entries if row.get("name")]
    references_by_entry = defaultdict(list)

    if payment_entry_names:
        reference_fields = ["parent", "reference_doctype", "reference_name"]
        reference_rows = frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": ["in", payment_entry_names]},
            fields=reference_fields,
        )

        for reference in reference_rows:
            references_by_entry[reference.get("parent")].append(reference)

    for entry in payment_entries:
        if entry.get("payment_type") != "Pay" or entry.get("mode_of_payment") != cash_mode_of_payment:
            continue

        references = references_by_entry.get(entry.get("name")) or []

        for reference in references:
            reference_doctype = reference.get("reference_doctype")
            reference_name = reference.get("reference_name")
            belongs_to_shift = False

            if reference_doctype and reference_name:
                belongs_to_shift = reference_belongs_to_shift(
                    reference_doctype,
                    reference_name,
                )

            if belongs_to_shift and reference_doctype in {"POS Invoice", "Sales Invoice"}:
                overpayment_invoice_names.add(reference_name)

    for invoice in invoices:
        conversion_rate = invoice.get("conversion_rate")
        base_grand_total = get_base_value(invoice, "grand_total", "base_grand_total", conversion_rate)
        company_currency_total += base_grand_total
        if base_grand_total >= 0:
            gross_company_currency_total += base_grand_total
            sale_invoices_count += 1
        else:
            returns_company_currency_total += abs(base_grand_total)
            returns_count += 1
        invoice_currency = invoice.get("currency") or company_currency
        invoice_total = invoice.get("rounded_total") or invoice.get("grand_total") or 0
        currency_entry = multi_currency_totals.setdefault(
            invoice_currency,
            {
                "currency": invoice_currency,
                "total": 0,
                "invoice_count": 0,
                "company_currency_total": 0,
                "exchange_rates": set(),
            },
        )
        currency_entry["total"] += flt(invoice_total)
        currency_entry["invoice_count"] += 1
        currency_entry["company_currency_total"] += flt(base_grand_total)

        if invoice_currency != company_currency:
            rate = flt(conversion_rate) if conversion_rate else None
            if not rate and flt(invoice_total):
                rate = abs(flt(base_grand_total)) / abs(flt(invoice_total)) if base_grand_total else None
            if rate:
                currency_entry["exchange_rates"].add(rate)

        loyalty_amount = flt(invoice.get("loyalty_amount") or 0)
        loyalty_points = flt(invoice.get("loyalty_points") or 0)
        if loyalty_amount or loyalty_points:
            loyalty_base_amount = flt(
                get_base_value(invoice, "loyalty_amount", "base_loyalty_amount", conversion_rate)
            )
            if not loyalty_base_amount and loyalty_amount:
                loyalty_base_amount = loyalty_amount
            is_loyalty_redemption = loyalty_amount > 0 or loyalty_points > 0
            if is_loyalty_redemption:
                loyalty_redeemed_company_currency_total += loyalty_base_amount
                loyalty_redeemed_points += loyalty_points
                loyalty_redeemed_invoice_count += 1

                loyalty_entry = loyalty_redeemed_totals_by_currency.setdefault(
                    invoice_currency,
                    {
                        "currency": invoice_currency,
                        "total": 0,
                        "company_currency_total": 0,
                        "points": 0,
                        "invoice_count": 0,
                        "exchange_rates": set(),
                    },
                )
                loyalty_entry["total"] += loyalty_amount
                loyalty_entry["company_currency_total"] += loyalty_base_amount
                loyalty_entry["points"] += loyalty_points
                loyalty_entry["invoice_count"] += 1

            if is_loyalty_redemption and invoice_currency != company_currency:
                rate = None
                if loyalty_amount:
                    rate = (
                        abs(loyalty_base_amount) / abs(loyalty_amount)
                        if loyalty_base_amount
                        else None
                    )
                if not rate and conversion_rate:
                    rate = flt(conversion_rate)
                if rate:
                    loyalty_entry["exchange_rates"].add(rate)

        customer_credit_amount = flt(invoice.get("posa_redeemed_customer_credit") or 0)
        if customer_credit_amount > 0:
            customer_credit_base_amount = flt(
                get_base_value(
                    invoice,
                    "posa_redeemed_customer_credit",
                    "base_posa_redeemed_customer_credit",
                    conversion_rate,
                )
            )

            customer_credit_redeemed_company_currency_total += customer_credit_base_amount
            customer_credit_redeemed_invoice_count += 1

            customer_credit_entry = customer_credit_redeemed_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "invoice_count": 0,
                    "exchange_rates": set(),
                },
            )
            customer_credit_entry["total"] += customer_credit_amount
            customer_credit_entry["company_currency_total"] += customer_credit_base_amount
            customer_credit_entry["invoice_count"] += 1

            if invoice_currency != company_currency:
                rate = None
                if customer_credit_amount:
                    rate = (
                        abs(customer_credit_base_amount) / abs(customer_credit_amount)
                        if customer_credit_base_amount
                        else None
                    )
                if not rate and conversion_rate:
                    rate = flt(conversion_rate)
                if rate:
                    customer_credit_entry["exchange_rates"].add(rate)

        change_amount = flt(invoice.get("change_amount") or 0)
        has_overpayment_entry = invoice.get("name") in overpayment_invoice_names

        if change_amount and not has_overpayment_entry:
            change_entry = change_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            change_entry["total"] += change_amount

            change_base_amount = flt(
                get_base_value(invoice, "change_amount", "base_change_amount", conversion_rate)
            )
            change_company_currency_total += change_base_amount
            change_entry["company_currency_total"] += change_base_amount

            total_change_entry = total_change_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            total_change_entry["total"] += change_amount
            total_change_entry["company_currency_total"] += change_base_amount

            if invoice_currency != company_currency:
                rate = None
                if change_amount:
                    rate = abs(change_base_amount) / abs(change_amount) if change_base_amount else None
                if not rate and conversion_rate:
                    rate = flt(conversion_rate)
                if rate:
                    change_entry["exchange_rates"].add(rate)
                    total_change_entry["exchange_rates"].add(rate)

        outstanding_company_currency = invoice.get("base_outstanding_amount")
        if outstanding_company_currency in (None, ""):
            outstanding_company_currency = invoice.get("outstanding_amount")
        if outstanding_company_currency in (None, ""):
            outstanding_company_currency = get_base_value(
                invoice,
                "outstanding_amount",
                "base_outstanding_amount",
                conversion_rate,
            )
        outstanding_company_currency = flt(outstanding_company_currency or 0)

        if outstanding_company_currency > 0:
            credit_invoices_count += 1
            credit_company_currency_total += outstanding_company_currency
            outstanding_invoice_currency = invoice.get("outstanding_amount")
            if outstanding_invoice_currency in (None, ""):
                base_divisor = flt(conversion_rate) or 0
                if base_divisor:
                    outstanding_invoice_currency = outstanding_company_currency / base_divisor
                else:
                    outstanding_invoice_currency = outstanding_company_currency
            outstanding_invoice_currency = flt(outstanding_invoice_currency or 0)
            credit_entry = credit_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "invoice_count": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            credit_entry["total"] += flt(outstanding_invoice_currency)
            credit_entry["invoice_count"] += 1
            credit_entry["company_currency_total"] += outstanding_company_currency

            if invoice_currency != company_currency:
                rate = None
                if outstanding_invoice_currency:
                    rate = abs(outstanding_company_currency) / abs(flt(outstanding_invoice_currency))
                if not rate and conversion_rate:
                    rate = flt(conversion_rate)
                if rate:
                    credit_entry["exchange_rates"].add(rate)

        is_return = bool(invoice.get("is_return"))
        if not is_return and flt(invoice_total) < 0:
            is_return = True

        if is_return:
            returns_entry = returns_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "invoice_count": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            returns_entry["total"] += abs(flt(invoice_total))
            returns_entry["invoice_count"] += 1
            returns_entry["company_currency_total"] += abs(flt(base_grand_total))

            if invoice_currency != company_currency:
                rate = flt(conversion_rate) if conversion_rate else None
                if not rate and flt(invoice_total):
                    rate = abs(flt(base_grand_total)) / abs(flt(invoice_total)) if base_grand_total else None
                if rate:
                    returns_entry["exchange_rates"].add(rate)

        for payment in invoice.get("payments", []):
            mode = payment.get("mode_of_payment")
            payment_currency = resolve_payment_currency(payment, invoice_currency)
            amount = flt(payment.get("amount") or 0)
            base_amount = get_base_value(payment, "amount", "base_amount", conversion_rate)
            accumulate_payment(
                payments_by_mode,
                mode,
                payment_currency,
                amount,
                base_amount,
                conversion_rate,
            )

        if change_amount and not has_overpayment_entry:
            accumulate_payment(payments_by_mode, cash_mode_of_payment, invoice_currency,
                               -change_amount, -change_base_amount, conversion_rate)

    for entry in payment_entries:
        mode = entry.get("mode_of_payment")
        receipt = payment_entry_receipt(entry, company_currency)
        payment_currency = receipt["currency"]
        amount, base_amount, entry_rate = receipt["amount"], receipt["base_amount"], receipt["rate"]

        if entry.get("payment_type") == "Pay" and mode == cash_mode_of_payment and entry.get("party_type") in (None, "Customer"):
            change_row = overpayment_change_totals_by_currency.setdefault(
                payment_currency,
                {
                    "currency": payment_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            refund_amount = abs(amount)
            refund_base_amount = abs(base_amount)
            change_row["total"] += refund_amount
            change_row["company_currency_total"] += refund_base_amount
            overpayment_change_company_currency_total += refund_base_amount

            total_change_entry = total_change_totals_by_currency.setdefault(
                payment_currency,
                {
                    "currency": payment_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            total_change_entry["total"] += refund_amount
            total_change_entry["company_currency_total"] += refund_base_amount

            if payment_currency != company_currency:
                rate = None
                if refund_amount:
                    rate = abs(refund_base_amount) / abs(refund_amount) if refund_base_amount else None
                if not rate and entry_rate:
                    rate = flt(entry_rate)
                if rate:
                    change_row["exchange_rates"].add(rate)
                    total_change_entry["exchange_rates"].add(rate)

        accumulate_payment(payments_by_mode, mode, payment_currency, amount, base_amount, entry_rate)

    configured_modes = frappe.get_all(
        "POS Payment Method",
        filters={"parent": pos_profile, "parenttype": "POS Profile"},
        fields=["mode_of_payment"], order_by="idx",
    )
    modes = list(dict.fromkeys(
        [row.get("mode_of_payment") for row in configured_modes]
        + [row.get("mode_of_payment") for row in (getattr(opening_shift_doc, "balance_details", None) or [])]
        + [row["mode_of_payment"] for row in payments_by_mode.values()]
    ))
    mode_accounts = {
        mode: frappe.db.get_value(
            "Mode of Payment Account", {"parent": mode, "company": company}, "default_account"
        )
        for mode in modes if mode
    }
    movements = shift_outflows(opening_shift_doc, cash_mode_of_payment, mode_accounts, query=frappe.get_all)
    if cash_mode_of_payment not in mode_accounts and any(
        row["mode_of_payment"] == cash_mode_of_payment for row in movements
    ):
        mode_accounts[cash_mode_of_payment] = frappe.db.get_value(
            "Mode of Payment Account", {"parent": cash_mode_of_payment, "company": company}, "default_account")
    for entry in payment_entries:
        if entry.get("payment_type") == "Pay" and entry.get("party_type") not in (None, "", "Customer"):
            receipt = payment_entry_receipt(entry, company_currency)
            movements.append({
                "doctype": "Payment Entry", "name": entry.get("name"),
                "mode_of_payment": entry.get("mode_of_payment"),
                "account": mode_accounts.get(entry.get("mode_of_payment")),
                "amount": abs(receipt["base_amount"]), "label": "Payment made",
                "included_in_receipts": True,
            })
    reconciliation = reconciliation_rows(opening_shift_doc, payments_by_mode.values(), movements, mode_accounts)
    for movement in movements:
        mode = movement["mode_of_payment"]
        if not mode:
            continue  # Paid from an account outside this register; retained in details.
        if not movement.get("included_in_receipts"):
            accumulate_payment(payments_by_mode, mode, company_currency, -movement["amount"], -movement["amount"])
        if mode == cash_mode_of_payment:
            cash_movement_count += 1
            cash_movement_company_currency_total += movement["amount"]
            kind = movement["label"]
            type_row = cash_movement_totals_by_type.setdefault(kind, {"movement_type": kind, "total": 0})
            type_row["total"] += movement["amount"]
    if cash_movement_count:
        cash_movement_totals_by_currency[company_currency] = {
            "currency": company_currency, "total": cash_movement_company_currency_total,
            "company_currency_total": cash_movement_company_currency_total, "exchange_rates": set(),
        }
    cash_row = next((row for row in reconciliation if row["mode_of_payment"] == cash_mode_of_payment), None)
    cash_expected_company_currency_total = cash_row["expected_amount"] if cash_row else 0
    # Keep original-currency detail while including the company-currency opening float.
    cash_expected_by_currency = {
        row["currency"]: {
            "currency": row["currency"], "total": flt(row["total"]),
            "company_currency_total": flt(row["company_currency_total"]),
            "exchange_rates": sorted(row.get("exchange_rates") or []),
        }
        for row in payments_by_mode.values() if row["mode_of_payment"] == cash_mode_of_payment
    }
    if cash_row and cash_row["opening_amount"]:
        opening_currency_row = cash_expected_by_currency.setdefault(company_currency, {
            "currency": company_currency, "total": 0, "company_currency_total": 0, "exchange_rates": [],
        })
        opening_currency_row["total"] += cash_row["opening_amount"]
        opening_currency_row["company_currency_total"] += cash_row["opening_amount"]
    cash_expected_totals = list(cash_expected_by_currency.values())

    average_invoice_value = 0
    if sale_invoices_count:
        average_invoice_value = gross_company_currency_total / sale_invoices_count

    def prepare_currency_rows(container, include_count=False, include_points=False):
        output = []
        for row in container.values():
            exchange_rates = row.get("exchange_rates") or []
            if isinstance(exchange_rates, set):
                exchange_rates = sorted({flt(rate) for rate in exchange_rates if flt(rate)})
            else:
                exchange_rates = [
                    flt(rate) for rate in exchange_rates if rate not in (None, "") and flt(rate)
                ]
                exchange_rates = sorted(set(exchange_rates))

            record = {
                "currency": row.get("currency"),
                "total": flt(row.get("total")),
                "company_currency_total": flt(row.get("company_currency_total")),
                "exchange_rates": exchange_rates,
            }
            if include_count:
                record["invoice_count"] = row.get("invoice_count", 0)
            if include_points:
                record["points"] = flt(row.get("points"))
            output.append(record)
        return sorted(output, key=lambda r: (r.get("currency") or ""))

    def prepare_payment_rows(container):
        output = []
        for row in container.values():
            exchange_rates = row.get("exchange_rates") or []
            if isinstance(exchange_rates, set):
                exchange_rates = sorted({flt(rate) for rate in exchange_rates if flt(rate)})
            else:
                exchange_rates = [
                    flt(rate) for rate in exchange_rates if rate not in (None, "") and flt(rate)
                ]
                exchange_rates = sorted(set(exchange_rates))

            output.append(
                {
                    "mode_of_payment": row.get("mode_of_payment"),
                    "currency": row.get("currency"),
                    "total": flt(row.get("total")),
                    "company_currency_total": flt(row.get("company_currency_total")),
                    "exchange_rates": exchange_rates,
                }
            )

        output.sort(key=lambda r: (r.get("mode_of_payment") or "", r.get("currency") or ""))
        return output

    def prepare_movement_type_rows(container):
        output = []
        for row in container.values():
            output.append(
                {
                    "movement_type": row.get("movement_type"),
                    "total": flt(row.get("total")),
                }
            )
        output.sort(key=lambda r: (r.get("movement_type") or ""))
        return output

    return {
        "reconciliation": reconciliation,
        "salespeople": salesperson_totals(invoices),
        "movements": movements,
        "total_invoices": total_invoices,
        "company_currency": company_currency,
        "company_currency_total": flt(company_currency_total),
        "multi_currency_totals": prepare_currency_rows(multi_currency_totals, include_count=True),
        "payments_by_mode": prepare_payment_rows(payments_by_mode),
        "credit_invoices": {
            "count": credit_invoices_count,
            "company_currency_total": flt(credit_company_currency_total),
            "by_currency": prepare_currency_rows(credit_totals_by_currency, include_count=True),
        },
        "sales_summary": {
            "gross_company_currency_total": flt(gross_company_currency_total),
            "net_company_currency_total": flt(company_currency_total),
            "average_invoice_value": flt(average_invoice_value),
            "sale_invoices_count": sale_invoices_count,
        },
        "returns": {
            "count": returns_count,
            "company_currency_total": flt(returns_company_currency_total),
            "by_currency": prepare_currency_rows(returns_totals_by_currency, include_count=True),
        },
        "change_returned": {
            "company_currency_total": flt(
                change_company_currency_total + overpayment_change_company_currency_total
            ),
            "by_currency": prepare_currency_rows(total_change_totals_by_currency),
            "invoice_change": {
                "company_currency_total": flt(change_company_currency_total),
                "by_currency": prepare_currency_rows(change_totals_by_currency),
            },
            "overpayment_change": {
                "company_currency_total": flt(overpayment_change_company_currency_total),
                "by_currency": prepare_currency_rows(overpayment_change_totals_by_currency),
            },
        },
        "loyalty_redemption": {
            "count": loyalty_redeemed_invoice_count,
            "points": flt(loyalty_redeemed_points),
            "company_currency_total": flt(loyalty_redeemed_company_currency_total),
            "by_currency": prepare_currency_rows(
                loyalty_redeemed_totals_by_currency,
                include_count=True,
                include_points=True,
            ),
        },
        "customer_credit_redeemed": {
            "count": customer_credit_redeemed_invoice_count,
            "company_currency_total": flt(customer_credit_redeemed_company_currency_total),
            "by_currency": prepare_currency_rows(
                customer_credit_redeemed_totals_by_currency,
                include_count=True,
            ),
        },
        "cash_expected": {
            "mode_of_payment": cash_mode_of_payment,
            "company_currency_total": flt(cash_expected_company_currency_total),
            "by_currency": sorted(
                cash_expected_totals,
                key=lambda row: (row.get("currency") or ""),
            ),
        },
        "cash_movements": {
            "count": cash_movement_count,
            "company_currency_total": flt(cash_movement_company_currency_total),
            "by_currency": prepare_currency_rows(cash_movement_totals_by_currency),
            "by_type": prepare_movement_type_rows(cash_movement_totals_by_type),
        },
    }


@frappe.whitelist()
def get_payment_reconciliation_details(closing_shift_doc):
    company_currency = frappe.get_cached_value("Company", closing_shift_doc.company, "default_currency")

    sales_breakdown = defaultdict(float)
    net_breakdown = defaultdict(float)
    payment_breakdown = {}

    def update_payment_breakdown(mode_of_payment, base_amount=0, currency=None, amount=0):
        if not mode_of_payment:
            return

        row = payment_breakdown.setdefault(
            mode_of_payment,
            {"base": 0.0, "currencies": defaultdict(float)},
        )
        row["base"] += flt(base_amount)
        if currency:
            row["currencies"][currency] += flt(amount)

    cash_mode_of_payment = (
        frappe.db.get_value("POS Profile", closing_shift_doc.pos_profile, "posa_cash_mode_of_payment")
        or "Cash"
    )

    payment_documents = []
    refunded_invoices = set()
    for row in closing_shift_doc.get("pos_payments", []):
        name = row.get("payment_entry")
        if not name or not frappe.db.exists("Payment Entry", name):
            continue
        doc = frappe.get_cached_doc("Payment Entry", name)
        doc.check_permission("read")
        payment_documents.append((row, doc))
        if doc.get("payment_type") == "Pay" and doc.get("mode_of_payment") == cash_mode_of_payment:
            refunded_invoices.update(
                (ref.get("reference_doctype"), ref.get("reference_name"))
                for ref in (doc.get("references") or [])
            )

    for row in closing_shift_doc.get("pos_transactions", []):
        invoice = row.get("sales_invoice") or row.get("pos_invoice")
        if not invoice:
            continue

        doctype = "Sales Invoice" if row.get("sales_invoice") else "POS Invoice"
        if not frappe.db.exists(doctype, invoice):
            continue

        invoice_doc = frappe.get_cached_doc(doctype, invoice)
        invoice_doc.check_permission("read")
        currency = invoice_doc.get("currency") or company_currency
        conversion_rate = (
            invoice_doc.get("conversion_rate")
            or invoice_doc.get("source_exchange_rate")
            or invoice_doc.get("target_exchange_rate")
            or invoice_doc.get("exchange_rate")
            or 1
        )

        sales_breakdown[currency] += flt(invoice_doc.get("grand_total") or 0)
        net_breakdown[currency] += flt(invoice_doc.get("net_total") or 0)

        for payment in invoice_doc.get("payments", []):
            update_payment_breakdown(
                payment.mode_of_payment,
                get_base_value(payment, "amount", "base_amount", conversion_rate),
                currency,
                payment.amount,
            )

        change_amount = invoice_doc.get("change_amount") or 0
        if change_amount and (doctype, invoice) not in refunded_invoices:
            update_payment_breakdown(
                cash_mode_of_payment,
                -get_base_value(
                    invoice_doc,
                    "change_amount",
                    "base_change_amount",
                    conversion_rate,
                ),
                currency,
                -change_amount,
            )

    for row, payment_doc in payment_documents:
        receipt = payment_entry_receipt(payment_doc, company_currency)
        update_payment_breakdown(
            row.get("mode_of_payment") or payment_doc.get("mode_of_payment"),
            receipt["base_amount"], receipt["currency"], receipt["amount"],
        )

    mode_summaries = []
    payment_breakdown_copy = payment_breakdown.copy()
    for detail in closing_shift_doc.get("payment_reconciliation", []):
        mop = detail.mode_of_payment
        breakdown = payment_breakdown_copy.pop(mop, None)
        currencies = []
        if breakdown:
            currencies = [
                frappe._dict({"currency": currency, "amount": amount})
                for currency, amount in sorted(breakdown["currencies"].items())
                if amount
            ]

        base_total = flt(detail.expected_amount) - flt(detail.opening_amount)

        mode_summaries.append(
            frappe._dict(
                {
                    "mode_of_payment": mop,
                    "base_amount": base_total,
                    "opening_amount": flt(detail.opening_amount),
                    "expected_amount": flt(detail.expected_amount),
                    "difference": flt(detail.difference),
                    "currency_breakdown": currencies,
                }
            )
        )

    for mop, breakdown in payment_breakdown_copy.items():
        mode_summaries.append(
            frappe._dict(
                {
                    "mode_of_payment": mop,
                    "base_amount": breakdown["base"],
                    "opening_amount": 0,
                    "expected_amount": breakdown["base"],
                    "difference": 0,
                    "currency_breakdown": [
                        frappe._dict({"currency": currency, "amount": amount})
                        for currency, amount in sorted(breakdown["currencies"].items())
                        if amount
                    ],
                }
            )
        )

    sales_currency_breakdown = [
        frappe._dict({"currency": currency, "amount": amount})
        for currency, amount in sorted(sales_breakdown.items())
        if amount
    ]
    net_currency_breakdown = [
        frappe._dict({"currency": currency, "amount": amount})
        for currency, amount in sorted(net_breakdown.items())
        if amount
    ]

    return frappe.render_template(
        "posawesome/posawesome/doctype/pos_closing_shift/closing_shift_details.html",
        {
            "data": closing_shift_doc,
            "currency": company_currency,
            "company_currency": company_currency,
            "mode_summaries": mode_summaries,
            "sales_currency_breakdown": sales_currency_breakdown,
            "net_currency_breakdown": net_currency_breakdown,
        },
    )
