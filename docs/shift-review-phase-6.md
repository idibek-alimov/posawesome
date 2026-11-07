# Shift discrepancy backend — Phase 6

Implemented locally 2026-11-06. The owner authorized the next phase in the bench-root
`POS_SHIFT_DISCREPANCY_PLAN.md`. Substantial unreported Phase 6 work was already present;
it was reviewed, completed and verified while preserving the earlier expense/UI changes.
Nothing was migrated, configured, posted on a business site, committed or deployed.

## Result

Closing and resolving a difference are separate operations. A 1,000 expected / 950
actual closing retains its original -50 and creates Pending review in the closing
transaction. A reason is required for a nonzero difference. Blind counting uses a count
note without displaying the hidden expected amounts. Balanced closings also retain
evidence and a Resolved review, allowing an independently recoverable safe transfer.

Supported manager commands preserve the original snapshot:

- Link a submitted, permitted source omitted from the original expectations. Validate
  company, explicit shift attribution, posting dates, currency, native GL effect and
  capacity. Original counted sources, another shift's sources, reused account effects,
  reversal documents and counted-cash safe transfers cannot falsely resolve money.
- Record a missing expense through the shared ERPNext POS Correction expense service.
  Its native posting and allocation share a savepoint/transaction. A missing taxi of 50
  posts once and allocates -50; a taxi of 20 leaves -30.
- Approve a configured genuine Cash loss/surplus. Only Retail Owner, Accounts Manager
  or Administrator may invoke it, and native Journal Entry create/submit permissions
  remain required. A shortage debits the configured shortage expense and credits the
  reviewed Cash account; a surplus reverses the cash direction with its configured
  counterpart. Bank/card, unmapped and foreign-currency differences use native handoffs.
- Correct a count with an actor, reason and previous/new count history. Each method's
  correction is bounded by its own original actual/expected interval, including repeated
  corrections when several methods share an account. Withdrawing the latest applicable
  count correction restores the unresolved amount.
- Record investigation/payment/refund/transfer/recovery/bank-reconciliation requests,
  withdraw them, and attach native handoff evidence. Requests alone resolve no money.
  The payment-amendment verifier additionally checks the original cancellation,
  unchanged sales totals, original method mapping and matching native GL changes.

The verifier does **not** grant permission to amend a closed/consolidated invoice.
Existing closed-shift submission and native consolidation/cancellation protections remain.
Specialized corrections require the accountant's permitted native route; do not expose
an unsupported one-click amendment in Phase 7. Native refunds, transfers and recoveries
retain their own forms and permissions. No payroll, automatic cashier liability,
receivable account or historic write-off is invented.

## Evidence, allocation and recovery

Five additive DocTypes are owned by POS Awesome:

| DocType | Purpose |
| --- | --- |
| POS Shift Review | Unique closing identity, immutable snapshot/hash, cashier reason, reviewer, version and status |
| POS Shift Review Account | Account/currency/direction group, expected, actual, original, allocated and remaining amounts |
| POS Shift Review Action | Unique request identity/fingerprint, actor, outcome, amount/currency and source/history evidence |
| POS Shift Source Claim | Unique financial voucher/account claim, signed capacity and allocated amount |
| POS Shift Review Settings | Explicit company shortage/surplus accounts, cost center and supported native dimensions |

The snapshot preserves method detail, original invoice amounts/payments/rates, source
identities and posting/currency details, plus financial voucher/account GL legs. Same-sign
aliases share an allocation group; opposite signs remain separate. Group expected/actual
amounts cover the methods in that group; the complete method breakdown stays in the
snapshot. Zero-difference accounts remain scope evidence. Company currency precision is
frozen with the review; unsupported currency posting fails closed.

`remaining = original_difference - valid_signed_allocations`.

Pending review, In review, Partially resolved, Resolved and Voided describe review state.
Failed native posting rolls back its resolution rather than creating a success record.
Requests and retries serialize by actor, lock current source/review rows, check review
version, and use unique request/claim constraints. Outcome/retry reads take review locks
before action-history locks. List/export restrictions include the shared expense policy's
applicable-for Company, Profile and Account User Permissions as well as native scope.
Cashiers cannot execute manager commands, see another cashier's review or self-approve.

Native source cancellation and Journal Entry reversals invalidate the affected financial
allocations in the same transaction, retaining history and recomputing remaining amounts.
A partial reversal retains only the still-posted portion. Previously invalidated actions
are not silently reactivated if a reversal is later cancelled; a manager must validate
and relink the still-posted capacity. Closing cancellation requires completed resolutions
to be reversed/withdrawn and transfer outcomes investigated, then preserves a Voided review.

These lifecycle hooks cover **resolution sources**. Later changes to sources originally
included in closing expectations do not rewrite that immutable closing or manufacture
new allocations. Such original-source corrections require explicit native investigation;
the Phase 7 detail and Phase 8 next-shift reconciliation must make subsequent changes
visible rather than treating the frozen snapshot as a current full-account balance.

## Closing and linked features

- POS API, native Desk and direct Document submission use one authoritative validator.
  It locks the stored opening shift, checks scope/transaction membership/actual counts,
  rejects stale expectations, fills authoritative totals and requires the explanation.
  The POS API accepts only closing intent and source references; caller identities,
  child-row identities, internal flags and forged review links are discarded before its
  constrained business-document permission escalation. Financial submission uses POST.
- Native Desk loads the same server draft, uses actual minus expected, preserves counts
  and notes entered during refresh, ignores obsolete responses and keeps save disabled
  on a failed refresh. POS validates company currency precision before emitting submission.
- Native invoice/payment/movement submission and cancellation serialize on the opening
  shift row. Authorized closed-shift Quick Expense corrections remain supported.
- POS consolidation passes `commit=False` through ERPNext's merge helpers. No intermediate
  commit/rollback or queued merge can separate successful closing from its review snapshot;
  the notification is deferred until commit. Existing native default callers keep their
  original transaction behavior.
- Counted-cash safe transfer uses a guarded native Internal Transfer Payment Entry without
  Money Hub's explicit commit/refresh boundary. One deterministic closing request preserves
  its original amount/destination/outcome. Zero is a real count, foreign currency is
  rejected, and a reversed transfer cannot be automatically sent again. Transfer never
  allocates a shortage or surplus. Historical closings without this provenance require
  native investigation instead of a new blind transfer.
- Fiscal printing, failed-close cart preservation, offline expense queues, pending financial
  request guards and original-currency closing details retain their existing contracts.
  Pricing/search/discount/UOM/stock/customer/invoice payload and receipt arithmetic are
  unchanged. POS Profile still owns company, payment methods, cash mode and configured
  back-office destination; no expense grants or accounting accounts are guessed.

## Files

Paths are relative to their owning app repositories.

POS Awesome:

- `posawesome/posawesome/doctype/pos_shift_review*/` and `pos_shift_source_claim/`:
  additive metadata/controllers and service-only immutable audit records.
- `posawesome/posawesome/shift_review/`: arithmetic, snapshots, capability/query scope,
  shared closing validation, serialized commands, native lifecycle hooks, safe transfers
  and controlled document/ledger tests.
- `posawesome/hooks.py`: optional source lifecycle and review permission/query hooks.
- `posawesome/posawesome/doctype/pos_closing_shift/`: controller lifecycle, shared API
  validation, transaction-owned consolidation, native Desk form/fields and regressions.
- `posawesome/posawesome/api/fiscal.py`: delegates safe transfer to the recoverable service.
- `frontend/src/posapp/components/pos/{closing/PaymentReconciliation,shell/ClosingDialog}.vue`,
  `frontend/src/posapp/composables/pos/closing/{closingAmounts,useClosingShift}.ts`:
  count note, preserved explanation, currency precision and submission guard.
- `frontend/tests/closingShift.spec.ts`, `scripts/closing_shift_form.test.cjs`, translations
  and contract/report updates: coverage, Russian/Tajik strings and handoff.

ERPNext:

- `erpnext/accounts/expense_services/shift_adjustments.py`: configured native JE and
  safe-transfer construction with native permissions, setup validation and no commit.
- `erpnext/accounts/expense_services/test_shift_adjustments.py`: setup restrictions and
  native consolidation transaction/default compatibility checks.
- `erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py`: opt-in caller
  transaction ownership; ordinary native callers retain the default behavior.
- `docs/expense-workflow-contract.md`: implementation boundary/status.

## Verification

- **188 backend tests plus 2 standalone loyalty checks passed**, including 49 review
  tests and 7 ERPNext setup/consolidation tests. Coverage includes missing 50, partial
  amounts, surplus, shared accounts/opposite signs, cancellation/partial reversal,
  posting failure rollback, immutable evidence, wrong company/source/actor, stale second
  reviewer, unique cross-shift source claims, retry lock order, transfer retry/reversal,
  API input sanitization and missing-schema guards. The real POSOpeningShiftDetail
  Document regression remains covered on both summary and submission paths.
- **30 frontend tests passed** across closing, shift state, loyalty, pending requests and
  offline movement retry; expected failure-path console messages are fixture assertions.
- **7 native closing-form Node tests passed**; **2 build-artifact tests passed**.
- Scoped frontend ESLint passed with zero warnings. Production build passed vue-tsc,
  Vite and the Chrome 109 CSS audit. Asset verification and Electron package configuration
  smoke passed. Existing bundle-size/browser-data advisories remain.
- Four actual Vue/Vuetify Chromium fixtures passed: RU desktop/light, TG phone/dark,
  RU blind phone/dark and TG blind tablet/light. Checked reason/count note, close guard,
  emitted input, hidden expectations, no page errors and no horizontal page overflow;
  desktop/phone captures were visually inspected. APIs/offline state were mocked.
- Python AST, new DocType JSON structure, native JavaScript syntax and both app diff
  whitespace checks passed. Optional Python Ruff is unavailable; a temporary formatter
  download failed because package-network access was unavailable. No repository dependency
  was added.

Backend/GL persistence, permissions and row locks in these tests use controlled fixtures.
They do **not** prove real MariaDB serialization, native financial posting/period/dimension
validation, permission-query compilation, private File behavior or authenticated interaction.
No live printing, QZ device or physical cash/bank movement was tested.

Reproduce from the bench root:

```bash
env/bin/python -m unittest \
 erpnext.accounts.expense_services.test_expense_policy \
 erpnext.accounts.expense_services.test_expense_commands \
 erpnext.accounts.expense_services.test_expense_queries \
 erpnext.accounts.expense_services.test_expense_history \
 erpnext.accounts.expense_services.test_shift_adjustments \
 posawesome.posawesome.api.test_expense_context \
 posawesome.posawesome.api.cash_movement.test_cash_movement \
 posawesome.posawesome.api.cash_movement.test_expense_retries \
 posawesome.patches.test_repair_expense_source_settings \
 posawesome.posawesome.doctype.pos_closing_shift.test_pos_closing_shift \
 posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_cash_movement_integration \
 posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_summary \
 posawesome.posawesome.shift_review.test_review -q
env/bin/python apps/posawesome/posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_overview_loyalty.py
node --test apps/posawesome/scripts/closing_shift_form.test.cjs
# In apps/posawesome/frontend:
yarn test:unit tests/closingShift.spec.ts tests/usePosShift.spec.ts tests/closingLoyaltySummary.spec.ts tests/pendingExpenseRequests.spec.ts tests/offlineCashMovements.spec.ts
yarn build
# In apps/posawesome:
yarn verify:build
yarn test:build-verify
yarn electron:smoke
```

The temporary browser harness is `/tmp/closing-phase-6-browser.mjs`; its fixtures and
screenshots are disposable, not product assets or authenticated site evidence.

## Setup and release boundary

Update both app sources together. An authorized standard site migration must synchronize
the earlier expense schema plus the new review DocTypes/closing fields before new closing
or resolution is enabled. The schema guard fails clearly rather than creating a closing
without review evidence. No historical reviews or financial losses are auto-posted/backfilled.

An authorized accountant/owner must configure POS Shift Review Settings per company:
explicit enabled company-currency shortage expense/surplus accounts, applicable cost center
and native accounting dimensions. Existing explicit expense category/wallet/register grants
remain required for missing expenses. Native JE/Payment Entry capabilities and record scope
must be validated; a Retail Owner role by itself does not bypass native posting permissions.
Unsupported bank/currency/complex invoice corrections remain in native workflows.

Phase 7 owns the manager list/detail and usable action dialogs; Phase 8 owns connected
navigation and subsequent-shift reconciliation. Phase 9 must rehearse migration/reruns,
native document/GL/permission/period/dimension behavior, real simultaneous review/close/
cancellation/reversal requests and outcome recovery on a migrated disposable site. Include
failure after consolidation/review creation and native safe-transfer cancellation/retry.
Original-source changes after close require explicit follow-up evidence, as described above.

Suggested future commits, only if separately authorized:

- POS Awesome: `feat(pos): add auditable shift discrepancy resolution services`
- ERPNext: `feat(accounts): support guarded shift adjustments and atomic POS consolidation`
