# -*- coding: utf-8 -*-
"""Canonical installation and schema setup for POS Awesome (replaces legacy migration patches)."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


POS_SUPERVISOR_ROLE = "POS Awesome Supervisor"
LEGACY_SUPERVISOR_FIELD = "posa_is_pos_supervisor"
LEGACY_BARCODE_UOM_FIELD = "Item Barcode-posa_uom"

CASH_MOVEMENT_PROFILE_FIELDS = [
    {
        "fieldname": "posa_enable_cash_movement",
        "label": "Enable Cash Movement",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "posa_print_format_rules",
    },
    {
        "fieldname": "posa_allow_pos_expense",
        "label": "Allow POS Expense",
        "fieldtype": "Check",
        "default": "0",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_enable_cash_movement",
    },
    {
        "fieldname": "posa_allow_cash_deposit",
        "label": "Allow Cash Deposit",
        "fieldtype": "Check",
        "default": "0",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_allow_pos_expense",
    },
    {
        "fieldname": "posa_default_expense_account",
        "label": "Default POS Expense Account",
        "fieldtype": "Link",
        "options": "Account",
        "depends_on": "eval:doc.posa_enable_cash_movement==1 && doc.posa_allow_pos_expense==1",
        "insert_after": "posa_allow_cash_deposit",
    },
    {
        "fieldname": "posa_allowed_expense_accounts",
        "label": "Allowed POS Expense Accounts",
        "fieldtype": "Table",
        "options": "POS Allowed Expense Account",
        "depends_on": "eval:doc.posa_enable_cash_movement==1 && doc.posa_allow_pos_expense==1",
        "insert_after": "posa_default_expense_account",
    },
    {
        "fieldname": "posa_default_source_account",
        "label": "Default POS Source Account",
        "fieldtype": "Link",
        "options": "Account",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_allowed_expense_accounts",
    },
    {
        "fieldname": "posa_allow_source_account_override",
        "label": "Allow Source Account Selection",
        "fieldtype": "Check",
        "default": "0",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_default_source_account",
    },
    {
        "fieldname": "posa_allowed_source_accounts",
        "label": "Allowed POS Source Accounts",
        "fieldtype": "Table",
        "options": "POS Allowed Source Account",
        "depends_on": "eval:doc.posa_enable_cash_movement==1 && doc.posa_allow_source_account_override==1",
        "insert_after": "posa_allow_source_account_override",
    },
    {
        "fieldname": "posa_back_office_cash_account",
        "label": "Back Office Cash Account",
        "fieldtype": "Link",
        "options": "Account",
        "depends_on": "eval:doc.posa_enable_cash_movement==1 && doc.posa_allow_cash_deposit==1",
        "insert_after": "posa_allowed_source_accounts",
    },
    {
        "fieldname": "posa_allow_cancel_submitted_cash_movement",
        "label": "Allow Cancel Submitted Cash Movement",
        "fieldtype": "Check",
        "default": "0",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_back_office_cash_account",
    },
    {
        "fieldname": "posa_allow_delete_cancelled_cash_movement",
        "label": "Allow Delete Cancelled Cash Movement",
        "fieldtype": "Check",
        "default": "0",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_allow_cancel_submitted_cash_movement",
    },
    {
        "fieldname": "posa_require_cash_movement_remarks",
        "label": "Require Cash Movement Remarks",
        "fieldtype": "Check",
        "default": "1",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_allow_delete_cancelled_cash_movement",
    },
    {
        "fieldname": "posa_cash_movement_max_amount",
        "label": "Cash Movement Max Amount",
        "fieldtype": "Currency",
        "options": "Company:company:default_currency",
        "depends_on": "eval:doc.posa_enable_cash_movement==1",
        "insert_after": "posa_require_cash_movement_remarks",
    },
]

FAST_POS_INDEXES = [
    (
        "Item",
        [
            "disabled",
            "is_sales_item",
            "is_fixed_asset",
            "item_group",
            "item_name",
            "item_code",
        ],
        "posa_item_fast_search",
    ),
    (
        "Item",
        [
            "modified",
            "item_group",
            "disabled",
            "is_sales_item",
            "is_fixed_asset",
            "item_code",
        ],
        "posa_item_delta_scope",
    ),
    (
        "Item Price",
        [
            "price_list",
            "currency",
            "item_code",
            "customer",
            "valid_from",
            "valid_upto",
        ],
        "posa_item_price_fast",
    ),
    (
        "Bin",
        ["warehouse", "modified", "item_code"],
        "posa_bin_delta",
    ),
    (
        "Bin",
        ["warehouse", "item_code", "modified"],
        "posa_bin_item_delta",
    ),
    (
        "Sales Invoice",
        ["docstatus", "company", "posting_date", "name"],
        "posa_si_hot_catalog",
    ),
    (
        "Sales Invoice Item",
        ["item_code", "warehouse", "parent"],
        "posa_sii_hot_catalog",
    ),
    (
        "Item Barcode",
        ["barcode", "parent"],
        "posa_barcode_parent",
    ),
]

SYNC_DELTA_INDEXES = [
    (
        "Item Price",
        ["price_list", "modified", "name"],
        "price_list_modified_name",
    ),
    (
        "Deleted Document",
        ["deleted_doctype", "creation", "deleted_name"],
        "doctype_creation_deleted_name",
    ),
    (
        "Bin",
        ["warehouse", "modified", "item_code"],
        "warehouse_modified_item_code",
    ),
    (
        "Bin",
        ["warehouse", "item_code", "modified"],
        "warehouse_item_code_modified",
    ),
    (
        "Item",
        [
            "modified",
            "item_group",
            "disabled",
            "is_sales_item",
            "is_fixed_asset",
            "item_code",
        ],
        "modified_group_disabled_sales_fixed_item",
    ),
    (
        "Item",
        [
            "disabled",
            "is_sales_item",
            "is_fixed_asset",
            "item_group",
            "modified",
            "item_code",
        ],
        "disabled_sales_fixed_group_modified_item",
    ),
    (
        "Customer",
        ["modified", "disabled", "customer_group", "name"],
        "modified_disabled_group_name",
    ),
    (
        "Customer",
        ["disabled", "customer_group", "modified", "name"],
        "disabled_group_modified_name",
    ),
    (
        "Price List",
        ["selling", "modified", "name"],
        "selling_modified_name",
    ),
]

COMPOSITE_AND_SCALE_INDEXES = [
    ("Item Price", ["price_list", "item_code"], "price_list_item_code"),
    (
        "Item",
        [
            "is_sales_item",
            "disabled",
            "is_fixed_asset",
            "has_variants",
            "item_group",
            "item_name",
        ],
        "sales_disabled_fixed_variants_group_name",
    ),
    ("Item Barcode", ["barcode"], "barcode"),
    ("Item Barcode", ["parent"], "parent"),
    ("Serial No", ["item_code", "warehouse", "status"], "item_warehouse_status"),
    ("Bin", ["item_code", "warehouse"], "item_code_warehouse"),
    (
        "Stock Ledger Entry",
        [
            "warehouse",
            "item_code",
            "batch_no",
            "is_cancelled",
            "posting_date",
            "posting_time",
            "creation",
        ],
        "warehouse_item_batch_cancel_posting_creation",
    ),
    ("Batch", ["item", "disabled", "expiry_date"], "item_disabled_expiry"),
    (
        "Item Price",
        [
            "price_list",
            "currency",
            "selling",
            "item_code",
            "uom",
            "valid_from",
            "valid_upto",
        ],
        "pricelist_currency_selling_item_uom_validfrom_upto",
    ),
    ("Customer", ["disabled", "customer_group", "name"], "disabled_customer_group_name"),
    ("Customer", ["disabled", "modified", "name"], "disabled_modified_name"),
    (
        "Pricing Rule",
        ["selling", "disable", "company", "valid_from", "valid_upto"],
        "selling_disable_company_validity",
    ),
]


def ensure_expense_source_settings():
    """Ensure legacy cash movement and source allowlist fields exist on POS Profile."""
    for child in ("pos_allowed_expense_account", "pos_allowed_source_account"):
        frappe.reload_doc("posawesome", "doctype", child)
    for field in CASH_MOVEMENT_PROFILE_FIELDS:
        custom_field_name = f"POS Profile-{field['fieldname']}"
        if not frappe.db.exists("Custom Field", custom_field_name):
            create_custom_field("POS Profile", field)
    frappe.clear_cache(doctype="POS Profile")
    frappe.db.updatedb("POS Profile")


def ensure_supervisor_role_and_cleanup_legacy_fields():
    """Ensure POS Awesome Supervisor role exists and remove obsolete custom fields."""
    if not frappe.db.exists("Role", POS_SUPERVISOR_ROLE):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": POS_SUPERVISOR_ROLE,
                "desk_access": 1,
                "is_custom": 1,
            }
        ).insert(ignore_permissions=True)

    legacy_user_cf = f"User-{LEGACY_SUPERVISOR_FIELD}"
    if frappe.db.exists("Custom Field", legacy_user_cf):
        users = frappe.get_all(
            "User",
            filters={LEGACY_SUPERVISOR_FIELD: 1},
            pluck="name",
            ignore_permissions=True,
        )
        for user in users:
            if user and not frappe.db.exists(
                "Has Role",
                {"parent": user, "parenttype": "User", "role": POS_SUPERVISOR_ROLE},
            ):
                user_doc = frappe.get_doc("User", user)
                user_doc.append("roles", {"role": POS_SUPERVISOR_ROLE})
                user_doc.save(ignore_permissions=True)
        frappe.delete_doc("Custom Field", legacy_user_cf, ignore_permissions=True, force=True)
        frappe.clear_cache(doctype="User")

    if frappe.db.exists("Custom Field", LEGACY_BARCODE_UOM_FIELD):
        frappe.delete_doc("Custom Field", LEGACY_BARCODE_UOM_FIELD, ignore_permissions=True, force=True)
        frappe.clear_cache(doctype="Item Barcode")


def ensure_pos_indexes():
    """Ensure all POS performance, scale, and offline sync delta indexes exist."""
    all_indexes = FAST_POS_INDEXES + SYNC_DELTA_INDEXES + COMPOSITE_AND_SCALE_INDEXES
    for doctype, fields, index_name in all_indexes:
        try:
            frappe.db.add_index(doctype, fields, index_name=index_name)
        except Exception as error:
            frappe.log_error(str(error), f"POS index setup: {index_name}")

    try:
        has_ft = frappe.db.sql(
            "SHOW INDEX FROM `tabItem` WHERE Key_name = 'item_name_description_ft'"
        )
        if not has_ft:
            frappe.db.sql(
                """
                ALTER TABLE `tabItem`
                ADD FULLTEXT INDEX item_name_description_ft (item_name, description)
                """
            )
    except Exception as error:
        frappe.log_error(str(error), "Add Item fulltext index")


def _available_legacy_mpesa_id(candidate, row_name):
    candidate = str(candidate)[:140]
    counter = 1
    while frappe.db.exists(
        "Mpesa Payment Register",
        {"transid": candidate, "name": ["!=", row_name]},
    ):
        suffix = f"-{counter}"
        candidate = str(candidate)[: 140 - len(suffix)] + suffix
        counter += 1
    return candidate


def secure_mpesa_callback_transactions():
    """Deduplicate and backfill any empty or duplicate Mpesa Payment Register transid values."""
    if not frappe.db.table_exists("Mpesa Payment Register"):
        return

    missing_ids = frappe.db.sql(
        """
        select name
        from `tabMpesa Payment Register`
        where transid is null or transid = ''
        """,
        pluck=True,
    )
    for name in missing_ids:
        replacement = _available_legacy_mpesa_id(f"legacy-missing-{name}", name)
        frappe.db.set_value(
            "Mpesa Payment Register",
            name,
            "transid",
            replacement,
            update_modified=False,
        )

    duplicates = frappe.db.sql(
        """
        select transid
        from `tabMpesa Payment Register`
        where coalesce(transid, '') != ''
        group by transid
        having count(*) > 1
        """,
        as_dict=True,
    )
    for duplicate in duplicates:
        rows = frappe.get_all(
            "Mpesa Payment Register",
            filters={"transid": duplicate.transid},
            fields=["name", "docstatus", "payment_entry", "creation"],
            order_by="docstatus desc, payment_entry desc, creation asc, name asc",
        )
        for row in rows[1:]:
            suffix = f"#duplicate-{row.name}"
            original = str(duplicate.transid)
            replacement = _available_legacy_mpesa_id(
                original[: max(1, 140 - len(suffix))] + suffix,
                row.name,
            )
            frappe.db.set_value(
                "Mpesa Payment Register",
                row.name,
                "transid",
                replacement,
                update_modified=False,
            )


ATTENDANCE_PROFILE_FIELDS = [
    {
        "fieldname": "posa_enforce_attendance",
        "label": "Enforce Attendance for Sales Persons",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "posa_sales_persons",
        "description": "Restrict salesperson choices to staff checked in at the attendance site",
    },
    {
        "fieldname": "posa_attendance_site",
        "label": "Attendance Site",
        "fieldtype": "Link",
        "options": "Retail Attendance Site",
        "depends_on": "eval:doc.posa_enforce_attendance==1",
        "mandatory_depends_on": "eval:doc.posa_enforce_attendance==1",
        "insert_after": "posa_enforce_attendance",
        "description": "Retail Attendance Site for checking staff presence",
    },
]


def ensure_attendance_profile_fields():
    """Ensure attendance enforcement fields exist on POS Profile."""
    for field in ATTENDANCE_PROFILE_FIELDS:
        create_custom_field("POS Profile", field, ignore_validate=True)


def setup_posawesome():
    """Run full idempotent POS Awesome setup on install and migrate."""
    from posawesome.posawesome.api.fiscal import ensure_fiscal_fields
    from posawesome.posawesome.api.label_templates import ensure_default_templates

    ensure_attendance_profile_fields()
    ensure_expense_source_settings()
    ensure_fiscal_fields()
    ensure_supervisor_role_and_cleanup_legacy_fields()
    ensure_pos_indexes()
    ensure_default_templates(force_update=True)
    secure_mpesa_callback_transactions()


after_install = setup_posawesome
after_migrate = setup_posawesome
execute = setup_posawesome
