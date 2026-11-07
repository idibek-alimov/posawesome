# Summary

Phase 9 local verification and release handoff, 2026-11-06. Phases 2–8 remain intact.
The owner authorized this phase and separately approved including the fresh-install
Retail Tax Settings fix. No business-site migration/configuration, business posting,
shift closing, transfer, bank operation, printer command, service restart, commit,
push or deployment was performed. Only the existing business database's read-only
inventory was accessed; all writes used dedicated disposable databases/services.

The native rehearsal found and fixed defects that fixtures had not exposed:

- A permission recheck during native Desk/print loading tried to read snapshot fields
  after Frappe redacted them. The review permission hook now uses a separate stored
  Document for that check, retaining the redacted response. Malformed evidence still
  fails closed. Native REST, list, Desk getdoc, export denial and print paths pass.
- Fresh installation marks patches as completed without running them. POS Awesome now
  calls its idempotent source-field repair from `after_install` as well as the existing
  upgrade patch. A clean installation has the required SQL columns without enabling
  spending or changing register payment methods.
- Native Attach handling already linked private receipts to Quick Expense. Its custom
  accounting-copy helper now retains that File rather than adding an identical second
  Quick Expense attachment. The native test checks both expense and journal links.
- Standalone native Link filters lacked accessible names. Shift Review and Expense Desk
  now label their native inputs. Scoped authenticated WCAG A/AA Axe checks pass.
- Retail Tax Settings had a Link default naming a supplier not yet created during cold
  installation. Removing that default preserves the existing explicit company setup
  workflow. A second clean install succeeded without a workaround; three native tests
  verify no provisioning on read, idempotent explicit setup and configured-supplier retention.

The base Retail Cashier role lacks native POS Profile read. This is an explicit rollout
configuration requirement, not justification for giving cashiers Accounts User. The
native tests use a narrow read grant plus a profile User Permission and check D4/D5.
No business user's grants or roles were changed.

# Files Changed

POS Awesome paths, relative to this repository:

- `posawesome/hooks.py`: run the source-field repair on fresh installation.
- `posawesome/posawesome/shift_review/{policy,snapshot}.py`: authorize already-redacted
  native Documents safely and keep invalid evidence failures actionable.
- `posawesome/posawesome/page/shift_review/shift_review.js`: accessible native filter names.
- `posawesome/posawesome/shift_review/test_native_workflow.py`: 13 native integration cases
  with actual parent/child Documents, accounting controllers, GL, roles and private files.
- `scripts/audit_shift_expenses.py`: reusable operator-only legacy/schema inventory using
  a database-enforced read-only consistent transaction and rollback; no Frappe initialization.
- `scripts/rehearse_shift_concurrency.py`: two real connections, competing approval and
  repeatable-read/next-opening transfer checks; requires two explicit disposable-site flags.
- `frontend/tests/smoke/shift-review.readonly.spec.ts`, smoke README: opt-in real Desk
  language/theme/keyboard/Axe/list/detail checks with optional known company/review.
- This report, `docs/shift-review-release.md`, feature/review contracts and bench-root plan:
  installation, setup, legacy audit, compatibility, recovery, rollback and evidence handoff.

ERPNext changes are listed in `../../erpnext/docs/expense-release-phase-9.md`: receipt
deduplication, accessible scope inputs, native test support/suites and the approved tax
supplier Link-default fix. No Frappe, HRMS or Web Sync application source was changed.

# Linked Features Checked

Review/source/expense services still use stored company/profile/opening and native
User Permissions. Only owner/Accounts Manager can approve genuine cash loss/surplus;
Retail Manager is denied. A cashier can record an authorized source expense, cannot
cancel it, and cannot read another actor's private receipt or manager review actions.

Actual native GL verified tea costing 20 from the till, taxi costing 50 from the bank,
office/Safe spending, omitted expenses of 20 + 30, loss of 50, surplus of 50,
expense/loss cancellation, native JE reversal, safe transfer of 950 and original
transfer replay. Original count/snapshot remain unchanged. An included source
cannot explain a shortage twice. Zero counted cash posts nothing. The next zero float
stays zero. A foreign bank balance of 10 at stored rate 80 contributes base 800 exactly once even when
two enabled wallet aliases refer to it; the original 10 remains separately visible.

Existing fixture suites cover remaining acceptance-matrix variants: more than 150 rows,
offsetting modes, shared accounts, stale totals/version, permissions, pending/failed
posting, old offline requests and recovery. Pending requests/queues still block closing.
Native claim/supplier routes were traced from app-owned contracts and link/read checks;
full native HRMS payable/payment and physical bank/settlement operations were not executed.

Item search, cart, prices/discounts, UOM, warehouses/stock, taxes on sales, invoice payloads,
receipt totals, QZ protocol and IndexedDB schema were not changed. POS Profile still owns
register payment/account/currency/print settings. No real cart or queue was cleared.

# Commands Run

Evidence directory: `/tmp/pos-shift-phase9` (private temporary operator storage, not a
durable dependency). Native code and reusable browser/audit/concurrency checks are versioned.

| Verification | Result and evidence type |
| --- | --- |
| Scoped backend suites from Phase 8 plus `test_shift_consolidation` | 232 passed; controlled permission/document/ledger fixtures |
| Native Quick Expense + Shift Workflow + Retail Tax Settings | 3 + 13 + 3 = 19 cases; real Frappe/MariaDB documents and GL on isolated sites |
| Two real connection scenarios | One native adjustment JE; second reviewer rejected stale version. Old repeatable-read snapshot cannot transfer after the next native opening commits |
| Vue/offline suites from Phase 8 | 50 passed across 9 files |
| Desk/closing/shared request Node suites | 46 passed across 4 files |
| Existing rendered browser fixtures | 46 passed: 14 review, 17 expense, 11 Vue/Vuetify opening/recovery, 4 Money Hub |
| Authenticated native browser | 6 EN/RU/TG desktop/phone, light/dark cases; actual boot language, native controls/RPCs, company selection, expense/review details and voucher links, keyboard, overflow, scoped Axe |
| POS production build | Type checking, Vite and Chrome 109 CSS audit passed |
| Full frontend lint | Zero errors; same 52 existing warnings; new smoke/native scripts scoped lint clean |
| Build artifact and Electron configuration checks | 12 assets verified; 2 artifact tests and Electron configuration smoke passed; no physical packaged terminal |
| Native migration | Two complete runs, then simulated missing source column/queued repair + two more full runs; flags/payment rows and hashes of financial/review records unchanged |
| SQL backup/restore | Dedicated disposable DB restored; all recorded document/GL/review row hashes match; no claim of a production or private-file restore |
| Clean installation after approved fixes | Second separate site, current ERPNext/POS source, no single-initialization workaround; source columns installed and supplier default empty until setup |
| Legacy audit | Real business DB SELECT-only transaction; no controller/page/setup invoked; report summarized below |

Representative native commands, on a disposable migrated site:

```bash
bench --site <test-site> run-tests --module erpnext.accounts.doctype.quick_expense.test_quick_expense
bench --site <test-site> run-tests --module posawesome.posawesome.shift_review.test_native_workflow
bench --site <test-site> run-tests --module erpnext.accounts.doctype.retail_tax_settings.test_retail_tax_settings
```

For this session the same Frappe test runner and migration classes ran from the bench's
`env/bin/python` against an isolated scratch sites directory. Dedicated MariaDB 10.11
and Redis 7 containers had no published host ports and no workers/scheduler. The native
HTTP server bound only 127.0.0.1:18099. No production service/config was reused for writes.
The installed Chromium executable was build 1228; the Chrome 109 claim is the build CSS
audit, not runtime/hardware certification. Private screenshots/logs/backups may expire
with `/tmp`; secrets were not committed or printed.
The temporary HTTP server and both dedicated containers were stopped after verification;
their scratch data/artifacts were retained privately for inspection. Business services
were not restarted or stopped.

After the clean install, its full native migration and all 19 integration tests also
passed together. The initial fixture run on that site exposed incomplete test-company
defaults after an interrupted native Company setup; the guarded test helper now uses
the native warehouse/cost-center setup methods to finish only `_Test Company`.

# Risks / Notes

The [release runbook](shift-review-release.md) contains exact migration/setup order,
guard behavior, compatibility, legacy inventory and uncertain-result recovery/rollback.
The real read-only audit found 5 unassigned Quick Expenses (stored total 152), 8 historical
closings / 15 method differences, 4 accounts shared by 2 enabled registers, and no wallet
aliases or unassigned legacy Expense cash movements. No historical record was assigned,
rewritten, converted into new evidence or posted as a loss.

Complete the intended site's backup/restore rehearsal (including private files), account/
category/dimension/source grants, actual user role/field/User Permission checks, old-client
upgrade and real HRMS/supplier/bank/printer checks before rollout. This phase does not
authorize those business actions or claim every installed-app/localization combination.
The missing-column rehearsal is not a migration of a complete historical production clone.

Suggested commits, only if later authorized:

- POS Awesome: `test(pos): rehearse shift review accounting permissions and upgrade recovery`
- ERPNext: `fix(accounts): validate expense release and allow clean tax settings install`
