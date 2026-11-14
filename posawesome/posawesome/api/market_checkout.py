"""Narrow cashier projections and native quick-return orchestration."""
import json
import hashlib
import re
from math import isfinite
from urllib.parse import parse_qs, urlparse
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, strip_html_tags
from posawesome.posawesome.api.pos_access import get_authorized_pos_profile, get_authorized_pos_item
from posawesome.posawesome.api.fiscal import scoped_invoice
from posawesome.posawesome.api.fiscal_contract import decimal


def permitted_profiles(profile):
    names = []
    for row in frappe.get_list("POS Profile", filters={"company": profile.company, "disabled": 0}, pluck="name"):
        try:
            get_authorized_pos_profile(row, company=profile.company)
            names.append(row)
        except frappe.PermissionError:
            continue
    return names


def _sale_lookup_query(query):
    query = str(query or "").strip()[:2048]
    # A scanned URL is data only: never follow it or contact an OFD from search.
    try:
        parameters = parse_qs(urlparse(query).query or query)
    except ValueError:
        parameters = {}
    for key in ("invoice_name", "invoice", "fdNumber", "fd", "i"):
        if parameters.get(key):
            query = parameters[key][0]
            break
    return query.removeprefix("POSA:")[:140]


@frappe.whitelist()
def purchase_history(pos_profile, query="", from_date=None, to_date=None, start=0, page_length=20):
    """Shared return/ordinary-receipt list, including other permitted cashiers.

    Parameterized UNION pagination orders SI and POS together. Do not apply native
    owner-only invoice lists here: register/company authorization is the agreed scope.
    No document, printer status or print/fiscal attempt is changed by browsing.
    """
    profile = get_authorized_pos_profile(pos_profile)
    profiles = permitted_profiles(profile)
    start = max(cint(start), 0)
    page_length = min(max(cint(page_length), 1), 50)
    from_date = str(from_date or nowdate())
    to_date = str(to_date or from_date)
    try:
        if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in (from_date, to_date)) or getdate(from_date) > getdate(to_date):
            raise ValueError
    except (ValueError, TypeError):
        frappe.throw(_("Select a valid purchase date range"))
    if not profiles:
        return dict(items=[], has_more=False, start=start, page_length=page_length)

    query = _sale_lookup_query(query)
    like = "%" + query.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    # Phone searches accept spaces, parentheses, dashes and country prefixes in
    # either input or stored values, without a 100-customer preselection cutoff.
    digits = re.sub(r"\D", "", query)
    phone_query = bool(digits) and not re.search(r"[^\d\s+().-]", query)
    phone_like = "%" + (digits[-9:] if len(digits) >= 9 else digits) + "%"
    def phone_sql(field):
        result = f"COALESCE({field}, '')"
        for separator in (" ", "+", "(", ")", "-", "."):
            result = f"REPLACE({result}, '{separator}', '')"
        return result

    params = dict(company=profile.company, profiles=profiles, from_date=from_date, to_date=to_date,
                  query=query, like=like, fd=query.removeprefix("ФД").strip(" №#"),
                  phone_like=phone_like, start=start, limit=page_length + 1)
    selects = []
    for doctype in ("Sales Invoice", "POS Invoice"):
        search = " AND COALESCE(i.is_consolidated, 0) = 0" if doctype == "Sales Invoice" else ""
        if query:
            search += """ AND (i.name LIKE %(like)s OR i.custom_fiscal_fd_number = %(fd)s
                OR i.customer_name LIKE %(like)s OR c.customer_name LIKE %(like)s
                OR c.mobile_no LIKE %(like)s OR i.contact_mobile LIKE %(like)s"""
            if phone_query:
                search += f" OR {phone_sql('c.mobile_no')} LIKE %(phone_like)s OR {phone_sql('i.contact_mobile')} LIKE %(phone_like)s"
            search += ")"
        # Table identifiers are fixed constants, never request values.
        selects.append(f"""SELECT '{doctype}' AS doctype, i.name, i.pos_profile,
            i.posting_date, i.posting_time, i.customer_name, i.grand_total, i.rounded_total,
            i.currency, i.custom_fiscal_fd_number,
            COALESCE(NULLIF(i.contact_mobile, ''), c.mobile_no) AS customer_phone
            FROM `tab{doctype}` i LEFT JOIN `tabCustomer` c ON c.name = i.customer
            WHERE i.company = %(company)s AND i.pos_profile IN %(profiles)s
            AND i.docstatus = 1 AND i.is_return = 0
            AND i.posting_date BETWEEN %(from_date)s AND %(to_date)s {search}""")
    rows = frappe.db.sql(" UNION ALL ".join(selects) + " ORDER BY posting_date DESC, posting_time DESC, doctype DESC, name DESC LIMIT %(limit)s OFFSET %(start)s", params, as_dict=True)
    return dict(items=rows[:page_length], has_more=len(rows) > page_length, start=start, page_length=page_length)


@frappe.whitelist()
def receipt_data(invoice_name, doctype="Sales Invoice"):
    doc, profile = scoped_invoice(invoice_name, doctype)
    fields = ("name", "doctype", "posting_date", "posting_time", "currency", "customer", "customer_name", "is_return",
              "total", "net_total", "grand_total", "rounded_total", "discount_amount", "paid_amount", "change_amount", "loyalty_amount",
              "outstanding_amount", "total_taxes_and_charges", "posa_redeemed_customer_credit")
    result = {f: doc.get(f) for f in fields}
    result["items"] = [{f: item.get(f) for f in ("item_code", "item_name", "qty", "rate", "amount", "price_list_rate", "discount_amount", "uom")} for item in doc.items]
    line_discount = sum(max(decimal(row.get("price_list_rate") or row.rate) - decimal(row.rate), 0) * abs(decimal(row.qty)) for row in doc.items)
    result["receipt_totals"] = dict(
        subtotal=str(abs(decimal(doc.total)) + line_discount),
        discount=str(line_discount + abs(decimal(doc.discount_amount))),
        total=str(abs(decimal(doc.rounded_total or doc.grand_total))),
    )
    result["payments"] = [dict(mode_of_payment=p.mode_of_payment, amount=p.amount,
        type=frappe.get_cached_value("Mode of Payment", p.mode_of_payment, "type")) for p in doc.get("payments") or []]
    result["taxes"] = [dict(description=t.description, rate=t.rate, included_in_print_rate=t.included_in_print_rate,
        amount=t.tax_amount_after_discount_amount if t.tax_amount_after_discount_amount is not None else t.tax_amount)
        for t in doc.get("taxes") or []]
    company = frappe.get_cached_doc("Company", doc.company)
    address = doc.get("company_address") or profile.get("company_address")
    result.update(store_name=company.company_name, tax_id=company.get("tax_id") or "", address="", contacts=company.get("phone_no") or "",
                  cashier=frappe.utils.get_fullname(doc.get("posa_cashier") or doc.owner), register=profile.name)
    if address:
        addr = frappe.get_cached_doc("Address", address)
        result["address"] = ", ".join(str(addr.get(f)) for f in ("address_line1", "address_line2", "city") if addr.get(f))
        result["contacts"] = addr.get("phone") or result["contacts"]
    if doc.customer != profile.customer:
        from posawesome.posawesome.api.customers import get_customer_info
        info = get_customer_info(doc.customer, doc.company)
        result.update(loyalty_points=info.get("loyalty_points"), stored_value_balance=info.get("stored_value_balance"))
    else:
        result["customer_name"] = ""
    return result


@frappe.whitelist()
def find_sales(pos_profile, query="", by_customer=0):
    profile = get_authorized_pos_profile(pos_profile)
    profiles = permitted_profiles(profile)
    query = str(query or "").strip()[:2048]
    if not cint(by_customer):
        query = _sale_lookup_query(query)
    query = query[:140]
    if query.startswith("POSA:"):
        query = query[5:]
    filters = dict(company=profile.company, pos_profile=["in", profiles], docstatus=1, is_return=0)
    if cint(by_customer) and query:
        # Registered customers only; bounded history never exposes management fields.
        customers = frappe.get_all("Customer", or_filters={"customer_name": ["like", f"%{query}%"], "mobile_no": ["like", f"%{query}%"]}, pluck="name", limit_page_length=100)
        from erpnext.selling.page.customer_hub.customer_data import find_duplicate_phone_customer
        phone_customer = find_duplicate_phone_customer(query)
        if phone_customer and phone_customer.name not in customers:
            customers.append(phone_customer.name)
        filters["customer"] = ["in", [c for c in customers if c != profile.customer] or [""]]
    rows = []
    for doctype in ("Sales Invoice", "POS Invoice"):
        or_filters = None
        if query and not cint(by_customer):
            or_filters = {"name": ["like", f"%{query}%"], "custom_fiscal_fd_number": query.removeprefix("ФД").strip(" №#")}
        for row in frappe.get_all(doctype, filters=filters, or_filters=or_filters,
            fields=["name", "pos_profile", "posting_date", "posting_time", "customer_name", "grand_total", "currency", "custom_fiscal_fd_number", "custom_fiscal_status"],
            order_by="posting_date desc, posting_time desc", limit_page_length=30):
            row["doctype"] = doctype
            rows.append(row)
    return sorted(rows, key=lambda r: (str(r.posting_date), str(r.posting_time)), reverse=True)[:30]


@frappe.whitelist()
def return_items(invoice_name, doctype, pos_profile):
    profile = get_authorized_pos_profile(pos_profile)
    doc, _source_profile = scoped_invoice(invoice_name, doctype)
    if doc.company != profile.company or doc.is_return:
        frappe.throw(_("Select a sale in the current company"), frappe.PermissionError)
    from posawesome.posawesome.api.invoice_processing.returns import get_invoice_for_return
    result = get_invoice_for_return(invoice_name, doc.pos_profile, doctype)
    result.pop("sales_team", None)
    return result


@frappe.whitelist()
def guest_item(pos_profile, code):
    profile = get_authorized_pos_profile(pos_profile)
    code = str(code or "").strip()
    barcode = frappe.db.get_value("Item Barcode", {"barcode": code}, ["parent", "uom"], as_dict=True)
    item_code = barcode.parent if barcode else code
    item = get_authorized_pos_item(item_code, profile)
    from posawesome.posawesome.api.item_processing.details import get_items_details
    result = get_items_details(profile.name, json.dumps([{"item_code": item.name, "uom": barcode.uom if barcode else item.stock_uom}]), price_list=profile.selling_price_list, customer=profile.customer)
    if not result:
        frappe.throw(_("No selling price found"))
    row = result[0]
    return {f: row.get(f) for f in ("item_code", "item_name", "rate", "price_list_rate", "uom", "stock_uom", "conversion_factor", "has_batch_no", "has_serial_no")}


@frappe.whitelist(methods=["POST"])
def refund(pos_profile, opening_shift, selected_items, request_id, invoice_name=None, doctype="Sales Invoice", as_credit=0):
    profile = get_authorized_pos_profile(pos_profile)
    if not request_id or len(str(request_id)) > 140:
        frappe.throw(_("Return request identity is required"))
    lock = "quick-return:" + hashlib.sha256(f"{frappe.local.site}:{profile.name}:{request_id}".encode()).hexdigest()[:48]
    if frappe.db.sql("SELECT GET_LOCK(%s, 10)", lock)[0][0] != 1:
        frappe.throw(_("This return is still processing; recover the same request"))
    release = lambda: frappe.db.sql("SELECT RELEASE_LOCK(%s)", lock)
    frappe.db.after_commit.add(release)
    frappe.db.after_rollback.add(release)
    result = _refund(pos_profile, opening_shift, selected_items, request_id, invoice_name, doctype, as_credit)
    doc = frappe.get_doc(result["doctype"], result["name"])
    result["update_stock"] = 1 if doc.doctype == "POS Invoice" else doc.get("update_stock")
    result["items"] = [{f: row.get(f) for f in ("item_code", "qty", "stock_qty", "conversion_factor", "warehouse")} for row in doc.items]
    return result


def _refund(pos_profile, opening_shift, selected_items, request_id, invoice_name=None, doctype="Sales Invoice", as_credit=0):
    """Build prices on the server, then use the existing idempotent POS submission."""
    from posawesome.posawesome.api.invoice_processing.creation import submit_invoice
    from posawesome.posawesome.api.idempotency import find_invoice_by_client_request_id
    profile = get_authorized_pos_profile(pos_profile)
    if not profile.get("posa_allow_return"):
        frappe.throw(_("Returns are disabled on this register"))
    if not request_id or len(str(request_id)) > 140:
        frappe.throw(_("Return request identity is required"))
    existing = find_invoice_by_client_request_id(request_id, pos_profile=profile.name, company=profile.company)
    if existing and existing.docstatus == 1:
        return dict(name=existing.name, doctype=existing.doctype, docstatus=existing.docstatus)
    selected = frappe.parse_json(selected_items) if isinstance(selected_items, str) else selected_items
    if not isinstance(selected, list) or not 1 <= len(selected) <= 100:
        frappe.throw(_("Select returned items"))
    current_doctype = "POS Invoice" if profile.get("create_pos_invoice_instead_of_sales_invoice") else "Sales Invoice"
    payload = dict(doctype=current_doctype, pos_profile=profile.name, company=profile.company,
        customer=profile.customer, is_pos=1, is_return=1, update_stock=1, posting_date=nowdate(),
        posa_pos_opening_shift=opening_shift, currency=profile.currency, selling_price_list=profile.selling_price_list,
        taxes_and_charges=profile.get("taxes_and_charges"), items=[], payments=[], posa_client_request_id=request_id)
    if existing:
        payload["name"] = existing.name
    if invoice_name:
        source, _source_profile = scoped_invoice(invoice_name, doctype)
        if source.company != profile.company or source.is_return or doctype != current_doctype or source.currency != profile.currency:
            frappe.throw(_("Return the sale using a register with the same invoice mode and company"))
        # Serialize source quantities through native submit, including concurrent returns.
        frappe.db.sql(f"SELECT name FROM `tab{doctype}` WHERE name=%s FOR UPDATE", source.name)
        available = return_items(source.name, doctype, profile.name)
        lookup = {r["name"]: r for r in available["items"]}
        payload.update(customer=source.customer, return_against=source.name, update_stock=1 if source.doctype == "POS Invoice" else source.get("update_stock"),
            taxes_and_charges=source.get("taxes_and_charges"),
            taxes=[{f: r.get(f) for f in ("charge_type", "account_head", "description", "rate", "included_in_print_rate", "cost_center")} for r in source.get("taxes") or []],
            sales_team=[dict(sales_person=r.sales_person, allocated_percentage=r.allocated_percentage) for r in source.get("sales_team") or []],
            apply_discount_on=source.get("apply_discount_on"), additional_discount_percentage=source.get("additional_discount_percentage"))
        used = set()
        for selected_row in selected:
            key, qty = selected_row.get("name"), flt(selected_row.get("qty"))
            row = lookup.get(key)
            if key in used or not row or not isfinite(qty) or qty <= 0 or qty > row["qty"]:
                frappe.throw(_("Return quantity exceeds remaining quantity"))
            used.add(key)
            original = next(r for r in source.items if r.name == key)
            item = {f: original.get(f) for f in ("item_code", "item_name", "rate", "price_list_rate", "discount_percentage", "discount_amount", "uom", "stock_uom", "conversion_factor", "batch_no", "serial_no", "warehouse", "is_free_item")}
            item.update(qty=-qty, **{"pos_invoice_item" if doctype == "POS Invoice" else "sales_invoice_item": key})
            item["warehouse"] = profile.warehouse
            payload["items"].append(item)
        if not source.get("additional_discount_percentage") and source.get("discount_amount"):
            fraction = sum(abs(flt(r["qty"]) * flt(r["rate"])) for r in payload["items"]) / abs(flt(source.total) or 1)
            payload["discount_amount"] = -abs(flt(source.discount_amount)) * fraction
    else:
        if not profile.get("posa_allow_return_without_invoice") or cint(as_credit):
            frappe.throw(_("Guest returns require cash and permission for returns without a receipt"))
        for selected_row in selected:
            row = guest_item(profile.name, selected_row.get("item_code"))
            qty = flt(selected_row.get("qty"))
            if not isfinite(qty) or qty <= 0 or row.get("has_batch_no") or row.get("has_serial_no"):
                frappe.throw(_("Use the full return cart for batch or serial items"))
            row.update(qty=-qty, rate=flt(row.get("rate") or row.get("price_list_rate")), warehouse=profile.warehouse)
            payload["items"].append(row)
    if cint(as_credit) and payload["customer"] == profile.customer:
        frappe.throw(_("Select a registered customer for store credit"))
    cash_mode = next((p.mode_of_payment for p in profile.payments if frappe.get_cached_value("Mode of Payment", p.mode_of_payment, "type") == "Cash"), None)
    if not cint(as_credit) and not cash_mode:
        frappe.throw(_("Configure a cash payment method on this POS Profile"))
    # Native draft calculation determines the actual refund; never trust a UI total.
    from posawesome.posawesome.api.invoice_processing.creation import update_invoice
    draft = update_invoice(json.dumps(payload, default=str))
    draft = draft.as_dict() if callable(getattr(draft, "as_dict", None)) else draft
    total = -abs(flt(draft.get("rounded_total") or draft.get("grand_total")))
    if total == 0:
        frappe.throw(_("Refund total must be positive"))
    if invoice_name and not cint(as_credit):
        previous_refunds = sum(abs(flt(r.paid_amount)) for r in frappe.get_all(doctype,
            filters=dict(return_against=source.name, is_return=1, docstatus=1), fields=["paid_amount"]))
        refundable = max(0, flt(source.paid_amount) - previous_refunds)
        if abs(total) > refundable + 0.001:
            frappe.throw(_("Cash refund exceeds the remaining amount paid. Use customer credit instead."))
    draft["payments"] = [] if cint(as_credit) else [dict(mode_of_payment=cash_mode, amount=total, type="Cash")]
    return submit_invoice(json.dumps(draft, default=str), json.dumps(dict(idempotency_key=request_id,
        pos_profile=profile.name, company=profile.company, is_credit_sale=0, total_change=0, paid_change=0,
        credit_change=0, is_cashback=1, redeemed_customer_credit=0, customer_credit_dict=[])), submit_in_background=False)
