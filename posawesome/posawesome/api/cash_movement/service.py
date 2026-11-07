import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from .permissions import (
    ensure_cancel_allowed,
    ensure_delete_allowed,
    ensure_feature_enabled,
    ensure_movement_allowed,
    ensure_owner_or_manager,
    is_manager,
)
from .queries import get_shift_movements, get_submitted_expenses as query_submitted_expenses
from .validation import (
    extract_allowed_accounts,
    ensure_no_duplicate_client_request,
    get_opening_shift,
    get_pos_profile,
    parse_payload,
    resolve_source_cash_account,
    resolve_target_account,
    validate_account_company,
    validate_amount,
    validate_company_consistency,
    validate_remarks,
)


def _enforce_shift_access(pos_opening_shift):
    shift_user = frappe.db.get_value("POS Opening Shift", pos_opening_shift, "user")
    if not shift_user:
        frappe.throw(_("POS Opening Shift not found."))
    if shift_user != frappe.session.user and not is_manager():
        frappe.throw(_("You are not allowed to access this shift."))


def _authorized_replay(existing, data, movement_type):
    """A receipt lookup may survive closure/config changes; it never posts money."""
    from decimal import Decimal, InvalidOperation
    from erpnext.accounts.expense_services.policy import check_company, check_user_scope, currency_precision
    from posawesome.posawesome.api.expense_context import validate_context

    if existing.user != frappe.session.user or existing.owner != frappe.session.user:
        frappe.throw(_("This request ID belongs to a different cash movement."), frappe.PermissionError)
    check_company(existing.company)
    check_user_scope("Account", existing.source_account)
    check_user_scope("Account", existing.target_account)
    validate_context(existing.company, existing.pos_profile, existing.pos_opening_shift,
                     "POS", "read", frappe.session.user, legacy=True)
    existing.check_permission("read")
    expected = {"pos_opening_shift": existing.pos_opening_shift, "pos_opening_shift_name": existing.pos_opening_shift,
                "pos_profile": existing.pos_profile, "pos_profile_name": existing.pos_profile,
                "company": existing.company, "movement_type": movement_type}
    if existing.movement_type != movement_type or any(data.get(key) and data[key] != value for key, value in expected.items()):
        frappe.throw(_("This request ID belongs to a different cash movement."), frappe.PermissionError)
    try:
        amount = Decimal(str(data.get("amount")))
        if not amount.is_finite() or Decimal(str(flt(amount, currency_precision(existing.company)))) != Decimal(str(existing.amount)):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(_("This request ID was already used with different movement details."))
    for key in ("source_account", "expense_account", "target_account", "against_name", "remarks"):
        supplied = key in data and (key in {"remarks", "against_name"} or bool(data.get(key)))
        if supplied and str(data.get(key) or "").strip() != (existing.get(key) or ""):
            frappe.throw(_("This request ID was already used with different movement details."))
    if data.get("posting_date") and getdate(data["posting_date"]) != getdate(existing.posting_date):
        frappe.throw(_("This request ID was already used with different movement details."))
    return existing.as_dict()


def _create_cash_movement(payload, movement_type):
    from erpnext.accounts.expense_services.commands import lock_actor

    data = parse_payload(payload)
    if data.get("movement_type") and data.get("movement_type") != movement_type:
        frappe.throw(_("The movement type does not match the original request."))
    # Serialize before looking for the old ID, including under REPEATABLE READ.
    lock_actor()
    existing = ensure_no_duplicate_client_request(data.get("client_request_id"))
    if existing:
        return _authorized_replay(existing, data, movement_type)
    opening_shift_name = data.get("pos_opening_shift") or data.get("pos_opening_shift_name")
    opening_shift = get_opening_shift(opening_shift_name)
    profile_name = data.get("pos_profile") or data.get("pos_profile_name") or opening_shift.pos_profile
    profile_doc = get_pos_profile(profile_name)
    validate_company_consistency(opening_shift, profile_doc)
    ensure_feature_enabled(profile_doc)
    ensure_movement_allowed(profile_doc, movement_type)
    amount = validate_amount(data.get("amount"), profile_doc)
    remarks = (data.get("remarks") or "").strip()
    against_name = (data.get("against_name") or "").strip()
    validate_remarks(remarks, profile_doc)

    source_account = resolve_source_cash_account(data, profile_doc)
    target_account, expense_account = resolve_target_account(data, profile_doc, movement_type)

    validate_account_company(source_account, profile_doc.company, _("Source account"))
    validate_account_company(target_account, profile_doc.company, _("Target account"))

    if movement_type == "Deposit" and source_account == target_account:
        frappe.throw(_("Source and target accounts cannot be the same for cash deposit."))

    movement_doc = frappe.get_doc(
        {
            "doctype": "POS Cash Movement",
            "posting_date": data.get("posting_date") or nowdate(),
            "company": profile_doc.company,
            "pos_profile": profile_doc.name,
            "pos_opening_shift": opening_shift.name,
            "user": frappe.session.user,
            "movement_type": movement_type,
            "amount": amount,
            "against_name": against_name,
            "source_account": source_account,
            "target_account": target_account,
            "expense_account": expense_account,
            "remarks": remarks,
            "client_request_id": data.get("client_request_id"),
        }
    )
    movement_doc.flags.ignore_permissions = True
    movement_doc.insert()
    # The backing Journal Entry is created atomically inside the document's
    # on_submit hook, so insert + JE + submit either all succeed or all roll
    # back together (no orphan JE on a submit-time failure).
    movement_doc.submit()
    movement_doc.reload()
    return movement_doc.as_dict()


@frappe.whitelist()
def get_cash_movement_request_outcome(client_request_id):
    from erpnext.accounts.expense_services.commands import lock_actor

    if not isinstance(client_request_id, str) or not client_request_id.strip() or len(client_request_id) > 140:
        frappe.throw(_("A stable request ID is required. Refresh the expense form and try again."))
    lock_actor()
    existing = ensure_no_duplicate_client_request(client_request_id)
    if not existing:
        return {"status": "not_found", "client_request_id": client_request_id}
    # Reuse full original-intent authorization; there is no create permission or open-shift requirement.
    data = dict(existing.as_dict(), amount=existing.amount)
    _authorized_replay(existing, data, existing.movement_type)
    return dict(name=existing.name, docstatus=existing.docstatus, journal_entry=existing.journal_entry,
        status={0: "draft", 1: "submitted", 2: "cancelled"}.get(existing.docstatus, "unknown"))


@frappe.whitelist()
def get_cash_movement_context(pos_profile=None, pos_opening_shift=None):
    profile_name = pos_profile
    if not profile_name and pos_opening_shift:
        profile_name = frappe.db.get_value("POS Opening Shift", pos_opening_shift, "pos_profile")
    if not profile_name:
        frappe.throw(_("POS Profile is required."))

    profile_doc = get_pos_profile(profile_name)
    allowed_expense_accounts = extract_allowed_accounts(profile_doc.get("posa_allowed_expense_accounts"))
    allowed_source_accounts = extract_allowed_accounts(profile_doc.get("posa_allowed_source_accounts"))
    default_source_account = None
    try:
        default_source_account = resolve_source_cash_account({}, profile_doc)
    except Exception:
        default_source_account = None

    shared_expense_ready = False
    if pos_opening_shift:
        from erpnext.accounts.expense_services import policy
        from erpnext.accounts.page.expense_desk.expense_desk import get_categories
        try:
            with policy.quiet_setup_checks():
                context = policy.get_context(profile_doc.company, profile_doc.name, pos_opening_shift, action="read")
                shift = frappe.db.get_value("POS Opening Shift", pos_opening_shift, ["status", "docstatus"], as_dict=True)
                shared_expense_ready = bool(shift and shift.docstatus == 1 and shift.status == "Open" and not profile_doc.disabled
                    and all(frappe.has_permission("Quick Expense", action) for action in ("create", "submit"))
                    and policy.get_sources(context) and get_categories(profile_doc.company))
        except (frappe.PermissionError, frappe.ValidationError):
            pass  # Keep the original entry available until explicit shared setup is usable.
    return {
        "shared_expense_ready": shared_expense_ready,
        "pos_profile": profile_doc.name,
        "company": profile_doc.company,
        "currency": profile_doc.currency,
        "enable_cash_movement": bool(profile_doc.get("posa_enable_cash_movement")),
        "allow_pos_expense": bool(profile_doc.get("posa_allow_pos_expense")),
        "allow_cash_deposit": bool(profile_doc.get("posa_allow_cash_deposit")),
        "allow_cancel_submitted_cash_movement": bool(
            profile_doc.get("posa_allow_cancel_submitted_cash_movement")
        ),
        "allow_delete_cancelled_cash_movement": bool(
            profile_doc.get("posa_allow_delete_cancelled_cash_movement")
        ),
        "require_cash_movement_remarks": bool(profile_doc.get("posa_require_cash_movement_remarks")),
        "cash_movement_max_amount": profile_doc.get("posa_cash_movement_max_amount"),
        "default_expense_account": profile_doc.get("posa_default_expense_account"),
        "allowed_expense_accounts": allowed_expense_accounts,
        "default_source_account": default_source_account,
        "allow_source_account_override": bool(profile_doc.get("posa_allow_source_account_override")),
        "allowed_source_accounts": allowed_source_accounts,
        "back_office_cash_account": profile_doc.get("posa_back_office_cash_account"),
        "cash_mode_of_payment": profile_doc.get("posa_cash_mode_of_payment"),
        "cost_center": profile_doc.get("cost_center"),
    }


@frappe.whitelist(methods=["POST"])
def create_pos_expense(payload):
    return _create_cash_movement(payload, "Expense")


@frappe.whitelist(methods=["POST"])
def create_cash_deposit(payload):
    return _create_cash_movement(payload, "Deposit")


@frappe.whitelist()
def get_shift_cash_movements(
    pos_opening_shift,
    movement_type=None,
    status="submitted",
    search_text=None,
    limit_start=0,
    limit_page_length=50,
):
    _enforce_shift_access(pos_opening_shift)
    return get_shift_movements(
        pos_opening_shift=pos_opening_shift,
        movement_type=movement_type,
        status=status,
        search_text=search_text,
        limit_start=limit_start,
        limit_page_length=limit_page_length,
    )


@frappe.whitelist()
def get_submitted_expenses(pos_opening_shift, limit_start=0, limit_page_length=50):
    _enforce_shift_access(pos_opening_shift)
    return query_submitted_expenses(
        pos_opening_shift=pos_opening_shift,
        limit_start=limit_start,
        limit_page_length=limit_page_length,
    )


@frappe.whitelist(methods=["POST"])
def cancel_cash_movement(name, reason=None):
    movement_doc = frappe.get_doc("POS Cash Movement", name, for_update=True)
    if movement_doc.movement_type == "Expense":
        from erpnext.accounts.expense_services.policy import require_manager
        require_manager()
        movement_doc.cancellation_reason = reason
    else:
        ensure_owner_or_manager(movement_doc)
    if movement_doc.docstatus != 1:
        frappe.throw(_("Only submitted cash movements can be cancelled."))

    profile_doc = get_pos_profile(movement_doc.pos_profile)
    ensure_feature_enabled(profile_doc)
    ensure_cancel_allowed(profile_doc)

    movement_doc.flags.ignore_permissions = True
    movement_doc.cancel()
    return {"name": movement_doc.name, "docstatus": movement_doc.docstatus}


@frappe.whitelist(methods=["POST"])
def delete_cash_movement(name):
    movement_doc = frappe.get_doc("POS Cash Movement", name)
    ensure_owner_or_manager(movement_doc)
    if movement_doc.docstatus != 2:
        frappe.throw(_("Only cancelled cash movements can be deleted."))

    profile_doc = get_pos_profile(movement_doc.pos_profile)
    ensure_feature_enabled(profile_doc)
    ensure_delete_allowed(profile_doc)

    movement_doc.delete(ignore_permissions=True)
    return {"deleted": name}


@frappe.whitelist(methods=["POST"])
def duplicate_cash_movement(name, posting_date=None):
    movement_doc = frappe.get_doc("POS Cash Movement", name)
    ensure_owner_or_manager(movement_doc)
    if movement_doc.docstatus not in (1, 2):
        frappe.throw(_("Only submitted or cancelled cash movements can be duplicated."))

    payload = {
        "pos_profile": movement_doc.pos_profile,
        "pos_opening_shift": movement_doc.pos_opening_shift,
        "amount": movement_doc.amount,
        "against_name": movement_doc.get("against_name"),
        "source_account": movement_doc.source_account,
        "remarks": movement_doc.remarks,
    }

    if movement_doc.movement_type == "Expense":
        payload["expense_account"] = movement_doc.expense_account
    else:
        payload["target_account"] = movement_doc.target_account

    if posting_date:
        try:
            payload["posting_date"] = str(getdate(posting_date))
        except Exception:
            frappe.throw(_("Invalid posting date."))

    return _create_cash_movement(payload, movement_doc.movement_type)
