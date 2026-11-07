# Shift expenses and review: release and recovery

This is an operator handoff for the combined ERPNext/POS Awesome changes in Phases
2–9. It is not authorization to deploy, change business grants or post historical
adjustments. The business policies D1–D5 in ERPNext's expense workflow contract apply.

## Installation and upgrade order

1. Save the exact customized app revisions and local diff, site configuration, database
   and private files. Preserve in-flight offline requests and their original IDs. Use
   a disposable restore of the intended site's backup for the final upgrade rehearsal.
2. Update **ERPNext and POS Awesome together**, retaining the existing Frappe v15
   environment. ERPNext owns expenses, wallets, categories and native accounting;
   POS Awesome requires ERPNext and owns openings, closings, review evidence and actions.
   HRMS is needed for actual Expense Claim/Employee Advance workflows, not Quick Expenses.
3. Build the POS frontend using its current scripts, and build the relevant native
   assets using the deployment's existing bench/image procedure. ERPNext serves
   `expense_entry.js` and `expense_requests.js`; the new POS Page requires native sync.
4. In the authorized maintenance window run `bench --site <site> migrate`. Do not use
   `--skip-failing` to conceal an unsuccessful upgrade. Resolve failures before reopening
   financial entry. Restart the actual web/worker processes and refresh assets/hooks
   using that deployment's procedure. Do not restart guessed container/service names.
5. Complete setup and the role tests below before allowing new financial commands.
   Closing/review/expense commands deliberately fail closed on missing schema/setup.

Schema sync adds expense request/cancellation identity fields and unique indexes;
company category mappings and wallet/register expense grants; closing reason/review
links; and POS Shift Review, Review Account, Review Action, Source Claim and Settings.
The review's snapshot/hash require native permission level 1 and are print-hidden.
No historical closing is reconstructed, expense inferred, original count rewritten,
payroll deduction created or loss posted by migration.

`posawesome.patches.repair_expense_source_settings` reloads the existing allowlist
child DocTypes, adds only missing legacy source fields and repairs their missing SQL
columns. It preserves existing register flags, values and payment methods. It is
registered as an upgrade patch **and an after-install hook**: Frappe marks patches
completed on fresh installation, so the hook is necessary there. Rerunning this repair
does not enable spending. New grant fields default off; configure them deliberately.

The Phase 9 cold installation found a Retail Tax Settings default link to
`Налоговый комитет` before that Supplier existed. After the owner explicitly included
the installation fix, the nonexistent Link default was removed. A second, clean site
installed both apps without the earlier workaround. Explicit company tax setup still
provisions the supplier through its existing native workflow; an existing configured
supplier is preserved. No business-site supplier, tax rates or templates were changed.

## Explicit business and permission setup

- Map each Quick Expense Category to the intended company expense account and cost
  center. Configure shortage expense, approved surplus account, cost center and native
  dimensions in POS Shift Review Settings. Confirm native open periods/budgets/dimensions.
- Configure Money Wallets deliberately. POS source grants must name each approved
  register and match its payment-account mapping. `accept_in_pos` alone is insufficient.
  Office/Safe sources require Allow Office Expenses; ordinary Desk entry cannot casually
  spend register funds. A correction needs its original opening and manager reason.
- Quick Expense and automatic counted-cash transfer support company-currency funding
  accounts. Use native accounting for foreign funding, fees, bank settlements, recovery
  and other complex corrections. Foreign Money Hub balances preserve their account
  currency while totals use stored company-currency GL values.
- Keep native Company/Account/Cost Center/POS Profile User Permissions and register
  assignments. A cashier needs **native read permission on the assigned POS Profile**
  in addition to Retail Cashier, Quick Expense create/submit and opening access. The
  base cashier bundle currently lacks POS Profile read. Configure a narrow native
  read grant with explicit profile User Permissions; do not add Accounts User just
  to make the cashier picker work. Test a second cashier and another register/company.
- Managers need permitted review/native source reads and ordinary expense correction/
  cancellation rights. Only Retail Owner/Accounts Manager approves genuine loss/surplus,
  with native JE create/submit permission. Retail Manager cannot approve those losses.
  Safe transfer additionally retains Money Hub capability and native PE create/submit.
- Inspect **Custom DocPerm** overrides as well as standard DocPerm after migration.
  A cashier must not receive snapshot/hash permission level 1, review action/source
  claim reads, or manager accounting capabilities. Verify REST get/list, Desk getdoc,
  print/export and each user's actual User Permission scope.
- Money Hub requires native Company, Money Wallet, Account and GL Entry read access.
  Reads no longer provision wallets. Configure missing wallets through deliberate setup.

No live role/source/account choices were made in Phase 9. Test-site grants are fixtures.

## Read-only legacy inventory

From the bench root, with operator access to that site's database:

```bash
env/bin/python apps/posawesome/scripts/audit_shift_expenses.py \
  --sites-path sites --site <site> > /private/operator/path/shift-expense-audit.json
```

The script reads credentials without printing them, opens a database-enforced read-only
consistent transaction, runs SELECTs and always rolls back/closes. It does not initialize
Frappe, invoke controllers/setup or commit. Optional `--db-host` changes only the connection
address. Store its record identifiers privately. The output gives missing schema, full
unassigned totals with at most 100 sample records, historical discrepancy counts, shared
register accounts and wallet aliases. It works before the new schema exists.

The 2026-11-06 read-only snapshot of the existing business database found:

- Five submitted unassigned Quick Expenses against Cash, stored total 152 in Radolfa.
- No unassigned submitted legacy Cash Movement expenses.
- Eight submitted historical closings with 15 payment-method differences and no new review.
- Cash, Alif, Dushanbe City and Eskata each mapped to two enabled profiles.
- No duplicate enabled Money Wallet aliases for one account.

These findings do not establish who incurred a shortage or which shift owns an expense.
Keep the original records. Any later attribution requires explicit manager evidence and
an auditable approved operation; historical accounting stays with the native accountant
workflow. Do not turn this inventory into a financial backfill or automatically create
reviews from today's account mappings. No automatic sharing/exclusivity choice was made.

## Compatibility and recovery

- Old Quick Expense/legacy Cash Movement history remains readable once migrated. Legacy
  offline Expense/Deposit payloads and IDs retain their endpoint/identity; they are not
  silently converted into fresh expenses. A forbidden/stale request remains recoverable
  and is not cleared from a real queue to make closing succeed.
- For an uncertain expense result, check the original ID with the shared outcome service.
  Retain input and ID; resend the same intent only after an authoritative not-found result.
  For review actions use `service.get_outcome` with the original actor/request ID. Never
  invent another ID because a response timed out. A stale version requires refreshed
  evidence and deliberate review of any changed amount before a new action.
- Closing success, fiscal printing and safe transfer are independent outcomes. A confirmed
  ERP closing is not submitted again because the printer/transfer response was lost.
  Check the printer journal and use the established journal/reprint workflow for an
  unknown fiscal result; never blindly send another fiscal close. Physical printer/QZ
  behavior has not been verified by this phase.
- Counted transfer is keyed to the original closing. A confirmed original transfer can
  be retrieved after the following opening without another payment. A first old-count
  transfer is refused once another opening exists. Use current physical evidence and
  the native workflow then. Count corrections or reversed transfers also require
  native investigation; zero counted cash posts no transfer.
- Native cancellation/reversal invalidates/recomputes the affected allocations and keeps
  their audit history. A reversed expense/loss can reopen a remaining difference.
  Reverse/withdraw completed effects before cancelling the closing; do not unlink/delete
  review history or edit its original snapshot to force cancellation.
- The following opening records the real available float. The previous unresolved amount
  is a separate origin, never automatically included in new physical cash or reposted.
- A claim or supplier bill already records its cost. Pay its native payable through HRMS/
  Payment Entry and retain the existing source; do not record another Quick Expense.

## Rollback

Before production rollout, rehearse restoring database **and matching private files**
to an isolated destination, plus code/assets at the recorded versions. Schema migration
contains DDL/commits and is not undone by a transaction rollback. The Phase 9 SQL restore
rehearsal used only its dedicated temporary database; it did not restore a business site.

After any new financial documents exist, operational code rollback must retain additive
tables, snapshots, request identities, vouchers and GL/audit history. Stop new entry,
inspect pending outcomes and native documents, and have the accountant handle necessary
reversals. Do not uninstall the new DocTypes, drop columns, delete submitted documents
or restore an old database over later business activity. Reverting a frontend bundle
alone does not reverse accounting or make an older server understand new workflow state.

## Verification commands and remaining release gates

Native accounting/permission suites on a disposable migrated site with `allow_tests`:

```bash
bench --site <test-site> run-tests --module erpnext.accounts.doctype.quick_expense.test_quick_expense
bench --site <test-site> run-tests --module posawesome.posawesome.shift_review.test_native_workflow
```

They create `_Test Company` using native setup, not broad Account test-fixture imports.
The real two-connection rehearsal also requires `shift_review_rehearsal = 1` and commits
its isolated fixtures so another connection can see them:

```bash
env/bin/python apps/posawesome/scripts/rehearse_shift_concurrency.py \
  --sites-path /isolated/bench/sites --site <test-site>
```

It leaves fixtures for inspection; dispose of the isolated database afterwards.
Do not run it against a business site. Browser commands and local-secret variables are
in `frontend/tests/smoke/README.md`. The Phase 9 report separates fixture, authenticated
native, GL/database, migration and hardware evidence.

Before rollout, still validate the intended business-site backup/configuration, actual
cashier/manager User Permissions and accounts/grants, real existing offline-client upgrade,
HRMS claim/supplier payment handoffs in the installed app set, bank reconciliation and
printer/QZ hardware. The isolated native suite does not certify every optional accounting
dimension/tax/localization, a full historical production clone upgrade, or Chrome 109
hardware/runtime. No deployment, commit, push, production migration or bank operation was
performed during this work.
