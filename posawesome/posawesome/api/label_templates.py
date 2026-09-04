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
        "description": "Standard retail label with safe printer margins, Radolfa header, clean divider, centered item name, barcode, short code, and large price (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.8, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_header", "type": "text", "x": 3.0, "y": 2.5, "width": 52.0, "height": 5.0, "fontSize": 11.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{company}"},
            {"id": "header_divider", "type": "line", "lineDirection": "horizontal", "x": 2.5, "y": 7.6, "width": 53.0, "height": 0.8, "borderWidth": 0.8, "borderColor": "#000000", "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "item_name", "type": "text", "x": 3.0, "y": 8.5, "width": 52.0, "height": 5.8, "fontSize": 10.0, "fontBold": False, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{item_name}"},
            {"id": "barcode_center", "type": "barcode", "x": 4.0, "y": 14.8, "width": 50.0, "height": 14.0, "symbology": "EAN13", "humanReadable": True, "zIndex": 2, "content": "{barcode}"},
            {"id": "short_code_val", "type": "text", "x": 4.5, "y": 29.5, "width": 14.0, "height": 7.0, "fontSize": 11.5, "fontBold": False, "textAlign": "left", "color": "#000000", "zIndex": 2, "content": "{short_code}"},
            {"id": "price_val", "type": "text", "x": 18.0, "y": 29.0, "width": 36.0, "height": 8.0, "fontSize": 21, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{price_formatted}"}
        ]
    },
    {
        "title": "Radolfa Discount / Sale (58x40mm)",
        "label_size": "58x40mm",
        "description": "Discount / sale promotion label with safe printer margins, Radolfa header, date, item name, АКЦИЯ! badge, strikethrough old price, short code with barcode, and bold sale price (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.8, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_header", "type": "text", "x": 3.0, "y": 2.4, "width": 52.0, "height": 4.8, "fontSize": 11.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{company}"},
            {"id": "header_divider", "type": "line", "lineDirection": "horizontal", "x": 2.5, "y": 7.4, "width": 53.0, "height": 0.8, "borderWidth": 0.8, "borderColor": "#000000", "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "date_header", "type": "text", "x": 31.0, "y": 7.8, "width": 23.5, "height": 4.2, "fontSize": 8.5, "fontBold": False, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{date:DD.MM.YYYY}"},
            {"id": "item_name", "type": "text", "x": 4.0, "y": 8.8, "width": 30.0, "height": 6.8, "fontSize": 10.0, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "promo_badge_bg", "type": "shape", "shapeType": "rect", "x": 4.0, "y": 16.5, "width": 22.0, "height": 6.8, "borderWidth": 0.5, "borderColor": "#000000", "color": "#000000", "zIndex": 2, "content": "", "condition": "{old_price} != ''"},
            {"id": "promo_badge_text", "type": "text", "x": 4.0, "y": 16.5, "width": 22.0, "height": 6.8, "fontSize": 10.5, "fontBold": True, "textAlign": "center", "color": "#ffffff", "zIndex": 3, "content": "АКЦИЯ!", "condition": "{old_price} != ''"},
            {"id": "old_price_label", "type": "text", "x": 28.0, "y": 11.0, "width": 26.5, "height": 4.2, "fontSize": 8.5, "fontBold": False, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "Старая цена:", "condition": "{old_price} != ''"},
            {"id": "old_price_val", "type": "text", "x": 28.0, "y": 14.5, "width": 26.5, "height": 5.5, "fontSize": 13.0, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{old_price_spaced}", "condition": "{old_price} != ''"},
            {"id": "old_price_strike", "type": "line", "lineDirection": "horizontal", "x": 27.5, "y": 17.2, "width": 27.5, "height": 0.8, "borderWidth": 0.8, "borderColor": "#000000", "color": "#000000", "zIndex": 4, "content": "", "condition": "{old_price} != ''"},
            {"id": "short_code_text", "type": "text", "x": 4.0, "y": 24.8, "width": 23.0, "height": 4.2, "fontSize": 9.5, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "Код: {short_code}"},
            {"id": "barcode_small", "type": "barcode", "x": 4.0, "y": 29.5, "width": 23.0, "height": 7.5, "symbology": "CODE128", "humanReadable": False, "zIndex": 3, "content": "{barcode}"},
            {"id": "new_sale_price", "type": "text", "x": 27.0, "y": 20.8, "width": 27.5, "height": 9.5, "fontSize": 21.0, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{price_spaced}"},
            {"id": "uom_text", "type": "text", "x": 27.0, "y": 32.0, "width": 27.5, "height": 4.8, "fontSize": 9.0, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "Цена за: {uom}"}
        ]
    },
    {
        "title": "Radolfa Sale & Discount (58x40mm)",
        "label_size": "58x40mm",
        "description": "Discount / sale promotion label with safe printer margins, Radolfa header, date, item name, АКЦИЯ! badge, strikethrough old price, short code with barcode, and bold sale price (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.8, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_header", "type": "text", "x": 3.0, "y": 2.4, "width": 52.0, "height": 4.8, "fontSize": 11.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 2, "content": "{company}"},
            {"id": "header_divider", "type": "line", "lineDirection": "horizontal", "x": 2.5, "y": 7.4, "width": 53.0, "height": 0.8, "borderWidth": 0.8, "borderColor": "#000000", "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "date_header", "type": "text", "x": 31.0, "y": 7.8, "width": 23.5, "height": 4.2, "fontSize": 8.5, "fontBold": False, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{date:DD.MM.YYYY}"},
            {"id": "item_name", "type": "text", "x": 4.0, "y": 8.8, "width": 30.0, "height": 6.8, "fontSize": 10.0, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "promo_badge_bg", "type": "shape", "shapeType": "rect", "x": 4.0, "y": 16.5, "width": 22.0, "height": 6.8, "borderWidth": 0.5, "borderColor": "#000000", "color": "#000000", "zIndex": 2, "content": "", "condition": "{old_price} != ''"},
            {"id": "promo_badge_text", "type": "text", "x": 4.0, "y": 16.5, "width": 22.0, "height": 6.8, "fontSize": 10.5, "fontBold": True, "textAlign": "center", "color": "#ffffff", "zIndex": 3, "content": "АКЦИЯ!", "condition": "{old_price} != ''"},
            {"id": "old_price_label", "type": "text", "x": 28.0, "y": 11.0, "width": 26.5, "height": 4.2, "fontSize": 8.5, "fontBold": False, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "Старая цена:", "condition": "{old_price} != ''"},
            {"id": "old_price_val", "type": "text", "x": 28.0, "y": 14.5, "width": 26.5, "height": 5.5, "fontSize": 13.0, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{old_price_spaced}", "condition": "{old_price} != ''"},
            {"id": "old_price_strike", "type": "line", "lineDirection": "horizontal", "x": 27.5, "y": 17.2, "width": 27.5, "height": 0.8, "borderWidth": 0.8, "borderColor": "#000000", "color": "#000000", "zIndex": 4, "content": "", "condition": "{old_price} != ''"},
            {"id": "short_code_text", "type": "text", "x": 4.0, "y": 24.8, "width": 23.0, "height": 4.2, "fontSize": 9.5, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "Код: {short_code}"},
            {"id": "barcode_small", "type": "barcode", "x": 4.0, "y": 29.5, "width": 23.0, "height": 7.5, "symbology": "CODE128", "humanReadable": False, "zIndex": 3, "content": "{barcode}"},
            {"id": "new_sale_price", "type": "text", "x": 27.0, "y": 20.8, "width": 27.5, "height": 9.5, "fontSize": 21.0, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{price_spaced}"},
            {"id": "uom_text", "type": "text", "x": 27.0, "y": 32.0, "width": 27.5, "height": 4.8, "fontSize": 9.0, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "Цена за: {uom}"}
        ]
    },
    {
        "title": "Radolfa Black Box Price (58x40mm)",
        "label_size": "58x40mm",
        "description": "High-contrast retail tag with top header, short code, item name, barcode, and solid black price box (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.8, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_text", "type": "text", "x": 3.5, "y": 2.5, "width": 26.0, "height": 5.0, "fontSize": 11, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{company}"},
            {"id": "short_code_text", "type": "text", "x": 30.0, "y": 2.5, "width": 24.0, "height": 5.0, "fontSize": 11, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "КОД: {short_code}"},
            {"id": "header_divider", "type": "line", "lineDirection": "horizontal", "x": 2.5, "y": 7.6, "width": 53.0, "height": 0.8, "borderWidth": 0.8, "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "item_name", "type": "text", "x": 3.0, "y": 8.5, "width": 52.0, "height": 6.5, "fontSize": 9.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "barcode_obj", "type": "barcode", "x": 4.0, "y": 15.5, "width": 50.0, "height": 12.0, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "price_bg_box", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 28.5, "width": 53.0, "height": 9.5, "borderWidth": 0, "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "white_price_text", "type": "text", "x": 3.0, "y": 29.5, "width": 52.0, "height": 8.0, "fontSize": 18, "fontBold": True, "textAlign": "center", "color": "#ffffff", "zIndex": 3, "content": "{price_formatted}"}
        ]
    },
    {
        "title": "Radolfa Promo 1+1 (58x40mm)",
        "label_size": "58x40mm",
        "description": "Buy 1 Get 1 Free promotion label with company branding, short code, and promo highlight (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.8, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "header_company_bg", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 28.0, "height": 5.8, "borderWidth": 0, "color": "#e8e8e8", "zIndex": 2, "content": ""},
            {"id": "promo_company", "type": "text", "x": 3.5, "y": 2.5, "width": 26.0, "height": 5.0, "fontSize": 10, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{company}"},
            {"id": "promo_banner_bg", "type": "shape", "shapeType": "rect", "x": 30.5, "y": 2.0, "width": 25.0, "height": 5.8, "borderWidth": 0, "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "promo_badge_text", "type": "text", "x": 30.5, "y": 2.5, "width": 25.0, "height": 5.0, "fontSize": 9.5, "fontBold": True, "textAlign": "center", "color": "#ffffff", "zIndex": 3, "content": "АКЦИЯ 1+1"},
            {"id": "promo_item_name", "type": "text", "x": 3.0, "y": 8.5, "width": 52.0, "height": 6.5, "fontSize": 9.5, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "#{short_code} · {item_name}"},
            {"id": "promo_barcode", "type": "barcode", "x": 4.0, "y": 15.5, "width": 50.0, "height": 12.0, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "promo_tagline", "type": "text", "x": 3.5, "y": 29.5, "width": 26.0, "height": 7.0, "fontSize": 9.5, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "1+1 В ПОДАРОК"},
            {"id": "promo_price", "type": "text", "x": 30.0, "y": 29.0, "width": 24.0, "height": 8.0, "fontSize": 17, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "{price_formatted}"}
        ]
    },
    {
        "title": "Radolfa Minimalist (58x40mm)",
        "label_size": "58x40mm",
        "description": "Minimalist dual-divider retail layout with header, short code, item name, barcode, and 19px big price (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.7, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_name", "type": "text", "x": 3.5, "y": 2.5, "width": 26.0, "height": 5.0, "fontSize": 11, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{company}"},
            {"id": "short_code", "type": "text", "x": 30.0, "y": 2.5, "width": 24.0, "height": 5.0, "fontSize": 11, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "#{short_code}"},
            {"id": "top_divider", "type": "line", "lineDirection": "horizontal", "x": 2.5, "y": 7.6, "width": 53.0, "height": 0.5, "borderWidth": 0.5, "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "item_name", "type": "text", "x": 3.0, "y": 8.5, "width": 52.0, "height": 6.5, "fontSize": 10, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "barcode_obj", "type": "barcode", "x": 4.0, "y": 15.5, "width": 50.0, "height": 12.5, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "bottom_divider", "type": "line", "lineDirection": "horizontal", "x": 2.5, "y": 29.0, "width": 53.0, "height": 0.5, "borderWidth": 0.5, "color": "#000000", "zIndex": 2, "content": ""},
            {"id": "price_text", "type": "text", "x": 3.0, "y": 29.8, "width": 52.0, "height": 7.5, "fontSize": 19, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{price_formatted}"}
        ]
    },
    {
        "title": "Radolfa Boutique Frame (58x40mm)",
        "label_size": "58x40mm",
        "description": "Double frame boutique tag with boxed short code, item name, crisp barcode, and 18px bold price (58x40mm)",
        "layout": [
            {"id": "border_outer", "type": "shape", "shapeType": "rect", "x": 2.5, "y": 2.0, "width": 53.0, "height": 36.0, "borderWidth": 0.8, "borderColor": "#000000", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "border_inner", "type": "shape", "shapeType": "rect", "x": 3.2, "y": 2.7, "width": 51.6, "height": 34.6, "borderWidth": 0.3, "borderColor": "#888888", "color": "transparent", "zIndex": 1, "content": ""},
            {"id": "company_name", "type": "text", "x": 4.0, "y": 3.0, "width": 26.0, "height": 4.8, "fontSize": 10.5, "fontBold": True, "textAlign": "left", "color": "#000000", "zIndex": 3, "content": "{company}"},
            {"id": "short_code", "type": "text", "x": 31.0, "y": 3.0, "width": 22.0, "height": 4.8, "fontSize": 10.5, "fontBold": True, "textAlign": "right", "color": "#000000", "zIndex": 3, "content": "№ {short_code}"},
            {"id": "item_name", "type": "text", "x": 4.0, "y": 8.5, "width": 50.0, "height": 6.5, "fontSize": 10, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{item_name}"},
            {"id": "barcode_obj", "type": "barcode", "x": 4.0, "y": 15.5, "width": 50.0, "height": 12.0, "symbology": "EAN13", "humanReadable": True, "zIndex": 3, "content": "{barcode}"},
            {"id": "price_text", "type": "text", "x": 4.0, "y": 29.0, "width": 50.0, "height": 7.0, "fontSize": 18, "fontBold": True, "textAlign": "center", "color": "#000000", "zIndex": 3, "content": "{price_formatted}"}
        ]
    }
]


def ensure_default_templates(force_update=False):
    """Seed or update built-in label templates into Barcode Label Template DocType."""
    current_titles = {tmpl["title"] for tmpl in BUILTIN_LABEL_TEMPLATES}

    if force_update:
        # Delete obsolete built-in templates that are not in current BUILTIN_LABEL_TEMPLATES
        try:
            all_templates = frappe.get_all("Barcode Label Template", fields=["name", "title"])
            for t in all_templates:
                if t.title not in current_titles and (t.title.startswith("Radolfa") or t.name.startswith("Radolfa")):
                    frappe.delete_doc("Barcode Label Template", t.name, force=True, ignore_permissions=True)
        except Exception:
            frappe.log_error("Failed to clean up obsolete barcode label templates")

    for tmpl in BUILTIN_LABEL_TEMPLATES:
        if frappe.db.exists("Barcode Label Template", {"title": tmpl["title"]}):
            if force_update:
                try:
                    doc = frappe.get_doc("Barcode Label Template", {"title": tmpl["title"]})
                    doc.label_size = tmpl["label_size"]
                    doc.description = tmpl["description"]
                    doc.layout_json = json.dumps(tmpl["layout"])
                    doc.flags.ignore_permissions = True
                    doc.flags.ignore_links = True
                    doc.save()
                except Exception:
                    frappe.log_error(f"Failed to update barcode template {tmpl['title']}")
        else:
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
        fields=["name", "title", "label_size", "description", "modified", "thumbnail", "layout_json"],
        order_by="title asc",
    )
    return templates


@frappe.whitelist()
def get_label_template_detail(name):
    """Return full template including layout_json."""
    if not name:
        frappe.throw(_("Template name is required"))
    if not frappe.db.exists("Barcode Label Template", name):
        doc_name = frappe.db.get_value("Barcode Label Template", {"title": name}, "name")
        if doc_name:
            name = doc_name
        else:
            frappe.throw(_("Template {0} not found").format(name))
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
