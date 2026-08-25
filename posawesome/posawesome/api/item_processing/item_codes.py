import frappe


def _next_short_code():
    last = frappe.db.sql("""
        SELECT custom_short_code FROM `tabItem`
        WHERE custom_short_code REGEXP '^[0-9]+$'
        ORDER BY CAST(custom_short_code AS UNSIGNED) DESC
        LIMIT 1
    """)
    return str(int(last[0][0]) + 1) if last and last[0][0] else "1000"


def _ean13_check_digit(base12):
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base12))
    return str((10 - (total % 10)) % 10)


def _next_barcode():
    last = frappe.db.sql("""
        SELECT barcode FROM `tabItem Barcode`
        WHERE barcode LIKE '20%%' AND LENGTH(barcode) = 13
        ORDER BY barcode DESC LIMIT 1
    """)
    next_num = int(last[0][0][:-1]) + 1 if last and last[0][0] else 200000000000
    base = str(next_num).zfill(12)
    return base + _ean13_check_digit(base)


def generate_short_code_and_barcode(doc, method=None):
    """Before-insert hook: auto-fill short code (from 1000) and a standard EAN-13 barcode."""
    if frappe.get_meta("Item").has_field("custom_short_code") and not doc.get("custom_short_code"):
        doc.custom_short_code = _next_short_code()

    if not doc.get("barcodes"):
        doc.append("barcodes", {"barcode": _next_barcode(), "barcode_type": "EAN"})
