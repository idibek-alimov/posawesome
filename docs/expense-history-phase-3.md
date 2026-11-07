# Phase 3 completion — expense history and legacy retries

Local implementation, 2026-11-05. Canonical reporting and ERPNext file map:
[ERPNext history report](../../erpnext/docs/expense-history-phase-3.md).
Policy remains [D1–D5](../../erpnext/docs/expense-workflow-contract.md).
No new owner decision was needed. Phase 4 awaits the owner's instruction.

## Compatible transition

The existing `/expenses` screen is the ordinary Quick Expense entry. The old Cash
Movement form links there and removes its duplicate Expense action **only after** the
current owner/open shift, native create/submit access, approved sources and usable
categories are available. Until then its original configured Cash-only entry remains.
Cash Movement Deposit, original records, endpoints and profile limits/flags remain.
New shared spending permission is never inferred from an old receiving/expense flag.

A legacy queued Expense stays a POS Cash Movement. No queue payload is converted into
Quick Expense, no original ID is replaced, and no historical JE is reposted. Native legacy
read permissions are additive for the retail business roles and Accounts Manager; user
roles themselves are not assigned. Native company/account/register restrictions remain.

## Retry and queue behavior

1. Legacy creation serializes by actor and checks the original ID with a current locking
   read **before** requiring an open shift or current posting configuration.
2. A known result is returned only after current native read scope, original actor,
   company/register/shift/type, amount and supplied original details agree. Original
   currency rounding is respected for old floating-point payloads.
3. An already submitted result can be recovered after shift closure or configuration
   changes. No new document or JE is created. A missing request still needs an open
   submitted owned shift and all existing posting/source checks.
4. A cancelled original is returned as cancelled; sync does not report another payment.
   It stays failed/retained for manager review. A scoped outcome endpoint is available.
5. Cash Movement entry durably saves its original request before sending, even online.
   Sync only acknowledges a named submitted movement with its backing JE. HTTP success
   alone is insufficient. Lost/unconfirmed responses retain the same payload and ID.
6. Existing object, payload-envelope and serialized payload shapes remain supported.
   Deposit retains its original endpoint and Cash-only semantics. Unsupported/missing
   operation identity stays retained; hydration no longer invents a new financial ID.
7. Queue states remain pending, syncing, failed, dead_letter and synced. Current-shift
   pending details expose status and errors separately from submitted history. Existing
   max-retry behavior and retained manager-review records remain; there is no automatic
   discard or repair of a cancelled/missing-ID request. The cashier must not re-enter it
   as a new expense to bypass a failed result. Advanced recovery UI remains Phase 4.
8. Ordinary Quick Expense remains online-only. Its persistent unknown-result evidence
   now participates in financial closing guards; it is not an offline posting queue.

Legacy source resolution now accepts the echoed configured default without requiring
source-override permission. A different source still requires the configured override.
Direct new movement writes cannot inject a backing JE to claim an unposted expense.
Legacy list queries use native row permissions before pagination.

## Changed POS files

| Area | Files / reason |
| --- | --- |
| History | `api/expense_history.py` plus hooks: optional read-only Expense descriptor/detail adapter, preserving native source identity. |
| Retry contract | `api/cash_movement/service.py`, `validation.py`, `queries.py`: authorized current original receipt, closed-shift recovery, native reads and default-source compatibility. |
| Native guard | `api/expense_context.py`: prevent injected accounting links on new legacy movements; existing posting scope unchanged. |
| Permissions | POS Cash Movement JSON: additive business-role read access; no new role assignments or cancellation grants. |
| Queue | `frontend/src/offline/cash_movements.ts`, `writeQueue.ts`: strict acknowledgement, immutable old payloads/IDs and explicit retained failures. Invoice/payment/customer payload rules and IndexedDB schema are unchanged. |
| Old entry | `CashMovementForm.vue`, `CashMovementView.vue`: setup-dependent shared-entry link, durable send and scoped pending state. |
| Shared history | `PosExpenseDesk.vue`: canonical IDs, full totals/actual funding, paging, status, native links and stale/error handling. Full UI simplification remains Phase 4. |
| Closing | `usePosShift.ts`, `ClosingDialog.vue`, `closing/pendingExpenses.ts`: ordinary unknown expense result blocks closing until confirmed. Existing reconciliation, actual-minus-expected sign, loyalty and transfer behavior remain. |
| Coverage | Backend replay/SQL tests, offline IndexedDB and closing tests, helper tests and RU/TG labels/messages. |

Checkout search/cart/prices/discounts/UOM/taxes, invoice payloads, fiscal/Z printing,
QZ/browser receipts and safe-transfer posting were checked for impact; they were not
redesigned. Existing closing calculations and the real opening-child Document regression
remain covered. No hardware print or authenticated checkout verification is claimed.

## Verification

- **119 scoped backend tests plus 2 standalone loyalty regressions** passed. Includes
  isolated SQLite execution of the actual history SQL; native permission compilation and
  native financial persistence remain isolated/mocked.
- **38 frontend tests** passed: legacy offline queue/old payloads, write queue transaction
  behavior, pending expense evidence, closing guards/summaries and legacy service routing.
- **10 Node request-helper tests** passed, including old session evidence migration and
  retaining another operation after a late response.
- Scoped ESLint with zero warnings passed. `yarn build` passed vue-tsc, Vite and Chrome
  109 CSS audit. Existing bundle-size and browser-data age advisories remain.
- `yarn verify:build`, `yarn test:build-verify` (2 tests) and `yarn electron:smoke` passed.
  Electron check verifies package configuration, not a packaged desktop runtime.
- Actual POS Vue component and actual ERPNext Expense Desk JS/CSS rendered in isolated
  Chromium fixtures at 1440/390 widths in Russian/Tajik: **8 history cases** passed
  pagination, unchanged full totals, correct legacy source/Quick Expense action targeting,
  optional cancelled history, no page errors and no page horizontal overflow. Native
  Desk baseline styles were supplied in the fixture; API responses were mocked. Actual
  RU/TG status/source/paging translations were used; full form localization review
  remains in Phases 4–5.
- The earlier cancellation/input fixture was rerun: 8 cashier/manager RU/TG desktop/mobile
  cases plus failed-cancellation retry and missing-source/category setup checks passed.
  These are fixtures, not authenticated site tests. Temporary fixture HTML was removed.
- Python AST, JavaScript syntax, changed DocType JSON and app diff checks passed.

Reproduction commands (bench root unless noted):

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
# In apps/posawesome/frontend:
yarn test:unit tests/offlineCashMovements.spec.ts tests/pendingExpenseRequests.spec.ts tests/writeQueueTransactions.spec.ts tests/usePosShift.spec.ts tests/closingLoyaltySummary.spec.ts tests/closingShift.spec.ts tests/cashMovement.spec.ts
yarn build
# In apps/posawesome:
yarn verify:build
yarn test:build-verify
yarn electron:smoke
```

## Release boundary

No site migration, setup/role assignment, live business/GL write, real queue clearing,
commit, push or deployment was performed. Both sites retain `allow_tests = false`.
Phase 2 schema/setup and Phase 3 read-permission synchronization are required before use.
Native MariaDB permission queries, real document/GL reversal, two-connection concurrent
retry/close checks and old-cache migration rehearsal remain Phase 9 release gates on a
migrated disposable site. The SQL fixture compiler is mocked; this does not prove those
native behaviors. No shortage is resolved by this phase; Phase 6/7 still deliver review
records, allocation and approved resolution.

Suggested per-app commit: `feat(expenses): unify paid history and preserve legacy retries`.
Stop here pending Phase 4 authorization.
