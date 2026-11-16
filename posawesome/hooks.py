app_name = "posawesome"
app_title = "Radolfa"
app_publisher = "defendicon"
app_description = "Radolfa POS"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "defendicon@github.com"
app_license = "GPLv3"
app_url = "https://github.com/defendicon/POS-Awesome-V15"
app_source_link = "https://github.com/defendicon/POS-Awesome-V15"
source_link = "https://github.com/defendicon/POS-Awesome-V15"

# POS Awesome extends ERPNext heavily (custom fields, controller overrides,
# and many `from erpnext...` imports). Declare the hard dependency so bench
# installs/loads ERPNext first and refuses to install without it.
required_apps = ["erpnext"]

persistent_cache_keys = ["posawesome:terminal-state"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# POS assets are loaded on-demand from the POS page bootstrap so the Desk shell
# does not retain stale bundles across bench builds.
app_include_js = []
app_include_css = []

# include js, css files in header of web template
# web_include_css = "/assets/posawesome/css/posawesome.css"
# web_include_js = "/assets/posawesome/js/posawesome.js"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "POS Profile": "posawesome/api/pos_profile.js",
    "Sales Invoice": "posawesome/api/invoice.js",
    "Company": "posawesome/api/company.js",
    "Item": "posawesome/api/item_desk.js",
    "Purchase Receipt": "posawesome/api/purchase_receipt_desk.js",
    "Stock Entry": "posawesome/api/stock_entry_desk.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "posawesome.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "posawesome.install.before_install"
after_install = "posawesome.setup.install.after_install"
# before_uninstall = "posawesome.uninstall.before_uninstall"
after_uninstall = "posawesome.uninstall.after_uninstall"
after_migrate = ["posawesome.setup.install.after_migrate"]

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "posawesome.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Item": {
        "before_insert": "posawesome.posawesome.api.item_processing.item_codes.generate_short_code_and_barcode",
        "after_insert": "posawesome.posawesome.api.item_processing.alternates.clear_alternate_item_caches",
        "on_update": "posawesome.posawesome.api.item_processing.alternates.clear_alternate_item_caches",
        "on_trash": "posawesome.posawesome.api.item_processing.alternates.clear_alternate_item_caches",
    },
    "Sales Invoice": {
        "before_validate": "posawesome.posawesome.api.fiscal.validate_fiscal_metadata",
        "before_update_after_submit": "posawesome.posawesome.api.fiscal.validate_fiscal_metadata",
        "validate": "posawesome.posawesome.api.invoice.validate",
        "before_submit": "posawesome.posawesome.api.invoice.before_submit",
        "before_cancel": "posawesome.posawesome.api.invoice.before_cancel",
        "on_cancel": "posawesome.posawesome.api.invoice.on_cancel",
    },
    "POS Invoice": {
        "before_validate": "posawesome.posawesome.api.fiscal.validate_fiscal_metadata",
        "before_update_after_submit": "posawesome.posawesome.api.fiscal.validate_fiscal_metadata",
        "validate": "posawesome.posawesome.api.invoice.validate",
        "before_submit": "posawesome.posawesome.api.invoice.before_submit",
        "before_cancel": "posawesome.posawesome.api.invoice.before_cancel",
        "on_cancel": "posawesome.posawesome.api.invoice.on_cancel",
    },
    "Customer": {
        "validate": "posawesome.posawesome.api.customer.validate",
        "after_insert": "posawesome.posawesome.api.customer.after_insert",
    },
    "Bin": {
        "after_insert": [
            "posawesome.posawesome.stock_realtime.publish_bin_stock_change",
            "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
        ],
        "on_update": [
            "posawesome.posawesome.stock_realtime.publish_bin_stock_change",
            "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
        ],
    },
    "Stock Ledger Entry": {
        "after_insert": "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
        "on_cancel": "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
    },
    "Serial No": {
        "after_insert": "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
        "on_update": "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
    },
    "Batch": {
        "after_insert": "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
        "on_update": "posawesome.posawesome.api.item_fetchers.clear_stock_caches",
    },
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"posawesome.tasks.all"
# 	],
# 	"daily": [
# 		"posawesome.tasks.daily"
# 	],
# 	"hourly": [
# 		"posawesome.tasks.hourly"
# 	],
# 	"weekly": [
# 		"posawesome.tasks.weekly"
# 	]
# 	"monthly": [
# 		"posawesome.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "posawesome.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "posawesome.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "posawesome.task.get_dashboard_data"
# }

# Override standard DocTypes with custom classes
override_doctype_class = {
    "POS Invoice": "posawesome.posawesome.overrides.pos_invoice.CustomPOSInvoice",
    "POS Invoice Merge Log": "posawesome.posawesome.overrides.pos_invoice_merge_log.CustomPOSInvoiceMergeLog",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                (
                    "Sales Invoice-posa_pos_opening_shift",
                    "POS Invoice-posa_pos_opening_shift",
                    "POS Profile-posa_pos_awesome_settings",
                    "POS Profile-posa_section_pricing_controls",
                    "POS Profile-posa_section_sales_returns",
                    "POS Profile-posa_section_sales_purchase",
                    "POS Profile-posa_section_inventory_controls",
                    "POS Profile-posa_section_print_delivery",
                    "POS Profile-posa_section_cash_movement",
                    "POS Profile-posa_allow_delete",
                    "POS Profile-posa_allow_user_to_edit_rate",
                    "POS Profile-posa_allow_user_to_edit_additional_discount",
                    "POS Profile-posa_allow_user_to_edit_item_discount",
                    "POS Profile-posa_display_items_in_stock",
                    "POS Profile-posa_allow_submissions_in_background_job",
                    "POS Profile-posa_allow_partial_payment",
                    "POS Profile-posa_allow_credit_sale",
                    "POS Profile-posa_pos_awesome_advance_settings",
                    "Batch-posa_batch_price",
                    "POS Profile-posa_max_discount_allowed",
                    "POS Profile-posa_enable_below_cost_guard",
                    "POS Profile-posa_below_cost_action",
                    "POS Profile-posa_minimum_margin_percentage",
                    "POS Profile-posa_missing_cost_action",
                    "POS Profile-posa_allow_return",
                    "POS Profile-posa_allow_return_without_invoice",
                    "POS Profile-posa_allow_free_batch_return",
                    "POS Profile-posa_col_1",
                    "POS Profile-create_pos_invoice_instead_of_sales_invoice",
                    "POS Invoice-posa_is_printed",
                    "Sales Invoice-posa_is_printed",
                    "Sales Invoice Reference-pos_invoice",
                    "POS Profile-posa_local_storage",
                    "POS Profile-posa_force_server_items",
                    "POS Profile-posa_cash_mode_of_payment",
                    "POS Profile-use_customer_credit",
                    "POS Profile-posa_use_gift_cards",
                    "POS Profile-posa_allow_supervisor_manage_gift_cards",
                    "Sales Invoice-gift_card_redemptions",
                    "POS Invoice-gift_card_redemptions",
                    "POS Profile-use_cashback",
                    "POS Profile-posa_hide_closing_shift",
                    "Customer-posa_discount",
                    "POS Profile-posa_apply_customer_discount",
                    "Sales Invoice-posa_offers",
                    "POS Invoice-posa_offers",
                    "Sales Invoice-posa_coupons",
                    "POS Invoice-posa_coupons",
                    "Sales Invoice Item-posa_offers",
                    "POS Invoice Item-posa_offers",
                    "Sales Invoice Item-posa_row_id",
                    "POS Invoice Item-posa_row_id",
                    "Sales Invoice Item-posa_offer_applied",
                    "POS Invoice Item-posa_offer_applied",
                    "Sales Invoice Item-posa_is_offer",
                    "POS Invoice Item-posa_is_offer",
                    "Sales Invoice Item-posa_is_replace",
                    "POS Invoice Item-posa_is_replace",
                    "POS Profile-posa_auto_set_batch",
                    "POS Profile-posa_search_serial_no",
                    "Sales Invoice-posa_additional_notes_section",
                    "POS Invoice-posa_additional_notes_section",
                    "Sales Invoice-posa_notes",
                    "Sales Invoice-posa_authorization_code",
                    "POS Invoice-posa_notes",
                    "POS Invoice-posa_authorization_code",
                    "Sales Invoice-posa_column_break_111",
                    "POS Invoice-posa_column_break_111",
                    "Sales Invoice-posa_delivery_date",
                    "POS Invoice-posa_delivery_date",
                    "Sales Invoice Item-posa_notes",
                    "POS Invoice Item-posa_notes",
                    "Sales Invoice Item-posa_delivery_date",
                    "POS Invoice Item-posa_delivery_date",
                    "Sales Order-posa_additional_notes_section",
                    "Sales Order-posa_notes",
                    "Sales Order Item-posa_notes",
                    "POS Profile-posa_allow_sales_order",
                    "POS Profile-custom_allow_select_sales_order",
                    "POS Profile-posa_create_only_sales_order",
                    "POS Profile-posa_column_break_112",
                    "POS Profile-posa_show_template_items",
                    "POS Profile-posa_hide_variants_items",
                    "Customer-posa_referral_code",
                    "POS Profile-posa_fetch_coupon",
                    "Company-posa_referral_section",
                    "Company-posa_auto_referral",
                    "Company-posa_column_break_22",
                    "Company-posa_customer_offer",
                    "Company-posa_primary_offer",
                    "Company-posa_referral_campaign",
                    "Customer-posa_referral_company",
                    "Customer-posa_referral_section",
                    "Customer-posa_birthday",
                    "Sales Order-posa_offers",
                    "Sales Order-posa_coupons",
                    "Sales Order Item-posa_row_id",
                    "POS Profile-posa_tax_inclusive",
                    "POS Profile-posa_use_percentage_discount",
                    "POS Profile-posa_allow_customer_purchase_order",
                    "POS Profile-posa_allow_purchase_order",
                    "POS Profile-posa_allow_purchase_receipt",
                    "POS Profile-posa_allow_create_purchase_items",
                    "POS Profile-posa_allow_create_purchase_suppliers",
                    "POS Profile-posa_allow_print_last_invoice",
                    "POS Profile-posa_display_additional_notes",
                    "POS Profile-posa_display_authorization_code",
                    "POS Profile-posa_allow_write_off_change",
                    "POS Profile-posa_new_line",
                    "POS Profile-posa_input_qty",
                    "POS Profile-posa_focus_cart_qty_after_item_add",
                    "POS Profile-posa_display_item_code",
                    "POS Profile-posa_allow_zero_rated_items",
                    "POS Profile-posa_allow_print_draft_invoices",
                    "POS Profile-posa_allow_select_print_format_in_payments",
                    "Address-posa_delivery_charges",
                    "Sales Invoice-posa_delivery_charges",
                    "Sales Invoice-posa_delivery_charges_rate",
                    "POS Invoice-posa_delivery_charges",
                    "POS Invoice-posa_delivery_charges_rate",
                    "POS Profile-posa_auto_set_delivery_charges",
                    "POS Profile-posa_use_delivery_charges",
                    "POS Profile-hide_expected_amount",
                    "POS Profile-posa_display_discount_percentage",
                    "POS Profile-posa_display_discount_amount",
                    "POS Profile-posa_allow_change_posting_date",
                    "POS Profile-posa_default_card_view",
                    "POS Profile-posa_default_sales_order",
                    "POS Profile-column_break_dqsba",
                    "POS Profile-posa_use_server_cache",
                    "POS Profile-posa_server_cache_duration",
                    "POS Profile-posa_fast_counter_mode",
                    "POS Profile-posa_hot_catalog_limit",
                    "POS Profile-posa_fast_counter_positive_stock_only",
                    "POS Profile-posa_allow_item_quick_edit",
                    "POS Profile-posa_ui_template",
                    "Item-retailmind_short_name",
                    "Item-retailmind_controlled_item",
                    "Item-retailmind_non_discountable",
                    "Item-retailmind_locked_for_sale",
                    "POS Profile-posa_allow_duplicate_customer_names",
                    "POS Profile-column_break_anyol",
                    "POS Profile-pose_use_limit_search",
                    "POS Profile-posa_search_batch_no",
                    "POS Profile-pos_awesome_payments",
                    "POS Profile-posa_use_pos_awesome_payments",
                    "POS Profile-posa_allow_make_new_payments",
                    "POS Profile-posa_allow_reconcile_payments",
                    "POS Profile-column_break_uolvm",
                    "POS Profile-posa_allow_mpesa_reconcile_payments",
                    "POS Profile-posa_enable_print_audit",
                    "POS Profile-posa_default_printer_profile",
                    "POS Profile-posa_qz_printer_name",
                    "POS Profile-posa_enable_camera_scanning",
                    "POS Profile-posa_camera_scan_type",
                    "POS Profile-posa_language",
                    "POS Profile-posa_enable_return_validity",
                    "POS Profile-posa_return_validity_days",
                    "POS Profile-posa_enable_cash_movement",
                    "POS Profile-posa_allow_pos_expense",
                    "POS Profile-posa_allow_cash_deposit",
                    "POS Profile-posa_default_expense_account",
                    "POS Profile-posa_allowed_expense_accounts",
                    "POS Profile-posa_default_source_account",
                    "POS Profile-posa_allow_source_account_override",
                    "POS Profile-posa_allowed_source_accounts",
                    "POS Profile-posa_back_office_cash_account",
                    "POS Profile-posa_allow_cancel_submitted_cash_movement",
                    "POS Profile-posa_allow_delete_cancelled_cash_movement",
                    "POS Profile-posa_require_cash_movement_remarks",
                    "POS Profile-posa_cash_movement_max_amount",
                    "POS Profile-posa_section_awesome_dashboard",
                    "POS Profile-posa_enable_awesome_dashboard",
                    "POS Profile-posa_allow_company_dashboard_scope",
                    "POS Profile-posa_low_stock_alert_threshold",
                    "POS Settings-posa_enable_return_validity",
                    "POS Settings-posa_return_validity_days",
                    "POS Settings-posa_section_dashboard",
                    "POS Settings-posa_enable_awesome_dashboard_global",
                    "POS Settings-posa_dashboard_default_scope",
                    "POS Settings-posa_dashboard_low_stock_alert_threshold",
                    "POS Invoice-posa_return_valid_upto",
                    "Sales Invoice-posa_return_valid_upto",
                    "Sales Invoice-posa_cashier",
                    "POS Invoice-posa_cashier",
                    "Sales Invoice-posa_below_cost_override",
                    "Sales Invoice-posa_below_cost_override_by",
                    "Sales Invoice-posa_below_cost_override_reason",
                    "Sales Invoice-posa_below_cost_override_details",
                    "POS Invoice-posa_below_cost_override",
                    "POS Invoice-posa_below_cost_override_by",
                    "POS Invoice-posa_below_cost_override_reason",
                    "POS Invoice-posa_below_cost_override_details",
                    "User-posa_pos_pin",
                    "User-custom_manager_badge",
                    "Sales Invoice-custom_fiscal_fd_number",
                    "Sales Invoice-custom_fiscal_fpd",
                    "Sales Invoice-custom_fiscal_shift_number",
                    "Sales Invoice-custom_fiscal_status",
                    "Sales Invoice-custom_fiscal_attempt",
                    "Sales Invoice-custom_fiscal_payload",
                    "Sales Invoice-custom_sales_person",
                    "POS Invoice-custom_fiscal_fd_number",
                    "POS Invoice-custom_fiscal_fpd",
                    "POS Invoice-custom_fiscal_shift_number",
                    "POS Invoice-custom_fiscal_status",
                    "POS Invoice-custom_fiscal_attempt",
                    "POS Invoice-custom_fiscal_payload",
                    "POS Invoice-custom_sales_person",
                    "POS Profile-posa_fiscal_section",
                    "POS Profile-posa_fiscal_printer_url",
                    "POS Profile-posa_fiscal_bridge_url",
                    "POS Profile-posa_unlimited_cashier_returns",
                    "POS Profile-posa_section_customer_display",
                    "POS Profile-posa_enable_customer_display",
                    "POS Profile-posa_auto_open_customer_display",
                    "POS Invoice-posa_client_request_id",
                    "POS Invoice-posa_redeemed_customer_credit",
                    "POS Invoice-posa_remaining_customer_credit_balance",
                    "POS Profile-custom_allow_create_quotation",
                    "POS Profile-posa_allow_delete_offline_invoice",
                    "POS Profile-posa_allow_line_item_name_override",
                    "POS Profile-posa_allow_offline_sale_without_stock_verification",
                    "POS Profile-posa_allow_price_list_rate_change",
                    "POS Profile-posa_block_sale_beyond_available_qty",
                    "POS Profile-posa_brand_logo",
                    "POS Profile-posa_brand_name",
                    "POS Profile-posa_brand_short_name",
                    "POS Profile-posa_branding_section",
                    "POS Profile-posa_default_country",
                    "POS Profile-posa_enable_custom_branding",
                    "POS Profile-posa_force_price_from_customer_price_list",
                    "POS Profile-posa_force_reload_items",
                    "POS Profile-posa_gift_card_liability_account",
                    "POS Profile-posa_open_print_in_new_tab",
                    "POS Profile-posa_print_format_rules",
                    "POS Profile-posa_raw_print_width",
                    "POS Profile-posa_raw_printing",
                    "POS Profile-posa_sales_persons",
                    "POS Profile-posa_search_limit",
                    "POS Profile-posa_show_custom_name_marker_on_print",
                    "POS Profile-posa_show_customer_balance",
                    "POS Profile-posa_silent_print",
                    "POS Profile-posa_smart_reload_mode",
                    "Payment Entry-posa_client_request_id",
                    "Sales Invoice Item-name_overridden",
                    "Sales Invoice-posa_client_request_id",
                    "Sales Invoice-posa_redeemed_customer_credit",
                    "Sales Invoice-posa_remaining_customer_credit_balance",
                ),
            ]
        ],
    },
    {
        "doctype": "Role",
        "filters": [["name", "in", ("POS Awesome Supervisor",)]],
    },
    {
        "doctype": "Property Setter",
        "filters": [
            [
                "name",
                "in",
                (
                    "Sales Invoice-posa_pos_opening_shift-no_copy",
                    "POS Invoice-posa_pos_opening_shift-no_copy",
                    "Sales Invoice Reference-sales_invoice-reqd",
                    "Sales Invoice-update_outstanding_for_self-default",
                ),
            ]
        ],
    },
    {
        "doctype": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    "POS Profile-posa_allow_multi_currency",
                    "POS Profile-posa_decimal_precision",
                ],
            ]
        ],
    },
]

# Permissions for Custom DocTypes
# --------------------------------
permissions = []

# ERPNext remains usable without POS Awesome; POS requests fail closed without this adapter.
expense_pos_context_validator = "posawesome.posawesome.api.expense_context.validate_context"
doc_events["Quick Expense"] = {
    "validate": "posawesome.posawesome.api.expense_context.validate_profile_expense_limits",
}
doc_events["POS Opening Shift"] = {
    "before_insert": "posawesome.posawesome.shift_review.transfers.lock_register_opening",
    "before_submit": "posawesome.posawesome.shift_review.transfers.lock_register_opening",
}
doc_events["POS Cash Movement"] = {
    "validate": "posawesome.posawesome.api.expense_context.validate_legacy_expense",
    "before_cancel": "posawesome.posawesome.api.expense_context.before_cancel_legacy_expense",
    "on_trash": "posawesome.posawesome.api.expense_context.protect_legacy_expense_history",
}
has_permission = {
    "POS Cash Movement": "posawesome.posawesome.api.expense_context.legacy_has_permission",
}
permission_query_conditions = {
    "POS Cash Movement": "posawesome.posawesome.api.expense_context.legacy_permission_query_conditions",
}

# Optional legacy history extension: ERPNext never imports POS Awesome.
expense_history_adapters = "posawesome.posawesome.api.expense_history.adapters"
expense_history_detail = "posawesome.posawesome.api.expense_history.detail"
expense_history_links = "posawesome.posawesome.shift_review.journey.expense_links"

# Review evidence and native source lifecycle share the accounting transaction.
for _doctype in ("Sales Invoice", "POS Invoice", "Payment Entry", "Quick Expense", "POS Cash Movement"):
    _events = doc_events.setdefault(_doctype, {})
    _previous = _events.get("before_submit", [])
    _events["before_submit"] = ([_previous] if isinstance(_previous, str) else list(_previous)) + [
        "posawesome.posawesome.shift_review.closing.guard_shift_source"
    ]
    _previous = _events.get("before_cancel", [])
    _events["before_cancel"] = ([_previous] if isinstance(_previous, str) else list(_previous)) + [
        "posawesome.posawesome.shift_review.closing.lock_shift_source_cancellation"
    ]
for _doctype in ("Journal Entry", "Payment Entry", "Quick Expense", "POS Cash Movement", "Sales Invoice", "POS Invoice"):
    _events = doc_events.setdefault(_doctype, {})
    _previous = _events.get("on_cancel", [])
    _events["on_cancel"] = ([_previous] if isinstance(_previous, str) else list(_previous)) + [
        "posawesome.posawesome.shift_review.lifecycle.changed"
    ]
doc_events.setdefault("Journal Entry", {})["before_submit"] = "posawesome.posawesome.shift_review.lifecycle.lock_reversal_source"
doc_events["Journal Entry"]["on_submit"] = "posawesome.posawesome.shift_review.lifecycle.changed"
has_permission.update({
    "POS Shift Review": "posawesome.posawesome.shift_review.policy.has_permission",
    "POS Shift Review Action": "posawesome.posawesome.shift_review.policy.action_has_permission",
    "POS Shift Source Claim": "posawesome.posawesome.shift_review.policy.action_has_permission",
})
permission_query_conditions.update({
    "POS Shift Review": "posawesome.posawesome.shift_review.policy.query_conditions",
    "POS Shift Review Action": "posawesome.posawesome.shift_review.policy.action_query_conditions",
    "POS Shift Source Claim": "posawesome.posawesome.shift_review.policy.claim_query_conditions",
})
