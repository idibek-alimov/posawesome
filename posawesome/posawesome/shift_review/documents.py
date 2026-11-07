"""Native controller invariants also protect REST, imports and direct document calls."""

import frappe
from frappe import _
from frappe.model.document import Document
from . import SERVICE


class ServiceDocument(Document):
    def validate(self):
        if self.flags.get("shift_review_service") is not SERVICE:
            frappe.throw(_("Shift review records are maintained by the authorized review service."), frappe.PermissionError)
        previous = self.get_doc_before_save()
        if previous:
            for key in self.immutable_fields:
                if previous.get(key) != self.get(key):
                    frappe.throw(_("Original shift review evidence cannot be overwritten."))

    def on_trash(self):
        frappe.throw(_("Shift review audit history cannot be deleted."))


class ReviewDocument(ServiceDocument):
    immutable_fields = ("company", "pos_profile", "pos_opening_shift", "closing_shift", "cashier", "currency",
                        "currency_precision", "cashier_reason", "snapshot_json", "snapshot_hash")


class ActionDocument(ServiceDocument):
    immutable_fields = ("review", "client_request_id", "request_fingerprint", "actor", "action", "row_key",
                        "signed_amount", "currency", "reason", "evidence_json", "source_doctype", "source_name",
                        "financial_doctype", "financial_name")


class ClaimDocument(ServiceDocument):
    immutable_fields = ("claim_key", "review", "row_key", "financial_doctype", "financial_name", "account", "capacity", "currency", "evidence_json")
