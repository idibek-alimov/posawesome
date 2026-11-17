# -*- coding: utf-8 -*-
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


def validate(doc, method=None):
    validate_attendance_settings(doc)


def validate_attendance_settings(doc):
    if not cint(doc.get("posa_enforce_attendance")):
        return

    site_name = doc.get("posa_attendance_site")
    if not site_name:
        frappe.throw(_("Attendance Site is required when attendance enforcement is enabled."))

    if not frappe.db.exists("Retail Attendance Site", site_name):
        frappe.throw(_("Attendance Site {0} not found.").format(site_name))

    site_company = frappe.db.get_value("Retail Attendance Site", site_name, "company")
    if site_company != doc.company:
        frappe.throw(
            _("The selected Attendance Site belongs to {0}, not {1}.").format(
                site_company, doc.company
            )
        )
