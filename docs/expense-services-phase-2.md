# Phase 2 completion — shared expense foundation

Local implementation, 2026-11-05. Scope and setup:
[ERPNext Phase 2 report](../../erpnext/docs/expense-services-phase-2.md).
Owner policies remain D1–D5 in the
[canonical expense contract](../../erpnext/docs/expense-workflow-contract.md).

## Changed areas and linked contracts

- ERPNext `accounts/expense_services/`: one funding/category/context policy, transactional
  record/cancel/status commands, scoped reads and meaningful permission/retry tests.
- Quick Expense controller/schema/native form: native JE posting, recipient semantics,
  cancellation/amendment/immutable-history guards, request metadata and receipt links.
- Money Wallet/category schemas: explicit register/office spending permission and
  company-specific expense/cost-center mappings; two small native child DocTypes.
- Expense Desk Python/JS: secured shared adapters, read-only initialization, separate
  refresh after posting, reason/version on cancellation. Money Hub's obsolete expense
  account-initialization import/call was removed; its broader behavior was preserved.
- POS `api/expense_context.py` and hooks: trusted stored shift/profile validation,
  historical manager correction context, configured limits and guarded legacy writes.
- Cash Movement: same public create/queue payloads, scoped duplicate-request checks,
  manager-only expense reversal with reason and protected posted expense history.
  Deposit's direct-write guard uses its existing Cash-only service rules.
- POS expense screen/client adapters: no first-active-register fallback, no inferred
  employee-party payment, shared request IDs, manager cancellation/reason, useful errors,
  hidden unavailable balances and preservation of an authoritative zero cash summary.
- Closing submission: opening-shift lock shared with newly posting expenses. Full native
  Desk closing accounting/review integration remains Phase 6.
- POS migration patch repairs missing legacy source fields without changing profile
  payments, spending flags, amounts or existing configuration values. Not run on a site.
- Russian/Tajik additions cover the main new expense actions and configuration/retry errors.

Checkout pricing, item search/cart, UOM, stock, invoice payloads, customer price lists,
fiscal/QZ printing, invoice/offline database formats and actual-to-safe transfer behavior
were traced and retained. New funding permissions do not change receiving methods or
copy methods across profiles. Expenses still reduce the actual source account once in
existing closing summaries. No shift discrepancy adjustment/review is claimed implemented.

## Verification

Final command results are recorded below after local checks. Browser results are isolated
fixtures, not an authenticated site. The fixture rendered the actual Vue component with
mocked reads/commands: Russian/Tajik cancellation labels, 1440px and 390px, cashier and
manager. It checked hidden cashier cancellation, manager reason gating and reason/version/
request ID payloads. No page errors or horizontal page overflow occurred in eight cases.
No existing browser profile, cart, queue or business record was used.

Native Quick Expense integration tests were rewritten to use `_Test Company`/Fiscal Year
fixtures, create an explicit test source/category, verify native JE/GL/retry/cancellation,
and reject unsupported party payments. They require a migrated disposable `allow_tests`
site and were not run against business data. Database-free tests isolate native posting
and transaction primitives; their concurrency fixture is not a two-connection DB rehearsal.

No live close, transfer, expense posting/reversal, schema migration, service restart,
deployment, commit or push was performed. Phase 3 remains awaiting owner authorization.

Suggested future commit subject: `feat(expenses): secure shared funding and posting services`

### Final local results

- 97 database-free backend regressions passed across shared policy/commands/reads, POS
  context, legacy movement guards/repair and the existing closing suites; 2 standalone
  closing-loyalty regressions passed (99 backend checks total).
- 15 scoped frontend unit tests passed (closing, shift and legacy Cash Movement).
- 8 browser-helper Node tests passed, including lost responses, reloads, changed intent,
  confirmed rollback and a cancelled original expense never becoming a new success.
- Eight actual-component browser cases passed: RU/TG reason label, desktop 1440/mobile
  390, cashier/manager; no page errors or page overflow. Additional checks passed for
  failed-cancellation input/ID preservation and disabled submission with missing setup.
  Existing translations were used for the new Tajik reason label; this is not a claim
  that the later full Expense UI translation/redesign phase is complete.
- Scoped ESLint with zero warnings passed. `yarn build` passed Vue type checking,
  production bundling and the Chrome 109 CSS audit. Existing bundle-size/browser-data
  advisories remain. Build asset verification, 2 artifact tests and Electron configuration
  smoke passed; no packaged Electron runtime or physical printing was exercised.
- Changed Python parsed, JavaScript syntax and DocType JSON/field-order checks passed.
  Both repositories passed whitespace checks with their existing CSV CRLF convention.
- Both configured sites still have `allow_tests = false`. The native accounting test
  class remains deferred to an approved migrated disposable site. No test setting was changed.

Representative commands from the bench root:

```sh
env/bin/python -m unittest \
  erpnext.accounts.expense_services.test_expense_policy \
  erpnext.accounts.expense_services.test_expense_commands \
  erpnext.accounts.expense_services.test_expense_queries \
  posawesome.posawesome.api.test_expense_context \
  posawesome.posawesome.api.cash_movement.test_cash_movement \
  posawesome.patches.test_repair_expense_source_settings \
  posawesome.posawesome.doctype.pos_closing_shift.test_pos_closing_shift \
  posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_cash_movement_integration \
  posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_summary -q
node --test apps/erpnext/erpnext/accounts/expense_services/test_expense_requests.cjs
```

Frontend: `yarn test:unit tests/usePosShift.spec.ts tests/closingLoyaltySummary.spec.ts
 tests/closingShift.spec.ts tests/cashMovement.spec.ts`, scoped ESLint, and `yarn build`.
App root: `yarn verify:build`, `yarn test:build-verify`, `yarn electron:smoke`.
Browser fixtures used a temporary Vite page and fresh Chromium contexts, with cleanup;
they did not connect to either business site. Ruff was unavailable locally and its tool
fetch failed; no application dependency was added.
