# Copyright (c) 2025, Youssef Restom and contributors
# For license information, please see license.txt

"""API for Barcode Label Template CRUD."""

import json
import frappe
from frappe import _

BUILTIN_LABEL_TEMPLATES = [
    {
        "title": "Radolfa Standard (58x40mm)",
        "label_size": "58x40mm",
        "description": "Standard retail label with Radolfa badge, short code, Cyrillic item name, barcode, and bold price (Xprinter XP-365B)",
        "layout": [
            {"id": "border_1", "type": "shape", "shapeType": "rect", "x": 1, "y": 1, "width": 56, "height": 38, "borderWidth": 0.5, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "header_bg", "type": "shape", "shapeType": "rect", "x": 1.5, "y": 1.5, "width": 55, "height": 6.5, "borderWidth": 0.3, "borderColor": "#666666", "color": "#e0e0e0", "zIndex": 2, "content": ""},
            {"id": "company_text", "type": "text", "x": 3, "y": 1.8, "width": 26, "height": 6, "fontSize": 10, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{company}"},
            {"id": "code_text", "type": "text", "x": 30, "y": 1.8, "width": 25, "height": 6, "fontSize": 10, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{short_code}"},
            {"id": "name_text", "type": "text", "x": 2, "y": 8.5, "width": 54, "height": 8.5, "fontSize": 10, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "barcode_obj", "type": "barcode", "x": 4, "y": 17.5, "width": 50, "height": 13.5, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "price_text", "type": "text", "x": 2, "y": 31.5, "width": 54, "height": 7, "fontSize": 15, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{price}"}
        ]
    },
    {
        "title": "Radolfa Discount / Sale (58x40mm)",
        "label_size": "58x40mm",
        "description": "Discount / Sale promo label with Radolfa header, old price strikethrough, and big sale price",
        "layout": [
            {"id": "border_1", "type": "shape", "shapeType": "rect", "x": 1, "y": 1, "width": 56, "height": 38, "borderWidth": 0.5, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "sale_bg", "type": "shape", "shapeType": "rect", "x": 1.5, "y": 1.5, "width": 55, "height": 6.5, "borderWidth": 0, "borderColor": "#000000", "color": "#222222", "zIndex": 2, "content": ""},
            {"id": "company_sale", "type": "text", "x": 3, "y": 1.8, "width": 24, "height": 6, "fontSize": 10, "fontBold": True, "textAlign": "left", "color": "#ffffff", "zIndex": 3, "content": "{company}"},
            {"id": "sale_tag", "type": "text", "x": 28, "y": 1.8, "width": 27, "height": 6, "fontSize": 10, "fontBold": True, "textAlign": "right", "color": "#ffffff", "zIndex": 3, "content": "★ СКИДКА ★"},
            {"id": "name_sale", "type": "text", "x": 2, "y": 8.5, "width": 54, "height": 7.5, "fontSize": 9.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "barcode_sale", "type": "barcode", "x": 4, "y": 16.5, "width": 50, "height": 13, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "old_price_text", "type": "text", "x": 3, "y": 30.5, "width": 24, "height": 6, "fontSize": 8.5, "fontBold": False, "textAlign": "left", "color": "#777777", "zIndex": 3, "content": "{old_price}"},
            {"id": "strike_line", "type": "line", "lineDirection": "horizontal", "x": 3, "y": 33.5, "width": 22, "height": 1, "borderWidth": 1, "borderColor": "#000000", "zIndex": 4, "content": ""},
            {"id": "new_price_text", "type": "text", "x": 28, "y": 30, "width": 28, "height": 8.5, "fontSize": 15, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{price}"}
        ]
    },
    {
        "title": "Radolfa Promo 1+1 (58x40mm)",
        "label_size": "58x40mm",
        "description": "Buy 1 Get 1 Free promotion label with Radolfa branding and promo highlight",
        "layout": [
            {"id": "border_1", "type": "shape", "shapeType": "rect", "x": 1, "y": 1, "width": 56, "height": 38, "borderWidth": 0.5, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_promo", "type": "text", "x": 3, "y": 1.8, "width": 26, "height": 6, "fontSize": 10, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{company}"},
            {"id": "promo_rect", "type": "shape", "shapeType": "rect", "x": 31, "y": 1.5, "width": 25, "height": 6.5, "borderWidth": 0, "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "promo_tag", "type": "text", "x": 31, "y": 1.8, "width": 25, "height": 6, "fontSize": 9.5, "fontBold": True, "textAlign": "center", "color": "#ffffff", "zIndex": 3, "content": "АКЦИЯ 1+1"},
            {"id": "name_promo", "type": "text", "x": 2, "y": 8.5, "width": 54, "height": 7.5, "fontSize": 9.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "barcode_promo", "type": "barcode", "x": 4, "y": 16.5, "width": 50, "height": 13, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "promo_desc", "type": "text", "x": 3, "y": 30.5, "width": 28, "height": 7, "fontSize": 8.5, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "1+1 В ПОДАРОК"},
            {"id": "price_promo", "type": "text", "x": 32, "y": 30, "width": 24, "height": 8.5, "fontSize": 14, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{price}"}
        ]
    },
    {
        "title": "Radolfa Compact (40x30mm)",
        "label_size": "40x30mm",
        "description": "Compact thermal label for small products with Radolfa header and barcode",
        "layout": [
            {"id": "border_1", "type": "shape", "shapeType": "rect", "x": 1, "y": 1, "width": 38, "height": 28, "borderWidth": 0.5, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "compact_header", "type": "text", "x": 2, "y": 1.5, "width": 36, "height": 4.5, "fontSize": 8.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "Radolfa · {short_code}"},
            {"id": "compact_name", "type": "text", "x": 2, "y": 6, "width": 36, "height": 5.5, "fontSize": 7.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{item_name}"},
            {"id": "compact_barcode", "type": "barcode", "x": 2.5, "y": 12, "width": 35, "height": 10.5, "symbology": "EAN13", "humanReadable": True, "zIndex": 2, "content": "{barcode}"},
            {"id": "compact_price", "type": "text", "x": 2, "y": 23, "width": 36, "height": 5.5, "fontSize": 11, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{price}"}
        ]
    }
]


def ensure_default_templates():
    """Seed built-in label templates into Barcode Label Template DocType if not present."""
    for tmpl in BUILTIN_LABEL_TEMPLATES:
        if not frappe.db.exists("Barcode Label Template", {"title": tmpl["title"]}):
            try:
                doc = frappe.get_doc({
                    "doctype": "Barcode Label Template",
                    "title": tmpl["title"],
                    "label_size": tmpl["label_size"],
                    "description": tmpl["description"],
                    "layout_json": json.dumps(tmpl["layout"]),
                })
                doc.flags.ignore_permissions = True
                doc.flags.ignore_links = True
                doc.insert()
            except Exception:
                frappe.log_error(f"Failed to seed barcode template {tmpl['title']}")


@frappe.whitelist()
def get_label_templates(label_size=None):
    """Return list of barcode label templates."""
    ensure_default_templates()
    filters = {"disabled": 0}
    if label_size:
        filters["label_size"] = label_size
    templates = frappe.get_all(
        "Barcode Label Template",
        filters=filters,
        fields=["name", "title", "label_size", "description", "modified", "thumbnail"],
        order_by="modified desc",
    )
    return templates


@frappe.whitelist()
def get_label_template_detail(name):
    """Return full template including layout_json."""
    if not name:
        frappe.throw(_("Template name is required"))
    doc = frappe.get_doc("Barcode Label Template", name)
    return {
        "name": doc.name,
        "title": doc.title,
        "label_size": doc.label_size,
        "description": doc.description,
        "layout_json": doc.layout_json,
        "modified": doc.modified,
        "thumbnail": doc.thumbnail,
    }


@frappe.whitelist()
def save_label_template(title, label_size, layout_json, description=None, name=None):
    """Create or update a barcode label template."""
    if not title or not label_size or not layout_json:
        frappe.throw(_("Title, label size, and layout JSON are required"))

    parsed = frappe.parse_json(layout_json)
    if not isinstance(parsed, list):
        frappe.throw(_("Layout JSON must be a JSON array"))

    if name:
        doc = frappe.get_doc("Barcode Label Template", name)
        doc.title = title
        doc.label_size = label_size
        doc.layout_json = layout_json
        if description is not None:
            doc.description = description
        doc.save()
    else:
        doc = frappe.get_doc({
            "doctype": "Barcode Label Template",
            "title": title,
            "label_size": label_size,
            "layout_json": layout_json,
            "description": description or "",
        })
        doc.insert()

    return {
        "name": doc.name,
        "title": doc.title,
        "label_size": doc.label_size,
    }


@frappe.whitelist()
def delete_label_template(name):
    """Delete a barcode label template."""
    if not name:
        frappe.throw(_("Template name is required"))
    frappe.delete_doc("Barcode Label Template", name)
    return {"success": True}


@frappe.whitelist()
def get_shipping_addresses(company, customer=None, delivery_note=None, sales_invoice=None):
    """Return ship-from and ship-to addresses for shipping label generation."""
    if not company:
        frappe.throw(_("Company is required"))

    ship_from = _get_company_address(company)

    ship_to = None
    address_name = None

    if delivery_note:
        address_name = frappe.db.get_value(
            "Delivery Note", delivery_note, "shipping_address_name"
        )
        if not address_name:
            address_name = frappe.db.get_value(
                "Delivery Note", delivery_note, "customer_address"
            )
    elif sales_invoice:
        address_name = frappe.db.get_value(
            "Sales Invoice", sales_invoice, "shipping_address_name"
        )
        if not address_name:
            address_name = frappe.db.get_value(
                "Sales Invoice", sales_invoice, "customer_address"
            )
    elif customer:
        addresses = frappe.get_all(
            "Address",
            filters=[
                ["Dynamic Link", "link_doctype", "=", "Customer"],
                ["Dynamic Link", "link_name", "=", customer],
                ["disabled", "=", 0],
            ],
            fields=["name"],
            order_by="is_primary_address desc, modified desc",
            limit=1,
        )
        if addresses:
            address_name = addresses[0]["name"]

    if address_name:
        ship_to = _format_address(address_name, "to")

    return {
        "ship_from": ship_from,
        "ship_to": ship_to,
    }


def _get_company_address(company):
    """Get primary address for a company."""
    address_name = frappe.db.get_value(
        "Address",
        filters=[
            ["Dynamic Link", "link_doctype", "=", "Company"],
            ["Dynamic Link", "link_name", "=", company],
            ["is_primary_address", "=", 1],
            ["disabled", "=", 0],
        ],
    )
    if not address_name:
        address_name = frappe.db.get_value(
            "Address",
            filters=[
                ["Dynamic Link", "link_doctype", "=", "Company"],
                ["Dynamic Link", "link_name", "=", company],
                ["disabled", "=", 0],
            ],
        )
    return _format_address(address_name, "from") if address_name else None


def _format_address(address_name, role):
    """Extract and format address fields into a dict."""
    addr = frappe.get_doc("Address", address_name)
    parts = [
        addr.address_line1,
        addr.address_line2,
        addr.city,
        addr.state,
        addr.pincode,
        addr.country,
    ]
    lines = [p for p in parts if p]

    return {
        "name": addr.name,
        "role": role,
        "address_title": addr.address_title or addr.name,
        "lines": lines,
        "full": "\n".join(lines),
        "email_id": addr.email_id,
        "phone": addr.phone,
        "country": addr.country or "",
        "pincode": addr.pincode or "",
        "city": addr.city or "",
        "state": addr.state or "",
    }
