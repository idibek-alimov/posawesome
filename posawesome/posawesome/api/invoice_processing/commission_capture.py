"""Private POS submission attestation; never a client API or queued capability.

ERPNext asks this module for authority only within the exact native submit. The
ordinary POS response, ledger schema and offline acknowledgement stay unchanged.
Disabled ERPNext capture performs no additional reads or writes here.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

import frappe


_submission = ContextVar("posa_commission_submission", default=None)
_worker = ContextVar("posa_commission_worker", default=None)
IDENTITY = ("doctype", "name", "company", "pos_profile", "posa_client_request_id",
            "posa_pos_opening_shift", "posa_cashier")


@dataclass(frozen=True)
class Submission:
    doc: object
    actor: str
    identity: tuple
    ledger_name: str | None
    worker: object


def _identity(doc):
    return tuple(doc.get(key) for key in IDENTITY)


def worker_context():
    """Server queue metadata only; this is not source capture authority."""
    return _worker.get()


@contextmanager
def queued_submission(kwargs):
    # Called inside each actual worker. Copy only server queue identity, never a
    # capability or private HR projection. Nested submit creates a NEW attestation.
    token = _worker.set({key: kwargs.get(key) for key in
                         ("ledger_name", "user", "cashier", "opening_shift", "opening_user")})
    try:
        yield
    finally:
        _worker.reset(token)


def submit_source(doc, ledger_name=None):
    token = _submission.set(Submission(doc, frappe.session.user, _identity(doc), ledger_name, _worker.get()))
    try:
        return doc.submit()
    finally:
        _submission.reset(token)


def authorized_source(doc):
    """Revalidate persisted POS authority at both native capture boundaries.

    Absence is not authority. Expected scope changes withhold evidence; unexpected
    DB/schema errors propagate to ERPNext's sanitized transaction rollback.
    """
    grant = _submission.get()
    if not grant or grant.doc is not doc:
        return False
    from erpnext.setup.staff_commission_snapshots import fail
    from posawesome.posawesome.api.invoice_processing import creation
    from posawesome.posawesome.api.pos_access import get_authorized_pos_profile
    from posawesome.posawesome.api.idempotency import assert_invoice_request_scope
    from posawesome.posawesome.api.terminal_state import (
        get_active_terminal_cashier, validate_assigned_terminal_cashier,
    )

    def require(condition):
        if not condition:
            fail("source_authority_required")

    require(grant.actor != "Guest" and grant.actor == frappe.session.user and
            grant.identity == _identity(doc) and bool(grant.ledger_name))
    try:
        profile = get_authorized_pos_profile(doc.pos_profile, company=doc.company)
        persisted = frappe.get_doc(doc.doctype, doc.name, for_update=True)
        assert_invoice_request_scope(persisted, pos_profile=profile.name,
                                     company=profile.company, permission_type="write")
        require(_identity(persisted) == grant.identity and persisted.docstatus in (0, 1))
        ledger = frappe.get_doc(creation.LEDGER_DOCTYPE, grant.ledger_name, for_update=True)
        creation._assert_submission_ledger_scope(ledger, profile.name, profile.company, doc.doctype)
        require(ledger.owner == grant.actor and ledger.invoice_name == doc.name and
                ledger.state == creation.STATE_DRAFT_CREATED and
                ledger.client_request_id == doc.posa_client_request_id and
                ledger.ledger_key == creation._submission_ledger_key(
                    ledger.client_request_id, doc.company, doc.pos_profile, doc.doctype))
        accepted = creation._json_loads(ledger.invoice_payload)
        request = creation._json_loads(ledger.request_data)
        require(accepted.get("posa_client_request_id") == ledger.client_request_id and
                accepted.get("posa_pos_opening_shift") == doc.posa_pos_opening_shift and
                request.get("_posa_authoritative_cashier") == doc.posa_cashier)
        shift = frappe.get_doc("POS Opening Shift", doc.posa_pos_opening_shift, for_update=True)
        require(shift.docstatus == 1 and shift.company == doc.company and
                shift.pos_profile == doc.pos_profile and shift.user == grant.actor)
        if grant.worker is not None:
            work = grant.worker
            require(work == dict(ledger_name=ledger.name, user=grant.actor, cashier=doc.posa_cashier,
                                 opening_shift=shift.name, opening_user=shift.user))
            cashier = validate_assigned_terminal_cashier(profile.name, doc.posa_cashier)
        else:
            require(shift.status == "Open" and not shift.pos_closing_shift)
            cashier = get_active_terminal_cashier(profile.name)
        require(bool(cashier) and cashier == doc.posa_cashier)
    except (frappe.PermissionError, frappe.DoesNotExistError):
        fail("source_authority_required")
    return True
