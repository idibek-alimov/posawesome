# Manager Shift Review — Phase 7

Implemented locally 2026-11-06 under the owner's authorization to start the next phase in
`POS_SHIFT_DISCREPANCY_PLAN.md`. Both customized app working trees already contained
Phases 2–6; those changes were preserved. No migration, configuration grants, business
posting, shift closing, money movement, cache refresh, commit, push or deployment occurred.

## Manager experience

POS Awesome ships `/app/shift-review`, with detail at `/app/shift-review/<review-name>`.
Only Retail Manager, Retail Owner, Accounts Manager and Administrator can use it. Both
read APIs enforce manager and native review-read access; the existing Phase 6 native
Company/Profile/Account permission queries and document scope remain authoritative.
Cashiers retain their own native review visibility without access to this management page.

The default list includes unresolved money across all dates. Selecting an individual
unresolved status or All also retains all dates; date filters apply only to Resolved or
Voided history. Summaries cover every matching record before pagination, count distinct
shifts, and keep shortage/surplus totals separate for each currency. Child queries use
bounded batches under permitted parent IDs. Registers, company, cashier, status and search
filters survive detail navigation within the cached Desk page. Rows identify each account
and its grouped payment methods; opposite differences on a shared account remain separate.

Detail retains original expected/actual/difference, valid explained amount and remaining
amount, cashier reason and reviewer. Supporting transactions, expenses/transfers and full
method counts are disclosed below the main review actions. Native source links respect
read access. Original-source changes, cancellation of original accounting vouchers and
permitted submitted JE reversals are visible without rewriting the closing snapshot.
Restricted sources show a restricted/unavailable state instead of their identity/content.

Supported actions use the existing serialized Phase 6 service:

- Link a submitted omitted source, with explicit attribution when it has no stored shift.
- Record a missing expense with the shared ERPNext form, fixed original shift/funding
  account, category, amount, optional note/recipient and private receipt. One atomic
  command posts and allocates it; the UI does not separately record another expense.
- Correct a method count or withdraw its active correction, preserving count history.
- Approve a configured Cash shortage/surplus with owner/Accounts Manager and native JE
  create/submit permissions. Opposite differences, banks, foreign currency and missing
  setup do not receive a posting button. Confirmation includes amount, date, both posting
  accounts, debit/credit direction and proposed remaining amount. A changed configured
  counterpart account invalidates confirmation on the server before any posting.
- Take the review/add a note (the acting manager becomes reviewer); request a native
  payment/refund/transfer/recovery/bank-reconciliation correction; withdraw requests;
  attach a permitted native outcome; verify a permitted native payment amendment.
  Request creation alone resolves nothing. No arbitrary reviewer assignment, payroll
  deduction, unsupported closed-invoice amendment or generic Mark resolved is added.

Financial confirmations describe the proposed source, account/category, amount and effect.
Posting failures retain dialog values and refresh the authoritative detail. After a proven
rollback, another deliberate confirmation uses refreshed version/remaining information.
A lost response retains its original actor-scoped request ID, exact args and version in
localStorage; Check result / Retry original request remain available independently of
current filters/setup. Unknown outcomes cannot be silently discarded to start a new intent.
Storage failure or unreadable evidence prevents sending a new financial request.

Expense Desk and Money Hub discover the installed POS app, synchronized review schema,
role and native read capability before showing a secondary Shift Review navigation item.
ERPNext uses optional discovery without importing POS Awesome. The submitted closing form
links permitted managers to its review. Broader post-close/expense-detail/next-shift
navigation and reconciliation remain Phase 8.

## Files changed in this phase

POS Awesome (relative to `apps/posawesome`):

- `posawesome/posawesome/page/shift_review/{__init__.py,shift_review.json,shift_review.js,shift_review.css}`:
  native Page metadata, list/detail, supported dialogs, scoped theme-aware/mobile styling,
  stale-request guards, offline/error states and persistent request recovery.
- `posawesome/posawesome/shift_review/desk.py`: read-only list/detail, currency-separated
  complete summaries, source permissions/current states and setup/native capability discovery.
- `posawesome/posawesome/shift_review/service.py`: optional expected counterpart check
  for a UI-confirmed cash adjustment; existing clients retain the existing guarded route.
- `posawesome/posawesome/shift_review/test_desk.py`, `scripts/shift_review.test.cjs`:
  projection, policy, source redaction/state, stale setup and request/retry checks.
- `posawesome/posawesome/doctype/pos_closing_shift/pos_closing_shift.js`: manager review link.
- `posawesome/translations/{ru,tg}.csv`, this report, contracts: localized wording and handoff.

ERPNext (relative to `apps/erpnext`):

- `erpnext/public/js/expense_entry.js`: extracted shared paid-expense form, including
  existing native private uploader and explicit options/receipt guards; Shift Review
  supplies a fixed shift/source and atomic review command adapter.
- `erpnext/accounts/page/expense_desk/{expense_desk.js,expense_desk.py,test_expense_desk.cjs}`:
  reuse shared form, optional authorized review discovery/navigation and existing form checks.
- `erpnext/accounts/page/money_hub/money_hub.js`: the same optional secondary navigation.
- `erpnext/translations/{ru,tg}.csv`: shared-form/review navigation translations.

Company, payment account mapping and expense grants still come from the stored POS Profile,
shift and existing shared expense policy. No cashier checkout, item search, cart, pricing,
discounts, UOM, stock, customer, invoice payload, offline queue, printing/QZ or POS frontend
bundle logic changed. The Phase 6 missing-expense/posting/cancellation and closing regression
suite covers the linked backend contracts; safe transfer remains independent of resolution.

## Verification and limits

- **206 backend tests passed**, including 18 new Desk projection/capability tests and 49
  existing shift-review tests. Controlled document/ledger checks include old
  unresolved money, separate signs/currencies, full totals before paging, bounded child
  reads, history periods, native read/posting permissions, redacted sources, cancelled
  accounting, immutable originals and changed-account confirmation.
- **31 native Desk Node tests passed**: 17 Expense Desk, 7 closing form and 7 review
  orchestration checks. They cover request
  identity, lost/malformed responses, stale scope, proven rollback and storage failure.
- Chromium fixtures: **13 Shift Review cases** across Russian/Tajik, desktop/tablet/phone and
  light/dark. Checked currencies, source links, supported/hidden actions, financial proposal,
  shared missing expense, count correction, native requests/outcomes, failed input retention,
  lost-response recovery, history filters and offline/error states. No page errors or page
  overflow. Desktop and phone captures were visually inspected. Axe reported no violations
  within the Russian desktop list/detail fixture; count correction was also keyboard exercised.
- 17 existing Expense Desk Chromium fixtures passed again after shared-form extraction:
  Russian/Tajik, 1440/834/390 widths, light/dark, source/category selection, posting, paging,
  details, private receipt controls, missing-result recovery, manager correction and errors.
- Scoped JS lint, JS/Python syntax, Page JSON and CRLF-aware diff checks passed. Translation
  CSV line endings were preserved. POS Vue/bundle code did not change in this phase, so its
  Vite/Chrome109 artifact/Electron builds were not repeated for a native Desk page change.

These use controlled fixture permissions/persistence/GL and mocked browser APIs/native
control shells with the real Desk stylesheet. They are not authenticated Desk checks,
actual private File uploads, native GL/period/dimension verification, or real MariaDB
concurrency checks. Existing Phase 9 migration, native financial and simultaneous-review
release gates remain mandatory. Existing untranslated framework/native-document wording
outside these screens is outside this phase.

Reproduce from bench root:

```bash
env/bin/python -m unittest posawesome.posawesome.shift_review.test_review \
 posawesome.posawesome.shift_review.test_desk -q
node --test apps/posawesome/scripts/shift_review.test.cjs \
 apps/posawesome/scripts/closing_shift_form.test.cjs \
 apps/erpnext/erpnext/accounts/page/expense_desk/test_expense_desk.cjs
```

The full Phase 6 backend regression command in `shift-review-phase-6.md` was also rerun
with `posawesome.posawesome.shift_review.test_desk` appended. Browser harnesses/captures
are disposable under `/tmp/shift-review-browser.cjs`, `/tmp/expense-desk-browser.cjs` and
`/tmp/shift-review-*.png`; they are fixture evidence, not production screenshots.

## Activation and next phase

Update both apps together; an authorized migration must synchronize the Phase 2–6 schema
and the standard Shift Review Page. Existing company adjustment settings, category accounts,
wallet/register grants and native roles remain required. No setup is performed on page load
and no historical review/loss is automatically created. Native actions remain disabled or
fail clearly until configuration is valid. Operator cache/restart steps follow the actual
bench deployment procedure during a separately authorized release.

Phase 8 is next: connect expense detail/post-close navigation, subsequent-shift evidence,
account-wide versus shift scope and independent transfer/printing recovery. Phase 9 then
rehearses migration and native GL/permissions/concurrency on a disposable controlled site.

Suggested future commits, only when committing is separately authorized:

- POS Awesome: `feat(pos): add manager shift review desk and guarded resolution dialogs`
- ERPNext: `refactor(accounts): share expense entry with optional shift review navigation`
