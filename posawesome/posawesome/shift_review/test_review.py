"""Controlled document/ledger fixtures, not native MariaDB or live GL verification."""

import copy
import json
import unittest
from contextlib import ExitStack
from decimal import Decimal
from inspect import unwrap
from unittest.mock import Mock, patch

import frappe
from erpnext.accounts.expense_services import commands, policy as expense_policy, shift_adjustments
from erpnext.accounts.doctype.quick_expense.quick_expense import QuickExpense
from posawesome.posawesome.shift_review import arithmetic, closing, lifecycle, policy, service, snapshot, transfers
from posawesome.posawesome.doctype.pos_closing_shift import pos_closing_shift as controller


class Doc(frappe._dict):
    def __init__(self, fixture, data):
        super().__init__(data)
        self.fixture = fixture
        self.flags = frappe._dict()
        self.setdefault("docstatus", 0)
        self.setdefault("creation", "2026-11-06 10:00:00")
        self.setdefault("modified", "2026-11-06 10:00:00")

    def append(self, field, data):
        self.setdefault(field, []).append(frappe._dict(data))

    def as_dict(self):
        return {k: v for k, v in self.items() if k not in {"fixture", "flags"}}

    def set(self, key, value):
        self[key] = value

    def check_permission(self, permission):
        if not self.fixture.permission(self.doctype, permission, doc=self):
            raise frappe.PermissionError("Native permission denied")

    def insert(self, **kwargs):
        if not self.name:
            self.name = f"{self.doctype}:{len(self.fixture.docs)+1}"
        for field in {"POS Shift Review Action": ["client_request_id"], "POS Shift Source Claim": ["claim_key"], "POS Shift Review": ["closing_shift"]}.get(self.doctype, []):
            if self.fixture.matches(self.doctype, {field: self[field]}):
                raise frappe.DuplicateEntryError(field)
        self.fixture.docs[(self.doctype, self.name)] = self
        return self

    def save(self, **kwargs):
        self.fixture.docs[(self.doctype, self.name)] = self
        return self

    def db_set(self, key, value=None, **kwargs):
        self.update(key if isinstance(key, dict) else {key: value})

    def submit(self):
        self.check_permission("submit")
        self.docstatus = 1
        if self.doctype == "Journal Entry":
            self.fixture.post(self)
        return self


class ReviewFixture(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.docs, self.ledger, self.locks, self.points = {}, [], [], {}
        self.roles = ["Retail Owner", "Accounts Manager"]
        self.denied = set()
        self.f = Mock(_dict=frappe._dict, PermissionError=frappe.PermissionError, ValidationError=frappe.ValidationError,
                      TimestampMismatchError=frappe.TimestampMismatchError, DoesNotExistError=frappe.DoesNotExistError)
        self.f.session.user = "owner"
        self.f.get_roles.side_effect = lambda *args: self.roles
        self.f.throw.side_effect = lambda message, exception=frappe.ValidationError, **kwargs: (_ for _ in ()).throw(exception(message))
        self.f.has_permission.side_effect = self.permission
        self.f.get_doc.side_effect = self.get_doc
        self.f.get_cached_doc.side_effect = self.get_doc
        self.f.new_doc.side_effect = lambda dt: Doc(self, dict(doctype=dt))
        self.f.get_cached_value.side_effect = self.cached
        self.f.db.get_value.side_effect = self.lookup
        self.f.db.set_value.side_effect = self.set_value
        self.f.db.exists.side_effect = lambda dt, filters: bool(self.matches(dt, filters if isinstance(filters, dict) else {"name": filters}))
        self.f.db.table_exists.return_value = True
        self.f.db.has_column.return_value = True
        self.f.get_all.side_effect = self.get_all
        self.f.db.get_values.side_effect = lambda dt, filters=None, fieldname=None, **kw: self.get_all(dt, filters, fieldname, **kw)
        self.f.db.savepoint.side_effect = self.savepoint
        self.f.db.rollback.side_effect = self.rollback
        self.f.utils.today.return_value = "2026-11-06"
        self.f.utils.now_datetime.return_value = "2026-11-06 12:00:00"
        for module in (service, policy, snapshot, lifecycle, closing, transfers, shift_adjustments):
            self.stack.enter_context(patch.object(module, "frappe", self.f))
            if hasattr(module, "_"):
                self.stack.enter_context(patch.object(module, "_", lambda value: value))
        self.stack.enter_context(patch.object(policy, "validate_context", side_effect=lambda company, profile, *args: dict(pos_profile=profile)))
        self.stack.enter_context(patch.object(expense_policy, "check_company", side_effect=lambda company, **kwargs: self.assertEqual(company, "Test")))
        self.stack.enter_context(patch.object(expense_policy, "check_user_scope"))
        self.stack.enter_context(patch.object(snapshot, "currency_precision", return_value=2))
        self.stack.enter_context(patch.object(expense_policy, "currency_precision", return_value=2))
        self.stack.enter_context(patch.object(service,"today",return_value="2026-11-06"))
        self.stack.enter_context(patch.object(service.expenses, "lock_actor", side_effect=lambda: self.locks.append(("User", "owner"))))
        self.stack.enter_context(patch.object(transfers, "lock_actor", side_effect=lambda: self.locks.append(("User", "owner"))))
        self.stack.enter_context(patch.object(expense_policy, "validate_account", side_effect=lambda name, company: self.get_doc("Account", name)))
        self.stack.enter_context(patch.object(shift_adjustments, "validate_setup", return_value={}))
        for name, kind in (("Till", "Cash"), ("Alif", "Bank"), ("Safe", "Cash"), ("Loss", "Expense"), ("Surplus", "Income"), ("Taxi", "Expense")):
            self.add("Account", name, company="Test", account_type=kind, account_currency="TJS", is_group=0, disabled=0)
        self.add("Company", "Test", default_currency="TJS")
        self.add("POS Shift Review Settings", "Setup", company="Test", shortage_account="Loss", surplus_account="Surplus", cost_center="CC")
        self.add("POS Closing Shift", "CLOSE", docstatus=1, company="Test", pos_profile="Register", pos_opening_shift="OPEN")
        self.add("POS Opening Shift", "OPEN", docstatus=1, company="Test", pos_profile="Register", user="cashier", status="Closed", period_start_date="2026-11-06 08:00:00")
        self.review = self.add("POS Shift Review", "REVIEW", company="Test", pos_profile="Register", pos_opening_shift="OPEN", closing_shift="CLOSE", cashier="cashier", currency="TJS", currency_precision=2, version=1, status="Pending review", accounts=[])
        self.build_review([dict(mode_of_payment="Cash", account="Till", expected_amount=1000)], {"Cash": 950})
        self.record = self.stack.enter_context(patch.object(service.expenses, "record", side_effect=self.record_expense))
        self.stack.enter_context(patch.object(commands, "frappe", self.f))

    def permission(self, doctype, permission, **kwargs):
        return (doctype, permission) not in self.denied

    def add(self, doctype, name, **kwargs):
        return Doc(self, dict(doctype=doctype, name=name, **kwargs)).insert()

    def get_doc(self, doctype, name=None, **kwargs):
        if isinstance(doctype, dict):
            return Doc(self, doctype)
        if kwargs.get("for_update"):
            self.locks.append((doctype, name))
        return self.docs[(doctype, name)]

    def matches(self, doctype, filters):
        result = []
        for (dt, _), doc in self.docs.items():
            if dt != doctype:
                continue
            valid = True
            for key, value in filters.items():
                actual = doc.get(key)
                if isinstance(value, (tuple, list)):
                    operator, expected = value
                    if operator == "in":
                        valid &= actual in expected
                    elif operator == ">=":
                        valid &= actual is not None and actual >= expected
                    else:
                        valid &= actual != expected
                else:
                    valid &= actual == value
            if valid:
                result.append(doc)
        return result

    def lookup(self, doctype, filters, field, **kwargs):
        self.locks.extend([(doctype, filters)] if kwargs.get("for_update") else [])
        if doctype == "User":
            return "owner"
        if not isinstance(filters, dict):
            filters = {"name": filters}
        rows = self.matches(doctype, filters)
        if not rows:
            return None
        row = rows[0]
        return frappe._dict({key: row.get(key) for key in field}) if isinstance(field, list) else row.get(field)

    def cached(self, doctype, name, field):
        doc = self.docs.get((doctype, name))
        return doc.get(field) if doc else None

    def set_value(self, doctype, name, field, value, **kwargs):
        self.docs[(doctype, name)][field] = value

    def get_all(self, doctype, filters=None, fields=None, **kwargs):
        if doctype == "GL Entry":
            rows = [row for row in self.ledger if all((row.get(key) in value[1] if isinstance(value, list) else row.get(key) == value) for key, value in filters.items())]
        else:
            rows = self.matches(doctype, filters or {})
        return [frappe._dict({field: row.get(field) for field in fields}) for row in rows]

    def savepoint(self, name):
        self.points[name] = ([(dt, n, copy.deepcopy(doc.as_dict())) for (dt,n), doc in self.docs.items()], copy.deepcopy(self.ledger))

    def rollback(self, save_point):
        rows, ledger = self.points[save_point]
        self.docs = {(dt,n):Doc(self,data) for dt,n,data in rows}; self.ledger = ledger

    def post(self, doc):
        self.assertAlmostEqual(sum(row.get("debit_in_account_currency", 0) - row.get("credit_in_account_currency", 0) for row in doc.accounts), 0)
        for row in doc.accounts:
            self.ledger.append(frappe._dict(name=f"GL{len(self.ledger)}", voucher_type=doc.doctype, voucher_no=doc.name, company=doc.company,
                account=row.account, account_currency="TJS", debit=row.get("debit_in_account_currency",0), credit=row.get("credit_in_account_currency",0),
                posting_date=doc.posting_date, is_cancelled=0, voucher_detail_no=None))

    def record_expense(self, payload):
        self.assertEqual(payload["entry_context"], "POS Correction")
        self.assertEqual(payload["pos_opening_shift"], "OPEN")
        if payload["expense_category"] != "Taxi":
            raise frappe.ValidationError("Category mapping required")
        doc = Doc(self, dict(doctype="Quick Expense", **payload, expense_account="Taxi", cost_center="CC", docstatus=1, mode_of_payment=None, bill_no=None, journal_entry=None, payment_entry=None, purchase_invoice=None)).insert()
        with patch("erpnext.accounts.doctype.quick_expense.quick_expense.frappe", self.f), patch("erpnext.accounts.doctype.quick_expense.quick_expense._", lambda value:value):
            QuickExpense.create_journal_entry(doc)
        return dict(name=doc.name, docstatus=1)

    def build_review(self, methods, counts):
        rows, groups = arithmetic.group_counts(methods, counts, 2)
        self.review.accounts=[]
        for group in groups:
            self.review.append("accounts", dict(group, currency="TJS", account_currency="TJS", account_type=self.get_doc("Account",group["account"]).account_type, methods_json=json.dumps(group["methods"]), allocated_amount=0,remaining_amount=float(group["original_difference"])))
        data=dict(version=1,company="Test",currency="TJS",precision=2,opening_shift="OPEN",closing_shift="CLOSE",period_start="2026-11-06 08:00:00",period_end="2026-11-06 12:00:00",cash_mode="Cash",methods=rows,groups=groups,sources=[])
        self.review.snapshot_json=snapshot.encode(data);self.review.snapshot_hash=commands.fingerprint(json.loads(self.review.snapshot_json))

    def act(self, action, args, key="request-0001", version=None):
        args=dict(reason="Investigated evidence", **args)
        return unwrap(service.act)("REVIEW",action,args,key,version if version is not None else self.get_doc("POS Shift Review","REVIEW").version)


class TestReviewArithmetic(unittest.TestCase):
    def test_missing50_partial_resolution_surplus_and_precision(self):
        self.assertEqual(arithmetic.remaining(-50,[-20],2),Decimal(-30))
        self.assertEqual(arithmetic.remaining(50,[20],2),Decimal(30))
        for value in ("NaN","inf",None,"0.001"):
            with self.assertRaises(ValueError): arithmetic.amount(value,2)
        for value in (-51,1,0):
            with self.assertRaises(ValueError): arithmetic.allocate(-50,[],value,2)

    def test_aliases_group_by_account_and_sign_without_netting(self):
        methods,groups=arithmetic.group_counts([dict(mode_of_payment=m,account="Till",expected_amount=e) for m,e in [("Cash",100),("Alias",100),("Card alias",100)]],dict(Cash=80,Alias=70,**{"Card alias":150}),2)
        self.assertEqual(sorted(Decimal(g["original_difference"]) for g in groups),[Decimal(-50),Decimal(50)])
        self.assertEqual(len(groups),2)
        self.assertEqual(len(methods),3)
        shortage = next(group for group in groups if group["sign"] == -1)
        self.assertEqual(Decimal(shortage["expected_amount"]), 200)
        self.assertEqual(Decimal(shortage["actual_amount"]), 150)


class TestReviewCommands(ReviewFixture):
    def test_missing_expense_resolves50_once_and_preserves_snapshot(self):
        before=self.review.snapshot_json;row=self.review.accounts[0]
        args=dict(row_key=row.row_key,signed_amount=-50,amount=50,category="Taxi",posting_date="2026-11-06")
        result=self.act("Missing expense",args,version=1)
        again=self.act("Missing expense",args,version=1)
        self.assertEqual(result,again);self.assertEqual(result["status"],"Resolved")
        self.assertEqual(self.record.call_count,1);self.assertEqual(self.review.snapshot_json,before)
        self.assertEqual(len(self.matches("Journal Entry",{})),1)
        till=1000-950+sum(Decimal(str(r.debit))-Decimal(str(r.credit)) for r in self.ledger if r.account=="Till")
        self.assertEqual(till,0);self.f.db.commit.assert_not_called()

    def test_partial_expense_and_cancelled_backing_journal_reopen_only_that_amount(self):
        row=self.review.accounts[0];result=self.act("Missing expense",dict(row_key=row.row_key,signed_amount=-20,amount=20,category="Taxi",posting_date="2026-11-06"))
        self.assertEqual(result["accounts"][0]["remaining_amount"],-30)
        je=self.matches("Journal Entry",{})[0];je.docstatus=2
        for leg in self.ledger:leg.is_cancelled=1
        lifecycle.changed(je,"on_cancel")
        self.assertEqual(self.review.accounts[0].remaining_amount,-50)
        self.assertEqual(self.review.status,"Pending review" if not self.review.reviewer else "In review")
        self.assertEqual(self.matches("POS Shift Review Action",{})[0].state,"Invalidated")

    def test_cash_adjustment_requires_D4_and_native_JE_permissions(self):
        row=self.review.accounts[0];self.roles=["Retail Manager","Accounts User"]
        with self.assertRaises(frappe.PermissionError):self.act("Cash adjustment",dict(row_key=row.row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertFalse(self.ledger)
        self.roles=["Accounts Manager"];self.denied.add(("Journal Entry","submit"))
        with self.assertRaises(frappe.PermissionError):self.act("Cash adjustment",dict(row_key=row.row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertFalse(self.ledger)

    def test_loss_adjustment_posts_once_and_missing_setup_posts_nothing(self):
        row=self.review.accounts[0];result=self.act("Cash adjustment",dict(row_key=row.row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertEqual(result["status"],"Resolved");self.assertEqual(sum(r.debit for r in self.ledger if r.account=="Loss"),50)
        self.assertEqual(sum(r.credit for r in self.ledger if r.account=="Till"),50)
        self.assertFalse(self.matches("Quick Expense",{}))

    def test_bank_and_shared_opposite_accounts_cannot_be_written_off_as_cash(self):
        self.build_review([dict(mode_of_payment="Alif",account="Alif",expected_amount=100)],dict(Alif=50))
        row=self.review.accounts[0]
        with self.assertRaises(frappe.ValidationError):self.act("Cash adjustment",dict(row_key=row.row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.build_review([dict(mode_of_payment="Cash",account="Till",expected_amount=100),dict(mode_of_payment="Alias",account="Till",expected_amount=100)],dict(Cash=50,Alias=150))
        row=self.review.accounts[0]
        with self.assertRaises(frappe.ValidationError):self.act("Cash adjustment",dict(row_key=row.row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertFalse(self.ledger)

    def test_missing_expense_failure_and_stale_version_roll_back_GL_and_action(self):
        row=self.review.accounts[0]
        with self.assertRaises(frappe.TimestampMismatchError):self.act("Missing expense",dict(row_key=row.row_key,signed_amount=-50,amount=50,category="Taxi",posting_date="2026-11-06"),version=0)
        self.assertFalse(self.ledger);self.assertFalse(self.matches("Quick Expense",{}));self.assertFalse(self.matches("POS Shift Review Action",{}))
        with self.assertRaises(frappe.ValidationError):self.act("Missing expense",dict(row_key=row.row_key,signed_amount=-50,amount=50,category="Unknown"))
        self.assertFalse(self.ledger)

    def test_count_correction_is_auditable_and_withdrawal_reopens_it(self):
        row=self.review.accounts[0];before=self.review.snapshot_json
        result=self.act("Count correction",dict(row_key=row.row_key,mode_of_payment="Cash",new_actual=1000))
        self.assertEqual(result["status"],"Resolved");self.assertFalse(self.ledger)
        name=result["operation"]["name"]
        result=self.act("Withdraw count correction",dict(action_name=name),key="withdraw-0001")
        self.assertEqual(result["accounts"][0]["remaining_amount"],-50);self.assertEqual(self.review.snapshot_json,before)

    def test_reusing_id_for_other_intent_or_actor_is_rejected(self):
        self.act("Investigate",{})
        with self.assertRaises(frappe.PermissionError):self.act("Recovery request",{},version=1)
        self.f.session.user="another-owner"
        with self.assertRaises(frappe.PermissionError):self.act("Investigate",{},version=1)

    def test_cashier_cannot_apply_manager_corrections(self):
        self.roles=["Retail Cashier"];self.f.session.user="cashier"
        with self.assertRaises(frappe.PermissionError):self.act("Investigate",{})

    def test_shortage_surplus_setup_and_zero_posting_guards(self):
        self.build_review([dict(mode_of_payment="Cash",account="Till",expected_amount=1000)],dict(Cash=1050))
        row=self.review.accounts[0]
        result=self.act("Cash adjustment",dict(row_key=row.row_key,signed_amount=50,posting_date="2026-11-06"))
        self.assertEqual(result["status"],"Resolved");self.assertEqual(sum(r.debit for r in self.ledger if r.account=="Till"),50)
        self.assertEqual(sum(r.credit for r in self.ledger if r.account=="Surplus"),50)

    def test_source_already_in_original_expectations_cannot_resolve_again(self):
        posted=self.record_expense(dict(company="Test",pos_profile="Register",pos_opening_shift="OPEN",entry_context="POS Correction",expense_category="Taxi",amount=50,paid_from="Till",posting_date="2026-11-06"))
        original=snapshot.read(self.review);original["sources"]=[dict(doctype="Quick Expense",name=posted["name"],vouchers=[])]
        self.review.snapshot_json=snapshot.encode(original);self.review.snapshot_hash=commands.fingerprint(json.loads(self.review.snapshot_json))
        with self.assertRaises(frappe.ValidationError):self.act("Link source",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,source_doctype="Quick Expense",source_name=posted["name"]))
        self.assertEqual(len(self.matches("Journal Entry",{})),1)

    def test_partial_native_reversal_preserves_only_still_posted_allocation(self):
        self.act("Cash adjustment",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,posting_date="2026-11-06"))
        original=self.matches("Journal Entry",{})[0]
        reverse=self.add("Journal Entry","REV",company="Test",docstatus=1,reversal_of=original.name,posting_date="2026-11-06",accounts=[frappe._dict(account="Till",debit_in_account_currency=20),frappe._dict(account="Loss",credit_in_account_currency=20)])
        self.post(reverse);lifecycle.changed(reverse,"on_submit")
        self.assertEqual(self.review.accounts[0].allocated_amount,-30);self.assertEqual(self.review.accounts[0].remaining_amount,-20)
        self.assertEqual(self.review.status,"Partially resolved")

    def test_timeout_outcome_is_actor_scoped_and_does_not_post_again(self):
        self.act("Investigate",{})
        result=unwrap(service.get_outcome)("request-0001")
        self.assertEqual(result["operation"]["state"],"Requested");self.assertFalse(self.ledger)
        self.f.session.user="another-owner"
        with self.assertRaises(frappe.PermissionError):unwrap(service.get_outcome)("request-0001")
        self.assertEqual(unwrap(service.get_outcome)("missing-request")["status"],"not_found")

    def test_snapshot_integrity_failure_blocks_actions(self):
        self.review.snapshot_json=self.review.snapshot_json.replace('"950.00"','"900.00"')
        with self.assertRaises(frappe.ValidationError):self.act("Investigate",{})


class TestReviewBoundaries(ReviewFixture):
    def test_second_reviewer_with_stale_version_cannot_post_a_second_loss(self):
        args = dict(row_key=self.review.accounts[0].row_key, signed_amount=-20, posting_date="2026-11-06")
        self.act("Cash adjustment", args, version=1)
        self.f.session.user = "second-owner"
        with self.assertRaises(frappe.TimestampMismatchError):
            self.act("Cash adjustment", args, key="second-reviewer", version=1)
        self.assertEqual(len(self.matches("Journal Entry", {})), 1)
        self.assertEqual(self.get_doc("POS Shift Review", "REVIEW").accounts[0].remaining_amount, -30)

    def test_one_unassigned_posted_effect_cannot_be_claimed_by_two_shifts(self):
        source = self.add("Journal Entry", "MISSING", company="Test", docstatus=1, posting_date="2026-11-06",
                          accounts=[frappe._dict(account="Till", credit_in_account_currency=50),
                                    frappe._dict(account="Taxi", debit_in_account_currency=50)])
        self.post(source)
        args = dict(row_key=self.review.accounts[0].row_key, signed_amount=-20, source_doctype="Journal Entry",
                    source_name=source.name, attribute_to_shift=True, reason="Assigned with evidence")
        unwrap(service.act)("REVIEW", "Link source", args, "first-claim", 1)
        copy_review = copy.deepcopy(self.review.as_dict())
        copy_review.update(name="OTHER-REVIEW", closing_shift="OTHER-CLOSE", pos_opening_shift="OTHER-OPEN", version=1)
        self.docs[("POS Shift Review", "OTHER-REVIEW")] = Doc(self, copy_review)
        with self.assertRaises(frappe.ValidationError):
            unwrap(service.act)("OTHER-REVIEW", "Link source", args, "second-claim", 1)
        self.assertEqual(len(self.matches("POS Shift Source Claim", {})), 1)

    def test_grouped_method_cannot_be_corrected_past_its_own_expected_count(self):
        self.build_review([dict(mode_of_payment="Cash",account="Till",expected_amount=100),
                           dict(mode_of_payment="Alias",account="Till",expected_amount=100)],dict(Cash=80,Alias=70))
        args = dict(row_key=self.review.accounts[0].row_key, mode_of_payment="Cash", new_actual=100)
        self.act("Count correction", args)
        with self.assertRaises(frappe.ValidationError):
            self.act("Count correction", dict(args, new_actual=120), key="overshoot-count")
        current = self.get_doc("POS Shift Review", "REVIEW")
        self.assertEqual(current.accounts[0].remaining_amount, -30)
        self.assertEqual(len(self.matches("POS Shift Review Action", {})), 1)

    def test_retry_and_outcome_lock_review_before_its_action_history(self):
        self.act("Investigate", {}, version=1)
        self.locks=[]
        self.act("Investigate", {}, version=1)
        types = [dt for dt, _ in self.locks]
        self.assertLess(types.index("POS Shift Review"), types.index("POS Shift Review Action"))
        self.locks=[]
        unwrap(service.get_outcome)("request-0001")
        types = [dt for dt, _ in self.locks]
        self.assertLess(types.index("POS Shift Review"), types.index("POS Shift Review Action"))

    def test_other_company_adjustment_settings_cannot_post(self):
        setup = self.get_doc("POS Shift Review Settings", "Setup")
        setup.company = "Other"
        with self.assertRaises(frappe.ValidationError):
            shift_adjustments.post_cash_adjustment("Test", "Till", -50, "2026-11-06", setup, "REVIEW", "Loss")
        self.assertFalse(self.ledger)

    def test_partial_source_cannot_be_allocated_twice_or_to_another_shift(self):
        posted=self.record_expense(dict(company="Test",pos_profile="Register",pos_opening_shift="OPEN",entry_context="POS Correction",expense_category="Taxi",amount=50,paid_from="Till",posting_date="2026-11-06"))
        args=dict(row_key=self.review.accounts[0].row_key,signed_amount=-30,source_doctype="Quick Expense",source_name=posted["name"])
        self.act("Link source",args)
        with self.assertRaises(frappe.ValidationError):self.act("Link source",args,key="duplicate-0001")
        self.assertEqual(self.get_doc("POS Shift Review","REVIEW").accounts[0].remaining_amount,-20)
        self.assertEqual(len(self.matches("POS Shift Review Action",{})),1)
        source=self.get_doc("Quick Expense",posted["name"]);source.pos_opening_shift="OTHER"
        with self.assertRaises(frappe.PermissionError):self.act("Link source",dict(args,signed_amount=-20),key="wrong-shift-0001")

    def test_denied_source_and_wrong_company_do_not_change_review(self):
        source=self.add("Journal Entry","UNREADABLE",company="Other",docstatus=1,posting_date="2026-11-06")
        self.denied.add(("Journal Entry","read"))
        args=dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,source_doctype="Journal Entry",source_name=source.name,attribute_to_shift=True)
        with self.assertRaises(frappe.PermissionError):self.act("Link source",args)
        self.denied.clear()
        with self.assertRaises(frappe.ValidationError):self.act("Link source",args)
        self.assertFalse(self.matches("POS Shift Review Action",{}))

    def test_native_posting_failure_leaves_no_resolution_or_claim(self):
        original=Doc.submit
        def fail(doc):
            if doc.doctype=="Journal Entry":raise frappe.ValidationError("Period is closed")
            return original(doc)
        with patch.object(Doc,"submit",fail):
            with self.assertRaises(frappe.ValidationError):self.act("Cash adjustment",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertFalse(self.ledger);self.assertFalse(self.matches("POS Shift Source Claim",{}));self.assertFalse(self.matches("Journal Entry",{}))

    def test_posting_and_allocation_share_rollback_even_if_action_insert_fails(self):
        with patch.object(service,"_insert_action",side_effect=frappe.DuplicateEntryError):
            with self.assertRaises(frappe.DuplicateEntryError):self.act("Cash adjustment",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertFalse(self.ledger);self.assertFalse(self.matches("POS Shift Source Claim",{}));self.assertFalse(self.matches("Journal Entry",{}))

    def test_source_lock_precedes_review_lock_for_existing_documents(self):
        source=self.record_expense(dict(company="Test",pos_profile="Register",pos_opening_shift="OPEN",entry_context="POS Correction",expense_category="Taxi",amount=50,paid_from="Till",posting_date="2026-11-06"))
        self.locks=[];self.act("Link source",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,source_doctype="Quick Expense",source_name=source["name"]))
        types=[dt for dt,_ in self.locks]
        self.assertLess(types.index("Quick Expense"),types.index("POS Shift Review"))
        self.assertLess(types.index("Journal Entry"),types.index("POS Shift Review"))

    def test_closing_cancellation_requires_reversal_and_preserves_voided_audit(self):
        self.act("Cash adjustment",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,posting_date="2026-11-06"))
        closed=self.get_doc("POS Closing Shift","CLOSE")
        with self.assertRaises(frappe.ValidationError):closing.before_cancel(closed)
        je=self.matches("Journal Entry",{})[0];je.docstatus=2
        for leg in self.ledger:leg.is_cancelled=1
        lifecycle.changed(je,"on_cancel");closing.before_cancel(closed)
        self.assertEqual(self.review.status,"Voided");self.assertIn("POS Shift Review",closed.ignore_linked_doctypes)
        self.assertEqual(len(self.matches("POS Shift Review Action",{})),1)

    def test_a_request_or_bank_handoff_is_never_a_financial_resolution(self):
        self.act("Bank reconciliation request",{})
        self.assertEqual(self.review.accounts[0].remaining_amount,-50)
        self.assertEqual(self.review.status,"In review");self.assertFalse(self.ledger)

    def test_cash_loss_setup_missing_stays_pending(self):
        self.docs.pop(("POS Shift Review Settings","Setup"))
        with self.assertRaises(frappe.ValidationError):self.act("Cash adjustment",dict(row_key=self.review.accounts[0].row_key,signed_amount=-50,posting_date="2026-11-06"))
        self.assertFalse(self.ledger);self.assertEqual(self.review.status,"Pending review")

    def test_native_amendment_proves_opposite_alias_differences_without_double_GL(self):
        self.build_review([dict(mode_of_payment="Cash",account="Till",expected_amount=100),dict(mode_of_payment="Alias",account="Till",expected_amount=100)],dict(Cash=50,Alias=150))
        old=self.add("Sales Invoice","OLD",company="Test",docstatus=2)
        original=snapshot.read(self.review);original["sources"]=[dict(doctype="Sales Invoice",name="OLD",invoice=dict(base_grand_total=200,base_net_total=200,payments=[dict(mode_of_payment="Cash",base_amount=100),dict(mode_of_payment="Alias",base_amount=100)]),vouchers=[dict(doctype="Sales Invoice",name="OLD",legs=[dict(account="Till",signed_amount="200")])])]
        self.review.snapshot_json=snapshot.encode(original);self.review.snapshot_hash=commands.fingerprint(json.loads(self.review.snapshot_json))
        new=self.add("Sales Invoice","NEW",company="Test",docstatus=1,amended_from="OLD",posa_pos_opening_shift="OPEN",base_grand_total=200,base_net_total=200,payments=[frappe._dict(mode_of_payment="Cash",base_amount=50),frappe._dict(mode_of_payment="Alias",base_amount=150)])
        self.ledger.append(frappe._dict(name="GL-NEW",voucher_type="Sales Invoice",voucher_no="NEW",company="Test",account="Till",account_currency="TJS",debit=200,credit=0,is_cancelled=0,posting_date="2026-11-06"))
        mop=Mock(side_effect=lambda dt, filters, field: "Till")
        lookup=self.f.db.get_value.side_effect
        self.f.db.get_value.side_effect=lambda dt,*a,**kw: "Till" if dt=="Mode of Payment Account" else lookup(dt,*a,**kw)
        result=self.act("Confirm payment correction",dict(source_doctype="Sales Invoice",source_name="NEW"))
        self.assertEqual(result["status"],"Resolved");self.assertEqual(len(self.ledger),1)
        self.assertEqual(sorted(row.allocated_amount for row in self.review.accounts),[-50,50])
        new.docstatus=2
        for leg in self.ledger:leg.is_cancelled=1
        lifecycle.changed(new,"on_cancel")
        self.assertEqual(sorted(row.remaining_amount for row in self.review.accounts),[-50,50])

    def test_safe_transfer_is_once_only_and_does_not_resolve_missing50(self):
        self.add("Money Wallet","TillWallet",company="Test",account="Till",wallet_name="Till",enabled=1)
        self.add("Money Wallet","SafeWallet",company="Test",account="Safe",wallet_name="Safe",wallet_type="Safe",enabled=1)
        native=Mock(return_value=self.add("Payment Entry","SAFE-PE",company="Test",docstatus=1))
        with patch.object(shift_adjustments,"post_shift_transfer",native):
            first=transfers.transfer("CLOSE");second=transfers.transfer("CLOSE")
            self.assertEqual(native.call_count,1);self.assertEqual(first["payment_entry"],second["payment_entry"])
            self.assertEqual(first["transferred_amount"],950);self.assertEqual(self.review.accounts[0].remaining_amount,-50)
            with self.assertRaises(frappe.ValidationError):transfers.transfer("CLOSE",900)
        self.f.db.commit.assert_not_called()

    def test_reversed_safe_transfer_cannot_be_silently_sent_again(self):
        self.add("Money Wallet","TillWallet",company="Test",account="Till",wallet_name="Till",enabled=1)
        self.add("Money Wallet","SafeWallet",company="Test",account="Safe",wallet_name="Safe",wallet_type="Safe",enabled=1)
        posted=self.add("Payment Entry","SAFE-PE",company="Test",docstatus=1)
        native=Mock(return_value=posted)
        with patch.object(shift_adjustments,"post_shift_transfer",native):
            transfers.transfer("CLOSE");posted.docstatus=2;lifecycle.changed(posted,"on_cancel")
            with self.assertRaises(frappe.ValidationError):transfers.transfer("CLOSE")
            self.assertEqual(native.call_count,1)


class TestClosingBoundary(ReviewFixture):
    def setUp(self):
        super().setUp()
        from posawesome.posawesome.doctype.pos_closing_shift.closing_processing import data, overview, creation
        self.data, self.overview, self.creation = data, overview, creation
        self.opening=self.get_doc("POS Opening Shift","OPEN");self.opening.status="Open"
        from posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_summary import opening_detail
        self.opening.balance_details=[opening_detail("Cash",1000)]
        self.closing=self.get_doc("POS Closing Shift","CLOSE");self.closing.docstatus=0;self.closing.user="cashier"
        self.closing.discrepancy_reason="Counted twice, short 50"
        self.closing.payment_reconciliation=[Doc(self,dict(doctype="POS Closing Shift Detail",mode_of_payment="Cash",opening_amount=1000,expected_amount=1000,closing_amount=950))]
        self.closing.pos_transactions=[];self.closing.pos_payments=[];self.closing.taxes=[]
        self.snapshot=dict(reconciliation=[dict(mode_of_payment="Cash",account="Till",opening_amount=1000,expected_amount=1000)],movements=[],cash_expected=dict(mode_of_payment="Cash"))
        self.stack.enter_context(patch.object(creation,"get_authorized_opening_shift",return_value=self.opening))
        self.stack.enter_context(patch.object(creation,"get_pos_invoices",return_value=[]))
        self.stack.enter_context(patch.object(creation,"get_payments_entries",return_value=[]))
        self.stack.enter_context(patch.object(overview,"build_closing_overview",return_value=self.snapshot))
        self.stack.enter_context(patch.object(creation,"normalize_pos_payment_references"))
        self.stack.enter_context(patch.object(closing,"flt",lambda value,precision=None:frappe.utils.flt(value,precision,rounding_method="Banker's Rounding")))

    def test_direct_controller_before_submit_recalculates_and_requires_explanation(self):
        controller.POSClosingShift.before_submit(self.closing)
        self.assertEqual(self.closing.payment_reconciliation[0].difference,-50)
        self.assertTrue(self.closing.flags.shift_review_context)
        self.closing.discrepancy_reason=""
        with self.assertRaises(frappe.ValidationError):controller.POSClosingShift.before_submit(self.closing)

    def test_missing_actual_and_stale_expectations_do_not_reach_submit(self):
        self.closing.payment_reconciliation[0].closing_amount=None
        with self.assertRaises(frappe.ValidationError):closing.validate(self.closing)
        self.closing.payment_reconciliation[0].closing_amount=950
        self.closing.payment_reconciliation[0].expected_amount=999
        with self.assertRaises(frappe.ValidationError):closing.validate(self.closing)

    def test_review_snapshot_and_closing_link_are_created_without_accounting_posting(self):
        self.docs.pop(("POS Shift Review","REVIEW"))
        closing.validate(self.closing)
        created=closing.create_review(self.closing)
        self.assertEqual(created.status,"Pending review");self.assertEqual(created.accounts[0].remaining_amount,-50)
        self.assertEqual(self.closing.shift_review,created.name);self.assertFalse(self.ledger)
        self.assertEqual(snapshot.read(created)["methods"][0]["actual"],"950.00")
        # The real native opening child remains a Document, not a subscriptable dict.
        self.assertFalse(isinstance(self.opening.balance_details[0],dict))

    def test_wrong_stored_company_and_reused_opening_are_rejected(self):
        self.closing.company="Other"
        with self.assertRaises(frappe.ValidationError):closing.validate(self.closing)
        self.closing.company="Test";self.opening.status="Closed"
        with self.assertRaises(frappe.ValidationError):closing.validate(self.closing)

    def test_direct_submitted_closing_edits_are_refused(self):
        with self.assertRaises(frappe.ValidationError):controller.POSClosingShift.before_update_after_submit(self.closing)

    def test_API_uses_the_same_validator_before_permission_escalation(self):
        self.stack.enter_context(patch.object(self.creation, "frappe", self.f))
        self.f.get_doc.side_effect = lambda value, *a, **kw: self.closing if isinstance(value, dict) else self.get_doc(value, *a, **kw)
        with patch.object(self.closing, "submit", create=True):
            result = unwrap(self.creation.submit_closing_shift)(json.dumps(dict(doctype="POS Closing Shift")))
        self.assertEqual(result, "CLOSE")
        self.assertEqual(self.closing.payment_reconciliation[0].difference, -50)
        self.assertTrue(self.closing.flags.shift_review_context)

    def test_API_strips_caller_document_identity_and_internal_flags(self):
        self.stack.enter_context(patch.object(self.creation, "frappe", self.f))
        source = dict(doctype="POS Closing Shift", name="ANOTHER-DRAFT", docstatus=1,
                      flags=dict(ignore_validate=True, ignore_links=True), shift_review="FORGED",
                      payment_reconciliation=[dict(name="ANOTHER-CHILD", mode_of_payment="Cash", closing_amount=950,
                                                   expected_amount=1000, parent="ANOTHER-DRAFT")])
        with patch.object(closing, "validate"), patch.object(self.creation, "normalize_pos_payment_references"):
            self.f.get_doc.side_effect=lambda payload: self.closing
            unwrap(self.creation.submit_closing_shift)(json.dumps(source))
        payload = self.f.get_doc.call_args.args[0]
        for key in ("name", "flags", "docstatus", "shift_review"):
            self.assertNotIn(key, payload)
        self.assertEqual(payload["payment_reconciliation"], [dict(mode_of_payment="Cash", closing_amount=950, expected_amount=1000)])

    def test_negative_physical_cash_fails_closed(self):
        self.closing.payment_reconciliation[0].closing_amount = -1
        with self.assertRaises(frappe.ValidationError):
            closing.validate(self.closing)

    def test_historical_payment_reference_cannot_cross_the_stored_company(self):
        payment = frappe._dict(name="OTHER-PE", company="Other")
        self.creation.get_payments_entries.return_value=[payment]
        with self.assertRaises(frappe.ValidationError):
            closing.validate(self.closing)

    def test_unmigrated_schema_fails_closed(self):
        self.f.db.has_column.return_value=False
        with self.assertRaises(frappe.ValidationError):
            closing.validate(self.closing)

    def test_source_cancellation_locks_the_same_shift_as_closing(self):
        entry = self.add("Payment Entry", "PAY", reference_no="OPEN")
        closing.lock_shift_source_cancellation(entry, "before_cancel")
        self.assertIn(("POS Opening Shift", "OPEN"), self.locks)

    def test_native_source_submission_serializes_with_close_and_rejects_closed_shift(self):
        invoice=self.add("Sales Invoice","NEW",company="Test",posa_pos_opening_shift="OPEN")
        closing.guard_shift_source(invoice)
        self.assertIn(("POS Opening Shift","OPEN"),self.locks)
        self.opening.status="Closed"
        with self.assertRaises(frappe.ValidationError):closing.guard_shift_source(invoice)
        expense=self.add("Quick Expense","CORRECTION",company="Test",pos_opening_shift="OPEN",entry_context="POS Correction")
        closing.guard_shift_source(expense)
        self.roles=["Retail Cashier"]
        with self.assertRaises(frappe.ValidationError):closing.guard_shift_source(expense)


class TestReviewDocumentGuard(ReviewFixture):
    def test_list_export_scope_includes_expense_specific_user_permissions(self):
        permissions = {
            "Account": [frappe._dict(doc="Till", applicable_for="Quick Expense")],
            "Company": [frappe._dict(doc="Test", applicable_for="Quick Expense")],
            "POS Profile": [frappe._dict(doc="Register", applicable_for="Quick Expense")],
        }
        self.f.db.escape.side_effect = lambda value: "'" + value.replace("'", "''") + "'"
        with patch("frappe.permissions.get_user_permissions", return_value=permissions):
            condition = policy.query_conditions()
        self.assertIn("a.account not in ('Till')", condition)
        self.assertIn("`tabPOS Shift Review`.company in ('Test')", condition)
        self.assertIn("`tabPOS Shift Review`.pos_profile in ('Register')", condition)

    def test_json_flags_cannot_spoof_service_identity_or_overwrite_snapshot(self):
        from posawesome.posawesome.shift_review import documents, SERVICE
        with patch.object(documents,"frappe",self.f),patch.object(documents,"_",lambda s:s):
            doc=Mock(flags={"shift_review_service":"SERVICE"})
            with self.assertRaises(frappe.PermissionError):documents.ReviewDocument.validate(doc)
            doc.flags={"shift_review_service":SERVICE};doc.immutable_fields=documents.ReviewDocument.immutable_fields
            previous=frappe._dict(company="Test",snapshot_json="old")
            doc.get_doc_before_save.return_value=previous
            doc.get.side_effect=lambda key: "new" if key=="snapshot_json" else previous.get(key)
            with self.assertRaises(frappe.ValidationError):documents.ReviewDocument.validate(doc)
            with self.assertRaises(frappe.ValidationError):documents.ReviewDocument.on_trash(doc)

    def test_permission_scope_checks_company_profile_and_every_funding_account(self):
        with patch.object(policy.expense_policy,"check_user_scope",side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):policy.scope(self.review)
        with patch.object(policy,"validate_context",return_value=dict(pos_profile="OTHER")):
            with self.assertRaises(frappe.PermissionError):policy.scope(self.review)
        self.roles=["Retail Cashier"];self.f.session.user="other-cashier"
        with self.assertRaises(frappe.PermissionError):policy.scope(self.review)


class TestNativeHandoffs(ReviewFixture):
    def test_nonfinancial_request_can_be_withdrawn_with_preserved_history(self):
        requested=self.act("Transfer request",{})
        result=self.act("Withdraw request",dict(request_action_name=requested["operation"]["name"]),key="withdraw-request")
        self.assertEqual(result["accounts"][0]["remaining_amount"],-50)
        self.assertEqual(self.matches("POS Shift Review Action",{})[0].state,"Withdrawn")
        self.assertFalse(self.ledger)

    def test_native_handoff_links_evidence_without_resolving_money(self):
        requested=self.act("Refund request",{})
        source=self.add("Payment Entry","REFUND",company="Test",docstatus=1,posting_date="2026-11-06")
        result=self.act("Confirm native handoff",dict(request_action_name=requested["operation"]["name"],source_doctype="Payment Entry",source_name=source.name,attribute_to_shift=True),key="native-refund")
        self.assertEqual(result["accounts"][0]["remaining_amount"],-50)
        self.assertEqual(self.matches("POS Shift Review Action",{})[0].state,"Handled")
        source.docstatus=2;lifecycle.changed(source,"on_cancel")
        self.assertEqual(self.matches("POS Shift Review Action",{})[1].state,"Invalidated")
