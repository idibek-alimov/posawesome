"""Add missing legacy source fields without changing register values or payment methods."""

import frappe

from posawesome.patches.add_pos_cash_movement_settings import execute as ensure_fields


def execute():
    for child in ("pos_allowed_expense_account", "pos_allowed_source_account"):
        frappe.reload_doc("posawesome", "doctype", child)
    ensure_fields()  # Existing Custom Fields and their configured values are left alone.
    frappe.clear_cache(doctype="POS Profile")
    frappe.db.updatedb("POS Profile")  # Also repair an existing Custom Field's missing column.
