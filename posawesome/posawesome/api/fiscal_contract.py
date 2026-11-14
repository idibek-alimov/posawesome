"""TP809 wire contract. No network or Frappe dependencies; money is integer tiyin."""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
import base64


def decimal(value):
    result = Decimal(str(value or 0))
    if not result.is_finite():
        raise ValueError("Invalid monetary value")
    return result


def tiyin(value):
    return int((decimal(value) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def allocate(total, weights):
    """Largest remainder allocation preserves the final submitted total exactly."""
    weights = [abs(decimal(w)) for w in weights]
    denominator = sum(weights)
    if total < 0 or not denominator:
        raise ValueError("Receipt must contain positive-value items")
    shares = [Decimal(total) * w / denominator for w in weights]
    result = [int(s.to_integral_value(rounding=ROUND_FLOOR)) for s in shares]
    order = sorted(range(len(shares)), key=lambda i: shares[i] - result[i], reverse=True)
    for i in order[:total - sum(result)]:
        result[i] += 1
    return result


def tax_codes(template, taxes):
    template = str(template or "").lower()
    if "simplified" in template or "усн" in template:
        code = ("SIMPLIFIED1", "ZERO_TAX")
        expected = Decimal(6)
    elif "general vat" in template or "ндс" in template:
        code = ("GENERAL", "STANDARD")
        expected = Decimal(14)
    else:
        raise ValueError("Configure a TJ Simplified Tax or TJ General VAT tax template before fiscal printing")
    for row in taxes:
        if decimal(row.get("rate")) not in (0, expected) or row.get("charge_type") == "Actual":
            raise ValueError("Tax rows do not match the selected TP809 tax regime")
    return code


def build_receipt(doc, payment_types):
    if doc.get("currency") != "TJS":
        raise ValueError("TP809 fiscal receipts require TJS")
    if int(doc.get("docstatus") or 0) != 1:
        raise ValueError("Fiscal printing requires a submitted invoice")
    taxes = doc.get("taxes") or []
    regime, vat = tax_codes(doc.get("taxes_and_charges"), taxes)
    rows = doc.get("items") or []
    is_return = bool(doc.get("is_return"))
    if not rows or any(decimal(r.get("qty")) == 0 or (decimal(r.get("qty")) < 0) != is_return for r in rows):
        raise ValueError("Mixed sale/return or zero-quantity fiscal receipts are not supported")
    total = abs(tiyin(doc.get("rounded_total") if doc.get("rounded_total") else doc.get("grand_total")))
    if not total:
        raise ValueError("Fiscal receipt total must be positive")
    # net_amount includes native invoice discounts. Allocate inclusive VAT and native
    # invoice rounding over those final weights, never over the pre-discount rate.
    sums = allocate(total, [r.get("net_amount", r.get("amount")) for r in rows])
    products = []
    for row, amount in zip(rows, sums):
        qty = abs(decimal(row.get("qty")))
        product = dict(name=str(row.get("item_name") or row.get("item_code"))[:128],
                       quantity=float(qty), price=tiyin(Decimal(amount) / 100 / qty),
                       sum=amount, commodity="SERVICE" if row.get("is_stock_item") == 0 else "GOODS",
                       vatCode=vat)
        if row.get("custom_marking_code"):
            product["code"] = base64.b64encode(row["custom_marking_code"].encode()).decode()
        products.append(product)
    cash = noncash = 0
    for payment in doc.get("payments") or []:
        amount = abs(tiyin(payment.get("amount")))
        kind = payment_types.get(payment.get("mode_of_payment"))
        if amount and kind not in ("Cash", "Bank"):
            raise ValueError("Fiscal payment requires a configured Cash or Bank Mode of Payment")
        if kind == "Cash":
            cash += amount
        else:
            noncash += amount
    change = abs(tiyin(doc.get("change_amount"))) if not is_return else 0
    # Credit notes and loyalty/deposit tenders cannot be mislabeled as cash.
    if cash + noncash - change != total:
        raise ValueError("Fiscal payment total does not match the submitted invoice; credit/loyalty tenders need a supported fiscal tender")
    if change > cash:
        raise ValueError("Change exceeds cash received")
    return dict(formCode="RECEIPT", ffdVersion="VER_1", shouldPrintSlip=True,
                operationType="REVERT_INCOME" if is_return else "INCOME", taxType=regime,
                consumerContacts=doc.get("contact_email") or doc.get("contact_mobile") or "",
                customMessage="Спасибо за покупку!", products=products, receiptSum=sum(sums),
                receiptCash=cash, receiptNonCash=noncash, cashChangeAmount=change,
                # A cashier-entered bank tender is not an acquiring-terminal response.
                # Do not print fabricated Visa/auth=0/OK from the MARKET example.
                bankRRN=None, bankCard=None, bankAuthCode=None,
                bankCardName=None, bankResult=None,
                taxes={"vats": [dict(vatCode=vat, vatSum=abs(tiyin(doc.get("total_taxes_and_charges"))) if vat == "STANDARD" else 0)]})
