"""Decimal-only reconciliation; a negative allocation explains a shortage."""

import hashlib
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def amount(value, precision, rounded=False):
    try:
        number = Decimal(str(value))
        unit = Decimal(1).scaleb(-int(precision))
        if not number.is_finite():
            raise ValueError("Amount must be finite")
        result = number.quantize(unit, rounding=ROUND_HALF_UP)
        if not rounded and result != number:
            raise ValueError("Use the closing currency precision")
        return result
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid amount") from None


def group_counts(reconciliation, counts, precision):
    groups = {}
    methods = []
    for row in reconciliation:
        mode = row["mode_of_payment"]
        actual = amount(counts[mode], precision)
        expected = amount(row["expected_amount"], precision, rounded=True)
        difference = actual - expected
        detail = dict(row, actual=str(actual), expected_amount=str(expected), difference=str(difference))
        methods.append(detail)
        if not difference:
            continue
        sign = -1 if difference < 0 else 1
        account = row.get("account") or "unmapped:" + mode
        key = hashlib.sha256(f"{account}|{sign}".encode()).hexdigest()[:24]
        group = groups.setdefault(key, dict(row_key=key, account=row.get("account"), sign=sign,
                                           expected_amount=Decimal(0), actual_amount=Decimal(0), original_difference=Decimal(0), methods=[]))
        group["expected_amount"] += expected
        group["actual_amount"] += actual
        group["original_difference"] += difference
        group["methods"].append(mode)
    # Retain zero-difference accounts as scope evidence too. Native list/export
    # permissions must not expose their snapshot through a review with no shortage.
    represented = {row["account"] for row in groups.values()}
    for detail in methods:
        account = detail.get("account")
        if account in represented:
            continue
        identity = account or "unmapped:" + detail["mode_of_payment"]
        key = hashlib.sha256(f"{identity}|0".encode()).hexdigest()[:24]
        group = groups.setdefault(key, dict(row_key=key, account=account, sign=0, expected_amount=Decimal(0), actual_amount=Decimal(0), original_difference=Decimal(0), methods=[]))
        group["expected_amount"] += Decimal(detail["expected_amount"])
        group["actual_amount"] += Decimal(detail["actual"])
        group["methods"].append(detail["mode_of_payment"])
    return methods, [dict(row, **{key: str(row[key]) for key in ("expected_amount", "actual_amount", "original_difference")}) for row in groups.values()]


def remaining(original, allocations, precision):
    original = amount(original, precision)
    total = sum((amount(value, precision) for value in allocations), Decimal(0))
    if total and (original * total <= 0 or abs(total) > abs(original)):
        raise ValueError("Resolution exceeds or has the wrong sign for the original difference")
    return original - total


def allocate(original, allocations, proposed, precision):
    proposed = amount(proposed, precision)
    rest = remaining(original, allocations, precision)
    if not proposed or proposed * rest <= 0 or abs(proposed) > abs(rest):
        raise ValueError("Resolution exceeds or has the wrong sign for the remaining difference")
    return rest - proposed


def status(rows, started=False, voided=False):
    if voided:
        return "Voided"
    if not any(Decimal(str(row["remaining_amount"])) for row in rows):
        return "Resolved"
    if any(Decimal(str(row["allocated_amount"])) for row in rows):
        return "Partially resolved"
    return "In review" if started else "Pending review"


def payment_totals(invoice, cash_mode, precision):
    result = defaultdict(Decimal)
    for row in invoice.get("payments", []):
        base = row.get("base_amount")
        if base in (None, ""):
            base = Decimal(str(row.get("amount") or 0)) * Decimal(str(invoice.get("conversion_rate") or 1))
        result[row["mode_of_payment"]] += amount(base, precision, rounded=True)
    change = invoice.get("base_change_amount")
    if change in (None, ""):
        change = Decimal(str(invoice.get("change_amount") or 0)) * Decimal(str(invoice.get("conversion_rate") or 1))
    result[cash_mode] -= amount(change, precision, rounded=True)
    return result
