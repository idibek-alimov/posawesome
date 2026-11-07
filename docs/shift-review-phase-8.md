# Summary

Phase 8 is implemented locally, 2026-11-06, following the owner's instruction to start
the next phase in `POS_SHIFT_DISCREPANCY_PLAN.md`. Existing Phases 2–7 edits in both
customized app repositories were preserved. Phase 9 is next. No site migration,
configuration/role changes, live posting, shift closing, money movement, printer call,
service restart, cache refresh, commit, push or deployment was performed.

Cashiers can see their own permitted original closing, reason, counts, remaining
amount and status while preparing the following opening. Older unresolved origins
remain available across all dates, with pagination. Original closing details and
printing/transfer recovery are secondary, expandable information. Managers can open
the authorized Shift Review page; the cashier projection contains no source/GL JSON,
reviewer action history, book balances or manager posting controls. Other cashiers'
records remain private. Managers retain the wider permitted list in Shift Review.

Expense Desk and POS expense detail now expose permitted shift/review connections.
Shift Review reuses the same expense entry and detail renderer. A native-document
link dismisses the detail modal; returning to the Desk page or from another window
refreshes the relevant data. POS expense history/detail also refresh on returning.
No ordinary expense is recorded by a navigation action.

Money Hub is kept as an account/wallet balance and transfer view. Reading it no longer
imports accounts or creates Money Wallets. It checks native Company, Money Wallet,
Account and ledger-read capability. Its account list and selected-wallet feed are
restricted to the permitted company/accounts. Total/cash/bank balances use native
company-currency ledger balances, preserve the original foreign-account balance on
cards, use native currency precision for each currency, and count enabled account aliases once. Disabled wallets do not inflate totals.
The ledger feed also has an explicit company constraint. Failed/obsolete reads cannot
leave earlier balances or movements presented as the current successful result.

## Reconciliation and supported routes

- Expected 1,000 / counted 950 still records the original −50. Explaining 20 with the
  atomic missing-expense command leaves −30; another 30 leaves zero. Each economic
  expense posts once. Neither operation rewrites the original counts or the following
  opening balance. Existing source/cancellation/reversal guards remain authoritative.
- The next opening uses the legitimate money physically available. If all counted 950
  was moved to the Safe, a following physical float of zero stays zero. Any new float
  must reflect real funds/transfer, never the unresolved book 50. The old origin stays
  in review until it is explained or approved. A later shift's own activity is scoped
  by its stored opening link; shared-bank balances remain account-wide.
- Opening amount labels now use company currency, consistent with closing/review counts,
  independently of the sales POS Profile currency. Opening-dialog cache metadata carries
  `count_currency_basis=company`; older unversioned chooser metadata requires a fresh
  server read. Cart, bootstrap financial queues and draft invoice caches are untouched.
  Fresh payment metadata updates currency labels without discarding counts already typed
  for the same register. Opening buttons wrap on phones and say Open shift.
- Shift Review retains company-currency original counts and shows the original invoice
  amount/currency alongside its frozen base amount. Money Hub uses the ledger's stored
  company-currency values, not a current-rate conversion of the account balance. The
  shared Quick Expense service still supports company-currency funding accounts only;
  foreign expenses/complex conversions use permitted native accounting forms.
- A safe-transfer retry retains its closing identity. A completed original request is
  returned without another payment, including after a following shift. A new transfer
  using an old count is refused once another submitted opening on that register exists,
  including one later cancelled, or another opening is already active. New openings
  and this transfer guard share a POS Profile row lock; posting checks use a current
  locking read after that lock rather than an earlier repeatable-read snapshot. The native transfer route must
  use current physical evidence at that point. Existing zero/currency/count-correction,
  cancellation/reversal and exact-source guards remain in place.
- Fiscal printing and Safe transfer remain after successful ERP closure, independent of
  discrepancy resolution. An unknown fiscal outcome gets a printer-journal/reprint
  recovery notice; this screen never blindly sends another fiscal close. The immediate
  print-outcome hint is actor-scoped in memory. After a reload the printer journal is
  authoritative; it is not inferred from the financial review or transfer state.
- Personally paid costs use HRMS Expense Claim approval and its native Create Payment
  workflow (`hrms.overrides.employee_payment_entry` / permitted native bank JE route).
  Supplier costs already recorded on Purchase Invoice use its native payment allocation.
  Paying either payable does not create a second Quick Expense. The shared form explains
  this and links only readable native documents. HRMS guidance, claim approval/payment
  controller, and supplier payment controls were traced; no HRMS code was changed.
- Refunds, bank settlement/reconciliation, transfer corrections and established recovery
  use the existing review request plus native Payment Entry/Journal Entry routes. A
  request itself resolves nothing. An omitted supported account effect can be linked
  once with explicit original-shift attribution; unsupported multi-document/foreign
  corrections remain with the accountant. No salary deduction, liability assumption,
  new recovery subsystem or automatic loss posting was introduced.

Initial expense reporting remains **paid Quick Expenses plus historical Expense cash
movements**, not an accrual P&L or a combined claims/supplier-bill report. Transfers,
unpaid claims/bills and payable settlement must not be added as new expense costs.
Unassigned legacy spending stays visible for explicit manager investigation; there is
no historical auto-linking, financial backfill or automatic write-off. Several registers
sharing one account retain separate supported transaction/shift attribution, while
Money Hub and native bank reconciliation show the whole permitted account.

# Files Changed

Paths are relative to their owning app repositories. These are Phase 8 changes on top
of the already uncommitted earlier phases.

POS Awesome:

- `posawesome/posawesome/shift_review/journey.py`: read-only cashier register/closing
  projections and the optional permission-scoped expense-to-shift/review link adapter.
- `posawesome/posawesome/api/expense_context.py`: extract the existing register read
  authorization for reuse before a new shift exists; expense validations retain it.
- `posawesome/posawesome/api/shifts.py`: company-currency opening labels and metadata basis.
- `posawesome/posawesome/shift_review/transfers.py`, `posawesome/hooks.py`: serialize
  new openings with late transfer checks; retain original transfer replay; register the
  optional expense detail link hook.
- `frontend/src/posapp/components/pos/shift/{OpeningDialog,ShiftReviewNotice}.vue`:
  previous origins/status at opening, untouched physical input, independent transfer
  recovery, printer notice, stale/offline/error handling and usable mobile actions.
- `frontend/src/posapp/stores/uiStore.ts`,
  `frontend/src/posapp/composables/pos/shared/usePosShift.ts`: actor-scoped in-memory
  last-closing print outcome; successful ERP closure still governs existing cleanup.
- `frontend/src/posapp/components/pos/expenses/PosExpenseDesk.vue`: linked review status
  and refreshing history/detail after native-document return.
- `posawesome/posawesome/page/shift_review/shift_review.js`,
  `posawesome/posawesome/shift_review/desk.py`: shared expense detail, native handoff
  navigation, return refresh and original invoice currency beside base amount.
- `posawesome/posawesome/doctype/pos_shift_review/pos_shift_review.json`: original raw
  evidence JSON/hash now require native manager permission level 1 and are print-hidden.
  Cashier level-0 counts/status remain readable. This metadata requires migration.
- `posawesome/posawesome/shift_review/test_journey.py`, `test_review.py`,
  `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_summary.py`,
  `frontend/tests/shiftReviewNotice.spec.ts`: journey/permission/currency/old-count tests,
  fixture support for the new date check and retained real child-Document regression.
- `posawesome/translations/{ru,tg}.csv`, contracts and this report: localized wording,
  currency/scope/recovery boundaries and activation notes. CSV line endings preserved.

ERPNext:

- `erpnext/public/js/expense_entry.js`: share existing expense detail and receipt display
  as well as entry; optional POS links; native-return callback; explicit claim/bill guidance.
- `erpnext/accounts/page/expense_desk/{expense_desk.js,expense_desk.py}`: optional hook
  without a POS import; shared detail wrappers and native-return refresh.
- `erpnext/accounts/page/money_hub/{money_hub.py,money_hub.js}`: read-only authorized wallet
  discovery, correct base/original balance currencies, alias/disabled handling, account
  scope explanation and guarded error/obsolete response handling. Existing transfer,
  creation, tax, supplier and other unrelated UI flows were not redesigned.
- `erpnext/accounts/page/money_hub/test_shift_balances.py`,
  `erpnext/accounts/expense_services/test_expense_queries.py`: currencies, complete
  account totals, native discovery capability, denied-wallet/company feed and optional hooks.
- `erpnext/translations/{ru,tg}.csv`, `docs/expense-workflow-contract.md`: shared localized
  text and current implementation status.

Bench-root `POS_SHIFT_DISCREPANCY_PLAN.md` records Phase 8 completion and Phase 9 next.

# Linked Features Checked

Stored POS Profile company, payment-account mappings, currency, register assignment and
native permissions still govern scope. The original closing/count/expense services,
source provenance, one-account aliases, cancellation/reversal and safe-transfer identities
remain authoritative. No logic changed for item search, cart lines, price lists, pricing
rules, discounts, UOM, stock/warehouse, customer, taxes, invoice submission payloads,
receipt totals, QZ Tray, IndexedDB schema or offline queue formats. Existing financial
queues and unresolved expense requests still block closing. No real queue was cleared.

# Commands Run

From bench root, the full Phase 6 backend regression command in
`shift-review-phase-6.md` was rerun with these additional modules:

```bash
posawesome.posawesome.shift_review.test_desk
posawesome.posawesome.shift_review.test_journey
erpnext.accounts.page.money_hub.test_shift_balances
```

**228 backend tests passed**, including existing closing and real
`POSOpeningShiftDetail` coverage, 15 new journey checks, 5 Money Hub checks and 2 new
optional-hook checks. These use controlled documents, permissions and ledger fixtures,
not native MariaDB posting or simultaneous real connections.

```bash
node --test apps/posawesome/scripts/shift_review.test.cjs \
  apps/posawesome/scripts/closing_shift_form.test.cjs \
  apps/erpnext/erpnext/accounts/page/expense_desk/test_expense_desk.cjs
```

**31 Node tests passed**. From `apps/posawesome/frontend`:

```bash
yarn test:unit tests/shiftReviewNotice.spec.ts tests/posExpenseDesk.spec.ts \
  tests/usePosShift.spec.ts tests/closingShift.spec.ts tests/closingLoyaltySummary.spec.ts \
  tests/pendingExpenseRequests.spec.ts tests/offlineCashMovements.spec.ts \
  tests/cashMovementRecovery.spec.ts tests/expenseReceipt.spec.ts
yarn build
yarn lint
```

**50 Vue/offline unit tests passed**, including 6 new notice/recovery/race checks.
Type checking, production Vite build and Chrome 109 CSS audit passed. Full frontend
lint has zero errors and the same 52 existing warnings; scoped changed frontend/native
Desk scripts passed zero-warning lint. Existing browser-data/chunk-size build warnings
were unchanged. From `apps/posawesome`, `yarn verify:build`, `yarn test:build-verify`
(2 checks) and `yarn electron:smoke` passed. Electron smoke checks packaging configuration,
not a running packaged terminal or physical hardware.

Chromium fixture evidence:

- 11 checks using the actual OpeningDialog/notice Vue and Vuetify components: Russian/
  Tajik, 1440/834/390 widths, light/dark, opening zero then entered 25 independent of old
  −50, partial status, restricted manager link, lost transfer result recovery and errors.
- 14 Shift Review native-control fixture cases, including the new shared expense detail,
  its permitted return link and refresh after native navigation. Existing missing expense,
  approval, original-request recovery, offline and stale-version checks remain passing.
- 17 Expense Desk native-control fixture cases, now also checking originating review links.
- 4 Money Hub balance/currency/error checks across Russian desktop and Tajik phone.

There were no page errors or whole-page horizontal overflow in these fixtures. Desktop
and phone opening captures were visually inspected; clipping found during review was fixed.
The existing isolated Shift Review Axe checks still pass. No new claim is made about a
full live-site accessibility audit. Fixtures use mocked RPC/persistence/native control
shells (actual Desk stylesheet) or actual Vue/Vuetify with mocked backend calls.
Disposable scripts/captures are under `/tmp/phase8-browser.mjs`,
`/tmp/phase8-money-browser.cjs`, `/tmp/shift-review-browser.cjs`,
`/tmp/expense-desk-browser.cjs` and `/tmp/phase8-*.png`; they may not survive a restart.

Python/JS syntax, review JSON, native script formatting/lint and CRLF-aware app diff
checks passed. No test dependency was installed.

# Risks / Notes

Update both apps together. The existing Phase 2–6 schema/setup and Phase 7 Page need an
authorized migration; include the new native review field-permission metadata and
refresh hooks/assets using the real deployment procedure. POS frontend assets were built
locally, without publishing them. The shared detail helper is served from ERPNext's
public assets. No site cache/service operation was performed.

Money Hub now requires configured Money Wallet records and native wallet/account/ledger
read access. Reading it no longer creates wallets for every bank/cash account. Configure
missing wallets deliberately in the native setup workflow; do not restore provisioning
as a side effect of navigation. Preserve explicit register expense grants; accepting a
customer payment remains distinct from permission to spend that wallet's funds.

Phase 9 must verify native field-level/API/export/print permissions, GL/base-account
currency figures, source cancellation/reversal, real two-connection register/review locks,
private files, migration reruns/rollback, legacy attribution/mapping audit, native claim/
supplier/recovery flows and printer/transfer operational recovery on a disposable controlled
site. Mocked ledger and browser checks are not authorization to perform business actions.
Raw GL provenance must remain unavailable to cashier native forms/API/export after migration.
Historical foreign/ambiguous cash-movement records require native accounting/audit handling;
no conversion or historic loss posting is invented by this phase.

Suggested commits, only if later authorized:

- POS Awesome: `feat(pos): connect shift review history and next-opening reconciliation`
- ERPNext: `fix(accounts): connect expense reviews and reconcile wallet balance scope`
