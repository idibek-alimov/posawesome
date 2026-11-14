# -*- coding: utf-8 -*-
# Copyright (c) 2026, Retail OS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


FISCAL_FIELDS = [
	{
		"fieldname": "custom_fiscal_fd_number",
		"label": "ФД Номер",
		"fieldtype": "Data",
		"insert_after": "naming_series",
		"read_only": 1,
		"in_standard_filter": 1,
		"description": "Government Fiscal Document Number (TP809)",
	},
	{
		"fieldname": "custom_fiscal_fpd",
		"label": "ФПД (Фискальный признак)",
		"fieldtype": "Data",
		"insert_after": "custom_fiscal_fd_number",
		"read_only": 1,
		"description": "Cryptographic signature of the receipt",
	},
	{
		"fieldname": "custom_fiscal_shift_number",
		"label": "Номер фискальной смены",
		"fieldtype": "Int",
		"insert_after": "custom_fiscal_fpd",
		"read_only": 1,
		"description": "TP809 Cashier shift number",
	},
	{
		"fieldname": "custom_fiscal_status",
		"label": "Статус фискализации",
		"fieldtype": "Select",
		"options": "Черновик\nФискализирован\nОшибка\nБез чека",
		"default": "Черновик",
		"insert_after": "custom_fiscal_shift_number",
		"read_only": 1,
		"in_standard_filter": 1,
		"description": "Fiscal status of this sale",
	},
	{
		"fieldname": "custom_sales_person",
		"label": "Продавец / Консультант",
		"fieldtype": "Link",
		"options": "Sales Person",
		"insert_after": "customer",
		"in_standard_filter": 1,
		"description": "Sales person tagged for commission calculations",
	},
]

USER_FIELDS = [
	{
		"fieldname": "custom_manager_badge",
		"label": "Штрихкод администратора",
		"fieldtype": "Data",
		"insert_after": "username",
		"description": "Barcode on manager badge (starts with MGR-)",
	}
]


def ensure_fiscal_fields():
	"""Ensure custom fiscal and authorization fields exist on target doctypes."""
	for doctype in ("POS Invoice", "Sales Invoice"):
		for fld in FISCAL_FIELDS:
			custom_name = f"{doctype}-{fld['fieldname']}"
			if not frappe.db.exists("Custom Field", custom_name):
				create_custom_field(doctype, fld)
		frappe.clear_cache(doctype=doctype)

	for fld in USER_FIELDS:
		custom_name = f"User-{fld['fieldname']}"
		if not frappe.db.exists("Custom Field", custom_name):
			create_custom_field("User", fld)
	frappe.clear_cache(doctype="User")


def validate_fiscal_metadata(doc, method=None):
	"""Native form/import/API saves cannot forge or overwrite printer outcomes.

	The scoped fiscal services use locked database writes after validating their
	prepared attempt. Ordinary invoice saves must preserve these server-owned fields.
	"""
	fields = [f["fieldname"] for f in FISCAL_FIELDS if f["fieldname"].startswith("custom_fiscal_")]
	fields += ["custom_fiscal_attempt", "custom_fiscal_payload"]
	fields = [f for f in fields if doc.meta.has_field(f)]
	previous = frappe.db.get_value(doc.doctype, doc.name, fields, as_dict=True) if fields and not doc.is_new() else None
	for field in fields:
		old = previous.get(field) if previous else "Черновик" if field == "custom_fiscal_status" else ""
		current = doc.get(field)
		if not previous and field == "custom_fiscal_status" and current in (None, "", "Черновик"):
			continue
		if field == "custom_fiscal_shift_number":
			changed = frappe.utils.cint(current) != frappe.utils.cint(old)
		else:
			changed = str(current or "") != str(old or "")
		if changed:
			frappe.throw(_("Fiscal results can only be changed through the guarded fiscal workflow."), frappe.PermissionError)


def scoped_invoice(invoice_name, doctype="POS Invoice"):
	from posawesome.posawesome.api.pos_access import get_authorized_pos_profile
	if doctype not in ("POS Invoice", "Sales Invoice"):
		frappe.throw(_("Unsupported invoice type"), frappe.PermissionError)
	doc = frappe.get_doc(doctype, invoice_name)
	profile = get_authorized_pos_profile(doc.get("pos_profile"), company=doc.company)
	if not doc.get("pos_profile") or doc.docstatus != 1:
		frappe.throw(_("A submitted POS sale is required"))
	return doc, profile


def _lock_invoice(doctype, name):
	# Supported doctypes are checked before interpolation; lock spans the request.
	frappe.db.sql(f"SELECT name FROM `tab{doctype}` WHERE name=%s FOR UPDATE", name)


def _receipt_payload(doc):
	from posawesome.posawesome.api.fiscal_contract import build_receipt
	payment_types = {p.mode_of_payment: frappe.get_cached_value("Mode of Payment", p.mode_of_payment, "type")
		for p in doc.get("payments") or []}
	source = doc.as_dict()
	for item in source.get("items") or []:
		item["is_stock_item"] = frappe.get_cached_value("Item", item.item_code, "is_stock_item")
	try:
		return build_receipt(source, payment_types)
	except ValueError as exc:
		frappe.throw(str(exc))


@frappe.whitelist()
def fiscal_checkout_context(invoice_name, doctype="POS Invoice"):
	"""Validate before opening hardware shift; never prepare/send an invoice here."""
	from posawesome.posawesome.api.terminal_state import get_active_terminal_cashier
	doc, profile = scoped_invoice(invoice_name, doctype)
	if doc.get("custom_fiscal_fd_number"):
		return dict(completed=True, fdNumber=doc.custom_fiscal_fd_number, fpd=doc.custom_fiscal_fpd)
	context = get_fiscal_context(invoice_name, doctype)
	if doc.get("custom_fiscal_status") == "Неизвестно":
		return context
	_receipt_payload(doc)
	context["cashier"] = frappe.utils.get_fullname(get_active_terminal_cashier(profile.name))
	return context


@frappe.whitelist(methods=["POST"])
def prepare_fiscal_receipt(invoice_name, doctype="POS Invoice"):
	doc, profile = scoped_invoice(invoice_name, doctype)
	_lock_invoice(doctype, invoice_name)
	doc.reload()
	if doc.get("custom_fiscal_fd_number"):
		return dict(completed=True, fdNumber=doc.custom_fiscal_fd_number, fpd=doc.custom_fiscal_fpd)
	if doc.get("custom_fiscal_status") == "Неизвестно":
		frappe.throw(_("Fiscal result unknown. Check the printer journal and reconcile the existing FD before retrying."))
	if not profile.get("posa_fiscal_printer_url") and not profile.get("posa_fiscal_bridge_url"):
		frappe.throw(_("Configure the TP809 printer or local bridge on POS Profile"))
	payload = _receipt_payload(doc)
	attempt = frappe.generate_hash(length=32)
	frappe.db.set_value(doctype, invoice_name, dict(custom_fiscal_attempt=attempt,
		custom_fiscal_payload=frappe.as_json(payload), custom_fiscal_status="Неизвестно"), update_modified=False)
	return dict(attempt=attempt, payload=payload, printer_url=profile.get("posa_fiscal_printer_url"),
		bridge_url=profile.get("posa_fiscal_bridge_url") or "http://localhost:5000")


@frappe.whitelist(methods=["POST"])
def save_fiscal_data(invoice_name, doctype="POS Invoice", fiscal_data=None, attempt=None):
	"""Acknowledge a prepared transmission; replay cannot overwrite another FD."""
	doc, profile = scoped_invoice(invoice_name, doctype)
	_lock_invoice(doctype, invoice_name)
	doc.reload()
	if not attempt or attempt != doc.get("custom_fiscal_attempt"):
		frappe.throw(_("Fiscal attempt does not match"), frappe.PermissionError)
	response = frappe.parse_json(fiscal_data) if isinstance(fiscal_data, str) else fiscal_data or {}
	if response.get("rc") != "SUCCESS":
		frappe.throw(_("Printer success response is required"))
	data = response.get("data") or {}
	fd, fpd = data.get("fdNumber"), data.get("fpd")
	if not str(fd or "").isdigit() or int(fd) <= 0 or not str(fpd or "").strip():
		frappe.throw(_("Printer response is missing FD or FPD"))
	if doc.get("custom_fiscal_fd_number") and (str(fd) != str(doc.custom_fiscal_fd_number) or str(fpd) != str(doc.custom_fiscal_fpd)):
		frappe.throw(_("This invoice already has a different fiscal document"))
	# An FD belongs to a particular device, not to every register globally.
	for dt in ("POS Invoice", "Sales Invoice"):
		duplicates = frappe.get_all(dt, filters=dict(pos_profile=doc.pos_profile, custom_fiscal_fd_number=str(fd)), fields=["name"])
		if any(dt != doctype or row.name != invoice_name for row in duplicates):
			frappe.throw(_("Fiscal document is already assigned to another sale"))
	frappe.db.set_value(doctype, invoice_name, dict(custom_fiscal_fd_number=str(fd), custom_fiscal_fpd=str(fpd),
		custom_fiscal_shift_number=int(data.get("shiftNumber") or 0), custom_fiscal_status="Фискализирован"), update_modified=False)
	return dict(success=True, fdNumber=fd, fpd=fpd)


@frappe.whitelist(methods=["POST"])
def record_fiscal_rejection(invoice_name, doctype, attempt, rc):
	doc, _profile = scoped_invoice(invoice_name, doctype)
	_lock_invoice(doctype, invoice_name)
	doc.reload()
	if attempt != doc.get("custom_fiscal_attempt") or doc.get("custom_fiscal_fd_number"):
		frappe.throw(_("Fiscal attempt does not match"))
	# Only explicit firmware refusal codes permit another transmission. Transport,
	# HTTP, parse and missing-response failures always retain the unknown result.
	if rc not in {"INVALID_DOC", "SHIFT_CLOSED", "SHIFT_MUST_BE_OPENED", "SHIFT_TOO_LONG", "FN_EXPIRED", "FN_BLOCKED", "CORE_IS_NOT_ACTIVATED", "CORE_IS_BLOCKED", "FISCAL_MODULE_EXPIRED"}:
		return dict(status="Неизвестно")
	frappe.db.set_value(doctype, invoice_name, "custom_fiscal_status", "Ошибка", update_modified=False)
	return dict(status="Ошибка")


@frappe.whitelist(methods=["POST"])
def confirm_unissued_fiscal_attempt(invoice_name, doctype, attempt, journal_checked=0):
	"""Human reconciliation of a missing FD; transport failures cannot call this automatically."""
	doc, _profile = scoped_invoice(invoice_name, doctype)
	_lock_invoice(doctype, invoice_name)
	doc.reload()
	if not frappe.utils.cint(journal_checked) or attempt != doc.get("custom_fiscal_attempt"):
		frappe.throw(_("Check the printer journal and confirm that no fiscal document was issued."))
	if doc.get("custom_fiscal_fd_number") or doc.get("custom_fiscal_status") != "Неизвестно":
		frappe.throw(_("This sale does not have an unknown fiscal result."))
	doc.add_comment("Comment", _("Printer journal checked by {0}: no fiscal document was issued for attempt {1}. A new fiscal attempt is permitted.").format(frappe.session.user, attempt))
	frappe.db.set_value(doctype, invoice_name, "custom_fiscal_status", "Ошибка", update_modified=False)
	return dict(status="Ошибка")


@frappe.whitelist(methods=["POST"])
def record_non_fiscal_sale(invoice_name, doctype="POS Invoice", reason=None):
	doc, _profile = scoped_invoice(invoice_name, doctype)
	_lock_invoice(doctype, invoice_name)
	doc.reload()
	if not doc.get("custom_fiscal_fd_number") and doc.get("custom_fiscal_status") != "Неизвестно":
		frappe.db.set_value(doctype, invoice_name, "custom_fiscal_status", "Без чека", update_modified=False)
	return dict(success=True)


@frappe.whitelist()
def get_fiscal_context(invoice_name, doctype="POS Invoice"):
	doc, profile = scoped_invoice(invoice_name, doctype)
	return dict(attempt=doc.get("custom_fiscal_attempt"), status=doc.get("custom_fiscal_status"),
		fdNumber=doc.get("custom_fiscal_fd_number"), printer_url=profile.get("posa_fiscal_printer_url"),
		bridge_url=profile.get("posa_fiscal_bridge_url") or "http://localhost:5000")


@frappe.whitelist()
def profile_fiscal_context(pos_profile=None):
	from posawesome.posawesome.api.pos_access import get_authorized_pos_profile
	profile = get_authorized_pos_profile(pos_profile)
	return dict(printer_url=profile.get("posa_fiscal_printer_url"),
		bridge_url=profile.get("posa_fiscal_bridge_url") or "http://localhost:5000")


@frappe.whitelist()
def verify_manager_badge(badge_code):
	"""
	Validate scanned manager barcode (prefix MGR-).
	Returns valid=True and supervisor identity if authorized.
	"""
	ensure_fiscal_fields()
	code = (badge_code or "").strip()
	if not code:
		return {"valid": False, "message": _("Штрихкод не указан")}

	# Must have MGR- prefix
	if not code.upper().startswith("MGR-"):
		return {"valid": False, "message": _("Штрихкод должен начинаться с MGR-")}

	suffix = code[4:].strip()

	# 1. Match custom_manager_badge on active User
	user = frappe.db.get_value(
		"User",
		{"custom_manager_badge": code, "enabled": 1},
		["name", "full_name"],
		as_dict=True,
	)

	# 2. Match username or email after MGR-
	if not user:
		user = frappe.db.get_value(
			"User",
			{"name": suffix, "enabled": 1},
			["name", "full_name"],
			as_dict=True,
		)

	# 3. Match administrator alias (MGR-ADMIN, MGR-ADMINISTRATOR)
	if not user and suffix.lower() in ("admin", "administrator", "super", "supervisor"):
		user = frappe.db.get_value(
			"User",
			{"name": "Administrator", "enabled": 1},
			["name", "full_name"],
			as_dict=True,
		)

	# 4. Check if the user has supervisor/manager roles
	if user:
		roles = set(frappe.get_roles(user["name"]))
		manager_roles = {"System Manager", "Accounts Manager", "Stock Manager", "Retail Manager", "Retail Owner", "POS Supervisor"}
		if roles.intersection(manager_roles):
			return {
				"valid": True,
				"manager_user": user["name"],
				"manager_name": user["full_name"] or user["name"],
				"duration_seconds": 60,
				"message": _("Скидка авторизована: {0}").format(user["full_name"] or user["name"]),
			}

	# Also check if current session user is already System Manager or Retail Manager
	current_roles = set(frappe.get_roles())
	if current_roles.intersection({"System Manager", "Retail Manager", "Retail Owner", "POS Supervisor"}):
		return {
			"valid": True,
			"manager_user": frappe.session.user,
			"manager_name": frappe.utils.get_fullname(frappe.session.user),
			"duration_seconds": 60,
			"message": _("Авторизовано текущим администратором"),
		}

	return {
		"valid": False,
		"message": _("Штрихкод администратора не распознан или у пользователя нет прав менеджера"),
	}


@frappe.whitelist(methods=["POST"])
def transfer_shift_cash_to_safe(pos_closing_shift_name, amount=None):
	from posawesome.posawesome.shift_review.transfers import transfer
	return transfer(pos_closing_shift_name, amount)
