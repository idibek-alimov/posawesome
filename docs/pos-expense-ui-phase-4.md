# Phase 4 — simple POS expense entry

Completed locally, 2026-11-06. Owner policies D1–D5 remain unchanged. No site migration,
configuration, live financial action, queue clearing, commit, push or deployment occurred.
The root `POS_SHIFT_DISCREPANCY_PLAN.md` controls delivery; stop before Phase 5 until
requested. This phase does not implement shortage accounting or Shift Review.

## Cashier experience

`/app/posapp/expenses` now has three main fields: Category, Amount and Paid from.
Notes, recipient and a private receipt photo/PDF are secondary. A register-required note
stays visible and required. There are no arbitrary category, expense-account, cost-center
or bank-wallet defaults. Only a unique permitted Cash source defaults; after an unavailable
selection is cleared, refresh does not silently replace it with a different source.
The displayed wallet and underlying account identify the actual payment source.

The compact history initially covers the whole current shift, including overnight activity.
Paid, cash and bank/wallet figures come from the shared full-result history service and
are period activity, never company account balances. Date/category/source/status/search
and permitted recipient filters stay under Filter history. Active scope remains visible.
Details progressively reveal notes, recipient, receipt, shift, native source and accounting
links. Historical Cash Movement and Quick Expense identities remain distinct. Cancelled
and draft records are optional and excluded from submitted spending totals. Custom dates
waiting to apply, loading, failure and offline states do not display plausible zero totals.

The read-only POS-owned `get_pos_expense_session` endpoint discovers the actor's native
permitted open shift or validates the explicitly supplied session shift. It rejects
ambiguity with a choose-register state and never selects the first active profile or
another shift when the explicit one is missing. It uses existing expense/profile scope
and native Quick Expense create/submit permissions. It avoids the older opening-shift
bootstrap, whose unrelated customer/tax setup can perform writes. Both browser form and
server continue to enforce configured notes, source rules and existing amount limits.

Cashiers cannot cancel submitted expenses. Managers use the detail action with a required
reason and stored modification version. The explanation distinguishes reversing an
accounting entry from actually receiving physical cash back. Native Expense Claim and
Purchase Invoice handoffs appear only with corresponding boot read access; all users
receive plain guidance to ask a manager when money was paid personally or remains unpaid.
No employee/advance/payroll posting is inferred from the optional recipient name.

## Failure and recovery

- A send is double-submit guarded. Failed sends retain input; confirmed success has its
  own source/amount/shift/document receipt even if the subsequent history refresh fails.
- New Quick Expense remains online-only, consistent with the existing shared service.
  Offline input remains in the mounted form. There is no new hidden posting queue.
- Pending record/cancel operations appear independently of form validity, session
  availability or current category/wallet setup. Check result uses the existing scoped
  outcome API and never creates an expense. Retry original request resends the saved
  intent through the existing helper, retaining its original ID.
- The shared helper clears evidence only for a named, coherent terminal result:
  submitted/cancelled for recording, cancelled for cancellation. Not found, draft,
  denied, corrupt or unconfirmed evidence is retained. In particular, an independent
  not-found check does not discard an original request that could still arrive late.
- A cancellation check returning a still-submitted original does not falsely report a
  completed cancellation. A cancelled original does not masquerade as a new payment.
- Legacy queued movement warnings link to Cash movements. Its pending list now offers
  read-only Check result using the original ID, even for retained review items. Missing
  IDs/corrupt payloads stay visible for a manager. This action neither deletes nor marks
  a queue entry synced, and never fabricates identity or replaces the original payload.
  Normal retry/sync remains the existing guarded queue path. Dead-letter/cancelled items
  still require explicit manager handling; no new discard/reset policy was introduced.
- Existing local evidence/financial-queue closing guards remain effective. Back to POS
  preserves the shared cart/session; closing's existing refresh recalculates source totals.
  Expense screens introduce no global scanner handlers; POS scanner hooks detach when its
  route unmounts, and Vuetify manages detail/cancellation dialog focus locally.

Receipts use native `/api/method/upload_file`, same-origin credentials, CSRF and
`is_private=1`. The UI accepts only a confirmed private native file path for new uploads;
no expense is submitted while its upload is incomplete or failed. The existing server
checks native File read access before linking it. The existing Quick Expense controller
attaches the receipt to the expense/accounting documents. Historic native file links
remain usable; active/external URLs are not rendered. Unsubmitted uploads remain native
private owner files; this phase does not add automatic File deletion. Native private-file
sharing/download and controller attachment propagation still need disposable-site release
verification; mocked upload responses do not prove native storage permissions.

## Files and linked behavior

| Files | Purpose |
| --- | --- |
| `frontend/src/posapp/components/pos/expenses/PosExpenseDesk.vue` | Simplified entry/history/detail, session/error states, stable recovery and manager cancellation. |
| `frontend/src/posapp/composables/pos/expenses/receipt.ts` | Private native upload and safe receipt paths. |
| `posawesome/posawesome/api/expense_context.py` | Read-only own-session discovery and native record capability; existing policy hooks retained. |
| `frontend/src/posapp/components/pos/cash/CashMovementView.vue` | Read-only original legacy outcome checks; retain unknown/malformed requests. |
| ERPNext `erpnext/public/js/expense_requests.js` | Shared independent result check without new posting policy. Desk's existing run behavior retained. |
| Tests and RU/TG CSV additions | Session/receipt permissions, private upload, recovery, original IDs, failure/input and history scope. |

The approved unique Expense entry/legacy transition from Phase 3 remains conditional on
usable shared setup and native access. Old Expense/Deposit endpoints, queued requests,
feature flags and transfers remain compatible. No account/category/profile grant was
added. Company currency comes from the validated expense context, including direct route
entry before the shared POS profile has loaded. This phase does not change checkout
search/cart, prices, discounts, UOM, warehouses, stock, taxes, invoice payloads, loyalty,
printing/QZ/fiscal receipts, closing arithmetic or safe-transfer posting.

## Verification and practical limits

- 125 scoped backend regressions plus 2 standalone closing loyalty checks passed.
  Includes five session-discovery regressions and native File read-denial policy checks.
  Financial persistence and native permission compilation remain isolated/mocked.
- 52 frontend checks passed, including 8 expense-screen workflow cases, 3 private-receipt
  checks, 3 legacy recovery checks and the existing offline/closing regression set.
- 15 shared request-helper checks passed, including independent checks after disabled
  setup, not-found retention and cancellation outcome distinctions.
- Scoped ESLint with zero warnings, vue-tsc/Vite production build and Chrome 109 CSS
  audit passed. Existing bundle-size/Browserslist advisories remain.
- Build asset verification, 2 build-artifact tests and Electron configuration smoke passed.
- Actual Vue/Vuetify Chromium fixtures in Russian/Tajik at 1440, 834 and 390 widths, both
  light/dark: 12 entry/history cases passed private-receipt selection, canonical category
  ID, full-total pagination, status filters, no page errors or page overflow. Additional
  disabled setup, not found, denied, no shift, lost response, offline/reconnect, required
  note and lost manager-cancellation cases passed. Browser APIs/uploads were mocked;
  only isolated browser storage was used. No authenticated business-site/hardware test
  is claimed. Browser fixture screenshots were visually inspected locally.
- Python AST, helper JS syntax, translation coverage and both app diff checks passed.

Reproduction commands from bench root unless indicated:

```bash
env/bin/python -m unittest \
 erpnext.accounts.expense_services.test_expense_policy \
 erpnext.accounts.expense_services.test_expense_commands \
 erpnext.accounts.expense_services.test_expense_queries \
 erpnext.accounts.expense_services.test_expense_history \
 posawesome.posawesome.api.test_expense_context \
 posawesome.posawesome.api.cash_movement.test_cash_movement \
 posawesome.posawesome.api.cash_movement.test_expense_retries \
 posawesome.patches.test_repair_expense_source_settings \
 posawesome.posawesome.doctype.pos_closing_shift.test_pos_closing_shift \
 posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_cash_movement_integration \
 posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_summary -q
env/bin/python apps/posawesome/posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_overview_loyalty.py
node --test apps/erpnext/erpnext/accounts/expense_services/test_expense_requests.cjs
# apps/posawesome/frontend:
yarn test:unit tests/posExpenseDesk.spec.ts tests/expenseReceipt.spec.ts tests/cashMovementRecovery.spec.ts tests/offlineCashMovements.spec.ts tests/pendingExpenseRequests.spec.ts tests/writeQueueTransactions.spec.ts tests/usePosShift.spec.ts tests/closingLoyaltySummary.spec.ts tests/closingShift.spec.ts tests/cashMovement.spec.ts
yarn build
# apps/posawesome:
yarn verify:build
yarn test:build-verify
yarn electron:smoke
```

Phase 2 migrations/source/category setup, Phase 3 permission synchronization and native
MariaDB/GL/reversal/concurrency/private-file/old-cache rehearsal remain rollout gates.
Both configured business sites retain `allow_tests=false`. Missing-money accounting is
still the previously documented gap until Phases 6–7 implement manager review/resolution.
Next authorized phase should be Phase 5, the ERPNext Expense Desk list/detail redesign.

Suggested commit: `feat(pos): simplify shift expenses and expose original request recovery`.
