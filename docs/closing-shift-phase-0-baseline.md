# Shift and expense roadmap: Phase 0 baseline

Completed 2026-11-05. Scope: preserve and verify the existing local shift-closing
implementation, trace its integrations, and inventory available configuration without
changing business records. Phase 1 policy/design work has not started.

## Source baseline and preservation

Both app working trees were clean at the start of this phase. The formerly uncommitted
closing implementation is already present in POS Awesome commit
`2721803395b8013dbb1c735e1f7b4d5c8c24aff6`
(`feat(closing): reconcile payment discrepancies, cash movements, and safe transfers in Closing Shift`).
The agent did not make that commit during this phase.

ERPNext baseline: `a25993f6b47d36d6009d6391294f164641fcbac9`.

Customized origins were verified:

- POS Awesome: `https://github.com/idibek-alimov/posawesome.git`.
- ERPNext: `https://github.com/idibek-alimov/erpnext.git`.

The 22-file closing commit matches the file inventory in
[closing-shift-summary.md](closing-shift-summary.md): closing components/composables,
shared summary/preparation/submission services, fiscal transfer/timeout handling,
Russian/Tajik translations, regression tests and implementation documentation.
No existing application source was reset or changed during Phase 0.

## Calculation and integration trace

| Contract | Existing behavior checked |
| --- | --- |
| Scope | Stored opening-shift owner/company/profile supply the authoritative context; submission checks profile/company/user and source transaction membership. |
| Expected amount | Shared `build_closing_overview` serves preparation and submission; expected = opening + net received - taken out. |
| Actual and difference | Actual must be finite; zero is valid; difference = actual - expected. A shortage is recorded but does not yet have a resolution workflow. |
| Opening-child regression | `summary.reconciliation_rows` uses `.get()` for real Frappe child Documents and dictionaries. Existing fixtures use the actual `POSOpeningShiftDetail` controller. |
| Receipts/returns | Company-currency totals, invoice change and customer refunds are counted once; Payment Entry uses the receiving/paying account side. |
| Outflows | Submitted shift-linked Quick Expenses and POS Cash Movements use their funding account; unrelated-account withdrawals do not reduce this register. Noncustomer payments are classified as taken out. |
| Submission | Server recalculates expectations and rejects stale transaction membership/totals. Blank/nonfinite counts fail; original opening and sales totals come from sources. |
| Offline/failure | Pending invoice/payment/cash-movement queues block closing. Failed close preserves shift/cart/counts; success gates cleanup. |
| Optional actions | Frontend submits ERP closing before fiscal Z printing and safe transfer; their failures are reported separately. |
| Safe transfer | Counted cash is used, including zero; the source wallet must match the configured cash account. Unsupported foreign-currency transfers are declined. |
| Transfer boundary | ERPNext Money Hub creates a native Internal Transfer Payment Entry and explicitly commits. Retry/duplicate-transfer protection remains a later integration concern. |

Inspected source includes `closing_processing/{creation,data,overview,summary}.py`,
`pos_closing_shift.py`, `api/fiscal.py`, `usePosShift.ts`, closing UI/composables and
ERPNext `accounts/page/money_hub/money_hub.py`.

Existing regression coverage exercises opening float, returns/change, customer receipts,
currency conversion, cash/card expenses, other-till outflows, salesperson allocation,
stale submission, authorization, lower actual counts and safe-transfer source selection.
The real-child submission regression has expected 500 / actual 450 and verifies that
submission recalculation succeeds without the reported subscriptability TypeError.
Its persistence/submit calls are mocked; it is not a live database closing.

## Read-only site and configuration inventory

Direct MariaDB connections used `START TRANSACTION READ ONLY`, explicit `SELECT`s,
rollback and connection close. No Expense Desk/Money Hub initialization endpoint was
called: those endpoints currently have setup side effects. Credentials were read only
inside the connection script and were neither printed nor saved in this report.

### Available sites

| Site | Observation | Verification limit |
| --- | --- | --- |
| `qpr-test.localhost` | Configured database connection unavailable (MariaDB error 2003); `allow_tests` not enabled. | No controlled live closing could be exercised there. |
| `radolfa.localhost` | Read-only database access succeeded; `allow_tests` not enabled. | Treated as business data, not a disposable test fixture; no transactions submitted or amended. |

The POS frontend has no ignored `.env.local` smoke configuration. The smoke README
was read; no authenticated browser smoke or real-device printer test was run.
No service was started/restarted and no test-site configuration was changed.

### Accessible site's record counts

| Record | Count |
| --- | ---: |
| POS Profile | 2 |
| POS Opening Shift | 15 (13 closed, 2 open; all submitted) |
| POS Closing Shift | 13 |
| POS Cash Movement | 0 |
| Quick Expense | 7 (all submitted) |
| Quick Expense Category | 9 |
| Money Wallet | 6 |
| Mode of Payment Account mapping | 5 |

Five of seven submitted Quick Expenses have no opening-shift link. Two have a shift
link, including one linked to a closed shift. These counts identify attribution work;
they do not establish which unlinked expenses should belong to a register or shift.
No historical links were inferred or changed.

### Profile, wallet and schema findings

- Both enabled profiles (`POS Main` and `Loyalty Program POS`) use TJS, cash mode `Cash`,
  and payment methods Cash, Eskata, Alif and Dushanbe city.
- Both profiles resolve those methods to the same accounts. Register/profile separation
  therefore cannot be inferred from the funding account alone.
- Wallets: Cash (Till), Alif/Eskata/Dushanbe city (Mobile Wallet), one Bank and one Safe.
  All six are enabled; the till/mobile wallets accept POS receipts, while Safe/Bank do not.
  All wallet `pos_profile` links are empty. This establishes current configuration, not
  cashier authorization to spend from the mobile wallets.
- Cash resolves to `Cash - R`; Wire Transfer also resolves to that account. Shared aliases
  must not generate duplicate account adjustments.
- Both profiles have Cash Movement, POS Expense and Cash Deposit flags turned off.
  The separate POS Expenses screen uses the shared Quick Expense endpoint; its actual
  feature/permission behavior must be deliberately reconciled in later phases.
- The database contains `posa_enable_cash_movement`, `posa_allow_pos_expense`,
  `posa_allow_cash_deposit` and `posa_cash_mode_of_payment` on POS Profile. It currently
  lacks the `posa_allow_source_account_override` and `posa_default_source_account`
  columns referenced by the newer source-configuration code. Do not assume source
  override configuration is installed; inspect/migrate it explicitly in the planned phase.
- Quick Expense contains funding source/method, profile/shift/origin and generated
  Journal Entry/Payment Entry/Purchase Invoice link fields.

These are one read-only snapshot, not a migration or statement/account reconciliation.
No account balances, cashier identities, receipt contents or credentials are included.

## Verification run in this phase

From the POS Awesome repository, with the bench Python:

```bash
/home/idibek/Desktop/Frapper/frappe-bench/env/bin/python -m unittest \
  posawesome.posawesome.doctype.pos_closing_shift.test_pos_closing_shift \
  posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_cash_movement_integration \
  posawesome.posawesome.doctype.pos_closing_shift.closing_processing.test_summary
/home/idibek/Desktop/Frapper/frappe-bench/env/bin/python \
  posawesome/posawesome/doctype/pos_closing_shift/closing_processing/test_overview_loyalty.py
```

Result: **35 + 2 backend tests passed**. These use isolated/mocked database integrations.

From `frontend/`:

```bash
yarn test:unit tests/usePosShift.spec.ts tests/closingLoyaltySummary.spec.ts tests/closingShift.spec.ts
yarn lint
yarn build
```

- **11 frontend tests passed**.
- Full frontend lint passed with existing unused-variable warnings outside closing files.
- Scoped ESLint with `--max-warnings 0` passed on the closing components/composables,
  fiscal-printer composable, shared shift composable and both changed test files.
- Build passed Vue/TypeScript checks, Vite bundling and the Chrome 109 CSS audit.
  Existing large-chunk and outdated Browserslist-data warnings remain. No dependency
  upgrade was performed.

From the app repository:

```bash
yarn verify:build
yarn test:build-verify
yarn electron:smoke
git -c core.whitespace=cr-at-eol diff --check
```

Build verification passed; **2 artifact-verifier tests passed**; Electron package
configuration smoke passed. The local build regenerated ignored build artifacts and
the artifact verifier wrote ignored checksums. These are local verification outputs,
not a deployment or packaged Electron run. ERPNext whitespace checks also passed.

## Completion, changed files and outstanding checks

Phase 0 is complete under its documented exit criteria: baseline accounted for,
reproducible local checks passed, integration/configuration inventory recorded and
the controlled-site limitation identified.

Files changed in this phase:

- `docs/closing-shift-phase-0-baseline.md`: durable baseline, inventory and check evidence.
- Bench-root `POS_SHIFT_DISCREPANCY_PLAN.md`: mark Phase 0 completed, update current
  authorization/status and link this report.

No runtime application source, accounting document or site configuration changed.
No commit, push, deployment, migration, cache refresh or financial operation was performed.
Item search, pricing, UOM, stock, invoice payloads and ordinary receipts were not changed.

Controlled authenticated closing, real GL posting/reversal, fund transfer and physical
fiscal/QZ printing remain release checks. They were not performed in Phase 0; a passing
isolated suite does not establish production readiness. The proposed shortage-resolution
workflow remains unimplemented and no accounting policy was silently chosen.

Next phase, only when the owner requests it: Phase 1 workflow/ownership contracts and
material policy decisions. Carry forward the shared accounts, five unlinked expenses,
disabled Cash Movement flags and missing source-setting fields as concrete design inputs.

Suggested commit subject, if later authorized:
`docs(pos): record shift and expense phase zero baseline`
