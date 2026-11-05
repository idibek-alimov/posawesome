# -*- coding: utf-8 -*-
# Copyright (c) 2026, Retail OS and contributors
# For license information, please see license.txt

import json
import math

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime
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


@frappe.whitelist()
def save_fiscal_data(invoice_name, doctype="POS Invoice", fiscal_data=None):
	"""Save fiscal identification returned by TP809 printer to the invoice."""
	ensure_fiscal_fields()
	if isinstance(fiscal_data, str):
		fiscal_data = json.loads(fiscal_data or "{}")
	elif not fiscal_data:
		fiscal_data = {}

	fd_number = fiscal_data.get("fdNumber") or fiscal_data.get("fd_number")
	fpd = fiscal_data.get("fpd")
	shift_number = fiscal_data.get("shiftNumber") or fiscal_data.get("shift_number")
	status = "Фискализирован" if fd_number else "Ошибка"

	updates = {
		"custom_fiscal_fd_number": str(fd_number) if fd_number else "",
		"custom_fiscal_fpd": str(fpd) if fpd else "",
		"custom_fiscal_shift_number": int(shift_number) if shift_number else 0,
		"custom_fiscal_status": status,
	}

	if frappe.db.exists(doctype, invoice_name):
		frappe.db.set_value(doctype, invoice_name, updates, update_modified=False)
		frappe.db.commit()

	return {"success": True, "invoice": invoice_name, "status": status, "fdNumber": fd_number}


@frappe.whitelist()
def record_non_fiscal_sale(invoice_name, doctype="POS Invoice", reason="Обычная продажа без чека"):
	"""Mark an invoice explicitly as completed without fiscal printing."""
	ensure_fiscal_fields()
	if frappe.db.exists(doctype, invoice_name):
		frappe.db.set_value(
			doctype,
			invoice_name,
			{
				"custom_fiscal_status": "Без чека",
			},
			update_modified=False,
		)
		frappe.db.commit()

	return {"success": True, "invoice": invoice_name, "status": "Без чека"}


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


@frappe.whitelist()
def transfer_shift_cash_to_safe(pos_closing_shift_name, amount=None):
	"""
	Auto-transfer cash from closed POS shift into 'Сейф магазина' in Money Hub.
	"""
	if not pos_closing_shift_name or not frappe.db.exists("POS Closing Shift", pos_closing_shift_name):
		return {"success": False, "message": _("Смена закрытия не найдена")}

	closing_shift = frappe.get_doc("POS Closing Shift", pos_closing_shift_name)
	from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.data import (
		get_authorized_opening_shift,
	)

	get_authorized_opening_shift(closing_shift.pos_opening_shift)
	if closing_shift.docstatus != 1:
		frappe.throw(_("Only a submitted closing shift can transfer cash to the safe."))
	company = closing_shift.company
	cash_mode = frappe.db.get_value("POS Profile", closing_shift.pos_profile, "posa_cash_mode_of_payment") or "Cash"
	cash_account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": cash_mode, "company": company}, "default_account"
	)
	counted = next(
		(flt(row.closing_amount) for row in closing_shift.get("payment_reconciliation", [])
		 if row.mode_of_payment == cash_mode), 0,
	)
	transfer_amt = counted if amount in (None, "") else flt(amount)
	if not math.isfinite(transfer_amt) or transfer_amt > counted:
		frappe.throw(_("Transfer amount cannot exceed the counted cash."))
	if transfer_amt <= 0:
		return {"success": False, "message": _("No counted cash to transfer to the safe.")}

	# Identify Safe wallet in Money Hub
	safe_wallet = frappe.db.get_value(
		"Money Wallet",
		{"company": company, "wallet_type": "Safe", "enabled": 1},
		["name", "wallet_name", "account"],
		as_dict=True,
	)

	if not safe_wallet:
		# Try name match
		safe_wallet = frappe.db.get_value(
			"Money Wallet",
			{"company": company, "wallet_name": ["like", "%сейф%"], "enabled": 1},
			["name", "wallet_name", "account"],
			as_dict=True,
		)

	if not safe_wallet:
		return {
			"success": False,
			"message": _("Кошелек «Сейф» не найден в Money Hub. Создайте его на странице /app/money-hub."),
		}

	# Select the wallet for this register's configured account, never another till.
	pos_cash_wallet = frappe.db.get_value(
		"Money Wallet", {"company": company, "account": cash_account, "enabled": 1},
		["name", "wallet_name", "account"], as_dict=True,
	) if cash_account else None
	if not pos_cash_wallet:
		return {"success": False, "message": _("No enabled wallet matches this register's cash account.")}
	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	for account in (pos_cash_wallet["account"], safe_wallet["account"]):
		if frappe.db.get_value("Account", account, "account_currency") != company_currency:
			return {"success": False, "message": _("Use Money Hub to transfer between accounts with different currencies.")}
	from_wallet_name = pos_cash_wallet["name"]

	try:
		from erpnext.accounts.page.money_hub.money_hub import transfer_money

		res = transfer_money(
			from_wallet=from_wallet_name,
			to_wallet=safe_wallet["name"],
			amount=transfer_amt,
			kind="Инкассация",
			note=f"Авто-инкассация при закрытии смены {pos_closing_shift_name}",
			company=company,
		)
		return {
			"success": True,
			"transferred_amount": transfer_amt,
			"target_wallet": safe_wallet["wallet_name"],
			"message": _("Transferred {0} {1} to {2}.").format(
				transfer_amt, company_currency, safe_wallet["wallet_name"]
			),
		}
	except Exception as e:
		frappe.log_error("Auto transfer to safe failed", str(e))
		return {"success": False, "message": str(e)}
