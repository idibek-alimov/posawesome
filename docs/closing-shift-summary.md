# Shift closing summary

The POS closing dialog shows money to reconcile, a short sales summary, and sales by
salesperson. Currency, credit, loyalty, change and withdrawal detail remains under
**View details**. On narrow screens each payment method becomes a compact card.
Russian and Tajik translations are included.

## Amounts and scope

One reconciliation row represents a configured or used payment method and identifies
its company accounting account. All closing amounts are in company currency.
These are shift totals, including the shift's opening balances, rather than current
company-wide bank or wallet balances.

- Expected = opening + net received − taken out.
- Difference = actual − expected. A negative difference means a shortage.
- Net received includes invoice payments, customer receipts/refunds, and change,
  counted once. Multi-currency Payment Entries use the receiving/paying till side.
- Taken out includes submitted, shift-linked POS Cash Movements, Quick Expenses and
  non-customer payments. The account actually charged takes priority over an expense's
  payment-method label. Other-register withdrawals remain in details without reducing
  this register's expected amount. Money added through a shift-linked Receive Payment
  Entry is included in net received.
- Cancelled documents are excluded. Printed drafts retain the existing preparation
  behavior; skipped return drafts are identified visibly.
- Sales and salesperson totals use submitted invoice grand totals, including returns,
  in company currency. Sales Team percentages split shared sales; missing allocations
  appear as Unassigned. Overallocated teams are normalized to prevent duplicate revenue.
  No purchase costs, margins, payroll or commission amounts are exposed.

Both the dialog preparation and saved closing record use `build_closing_overview`.
Submitting recalculates expected amounts on the server, checks transaction membership
and the stored opening shift's owner/company/profile, and rejects stale totals.
Refreshing loads the full closing draft and retains the cashier's entered counts.
Opening amounts and final sales totals are sourced from stored documents.

POS Profile controls payment methods, cash mode, invoice type and hidden expected
amounts. Blind counting hides expected amounts, receipts, withdrawals, differences
and expandable details. No IndexedDB schema or POS Profile fields were added.

## Shortages and actual counts

A lower actual count is allowed when closing; it saves a negative difference on the
POS Closing Shift reconciliation row. For example, expected 1,000 and actual 950 saves
−50. The discrepancy itself does not create a Journal Entry, alter the account balance,
write off missing money or deduct an employee's salary. If automatic safe transfer is
selected, it transfers the counted cash (950 in this example). The shortage remains
unreconciled in the books; card/bank differences are likewise recorded for review.
The payment-method rows cover this shift's opening amounts and linked transactions.

Opening balance rows use their shared `.get()` interface, supporting both dictionaries
from closing preparation and Frappe `POSOpeningShiftDetail` documents from submission.
The backend regression fixtures instantiate the real child controller with isolated
metadata. They reproduce the former TypeError and exercise submission recalculation
with those child documents and a lower actual cash count.

## Closing and optional actions

Pending offline invoices, payments or cash movements block closing. Totals must be
refreshed after those records sync. A failed request shows an error, and the dialog
stays open with entered amounts. Repeated submission is guarded. Failed closing
preserves the active shift and cart.

Fiscal Z printing and safe transfer follow successful ERP submission. Their failures
are reported separately from the shift's result. Printing has a timeout. Transfer
previews use the actual count, including a legitimate zero; no expected-amount fallback
is used. The source wallet must match the configured cash account. Cross-currency
automatic transfers are left to Money Hub, whose existing permissions still apply.

## Files changed

| File (relative to this app) | Purpose |
| --- | --- |
| `frontend/src/posapp/components/pos/shell/ClosingDialog.vue` | Compact layout, sales/salesperson summaries, disclosure, loading/retry, queue state and action previews. |
| `frontend/src/posapp/components/pos/closing/ClosingHeader.vue` | Small shift header, context and accessible dialog title. |
| `frontend/src/posapp/components/pos/closing/PaymentReconciliation.vue` | Responsive reconciliation, blank counts, consistent signed differences and account labels. |
| `frontend/src/posapp/composables/pos/closing/closingAmounts.ts` | Shared actual-count parsing and difference convention. |
| `frontend/src/posapp/composables/pos/closing/useClosingSummary.ts` | Expose salesperson and movement summaries alongside existing detail formatters. |
| `frontend/src/posapp/composables/pos/closing/useClosingShift.ts` | Complete refreshes, preserved counts, explicit failures, stale-response and submission guards. |
| `frontend/src/posapp/composables/pos/shared/usePosShift.ts` | Queue checks, shared preparation snapshot, success/failure events and ordered closing actions. |
| `frontend/src/posapp/composables/pos/payments/useFiscalPrinter.ts` | Bound Z-report request duration. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/summary.py` | Shared receipt interpretation, salesperson allocation, withdrawal attribution and reconciliation rows. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/overview.py` | Authoritative shift snapshot; remove duplicate refund deduction; align source-linked payment details. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/creation.py` | Reuse the snapshot for preparation/submission and validate current source totals. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/data.py` | Stored-shift authorization and till-side Payment Entry fields. |
| `posawesome/posawesome/api/fiscal.py` | Exact counted-cash transfer, configured source wallet, currency checks and localized result. |
| `posawesome/translations/ru.csv`, `posawesome/translations/tg.csv` | Closing labels, explanations and error messages. |
| `frontend/tests/closingShift.spec.ts`, `frontend/tests/usePosShift.spec.ts` | Counts, failures, refreshed documents, queued records, stale requests and cart preservation. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_summary.py` | Financial reconciliation, permissions, allocations, stale submission and safe-transfer regression coverage. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_cash_movement_integration.py` | Updated shared-calculation integration fixtures. |
| `posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_overview_loyalty.py` | Include stored-shift loader in the standalone fixture. |
| `posawesome/posawesome/doctype/pos_closing_shift/test_pos_closing_shift.py` | Preserve existing permission/loyalty/draft coverage with isolated request wrappers. |
| `docs/closing-shift-summary.md` | Behavior, scope and verification record. |

## Linked features reviewed

The impact trace covers POS Profile company/currency/payment methods and invoice type,
opening balances, returns and change, Payment Entries, Quick Expenses, POS Cash Movements,
Money Hub transfer accounts, offline financial queues, native closing records and their
source-linked payment detail, and fiscal Z printing. Item search, cart rows, price lists,
pricing rules, discounts, UOM conversion, stock checks, Sales Invoice creation payloads,
and normal sale-receipt/QZ printing retain their existing paths. This is an impact review;
those checkout workflows were not exercised against a live site for this change.

## Verification

- 35 isolated backend tests passed across `test_pos_closing_shift`,
  `test_cash_movement_integration` and `test_summary` using the bench Python and
  `python -m unittest`.
- 2 standalone loyalty/customer-credit overview tests passed.
- `yarn test:unit tests/usePosShift.spec.ts tests/closingLoyaltySummary.spec.ts tests/closingShift.spec.ts`:
  11 frontend tests passed.
- `yarn lint`: zero errors; 52 existing warnings outside changed closing files.
  Scoped ESLint on changed frontend code and tests passed without warnings.
- `yarn build`: type check, production bundle and Chrome 109 CSS audit passed.
- `yarn verify:build`, `yarn test:build-verify`, `yarn electron:smoke` passed.
  Electron verification checks package configuration; it is not a packaged application run.
- A local browser fixture rendered the actual Vue/Vuetify dialog at 1440 px in
  English, Russian and Tajik, and at 390 px in Russian and Tajik. It checked
  overflow, details/source links, blind counting, loading errors, queued records,
  retained counts, submission completion and keyboard cancellation guards.
  Axe found no accessibility violations in the English dialog fixture.

These were mocked or isolated checks. No real shift was closed, invoice submitted,
queue cleared, funds transferred, fiscal printer contacted or QZ/browser receipt
printed during verification. No schema migration is required. Deployment, service
reloads and site translation-cache refreshes were not performed.

## Remaining limits

Only documents linked to the opening shift are included. Unlinked Money Hub or
ledger operations cannot be inferred as belonging to this shift. If payment methods
share an account, a withdrawal uses its matching method or the first configured
method for that account; this screen preserves native reconciliation by payment method.
Safe transfer still depends on existing Money Hub wallet configuration and permissions.
An authenticated test-site closing and physical printer verification remain necessary
before production rollout.

Suggested commit message: `feat(pos): simplify shift closing and reconcile shared totals`
