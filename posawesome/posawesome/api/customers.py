# -*- coding: utf-8 -*-
# Copyright (c) 2020, Youssef Restom and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe.utils import nowdate, flt, cstr, get_datetime
from frappe import _
from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
    get_loyalty_program_details_with_points,
)
from frappe.utils.caching import redis_cache
from .utils import assert_pos_profile_write_allowed, fetch_sales_person_names
from .stored_value import get_stored_value_summary


def _load_json_arg(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _assert_customer_write_allowed(pos_profile_doc=None, company=None):
    return assert_pos_profile_write_allowed(pos_profile_doc, company=company)


def _mobile_search_keys(value):
    digits = "".join(character for character in cstr(value or "") if character.isdigit())
    if not digits:
        return []
    keys = {digits}
    if digits.startswith("00") and len(digits) > 2:
        keys.add(digits[2:])
    if digits.startswith("0") and len(digits) > 1:
        keys.add(digits[1:])
    for tail_length in (10, 9, 8):
        if len(digits) > tail_length:
            keys.add(digits[-tail_length:])
    return [key for key in keys if len(key) >= 4]


def _mobile_matches_search(mobile_no, search_term):
    customer_keys = _mobile_search_keys(mobile_no)
    search_keys = _mobile_search_keys(search_term)
    return any(
        search_key in customer_key or customer_key in search_key
        for search_key in search_keys
        for customer_key in customer_keys
    )


def _find_duplicate_customer_records(
    customer_name=None,
    mobile_no=None,
    email_id=None,
    tax_id=None,
    posa_barcode=None,
    exclude_customer=None,
    allow_duplicate_names=False,
):
    """Return exact duplicate candidates without loading the full customer table."""
    checks = []
    if customer_name and not allow_duplicate_names:
        checks.append(("customer_name", str(customer_name).strip()))
    if mobile_no:
        checks.append(("mobile_no", str(mobile_no).strip()))
    if posa_barcode:
        checks.append(("posa_barcode", str(posa_barcode).strip()))
    if email_id:
        checks.append(("email_id", str(email_id).strip().lower()))
    if tax_id:
        checks.append(("tax_id", str(tax_id).strip()))

    matches = {}
    if mobile_no:
        try:
            from erpnext.selling.page.customer_hub.customer_data import find_duplicate_phone_customer
            dup = find_duplicate_phone_customer(mobile_no, exclude_customer=exclude_customer)
            if dup:
                dup_name = dup.get("name")
                if dup_name:
                    match = matches.setdefault(
                        dup_name,
                        {
                            "name": dup_name,
                            "customer_name": dup.get("customer_name"),
                            "mobile_no": dup.get("mobile_no"),
                            "email_id": dup.get("email_id"),
                            "tax_id": dup.get("tax_id"),
                            "posa_barcode": dup.get("posa_barcode"),
                            "customer_group": dup.get("customer_group"),
                            "matching_fields": [],
                        },
                    )
                    if "mobile_no" not in match["matching_fields"]:
                        match["matching_fields"].append("mobile_no")
        except Exception:
            pass

    for fieldname, value in checks:
        if not value:
            continue
        filters = {fieldname: value, "disabled": 0}
        if exclude_customer:
            filters["name"] = ["!=", exclude_customer]
        for customer in frappe.get_all(
            "Customer",
            filters=filters,
            fields=["name", "customer_name", "mobile_no", "email_id", "tax_id", "posa_barcode", "customer_group"],
            limit_page_length=5,
        ):
            customer_name_key = customer.get("name")
            if not customer_name_key:
                continue
            match = matches.setdefault(customer_name_key, dict(customer, matching_fields=[]))
            if fieldname not in match["matching_fields"]:
                match["matching_fields"].append(fieldname)

    return list(matches.values())


@frappe.whitelist()
def find_duplicate_customers(
    customer_name,
    company,
    pos_profile_doc,
    mobile_no=None,
    email_id=None,
    tax_id=None,
    posa_barcode=None,
    customer_id=None,
):
    pos_profile_doc_obj = _assert_customer_write_allowed(pos_profile_doc, company=company)
    pos_profile = pos_profile_doc_obj.as_dict() if pos_profile_doc_obj else {}
    return _find_duplicate_customer_records(
        customer_name=customer_name,
        mobile_no=mobile_no,
        email_id=email_id,
        tax_id=tax_id,
        posa_barcode=posa_barcode,
        exclude_customer=customer_id,
        allow_duplicate_names=bool(pos_profile.get("posa_allow_duplicate_customer_names", True)),
    )


def get_customer_groups(pos_profile):
    customer_groups = []
    if pos_profile.get("customer_groups"):
        # Get items based on the item groups defined in the POS profile
        for data in pos_profile.get("customer_groups"):
            group_name = data.get("customer_group") if data else None
            if not group_name:
                continue
            customer_groups.extend([d.get("name") for d in get_child_nodes("Customer Group", group_name)])

    return list(set(customer_groups))


def get_child_nodes(group_type, root):
    if not root:
        return []
    result = frappe.db.get_value(group_type, root, ["lft", "rgt"])
    if not result:
        return []
    lft, rgt = result
    return frappe.get_all(
        group_type,
        filters={"lft": [">=", lft], "rgt": ["<=", rgt]},
        fields=["name", "lft", "rgt"],
        order_by="lft",
    )


def get_customer_group_condition(pos_profile):
    cond = "disabled = 0"
    customer_groups = get_customer_groups(pos_profile)
    if customer_groups:
        escaped_groups = [frappe.db.escape(g) for g in customer_groups]
        cond = " customer_group in ({})".format(", ".join(escaped_groups))

    return cond


@frappe.whitelist()
def get_customer_balance(customer, company=None):
    if not customer:
        return {"balance": 0, "customer_name": None, "currency": None}

    if not company:
        if frappe.db.exists("DocType", "POS Session"):
            pos_session = frappe.db.get_value(
                "POS Session",
                {"user": frappe.session.user, "status": "Open"},
                "pos_profile",
            )
            if pos_session:
                company = frappe.db.get_value("POS Profile", pos_session, "company")
        if not company:
            company = frappe.defaults.get_user_default("Company") or frappe.db.get_default("Company")

    from erpnext.accounts.party import get_dashboard_info

    try:
        customer_name = frappe.db.get_value("Customer", customer, "customer_name")

        dashboard_info = get_dashboard_info("Customer", customer)
        company_data = [d for d in dashboard_info if d.get("company") == company]

        if company_data:
            balance = flt(company_data[0].get("total_unpaid", 0))
        else:
            balance = 0

        return {
            "balance": balance,
            "customer_name": customer_name,
            "currency": company_data[0].get("currency") if company_data else None,
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error fetching customer balance"))
        return {"balance": 0, "customer_name": None, "currency": None}


@frappe.whitelist()
def get_customer_names(pos_profile, limit=None, offset=None, start_after=None, modified_after=None):
    _pos_profile = json.loads(pos_profile)
    ttl = _pos_profile.get("posa_server_cache_duration")
    if ttl:
        ttl = int(ttl) * 60

    @redis_cache(ttl=ttl or 1800)
    def __get_customer_names(pos_profile, limit=None, offset=None, start_after=None, modified_after=None):
        return _get_customer_names(pos_profile, limit, offset, start_after, modified_after)

    def _get_customer_names(pos_profile, limit=None, offset=None, start_after=None, modified_after=None):
        pos_profile = json.loads(pos_profile)
        filters = {"disabled": 0}

        customer_groups = get_customer_groups(pos_profile)
        if customer_groups:
            filters["customer_group"] = ["in", customer_groups]

        if modified_after:
            try:
                parsed_modified_after = get_datetime(modified_after)
            except Exception:
                frappe.throw(_("modified_after must be a valid ISO datetime"))
            filters["modified"] = [">", parsed_modified_after.isoformat()]

        if start_after:
            filters["name"] = [">", start_after]

        customers = frappe.get_all(
            "Customer",
            filters=filters,
            fields=[
                "name",
                "modified",
                "mobile_no",
                "email_id",
                "tax_id",
                "customer_name",
                "loyalty_program",
                "default_price_list",
                "customer_group",
                "territory",
                "primary_address",
                "posa_barcode",
                "posa_birthday",
            ],
            order_by="name",
            limit_start=None if start_after else offset,
            limit_page_length=limit,
        )
        return customers

    if _pos_profile.get("posa_use_server_cache") and not (limit or offset or start_after or modified_after):
        return __get_customer_names(pos_profile, limit, offset, start_after, modified_after)
    else:
        return _get_customer_names(pos_profile, limit, offset, start_after, modified_after)


def _barcode_matches_search(posa_barcode, search_term):
    barcode = cstr(posa_barcode or "").strip().lower()
    term = cstr(search_term or "").strip().lower()
    if not barcode or not term:
        return False
    return term in barcode


@frappe.whitelist()
def search_customers(pos_profile, search_term, limit=200):
    """Find mobile-number or barcode matches that may not have reached the local POS cache yet."""
    profile = _load_json_arg(pos_profile) or {}
    clean_term = cstr(search_term or "").strip()
    search_keys = _mobile_search_keys(clean_term)
    if not search_keys and len(clean_term) < 3:
        return []

    try:
        result_limit = max(1, min(int(limit or 200), 200))
    except (TypeError, ValueError):
        result_limit = 200

    customer_fields = [
        "name",
        "modified",
        "mobile_no",
        "email_id",
        "tax_id",
        "customer_name",
        "loyalty_program",
        "default_price_list",
        "customer_group",
        "territory",
        "primary_address",
        "posa_barcode",
        "posa_birthday",
    ]

    customer_groups = get_customer_groups(profile)
    matches = []
    seen_names = set()

    if search_keys:
        digits = max(search_keys, key=len)
        fragment = digits[-4:]
        filters = {
            "disabled": 0,
            "mobile_no": ["like", f"%{fragment}%"],
        }
        if customer_groups:
            filters["customer_group"] = ["in", customer_groups]

        candidates = frappe.get_all(
            "Customer",
            filters=filters,
            fields=customer_fields,
            order_by="name",
            limit_page_length=max(result_limit * 5, 500),
        )
        for customer in candidates:
            if _mobile_matches_search(customer.get("mobile_no"), clean_term):
                cname = customer.get("name")
                if cname and cname not in seen_names:
                    seen_names.add(cname)
                    matches.append(customer)

    if len(clean_term) >= 3 and len(matches) < result_limit:
        barcode_filters = {
            "disabled": 0,
            "posa_barcode": ["like", f"%{clean_term}%"],
        }
        if customer_groups:
            barcode_filters["customer_group"] = ["in", customer_groups]
        try:
            barcode_candidates = frappe.get_all(
                "Customer",
                filters=barcode_filters,
                fields=customer_fields,
                order_by="name",
                limit_page_length=result_limit,
            )
            for customer in barcode_candidates:
                if _barcode_matches_search(customer.get("posa_barcode"), clean_term):
                    cname = customer.get("name")
                    if cname and cname not in seen_names:
                        seen_names.add(cname)
                        matches.append(customer)
        except Exception:
            pass

    return matches[:result_limit]


@frappe.whitelist()
def get_customers_count(pos_profile):
    pos_profile = json.loads(pos_profile)
    filters = {"disabled": 0}
    customer_groups = get_customer_groups(pos_profile)
    if customer_groups:
        filters["customer_group"] = ["in", customer_groups]
    return frappe.db.count("Customer", filters)


@frappe.whitelist()
def get_customer_info(customer=None, company=None):
    customer = cstr(customer or "").strip()
    if not customer:
        return {}

    customer = frappe.get_doc("Customer", customer)

    res = {"loyalty_points": None, "conversion_factor": None}

    res["email_id"] = customer.email_id
    res["mobile_no"] = customer.mobile_no
    res["image"] = customer.image
    res["loyalty_program"] = customer.loyalty_program
    res["customer_price_list"] = customer.default_price_list
    res["customer_group"] = customer.customer_group
    res["customer_type"] = customer.customer_type
    res["territory"] = customer.territory
    res["birthday"] = customer.posa_birthday
    res["posa_birthday"] = customer.posa_birthday
    res["posa_barcode"] = customer.get("posa_barcode")
    res["gender"] = customer.gender
    res["tax_id"] = customer.tax_id
    res["posa_discount"] = customer.posa_discount
    res["name"] = customer.name
    res["customer_name"] = customer.customer_name
    res["customer_group_price_list"] = frappe.get_value(
        "Customer Group", customer.customer_group, "default_price_list"
    )

    effective_price_list = res.get("customer_price_list") or res.get("customer_group_price_list")
    if effective_price_list:
        res["price_list_currency"] = frappe.get_value("Price List", effective_price_list, "currency")
    else:
        res["price_list_currency"] = None

    if customer.loyalty_program:
        lp_details = get_loyalty_program_details_with_points(
            customer.name,
            customer.loyalty_program,
            silent=True,
            include_expired_entry=False,
        )
        res["loyalty_points"] = lp_details.get("loyalty_points")
        res["conversion_factor"] = lp_details.get("conversion_factor")
        res["collection_factor"] = lp_details.get("collection_factor")
        res["loyalty_tier"] = lp_details.get("tier_name")

    company = cstr(company or "").strip()
    if company:
        stored_value = get_stored_value_summary(customer=customer.name, company=company)
        res["stored_value_balance"] = stored_value.get("available_amount", 0)
        res["stored_value_sources"] = stored_value.get("source_count", 0)
    else:
        res["stored_value_balance"] = 0
        res["stored_value_sources"] = 0

    addresses = frappe.db.sql(
        """
	SELECT
	    address.name as address_name,
	    address.address_line1,
	    address.address_line2,
	    address.city,
	    address.state,
	    address.country,
	    address.address_type
	FROM `tabAddress` address
	INNER JOIN `tabDynamic Link` link
	    ON (address.name = link.parent)
	WHERE
	    link.link_doctype = 'Customer'
	    AND link.link_name = %s
	    AND address.disabled = 0
	    AND address.address_type = 'Shipping'
	ORDER BY address.creation DESC
	LIMIT 1
	""",
        (customer.name,),
        as_dict=True,
    )

    if addresses:
        addr = addresses[0]
        res["address_line1"] = addr.address_line1 or ""
        res["address_line2"] = addr.address_line2 or ""
        res["city"] = addr.city or ""
        res["state"] = addr.state or ""
        res["country"] = addr.country or ""

    return res


@frappe.whitelist()
def create_customer(
    customer_name,
    company,
    pos_profile_doc,
    customer_id=None,
    tax_id=None,
    mobile_no=None,
    email_id=None,
    referral_code=None,
    birthday=None,
    posa_barcode=None,
    customer_group=None,
    tier=None,
    territory=None,
    customer_type=None,
    gender=None,
    method="create",
    address_line1=None,
    city=None,
    country=None,
):
    pos_profile_doc_obj = _assert_customer_write_allowed(pos_profile_doc, company=company)
    pos_profile = pos_profile_doc_obj.as_dict() if pos_profile_doc_obj else {}

    clean_barcode = cstr(posa_barcode or "").strip() or None

    # Format birthday to MySQL compatible format (YYYY-MM-DD) if provided
    formatted_birthday = None
    if birthday:
        try:
            clean_bday = cstr(birthday).strip().replace(".", "-").replace("/", "-")
            if len(clean_bday) == 8 and clean_bday.isdigit():
                day, month, year = clean_bday[:2], clean_bday[2:4], clean_bday[4:]
                formatted_birthday = f"{year}-{month}-{day}"
            elif "-" in clean_bday:
                date_parts = clean_bday.split("-")
                if len(date_parts) == 3:
                    if len(date_parts[0]) == 4:
                        year, month, day = date_parts
                    else:
                        day, month, year = date_parts
                    formatted_birthday = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except Exception:
            frappe.log_error(f"Error formatting birthday: {birthday}", "POS Awesome")

    if method == "create":
        duplicate_customers = _find_duplicate_customer_records(
            customer_name=customer_name,
            mobile_no=mobile_no,
            email_id=email_id,
            tax_id=tax_id,
            posa_barcode=clean_barcode,
            allow_duplicate_names=bool(pos_profile.get("posa_allow_duplicate_customer_names", True)),
        )
        if duplicate_customers:
            existing = duplicate_customers[0]
            frappe.throw(
                _("Customer already exists: {0}").format(
                    existing.get("customer_name") or existing.get("name")
                )
            )
        else:
            customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "posa_referral_company": company,
                    "tax_id": tax_id,
                    "mobile_no": mobile_no,
                    "email_id": email_id,
                    "posa_referral_code": referral_code,
                    "posa_birthday": formatted_birthday,
                    "posa_barcode": clean_barcode,
                    "customer_type": customer_type,
                    "gender": gender,
                }
            )

            # Resolve tier and loyalty program
            selected_tier = tier or customer_group
            tier_doc = None
            if selected_tier and frappe.db.exists("Customer Tier", selected_tier):
                tier_doc = frappe.get_doc("Customer Tier", selected_tier)
            elif not selected_tier or selected_tier in ("Individual", "All Customer Groups"):
                default_tier = frappe.db.get_single_value("Customer Loyalty Settings", "default_tier") or "Базовый"
                if frappe.db.exists("Customer Tier", default_tier):
                    tier_doc = frappe.get_doc("Customer Tier", default_tier)

            if tier_doc:
                customer.customer_group = tier_doc.customer_group
                customer.loyalty_program = tier_doc.loyalty_program
                customer.loyalty_program_tier = tier_doc.tier_name
            elif customer_group and not frappe.db.get_value("Customer Group", customer_group, "is_group"):
                customer.customer_group = customer_group
            else:
                customer.customer_group = (
                    frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "Individual"
                )

            if territory and not frappe.db.get_value("Territory", territory, "is_group"):
                customer.territory = territory
            else:
                customer.territory = (
                    frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
                )

            customer.save()

            if address_line1 or city:
                args = {
                    "name": f"{customer.customer_name} - Shipping",
                    "doctype": "Customer",
                    "customer": customer.name,
                    "address_line1": address_line1 or "",
                    "address_line2": "",
                    "city": city or "",
                    "state": "",
                    "pincode": "",
                    "country": country or "",
                    "company": company,
                    "pos_profile_doc": pos_profile_doc,
                }
                make_address(json.dumps(args))

            return customer
    elif method == "update":
        if clean_barcode:
            barcode_dups = _find_duplicate_customer_records(
                posa_barcode=clean_barcode,
                exclude_customer=customer_id,
                allow_duplicate_names=True,
            )
            if barcode_dups:
                existing = barcode_dups[0]
                frappe.throw(
                    _("Card barcode {0} is already assigned to {1}").format(
                        clean_barcode, existing.get("customer_name") or existing.get("name")
                    )
                )
        customer_doc = frappe.get_doc("Customer", customer_id)
        customer_doc.customer_name = customer_name
        customer_doc.tax_id = tax_id
        customer_doc.mobile_no = mobile_no
        customer_doc.email_id = email_id
        customer_doc.posa_referral_code = referral_code
        customer_doc.posa_birthday = formatted_birthday
        customer_doc.posa_barcode = clean_barcode
        customer_doc.customer_type = customer_type
        customer_doc.gender = gender

        # If tier changed, sync via update_customer_tier so points follow
        selected_tier = tier or customer_group
        if selected_tier and frappe.db.exists("Customer Tier", selected_tier):
            if customer_doc.customer_group != selected_tier:
                try:
                    from erpnext.selling.page.customer_hub.customer_data import update_customer_tier
                    update_customer_tier(customer_doc.name, selected_tier)
                    customer_doc.reload()
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(), "POS Customer Tier Update Error")

        customer_doc.save()

        # ensure contact details are synced correctly
        if mobile_no:
            set_customer_info(
                customer_doc.name,
                "mobile_no",
                mobile_no,
                pos_profile_doc=pos_profile_doc,
                company=company,
            )
        if email_id:
            set_customer_info(
                customer_doc.name,
                "email_id",
                email_id,
                pos_profile_doc=pos_profile_doc,
                company=company,
            )

        existing_address_name = frappe.db.get_value(
            "Dynamic Link",
            {
                "link_doctype": "Customer",
                "link_name": customer_id,
                "parenttype": "Address",
            },
            "parent",
        )

        if existing_address_name:
            address_doc = frappe.get_doc("Address", existing_address_name)
            address_doc.address_line1 = address_line1 or ""
            address_doc.city = city or ""
            address_doc.country = country or ""
            address_doc.save()
        else:
            if address_line1 or city:
                args = {
                    "name": f"{customer_doc.customer_name} - Shipping",
                    "doctype": "Customer",
                    "customer": customer_doc.name,
                    "address_line1": address_line1 or "",
                    "address_line2": "",
                    "city": city or "",
                    "state": "",
                    "pincode": "",
                    "country": country or "",
                    "company": company,
                    "pos_profile_doc": pos_profile_doc,
                }
                make_address(json.dumps(args))

        return customer_doc


@frappe.whitelist()
def set_customer_info(customer, fieldname, value="", pos_profile_doc=None, company=None):
    _assert_customer_write_allowed(pos_profile_doc, company=company)

    if fieldname == "loyalty_program":
        frappe.db.set_value("Customer", customer, "loyalty_program", value)

    contact = frappe.get_cached_value("Customer", customer, "customer_primary_contact") or ""

    if contact:
        contact_doc = frappe.get_doc("Contact", contact)
        if fieldname == "email_id":
            contact_doc.set("email_ids", [{"email_id": value, "is_primary": 1}])
            frappe.db.set_value("Customer", customer, "email_id", value)
        elif fieldname == "mobile_no":
            contact_doc.set("phone_nos", [{"phone": value, "is_primary_mobile_no": 1}])
            frappe.db.set_value("Customer", customer, "mobile_no", value)
        contact_doc.save()

    else:
        contact_doc = frappe.new_doc("Contact")
        contact_doc.first_name = customer
        contact_doc.is_primary_contact = 1
        contact_doc.is_billing_contact = 1
        if fieldname == "mobile_no":
            contact_doc.add_phone(value, is_primary_mobile_no=1, is_primary_phone=1)

        if fieldname == "email_id":
            contact_doc.add_email(value, is_primary=1)

        contact_doc.append("links", {"link_doctype": "Customer", "link_name": customer})

        contact_doc.flags.ignore_mandatory = True
        contact_doc.save()
        frappe.set_value("Customer", customer, "customer_primary_contact", contact_doc.name)


@frappe.whitelist()
def get_customer_addresses(customer):
    return frappe.db.sql(
        """
        SELECT
            address.name,
            address.address_line1,
            address.address_line2,
            address.address_title,
            address.city,
            address.state,
            address.country,
            address.address_type
        FROM `tabAddress` as address
        INNER JOIN `tabDynamic Link` AS link
                                ON address.name = link.parent
        WHERE link.link_doctype = 'Customer'
            AND link.link_name = %s
            AND address.disabled = 0
        ORDER BY address.name
        """,
        (customer,),
        as_dict=1,
    )


@frappe.whitelist()
def make_address(args):
    args = _load_json_arg(args)
    _assert_customer_write_allowed(args.get("pos_profile_doc"), company=args.get("company"))

    address = frappe.get_doc(
        {
            "doctype": "Address",
            "address_title": args.get("name"),
            "address_line1": args.get("address_line1"),
            "address_line2": args.get("address_line2"),
            "city": args.get("city"),
            "state": args.get("state"),
            "pincode": args.get("pincode"),
            "country": args.get("country"),
            "address_type": "Shipping",
            "links": [{"link_doctype": args.get("doctype"), "link_name": args.get("customer")}],
        }
    ).insert()

    return address


@frappe.whitelist()
def get_sales_person_names(pos_profile=None):
    return fetch_sales_person_names(pos_profile=pos_profile)


@frappe.whitelist()
def get_customer_tiers():
    """Return available customer tiers for POS quick registration."""
    tiers = []
    default_tier = "Базовый"
    try:
        if frappe.db.exists("DocType", "Customer Tier"):
            from erpnext.selling.doctype.customer_tier.customer_tier import get_ordered_tiers
            tiers = get_ordered_tiers()
            default_tier = frappe.db.get_single_value("Customer Loyalty Settings", "default_tier") or "Базовый"
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_customer_tiers error")
    return {
        "tiers": tiers,
        "default_tier": default_tier,
    }

