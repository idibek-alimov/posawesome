# Summary

The owner clarified that the MariaDB data is development data and may be reset if
needed, then selected the **local bench at `radolfa.localhost:8000`**. That site is
now migrated and configured for manual testing. No reset was necessary. The separate
Docker `mysite.localhost` database was not migrated or reset.

The local site's migration completed across Frappe, ERPNext, POS Awesome and HRMS.
A database/configuration backup was saved before migration:
`sites/radolfa.localhost/private/backups/20261106_183919-radolfa_localhost-database.sql.gz`.
The native schema audit now reports no missing shift/expense fields or tables.
Maintenance mode is off and the site's scheduler is enabled.

# Test access and steps

Use `http://radolfa.localhost:8000/login`. Newly created development users are:

| User | Role | Intended test |
| --- | --- | --- |
| `pos-cashier@example.test` | Retail Cashier | POS spending, count/close, own review status |
| `pos-manager@example.test` | Retail Manager | Investigate and record missing expenses; cannot approve genuine loss/surplus |
| `pos-owner@example.test` | Retail Owner | Manager actions plus configured loss/surplus approval |

Passwords/PINs are in the **private local file**
`sites/radolfa.localhost/private/pos-shift-development/credentials.json`.
They are deliberately absent from Git and this report. Existing Administrator/user
credentials were not changed. Use separate browser profiles/private windows for the
roles so terminal sessions and actor-scoped caches remain distinct. Hard-refresh if
an already-open browser still has the earlier bundles. No real browser queue was cleared.

An explicitly labelled demonstration is available at:
`http://radolfa.localhost:8000/app/shift-review/2f37dq2r2a`.
Opening `POSA-OS-26-0000016` counted 1,000; its recorded tea expense was 20; closing
`POSA-CS-26-0000014` expected 980 and counted 930, leaving **−50 / Pending review**.
The cashier's original reason/counts are retained. No loss adjustment or transfer was
posted for that demonstration, so the manager/owner can exercise its review actions.

The real browser check also created an active cashier opening
`POSA-OS-26-0000017` for **POS Main**, with a cash float of 1,000 and other methods zero.
That shift is ready for the owner's next manual POS test:

1. Log in as the test cashier, open `/app/posapp`, select that cashier and enter its PIN.
2. Record tea costing 20 from Cash; the shift's expected cash becomes 980.
3. Close with 930 counted and a reason; expect a separate pending shortage of 50.
   Leave physical fiscal printing and transfer options off for the initial software test.
4. Log in as manager/owner and open `/app/shift-review`; select the correct closing origin.
   Record a **new omitted expense** of 20, then 30, to check partial/resolved states.
   The earlier recorded tea expense is already in expected totals and cannot be linked
   again to explain the shortage. Original counted 930 remains unchanged.
5. Inspect `/app/expense-desk` and native journal links. For a genuine-loss test, only
   the owner account may use the approved cash adjustment action. Use the native
   correction/cancellation workflows when undoing a test; do not edit original counts.

Money Hub shows the entire account's book balance, including retained earlier test data.
It is not the same scope as one shift's float/count. The earlier demonstration and the
new test remain separate origins rather than being carried into the next opening.

# Setup applied

- **POS Main:** retained its payment mappings, company/currency, warehouse, prices and
  sales configuration. Assigned the three new users and selected the existing Safe
  account as its explicit counted-cash destination.
- **Funding sources:** enabled explicit POS Main expense grants on Cash, Alif, Eskata
  and Dushanbe city wallets. Enabled office spending on the existing Safe wallet.
  No grants were inferred for the other register.
- **Categories:** added Radolfa company rows using the nine categories' already valid
  expense accounts and `Main - R` cost center. No category/account was guessed or replaced.
- **Review settings:** configured clearly named `POS Cash Shortage (Dev) - R` and
  `POS Cash Surplus (Dev) - R` accounts and `Main - R` cost center. These are development
  mappings, not a new financial policy or automatic write-off.
- **Permissions:** a dedicated `POS Development Register Access` role grants native
  register read and owner-only opening read to the new test users. Native Company and
  POS Profile User Permissions restrict them to Radolfa/POS Main. Existing cashiers were
  not given Accounts User or broad opening-write permissions. Retail role bundles and
  existing native posting permissions remain authoritative.
- **PINs:** assigned only to the newly created test users. No welcome emails were sent.

# Files Changed

Two defects were found using real cashier sessions after migration:

- `posawesome/posawesome/doctype/pos_closing_shift/pos_closing_shift.py`: the already
  authorized/locked closing now updates its exact opening's lifecycle link with
  `save(ignore_permissions=True)`. Cancellation uses the same constrained lifecycle
  update after its manager/reversal checks. This avoids granting general opening write
  access to a cashier. Native validations still run.
- `posawesome/posawesome/shift_review/test_native_workflow.py`: a native regression closes
  the cashier's own shift through the public API and proves general opening write
  permission is absent before and after closing.
- `frontend/src/posapp/components/pos/employee/EmployeeSwitchDialog.vue`: before a first
  register exists, the PIN overlay no longer covers opening setup. The terminal's locked
  state remains true. Once a register context exists, the normal PIN dialog/loading/
  error flow applies. The already-known employee-list scope remains a valid context.
- `frontend/tests/employeeSwitchDialog.spec.ts`: verifies first register setup retains
  the lock and that a selected register requires normal PIN authorization.
- `scripts/audit_shift_expenses.py`: distinguish scalar SQL columns from Frappe Table
  fields, checking the latter through their Custom Field metadata and child tables.
  This prevents a migrated allowlist from being falsely reported as a missing parent column.

ERPNext:

- `erpnext/public/js/retail_security.js`: the cashier route guard waits for a resolved
  initial route instead of indexing `null` during native Desk startup. Its change listener
  still redirects restricted cashier navigation to POS.
- `erpnext/setup/test_retail_security.cjs`: four startup/navigation regression cases.

Local runtime (outside the app repositories):

- `sites/gunicorn.conf.py`: uses Frappe's existing static/public-file middleware in the
  local Gunicorn worker. The direct port-8000 address previously returned 404 for assets.
  Private files retain native permission checks. No framework source was changed.
- Reloaded only the local bench web/worker/scheduler processes so current Python/hooks
  were active. Supervisor control required root access, so the user-owned processes were
  restarted through their configured Supervisor autorestart. Redis/socketio and Docker
  business services were not restarted.

# Linked Features Checked

Cashier register authorization, PIN lock state, native opening/closing lifecycle,
expense-source grants, original closing evidence, partial review, D4/D5 role boundaries
and native source links were checked. A new native expense/journal of 20 and the labelled
closing example were committed only in the explicitly disposable development site.
No fiscal/printer or bank command was sent. No historical expense was attributed,
reposted or written off. Cart/pricing/UOM/stock/invoice calculations were not changed.

# Commands Run

- `bench --site radolfa.localhost backup` and `bench --site radolfa.localhost migrate`:
  completed without skipping patches or resetting data.
- Native source/permission/setup checks and the read-only schema audit: no missing schema.
- Public cashier opening/expense/closing APIs: one native expense/JE, expected 980,
  counted 930, original pending difference −50; cashier retains no general opening write.
- **20 native integration tests** on the recovered separate disposable test database,
  including the new cashier-close regression. No `_Test Company` fixtures were run on
  the Radolfa development site itself.
- **117 scoped backend tests**, **67 Vue/store/offline tests**, and **50 Node tests** passed.
- POS production build/type check and Chrome 109 CSS audit passed; ERPNext native assets
  were built with `bench build --app erpnext`. Twelve POS assets, two artifact tests and
  Electron packaging configuration checks passed.
- Authenticated real browser: owner and manager review/expense screens; genuine-loss
  action available only to owner; fresh cashier opening setup, native shift creation,
  correct PIN unlock, own pending review and redacted evidence/transfer capabilities.
- Frontend lint: zero errors and existing warnings. Changed POS component/test scoped
  lint passed without warnings. The ERPNext route script has zero errors and two existing
  escaped-script-tag warnings in the untouched badge-print code.
- Python/JS syntax and both app repositories' CRLF-aware diff checks passed.

Private scripts, logs, screenshots and credentials now live under the site's
`private/pos-shift-development` directory because a machine restart cleared `/tmp` during
the handoff. This directory is local operator material and is not committed or public.

# Risks / Notes

This is development activation, not a production deployment. Real printer/QZ, bank
settlement, remaining HRMS/supplier handoffs and eventual production configuration still
need their own checks. New test logins/grants and the `(Dev)` accounts are development
setup. No commit or push was performed. A reset remains unnecessary for this upgrade.

Suggested commits, only if later authorized:

- POS Awesome: `fix(pos): allow scoped cashier closing and first register setup`
- ERPNext: `fix(desk): defer cashier route guard until initial navigation resolves`

# Manual-test follow-up: balances and expense form

## Summary

The owner reported a Money Wallet permission error for `pos-manager@example.test`
and `Cannot read properties of undefined (reading 'posting_date')` when opening
**Record missing expense**. Both were reproduced with that authenticated account.
The owner explicitly selected **Allow managers to view balances** after clarifying
that Money Hub exposes full cash/bank balances. Both fixes are now active on
`radolfa.localhost:8000`; a second local migration completed successfully. No reset
or Docker-site migration was performed.

## Files Changed

- ERPNext `erpnext/accounts/doctype/money_wallet/money_wallet.json`: native **read**
  permission for Retail Manager. No native wallet create/write permission or Accounts
  Manager role was added. Existing Company/Account/User Permissions remain enforced.
- ERPNext `erpnext/setup/retail_security.py`: include Money Hub in manager/owner page
  setup. Clarify that profit/purchase-cost masking is separate from balance access;
  those financial roles remain unchanged.
- ERPNext `erpnext/public/js/expense_entry.js`: initialize the native Dialog's layout
  document. Frappe's collapsible-section mandatory check dereferences that document
  during construction, before callers can assign it. The same fix serves ordinary
  Expense Desk entry, POS corrections and Shift Review missing expenses.
- POS Awesome `frontend/tests/smoke/shift-review.readonly.spec.ts` and smoke README:
  live native regression opens both forms, checks date/category/required-note controls,
  reaches the review confirmation and cancels it. It waits for native modal show
  completion before accessing the current dialog.
- POS Awesome `posawesome/posawesome/shift_review/test_native_workflow.py`: verify
  actual manager wallet/balance reads, absence of native wallet create/write and
  profit/cost permission, genuine-loss denial, and cashier wallet-read denial.
- Canonical ERPNext design standard/expense contract and handoff reports: record the
  owner's explicit balance-visibility decision and current runtime status.

## Linked Features Checked

Money Hub whole-account reads, original company/user restrictions, manager versus
owner loss approval, cashier restrictions, ordinary expense entry, shift/account source
options, required date/note fields and cancelled final confirmation. Original counts,
review state, source postings and the owner's manual test documents were not changed
by these browser checks. Native financial-posting tests ran only on the isolated
disposable test site. Existing Money Hub mutation APIs were not changed by this fix.

## Commands Run

- `bench --site radolfa.localhost migrate`: completed, including after-migrate hooks.
- **20 native integration tests passed** on the separate disposable site, including
  native manager balance access and genuine-loss rejection.
- **28 Node orchestration/startup tests passed** (Expense Desk, Shift Review and retail
  route guard).
- Authenticated Playwright `-g 'shared expense entry'`: ordinary entry and pending
  review `2f37dq2r2a`, date/category/required-note checks, final confirmation cancelled.
- Separate authenticated manager/owner browser checks: Money Hub RPC 200 with balances
  rendered, no permission modal, correct genuine-loss action boundary, native missing-
  expense date/form on 390px mobile viewport with no modal overflow or uncaught errors.
- Scoped ESLint/Prettier, JavaScript/Python syntax and CRLF-aware app diff checks passed.
  A frontend bundle build is unnecessary for this raw shared JS asset, role metadata
  and tests. No pricing, invoice, offline or printing implementation changed.

## Risks / Notes

Log out/in as manager to refresh cached boot permissions, then use **Ctrl+Shift+R**.
Open `/app/money-hub`, then return to the intended review and retry **Record missing
expense**. The prepared example remains unresolved for manual testing because the
browser checks cancelled before posting. Test evidence and screenshots are under
`sites/radolfa.localhost/private/pos-shift-development/manager-fixes`.
The isolated test DB/Redis containers were restored to their stopped state afterward.
No commit, push, production publication or new real-site financial posting was performed.

Suggested commits, only if later authorized:

- ERPNext: `fix(expenses): initialize entry dialog and allow manager balance reads`
- POS Awesome: `test(expenses): cover native entry dialog and manager balance access`
