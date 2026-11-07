"""Optional ERPNext expense adapter. The stored shift establishes register scope."""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.expense_services.policy import CASHIER_ROLES, check_user_scope, is_manager


@frappe.whitelist()
def get_pos_expense_session(pos_opening_shift=None):
    """Read-only session discovery; never invoke register bootstrap/setup writes."""
    from erpnext.accounts.expense_services import policy

    filters = dict(user=frappe.session.user, docstatus=1, status="Open",
                   pos_closing_shift=["is", "not set"])
    if pos_opening_shift:
        filters["name"] = pos_opening_shift
    shifts = frappe.get_list("POS Opening Shift", filters=filters,
                             fields=["name", "company", "pos_profile"], limit_page_length=2)
    if not shifts:
        return dict(status="no_shift")
    if len(shifts) != 1:
        return dict(status="select_shift")
    shift = shifts[0]
    context = policy.get_context(shift.company, shift.pos_profile, shift.name, "POS", action="read")
    profile = frappe.get_cached_doc("POS Profile", context.pos_profile)
    return dict(status="ready", company=context.company, pos_profile=context.pos_profile,
                pos_opening_shift=context.pos_opening_shift,
                can_record=not profile.disabled and all(frappe.has_permission("Quick Expense", action)
                    for action in ("create", "submit")),
                note_required=bool(profile.get("posa_require_cash_movement_remarks")),
                cash_movement_enabled=bool(profile.get("posa_enable_cash_movement")))


def authorized_profile(company, pos_profile, user):
    """Shared register-read scope, including before the next shift exists."""
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    if profile.company != company:
        frappe.throw(_("The register and opening shift must belong to the same company."))
    check_user_scope("POS Profile", profile.name, user)
    if not frappe.has_permission("POS Profile", "read", doc=profile, user=user):
        frappe.throw(_("You do not have access to this register."), frappe.PermissionError)
    assigned = {r.user for r in profile.get("applicable_for_users", [])}
    owner = user == "Administrator" or bool({"Retail Owner", "Accounts Manager"}.intersection(frappe.get_roles(user)))
    if assigned and user not in assigned and not owner:
        frappe.throw(_("This register is not assigned to you."), frappe.PermissionError)
    return profile


def validate_context(company, pos_profile, pos_opening_shift, entry_context, action, user, legacy=False):
    if not pos_opening_shift and not (action == "read" and is_manager(user) and pos_profile):
        frappe.throw(_("Select the POS Opening Shift for this expense."))
    if action == "create":
        # Serialize new expenses with closing's update of the same shift row.
        frappe.db.get_value("POS Opening Shift", pos_opening_shift, "name", for_update=True)
    shift = frappe.get_doc("POS Opening Shift", pos_opening_shift, for_update=action == "create") if pos_opening_shift else None
    if shift:
        if shift.docstatus != 1 or shift.company != company:
            frappe.throw(_("Select a submitted opening shift in the expense company."))
        if pos_profile and pos_profile != shift.pos_profile:
            frappe.throw(_("The POS Profile does not match the stored opening shift."))
        pos_profile = shift.pos_profile
    profile = authorized_profile(company, pos_profile, user)
    if entry_context == "POS":
        if shift.user != user:
            frappe.throw(_("Only the shift owner can record a normal POS expense."), frappe.PermissionError)
        if not is_manager(user) and not CASHIER_ROLES.intersection(frappe.get_roles(user)) and not (legacy and action == "read"):
            frappe.throw(_("You are not authorized to record POS expenses."), frappe.PermissionError)
        if action == "create" and (shift.status != "Open" or profile.disabled):
            frappe.throw(_("An active open shift and enabled register are required."))
    elif not is_manager(user):
        frappe.throw(_("Only a manager can correct shift expenses."), frappe.PermissionError)
    accounts = set()
    for row in profile.get("payments", []):
        account = frappe.db.get_value("Mode of Payment Account",
            {"parent": row.mode_of_payment, "company": company}, "default_account")
        if account:
            accounts.add(account)
    return dict(pos_profile=profile.name, pos_opening_shift=shift.name if shift else None, source_accounts=sorted(accounts),
                note_required=bool(profile.get("posa_require_cash_movement_remarks")))


def validate_profile_expense_limits(doc, method=None):
    """Existing configured limits stay effective on the new shared expense path."""
    if not doc.pos_profile:
        return
    profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
    maximum = flt(profile.get("posa_cash_movement_max_amount"))
    if maximum > 0 and doc.amount > maximum:
        frappe.throw(_("Amount exceeds the register's configured expense limit."))
    if profile.get("posa_require_cash_movement_remarks") and not (doc.description or "").strip():
        frappe.throw(_("Enter the expense note required by this register."))


def validate_legacy_expense(doc, method=None):
    """Retain the Cash-only queue contract while guarding direct document writes."""
    if doc.movement_type not in {"Expense", "Deposit"} or doc.docstatus == 2:
        return
    from erpnext.accounts.expense_services.policy import (
        check_company, positive_amount, currency_precision, validate_account,
    )
    from posawesome.posawesome.api.cash_movement import validation, permissions

    check_company(doc.company)
    if doc.get("journal_entry"):
        frappe.throw(_("Accounting links are set by the cash movement workflow."))
    shift = validation.get_opening_shift(doc.pos_opening_shift)
    profile = validation.get_pos_profile(doc.pos_profile)
    validation.validate_company_consistency(shift, profile)
    check_user_scope("POS Profile", profile.name)
    permissions.ensure_feature_enabled(profile)
    permissions.ensure_movement_allowed(profile, doc.movement_type)
    positive_amount(doc.amount, currency_precision(doc.company))
    validation.validate_amount(doc.amount, profile)
    validation.validate_remarks(doc.remarks, profile)
    configured = profile.get("posa_default_source_account")
    cash_method = profile.get("posa_cash_mode_of_payment") or "Cash"
    if not configured and cash_method in {row.mode_of_payment for row in profile.get("payments", [])}:
        configured = frappe.db.get_value("Mode of Payment Account",
            {"parent": cash_method, "company": doc.company}, "default_account")
    approved = {configured} if configured else set()
    if profile.get("posa_allow_source_account_override"):
        approved.update(validation.extract_allowed_accounts(profile.get("posa_allowed_source_accounts")))
    if doc.source_account not in approved:
        frappe.throw(_("Configure an explicit register cash source before posting this movement."))
    default = validation.resolve_source_cash_account({}, profile)
    payload = {} if doc.source_account == default else {"source_account": doc.source_account}
    if validation.resolve_source_cash_account(payload, profile) != doc.source_account:
        frappe.throw(_("Source account must match the register's configured cash source."))
    if doc.movement_type == "Expense":
        allowed = validation.extract_allowed_accounts(profile.get("posa_allowed_expense_accounts"))
        if doc.expense_account not in set(allowed + [profile.get("posa_default_expense_account")]):
            frappe.throw(_("Configure the register's allowed expense accounts before posting this legacy expense."))
    target, _expense = validation.resolve_target_account(
        {"expense_account": doc.expense_account, "target_account": doc.target_account}, profile, doc.movement_type
    )
    if target != doc.target_account:
        frappe.throw(_("Expense account must match the register configuration."))
    validate_account(doc.source_account, doc.company)
    validate_account(doc.target_account, doc.company, expense=doc.movement_type == "Expense")
    if doc.user != frappe.session.user:
        frappe.throw(_("Only the shift owner can record a normal POS expense."), frappe.PermissionError)


def before_cancel_legacy_expense(doc, method=None):
    from erpnext.accounts.expense_services.policy import check_company, require_manager, same_stored_value
    from posawesome.posawesome.api.cash_movement import permissions

    original = frappe.get_doc("POS Cash Movement", doc.name, for_update=True)
    # A caller cannot relabel an Expense as Deposit, or replace the JE, during cancellation.
    for field in ("company", "pos_profile", "pos_opening_shift", "user", "movement_type", "amount",
                  "source_account", "target_account", "expense_account", "journal_entry", "posting_date",
                  "against_name", "remarks", "client_request_id"):
        if not same_stored_value(field, original.get(field), doc.get(field)):
            frappe.throw(_("Cancel the original movement without changing its accounting or shift links."))
    check_company(original.company)
    check_user_scope("Account", original.source_account)
    check_user_scope("Account", original.target_account)
    profile = frappe.get_cached_doc("POS Profile", original.pos_profile)
    permissions.ensure_feature_enabled(profile)
    permissions.ensure_cancel_allowed(profile)
    if original.movement_type != "Expense":
        permissions.ensure_owner_or_manager(original)
        return
    require_manager()
    validate_context(original.company, original.pos_profile, original.pos_opening_shift,
                     "POS Correction", "read", frappe.session.user)
    if not (doc.get("cancellation_reason") or "").strip():
        frappe.throw(_("Enter a reason before cancelling this expense."))
    doc.add_comment("Comment", _("Expense cancelled by {0}: {1}").format(frappe.session.user, doc.cancellation_reason))


def protect_legacy_expense_history(doc, method=None):
    if doc.movement_type == "Expense" and doc.docstatus != 0:
        frappe.throw(_("Posted expense history cannot be deleted."))


def legacy_has_permission(doc, ptype=None, user=None, **kwargs):
    stored_type = frappe.db.get_value("POS Cash Movement", doc.name, "movement_type") if ptype in {"write", "cancel", "amend", "delete"} and doc.name else None
    if doc.movement_type != "Expense" and stored_type != "Expense":
        return None
    from erpnext.accounts.expense_services.policy import check_company
    user = user or frappe.session.user
    try:
        if ptype in {"cancel", "amend", "delete"} and not is_manager(user):
            return False
        check_company(doc.company, user)
        check_user_scope("Account", doc.source_account, user)
        validate_context(doc.company, doc.pos_profile, doc.pos_opening_shift,
                         "POS Correction" if is_manager(user) else "POS", "read", user, legacy=True)
    except (frappe.PermissionError, frappe.ValidationError):
        return False
    return None


def legacy_permission_query_conditions(user=None):
    from erpnext.accounts.expense_services.policy import permission_query_conditions
    condition = permission_query_conditions(user, legacy=True).replace("`tabQuick Expense`", "`tabPOS Cash Movement`")
    return f"(`tabPOS Cash Movement`.movement_type != 'Expense' or ({condition or '1=1'}))"
