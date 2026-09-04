# Copyright (c) 2026, Youssef Restom and contributors
# For license information, please see license.txt

import frappe
from posawesome.posawesome.api.label_templates import ensure_default_templates


def execute():
    """Update built-in barcode label templates with enhanced designs and layouts."""
    ensure_default_templates(force_update=True)
