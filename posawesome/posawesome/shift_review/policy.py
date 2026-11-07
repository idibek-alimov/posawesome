"""Review capability is separate from shift closing and native accounting privileges."""

import frappe
from frappe import _
from erpnext.accounts.expense_services import policy as expense_policy
from posawesome.posawesome.api.expense_context import validate_context

MANAGERS = {"Retail Manager", "Retail Owner", "Accounts Manager"}
APPROVERS = {"Retail Owner", "Accounts Manager"}


def require_schema():
    if not frappe.db.has_column("POS Closing Shift", "shift_review") or not frappe.db.table_exists("POS Shift Review Action"):
        frappe.throw(_("The shift review upgrade requires a site migration before closing or resolving shifts."))


def is_manager(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(MANAGERS.intersection(frappe.get_roles(user)))


def require_approver():
    if frappe.session.user != "Administrator" and not APPROVERS.intersection(frappe.get_roles()):
        frappe.throw(_("Only the owner or Accounts Manager can approve a loss or surplus."), frappe.PermissionError)


def scope(review, write=False, user=None):
    # Desk getdoc and print paths check permission again after removing level-1
    # fields. Authorize against the stored evidence without putting that evidence
    # back on the already-redacted response Document.
    if review.name and not review.get("snapshot_json"):
        review = frappe.get_doc("POS Shift Review", review.name)
    user = user or frappe.session.user
    manager = is_manager(user)
    if user == "Guest" or (write and not manager):
        frappe.throw(_("An authorized manager is required to change a shift review."), frappe.PermissionError)
    expense_policy.check_company(review.company, user=user)
    context = validate_context(review.company, review.pos_profile, review.pos_opening_shift,
                               "POS Correction" if manager else "POS", "read", user)
    if context["pos_profile"] != review.pos_profile or (not manager and review.cashier != user):
        frappe.throw(_("You do not have access to this shift review."), frappe.PermissionError)
    from .snapshot import read
    evidence = read(review)
    accounts = {row.account for row in review.get("accounts", []) if row.account}
    accounts.update(row.get("account") for row in evidence["methods"] if row.get("account"))
    for account in sorted(accounts):
        expense_policy.check_user_scope("Account", account, user=user)
    return review


def has_permission(doc, ptype=None, user=None, **kwargs):
    if ptype not in {"read", "select", "print", "export", "report"}:
        return False
    try:
        scope(doc, user=user)
    except (frappe.PermissionError, frappe.ValidationError, frappe.DoesNotExistError):
        return False
    return None


def query_conditions(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return ""
    roles = set(frappe.get_roles(user))
    if not roles.intersection(MANAGERS | {"Retail Cashier", "Sales User"}):
        return "1=0"
    actor = frappe.db.escape(user)
    conditions = []
    if not roles.intersection(MANAGERS):
        conditions.append(f"`tabPOS Shift Review`.cashier = {actor}")
    if not roles.intersection(APPROVERS):
        conditions.append(f"""exists (select p.name from `tabPOS Profile` p
            where p.name = `tabPOS Shift Review`.pos_profile and
            (not exists (select u.name from `tabPOS Profile User` u where u.parent=p.name and u.parenttype='POS Profile')
            or exists (select u.name from `tabPOS Profile User` u where u.parent=p.name and u.parenttype='POS Profile' and u.user={actor})))""")
    # Native Company/Profile user permissions are also compiled by get_list. Child
    # funding accounts need an explicit scope condition to protect list exports.
    from frappe.permissions import get_allowed_docs_for_doctype, get_user_permissions
    permissions = get_user_permissions(user)
    # scope() also uses the shared expense adapter. Its applicable-for permissions
    # must hold on list/export paths, even when they target Quick Expense rather
    # than this new DocType. Apply the native linked-record scopes conservatively.
    for doctype, field, contexts in (
        ("Company", "company", ("Quick Expense", "POS Profile", "Account", "Company")),
        ("POS Profile", "pos_profile", ("Quick Expense", "POS Profile")),
    ):
        for context in contexts:
            allowed = get_allowed_docs_for_doctype(permissions.get(doctype, []), context)
            if allowed:
                values = ", ".join(frappe.db.escape(name) for name in allowed)
                conditions.append(f"`tabPOS Shift Review`.{field} in ({values})")
    for context in ("POS Shift Review", "Quick Expense", "Account"):
        allowed = get_allowed_docs_for_doctype(permissions.get("Account", []), context)
        if allowed:
            accounts = ", ".join(frappe.db.escape(name) for name in allowed)
            conditions.append(f"""not exists (select a.name from `tabPOS Shift Review Account` a
                where a.parent=`tabPOS Shift Review`.name and coalesce(a.account,'')!='' and a.account not in ({accounts}))""")
    return " and ".join(f"({condition})" for condition in conditions)


def action_has_permission(doc, ptype=None, user=None, **kwargs):
    if ptype not in {"read", "select", "print", "export", "report"} or not is_manager(user):
        return False
    try:
        scope(frappe.get_doc("POS Shift Review", doc.review), user=user)
    except (frappe.PermissionError, frappe.ValidationError, frappe.DoesNotExistError):
        return False
    return None


def action_query_conditions(user=None):
    if not is_manager(user):
        return "1=0"
    permitted = frappe.get_list("POS Shift Review", fields=["name"], limit_page_length=0, run=False, order_by="", user=user or frappe.session.user)
    if not isinstance(permitted, str):
        return "1=0"
    return f"`tabPOS Shift Review Action`.review in ({permitted})"


def claim_query_conditions(user=None):
    return action_query_conditions(user).replace("`tabPOS Shift Review Action`", "`tabPOS Shift Source Claim`")
