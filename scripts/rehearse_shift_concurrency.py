"""Real two-connection rehearsal, with committed native fixtures on an isolated site.

Requires BOTH allow_tests and shift_review_rehearsal in that site's configuration.
Never point this at a business site. Fixtures remain for inspection; dispose of the
isolated database afterwards rather than deleting submitted accounting history.
"""

import argparse
import json
import os
import threading
from pathlib import Path
from uuid import uuid4

import frappe

from erpnext.accounts.expense_services.native_test_support import ensure_test_company
from posawesome.posawesome.shift_review import service, transfers
from posawesome.posawesome.shift_review.test_native_workflow import TestNativeShiftWorkflow


def rehearse(site, sites_path):
    frappe.init(site, sites_path=str(sites_path))
    if not (frappe.conf.get("allow_tests") and frappe.conf.get("shift_review_rehearsal")):
        raise RuntimeError("Both disposable-site rehearsal flags are required")
    frappe.connect()
    ensure_test_company()
    fixture = TestNativeShiftWorkflow()
    fixture.setUp()
    closing, review = fixture.close()
    other = frappe.get_doc(dict(doctype="User", email="review-race-" + uuid4().hex[:8] + "@example.test",
        first_name="Concurrent accountant", send_welcome_email=0,
        roles=[dict(role="Accounts Manager")])).insert().name
    frappe.db.commit()
    row = next(row for row in review.accounts if row.account == fixture.cash)
    args = dict(reason="Isolated concurrency rehearsal", row_key=row.row_key, signed_amount=-50,
                posting_date=frappe.utils.today())
    first = service.act(review.name, "Cash adjustment", args, uuid4().hex, review.version)
    started, finished = threading.Event(), threading.Event()
    outcome = {}

    def competing_approval():
        try:
            frappe.init(site, sites_path=str(sites_path))
            frappe.connect()
            frappe.set_user(other)
            started.set()
            service.act(review.name, "Cash adjustment", args, uuid4().hex, review.version)
            frappe.db.commit()
            outcome["result"] = "unexpected duplicate approval"
        except frappe.TimestampMismatchError:
            outcome["result"] = "stale review rejected"
            frappe.db.rollback()
        except Exception as error:
            outcome["error"] = type(error).__name__ + ": " + str(error)
            frappe.db.rollback()
        finally:
            frappe.destroy()
            finished.set()

    worker = threading.Thread(target=competing_approval, daemon=True)
    worker.start()
    try:
        assert started.wait(10), "Second connection did not start"
        assert not finished.wait(0.25), "Second approval did not wait for the review lock"
    finally:
        # Release the first native posting only after the second connection starts.
        frappe.db.commit()
    worker.join(timeout=20)
    assert finished.is_set(), "Concurrent approval did not finish"
    assert outcome == {"result": "stale review rejected"}, outcome
    assert fixture.balance(fixture.cash) == -50
    assert frappe.db.count("POS Shift Review Action", {"review": review.name, "action": "Cash adjustment"}) == 1
    assert frappe.get_doc("Journal Entry", first["operation"]["financial_name"]).docstatus == 1

    # Establish an old repeatable-read snapshot before another connection commits
    # the next native opening. The old-count transfer must use a current read.
    frappe.db.sql("SELECT name FROM `tabPOS Opening Shift` WHERE pos_profile=%s", fixture.profile.name)
    original_db = frappe.local.db
    frappe.connect()
    new_db = frappe.local.db
    try:
        next_opening = fixture.open_shift(0)
        new_db.commit()
    finally:
        new_db.close()
        frappe.local.db = original_db
    assert not frappe.db.exists("POS Opening Shift", next_opening.name), "Expected an older repeatable-read snapshot"
    try:
        transfers.transfer(closing.name)
    except frappe.ValidationError as error:
        assert "Another shift has opened" in str(error), str(error)
    else:
        raise AssertionError("The stale original count was transferred after a following opening")
    frappe.db.rollback()
    assert fixture.balance(fixture.safe) == 0
    assert not frappe.db.exists("POS Shift Review Action", {"review": review.name, "action": "Safe transfer"})
    frappe.db.rollback()
    frappe.destroy()
    return {"concurrent_approval": "one native JE; stale competing review rejected",
            "old_snapshot_transfer": "following native opening found by current locking read; no transfer posted"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites-path", type=Path, required=True)
    parser.add_argument("--site", required=True)
    args = parser.parse_args()
    root = args.sites_path.resolve()
    if (root / args.site).resolve().parent != root:
        parser.error("--site must be a direct child of --sites-path")
    os.environ["FRAPPE_BENCH_ROOT"] = str(root.parent)
    os.chdir(root)
    print(json.dumps(rehearse(args.site, root), indent=2))


if __name__ == "__main__":
    main()
