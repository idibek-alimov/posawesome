import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    from posawesome.posawesome.api.fiscal import FISCAL_FIELDS
    fields = [dict(f) for f in FISCAL_FIELDS if f["fieldname"] != "custom_sales_person"]
    for field in fields:
        if field["fieldname"] == "custom_fiscal_status":
            field["options"] = "Черновик\nФискализирован\nОшибка\nБез чека\nНеизвестно"
        field["allow_on_submit"] = 1
        field["no_copy"] = 1
    fields += [dict(fieldname="custom_fiscal_attempt", label="Fiscal attempt", fieldtype="Data", read_only=1, hidden=1, allow_on_submit=1, no_copy=1),
               dict(fieldname="custom_fiscal_payload", label="Fiscal payload", fieldtype="Long Text", read_only=1, hidden=1, allow_on_submit=1, no_copy=1)]
    profile = [dict(fieldname="posa_fiscal_section", label="TP809 Fiscal Printer", fieldtype="Section Break", insert_after="print_format"),
               dict(fieldname="posa_fiscal_printer_url", label="TP809 printer URL (desktop)", fieldtype="Data", insert_after="posa_fiscal_section"),
               dict(fieldname="posa_fiscal_bridge_url", label="Local fiscal bridge URL (browser)", fieldtype="Data", insert_after="posa_fiscal_printer_url", default="http://localhost:5000"),
               dict(fieldname="posa_unlimited_cashier_returns", label="Cashier returns without time limit", fieldtype="Check", default="1", insert_after="posa_fiscal_bridge_url")]
    create_custom_fields({"Sales Invoice": fields, "POS Invoice": fields, "POS Profile": profile}, update=True)
