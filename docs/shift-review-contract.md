# POS shift review contract

Phase 1 contract, 2026-11-05; implementation status updated 2026-11-06. Phase 6 backend
and the Phase 7 manager page and Phase 8 connected journey are implemented locally. See the [journey report](shift-review-phase-8.md). See the [manager UI report](shift-review-phase-7.md) and
[implementation/setup report](shift-review-phase-6.md) for supported actions and release gates.
Phase 9 local native verification and release handoff are complete; see the
[evidence report](shift-review-phase-9.md) and [operator runbook](shift-review-release.md).
The intended business-site setup/upgrade, installed-app handoffs and hardware still need
their own release checks and authorization.
The owner subsequently authorized activation of the disposable local development site;
`radolfa.localhost:8000` is now migrated/configured. See the
[development setup report](shift-review-development-setup.md); this does not describe a
production rollout or a migration of the separate Docker site.
Canonical ordinary expense rules and the approved action matrix live
in [the shared ERPNext expense contract](../../erpnext/docs/expense-workflow-contract.md).
Use that contract instead of maintaining a second list of role/source policies here.

## User-approved journey

The owner confirmed D1–D5 in the shared contract: close with Pending review, restricted
POS spending sources and controlled Desk corrections, spendable Alif/DC/Eskata wallets,
owner/Accounts Manager approval for true losses/surpluses, and manager-only expense
cancellation/correction. Local services enforce these rules; site migration/setup and
controlled native verification are required before rollout.

1. Cashier records actual paid expenses against the correct permitted shift source.
2. Cashier counts each payment method and sees the signed difference, subject to existing
   blind-count settings. A nonzero difference requires an explanation under the new flow.
3. Closing succeeds with its immutable count snapshot; a difference creates Pending review.
4. Optional safe transfer uses counted cash; fiscal printing and transfer have separate
   outcomes and never themselves resolve a shortage.
5. Manager opens one native Desk Shift Review screen, linked from Expense Desk, Money Hub
   where permitted and closing records. Default list covers all unresolved dates.
6. Manager investigates source payments, expenses/transfers and evidence, then links a
   valid missing source, records a missing expense or performs an authorized correction.
7. A genuine loss/surplus requires owner/Accounts Manager approval and native posting.
8. Resolution is recognized only for successfully posted/validated corrections. Keep
   original counts, partial unresolved amounts, reviewer history and source links.

POS Awesome owns the shift/review records, permissions and calculations even though
the manager screen uses Frappe Desk. ERPNext owns ordinary expense/accounting services.
Do not move this feature to ERPNext merely because the screen is opened from Desk.

## Native reuse and why a review record is needed

Investigated local native `POS Closing Entry` and `POS Closing Entry Detail`, POS Awesome
`POS Closing Shift`, POS Profile write-off fields, invoice merge overrides, Journal Entry,
Payment Entry and HRMS claim/advance controllers/hooks.

- Native closing reconciles payment amounts and consolidates invoices. No per-account
  manager investigation/approval/partial-resolution lifecycle was found there.
- POS Profile `write_off_account`, `write_off_cost_center` and `write_off_limit` relate
  to invoice/payment write-offs. They do not provide shift discrepancy approval or prove
  permission to write off a closing shortage. Do not repurpose them silently.
- The customized invoice merge code normalizes return payment totals. It is not a shift
  cash-loss mechanism and must not be used to conceal a shortage in sales/returns.
- Native Journal Entry/Payment Entry supply financial posting/cancellation and their
  existing validations. HRMS supplies claim/advance/reimbursement workflows. Reuse them;
  no bespoke GL editing or duplicate payable system is needed.

Design decision: add POS-owned auditable review/allocation records rather than another
financial ledger or a boolean resolved flag on each closing row. Exact DocType names and
schema are finalized in Phase 6; preserve one review identity per submitted closing,
per-account/currency discrepancy identity and independently auditable resolution actions.

## Original snapshot, signs and account scope

The closing snapshot retains stored opening scope, source IDs included in expectations,
account/method mappings, currencies/rates and expected/actual/difference at close.
Later corrections do not overwrite those figures. Snapshot source provenance is necessary
to determine whether an allegedly missing expense was already counted.

`expected = opening + net_received - taken_out`

`original_difference = actual - expected`

Negative means shortage; positive means surplus. The POS Vue dialog and Python backend
use this convention. Existing native POS Awesome Desk JavaScript currently uses the
opposite sign when a closing amount changes and calculates expectations separately.
Phase 6 now aligns that form and alternate document entry/submission paths with the
shared server calculation. The original closing snapshot remains immutable.

For each account/currency, resolution allocations have the same signed convention as
the discrepancy they explain:

`remaining = original_difference - sum(valid_signed_allocations)`

Missing expense of 50 explaining a shortage has allocation -50; a surplus adjustment of 50 has
allocation +50. UI may display shortage magnitude of 50 with an explicit Shortage label.
Reject over-allocation, invalid signs and duplicate use of a source leg; validate currency
precision/rates explicitly. Do not combine unrelated currencies or net different accounts.

One ledger account may serve several modes/profiles. Preserve mode detail but post
account-level corrections only once. Opposite differences may indicate payment attribution
errors requiring an audited native correction, not an automatic net-zero dismissal.
Explicitly retain which shift incurred spending; shared account and posting date do not
prove unique shift membership. Full wallet/bank balance is not a shift's expected amount.

## Resolution commands and accounting boundaries

| Command | Required checks and result |
| --- | --- |
| Create review at close | Atomic with successful close under D1; unique closing identity, authoritative source snapshot, reason and account rows. No loss posting from closing itself. |
| Read/assign/investigate | Company/profile/record capability; assigned scope; cashier sees only permitted explanation/status, no unrelated employee/global financial data. |
| Link existing transaction | Submitted valid document, correct cash-flow leg/company/account/currency/shift evidence; missing from original expected snapshot and not already allocated. Link only, no repeated financial posting. |
| Record missing expense | Manager correction context, prefilled approved source/shift, stable request ID and remaining-version check; call shared expense service, then allocate the successfully submitted effect once. |
| Correct count | Audited original/new count, reason/evidence and actor; demonstrate actual count explanation. Do not silently rewrite closing or post a loss to compensate for a data-entry error. |
| Correct payment attribution | Use the permitted native invoice/accounting correction route, respecting submitted/consolidated invoice protections. Requesting correction alone is not resolution. |
| Approve genuine loss/surplus | D4 capability, explicit reason/account configuration/dimensions/period/currency and remaining amount; submit native JE through guarded posting. |
| Recoverable claim | Specialized native/accountant-approved treatment with established obligation; no automatic employee/payroll link. Track book correction separately from later repayment status. |
| Cancel/amend/reverse resolution | Appropriate manager/accounting capability and native rules; invalidate/reverse allocations consistently, recompute remaining and retain all history. |

An explanation or uploaded receipt alone does not resolve money. The source must be a
valid submitted correction or validated count revision covering the amount. A source
already present in expected totals cannot be attached to resolve that difference again.

Serialize approval/posting/allocation with locks/unique operation keys and version checks.
Lost responses return authoritative operation status. Financial posting and allocation
must share a transaction where possible; no commit from expense setup/refresh helpers.
Native source lifecycle hooks must keep reviews correct even when cancellation or
amendment happens outside the review page. Never delete the record of the old resolution.

Money Hub M2a `transfer_money()` now uses native Payment Entry permissions and an
immutable request receipt in the same transaction, without an explicit commit or
balance refresh. Its Desk caller persists a stable request ID and can recover the
submitted/cancelled native source. See the
[M2a contract and checks](../../erpnext/docs/simplification/money-hub-m2a.md).
It remains a separate command from closing/expense submission; do not present separate
HTTP requests as one atomic transaction. POS counted-cash transfers retain their own
closing provenance and idempotency contract; do not route them through the generic hub.
In particular, do not reverse a successful closing or repeat a successful transfer when
printing or a subsequent action fails. Cashier transfer permission follows native money
movement policy; approving a shortage does not grant transfer rights.

## Worked manager workflows

All cash examples assume an isolated till book balance of 1,000, actual 950, transfer of 950
and no other activity; source balances in a shared real account may differ.

### Forgotten taxi payment of 50

1. Original closing shows expected 1,000, actual 950, difference -50; Pending review.
2. Cashier can close and transfer actual 950 to Safe if authorized. Till books retain 50
   until explanation/accounting is resolved; this is not a new payout.
3. Manager opens Shift Review, verifies the taxi evidence and checks no such expense was
   already in the original calculation or posted separately.
4. If unrecorded, Record missing expense creates one expense of 50 against the original till
   through the authorized closed-shift context. If already posted but omitted from the
   snapshot, link that valid existing effect instead of posting again.
5. Allocate -50. Original difference stays -50; remaining 0; Resolved with source links.
   No extra cash-shortage expense is created. If only 20 is explained, remaining is -30.

### Confirmed loss of 50

1. Same original close and optional actual 950 transfer; investigate first.
2. Manager documents conclusion; owner/Accounts Manager reviews and approves the loss.
3. With explicit company configuration, native JE debits shortage expense of 50 and credits
   the correct till by 50. This recognizes missing cash; it does not physically pay another 50.
4. Allocate -50 only after successful submission. Under example assumptions, till book
   balance 0 matches empty drawer; Safe received 950; original evidence remains.
5. Cancelled/reversed posting invalidates its allocation and restores the unresolved
   amount/status according to native cancellation/period rules and audit history.

### Delayed or net card settlement

1. Record the difference and keep it Pending review. Do not classify it as physical
   cash loss simply because a bank statement has less than the shift receipts.
2. Manager/accountant checks receipts, settlement records, shared account activity,
   fees, reversals and native bank reconciliation.
3. Link an actual valid correction/settlement explanation when it covers the discrepancy;
   awaiting a settlement alone does not mean resolved. Any fee uses its real configured
   accounting route, and an existing fee/bill is not expensed twice.
4. Unsupported bank/currency or recovery cases remain pending with a native handoff.

### Surplus and next shift

A surplus remains separate from shortages; confirm cause and D4 approval before a native
adjustment. Configure its proper company account before offering that action. Do not add
surplus to sales to make counts match. An old pending shortage remains tied to its original
shift; a new shift uses the actual legitimate opening float, with old unresolved/book
differences disclosed separately. Do not generate a second 50 loss from the same origin.

## Configuration deferred to the dependent phases

These items are deliberately setup requirements, not unanswered user-policy questions:

- Phase 2: exact company category accounts, cost centers/dimensions, allowed profile/source
  rows, role-capability mapping and installed schema migration. No arbitrary amount limit.
- Phase 6: explicit shortage/surplus accounts, currency/precision and approval posting
  configuration before actions are enabled. No clearing-account policy is invented.
- Native handoff: recovery/claims, complex invoice amendments or unsupported bank/currency
  treatment remain native/accountant workflows; no salary deduction integration in this scope.
- Phase 9: read-only historical discrepancy discovery and explicit audited linking.
  Older closes lack new snapshot provenance; do not automatically resolve/post historical losses.

Absent configuration leaves the dependent operation unavailable with a clear explanation.
It does not prevent ordinary investigation or authorize setup writes when opening a page.

## Phase 1 evidence and completion

Source review covered controllers, DocType permissions, role bundles and active hooks in
ERPNext/POS Awesome/HRMS; no hidden shift-resolution lifecycle was found in those paths.
Native invoice write-off and employee claim workflows are distinct and remain reusable.
The five owner decisions are reflected in the canonical matrix; the worked examples
above define acceptance behavior, not a live-site financial test.

Phase 1 changed documentation only. Existing Phase 0 report and its source baseline are
preserved. No application code, DocTypes, site roles, configuration or accounting records
changed; no migration, build, financial posting, commit, push or deployment was performed.
Checks: cross-app paths, decision/matrix consistency, example arithmetic and whitespace.
Runtime builds/tests are not rerun for these document-only changes.

Next phase is Phase 2 shared expense configuration/validation/posting, only after the
owner requests it. Suggested future documentation commit subject:
`docs(pos): define approved expense and shift review contracts`
