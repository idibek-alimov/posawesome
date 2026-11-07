"""Read-only legacy adapter. No conversion or financial reposting."""

import frappe


def adapters():
    common = ("name", "posting_date", "creation", "modified", "company", "pos_profile", "pos_opening_shift",
        "amount", "journal_entry", "docstatus", "owner", "amended_from")
    return [dict(doctype="POS Cash Movement", filters={"movement_type": "Expense"},
        fields=dict({field: field for field in common}, paid_from="source_account",
            expense_category="expense_account", beneficiary_name="against_name", description="remarks"))]


def detail(source_doctype, name):
    if source_doctype != "POS Cash Movement":
        return None
    doc = frappe.get_doc(source_doctype, name)
    doc.check_permission("read")
    if doc.movement_type != "Expense":
        frappe.throw(frappe._("Unsupported expense source."))
    return dict(doc.as_dict(), source_doctype=source_doctype, source_id=f"{source_doctype}:{name}",
        paid_from=doc.source_account, expense_category=doc.expense_account,
        beneficiary_name=doc.against_name, description=doc.remarks)
