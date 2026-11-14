# MARKET checkout, receipts and returns

Status: Implemented locally (focused tests passed); Verification: Queued for test agent (V51).
Owner interview completed 2026-11-13; final development activation/checks 2026-11-14.

## Purchase-history correction — owner decisions and bounded plan (2026-11-14)

The owner rejected the empty search-first return screen and last-sale-only print
shortcut. Both «Возврат» and «Чеки» must open the same familiar purchase history:
today by default, newest first, with a single phone/name/invoice/FD search and any
older date range. Show date/time, customer/phone, register, amount and inspectable
items so a walk-in customer's morning purchase can be found in the afternoon.
«Чеки» prints **ordinary receipts only**, including earlier sales and reprints.
It must work even when this browser has no remembered last invoice. All submitted
sales are searchable; no invented physical-print status or fiscal issuance is added.

Bounded implementation: shared paginated, company/permitted-register-scoped history
API and Vue purchase list; reuse it in quick returns and a dedicated ordinary-receipt
dialog; replace the last-sale toolbar/menu action with «Чеки»; preserve guest returns,
source quantities, refund identity/recovery, cart/offline queues and existing submitted
receipt renderer/printer routing. No pricing, tax, refund posting, fiscal protocol,
profile settings, access grants or schema changes. Run new focused frontend/native
history cases, build affected assets, clear cache/refresh services and perform a brief
read-only actual-site smoke. Retained matrices remain queued under V51.

## Settled owner decisions

- Cashiers get three independent checkout actions: no paper, store receipt, fiscal receipt.
- Preserve the submitted sale if fiscal delivery times out. Persist an unknown outcome;
  reconcile the existing fiscal document before another transmission. Never silently
  downgrade an unknown fiscal result to a non-fiscal sale.
- Electron main process calls TP809 on the cashier LAN. Browsers use a local bridge.
  Printer/bridge addresses belong to POS Profile; the bench need not reach the shop LAN.
- Cashiers may return another cashier's purchases within their permitted registers/company,
  without supervisor approval or a time limit. Registered customers receive cash or native
  customer credit. Guest returns without a receipt use current selling prices and cash only.
- Use existing native submission, stock, payment, credit, loyalty and offline recovery paths.
  No role grants, real test transactions, automatic fiscal shift closure, production release,
  commits or pushes. Physical printer/OFD acceptance requires an actual configured device.

## Reference analysis

Inspected `/home/idibek/Downloads/MARKET/POS_CHECKOUT_GUIDE.md`, `GEMINI.md`,
`dfm_extracted/MainFormKassaMag.dfm.txt` (`frxRepKLCH80`),
`dfm_extracted/FormOplataVozvrat.dfm.txt`, `fiscal_printer_client.py` and
`erpnext_integration/`.

- MARKET separates finalization from receipt choice, distributes discounts before posting,
  and uses `INCOME`/`REVERT_INCOME`. Fiscal reprinting uses `getFDByNumber`, never a second sale.
- Return payment form shows customer/balance, original amount, discount, refund amount,
  cash/bank choice, numeric keypad and finish/finish-with-receipt actions.
- The extracted DFM loses all extended-precision geometry and misreads signed font heights.
  Recovered these read-only from `Kassa_mag.exe`, TPF0 offset **9917856**, using the existing
  batch parser with x87 80-bit decoding and signed int8. Reference geometry:
  80.2 mm roll, 8.5 mm right margin, 5 mm vertical margins, endless height;
  270.992301 FastReport units (~71.7 mm) content, Calibri 11–12 px body,
  15 px store name, 16 px document title and 21 px bold grand total.
- Item name/article is a separate line; numeric child line contains rate, multiplication,
  quantity/UOM, equals, amount and discount. Footer contains gross before discount,
  discount, grand total, deposit tender, received, change, remaining deposit and thanks.
  User-requested contacts/customer and invoice barcode extend that structure. MARKET's
  report script suppresses thanks on returns; the requested footer takes precedence.
- The reference integration scripts are examples: their float rounding, hardcoded general
  tax, payment-name guessing and automatic submit hook are unsuitable as shared authority.

## Existing implementation and impact

- `Payments.vue` currently conflates store-print and fiscal completion. Shared
  `PaymentActionButtons.vue` also serves unrelated payment-entry screens: preserve those.
- `useFiscalPrinter.ts` currently sends incorrect simplified codes (`SIMPLIFIED`, `NONE`),
  raw signed return items, and bridge-only hardcoded transport. Retry currently resends.
- `api/fiscal.py` has schema creation on requests and unscoped fiscal writes. Move setup
  to migration; scope operations to permitted profiles and supported submitted invoices.
- Preserve Sales Invoice and POS Invoice modes, submission identities, background payment
  completion, offline IndexedDB/outbox, print fallback and QZ routing.
- Existing toolbar already has a profile-controlled Return action. Existing return search
  is a large filter dialog; reuse native return/cart/payment accounting beneath a compact flow.
- POS Profile owns company, warehouse, currency, tax template, selling/customer price list,
  payment account/type, receipt settings and printer endpoints. Do not recalculate prices
  independently or expose costs/margins in returns/receipt responses.

## Bounded implementation

1. Fiscal contract: integer-tiyin Decimal allocation from submitted final amounts,
   exact products/payment/receipt reconciliation, explicit template mapping
   (`SIMPLIFIED1`/`ZERO_TAX`, `GENERAL`/`STANDARD`), positive refund amounts,
   durable attempt/result guards, identifier persistence and existing-FD reprint.
2. Transport: allowlisted Electron IPC; local browser bridge supporting the same canonical
   payload, explicit failure/unknown states and recovery without duplicate transmission.
3. Shared MARKET 80 mm store receipt for checkout/last/recent invoice printing with
   submitted totals, customer loyalty/credit provenance and scannable invoice barcode.
4. Three checkout buttons and keyboard behavior; last/recent receipt actions without cart reload.
5. Compact receipt/FD lookup, customer history and guest product return flow. Native
   quantity, pricing, warehouse, payment and customer-credit validation remain authoritative.
6. Focused new/changed Vitest and fiscal/backend cases only; frontend production build,
   backup before migration, migrations/cache/service refresh, brief read-only actual-site smoke.
   Queue retained regressions, full browser/offline matrices and physical TP809/OFD tests.

Completion requires all three actions, exact monetary contract, guarded fiscal recovery,
three return paths, development activation and recorded focused evidence. Do not count
mocked fiscal responses or HTML fixtures as physical printing/OFD verification.


## Delivered behavior and files

| Files (relative to POS Awesome) | Purpose |
| --- | --- |
| `posawesome/posawesome/api/fiscal_contract.py`, `fiscal.py` | Server-derived TP809 payload, Decimal/tiyin reconciliation, firmware codes, supported document/profile scope, prepared attempt/result guards, FD/FPD persistence, known rejection vs unknown outcome, audited confirmation that a checked journal has no fiscal document. Native invoice-save hooks in `posawesome/hooks.py` reject forged/overwritten fiscal metadata; scoped fiscal services own the locked writes. |
| `posawesome/patches/add_market_checkout_fields.py`, `posawesome/patches.txt` | Idempotent submitted-invoice fields, non-copying fiscal identifiers/attempts, POS Profile device/bridge settings and unlimited cashier-return setting. Covers Sales Invoice and POS Invoice. |
| `electron/fiscal.js`, `electron/main.js`, `electron/preload.js` | Restricted main-frame IPC, local-device URL/endpoint allowlist, direct main-process HTTP and persistent unknown/result journal. No browser CORS dependency in desktop mode. |
| `scripts/fiscal_bridge.py` | Loopback-only browser bridge, explicit allowed origins and SQLite transmission/result journal. Forwards the canonical server payload without another currency conversion. |
| `frontend/src/posapp/services/fiscalTransport.ts`, `composables/pos/payments/useFiscalPrinter.ts` | Shared desktop/browser transport, durable success acknowledgement recovery, existing-FD reprint, positive FD validation and human reconciliation. Never automatically sends again after timeout/paper failure. |
| `frontend/src/posapp/services/marketReceipt.ts`, `composables/core/useLastInvoicePrinting.ts` | One escaped MARKET 80 mm HTML/Code128 receipt for checkout and late printing. Native Sales Order/quotation printing retains its document path. QZ uses the same HTML values/layout; browser print provides the normal fallback. |
| `frontend/src/posapp/components/pos/Payments.vue`, `payments/PaymentActionButtons.vue`, `dialogs/FiscalOfflineDialog.vue` | Three independent checkout actions, store-receipt F11/Shift+Enter, submission guard, correct deferred completion mode and explicit fiscal recovery. Unrelated payment-entry screens keep their two existing actions. |
| `frontend/src/posapp/components/pos/invoice/InvoiceActionButtons.vue`, `flows/InvoiceManagement.vue`, `stores/uiStore.ts` | Last-sale receipt action, one-click recent invoice store receipt, fiscal duplicate/recovery action and remembered document type. No cart reload is needed for printing. |
| `posawesome/posawesome/api/market_checkout.py`, `frontend/src/posapp/components/pos/flows/Returns.vue` | Compact receipt/FD/fiscal-QR lookup, normalized phone/name history and guest product scan. Server prices and native invoice calculation/submission determine refunds. Cash or native customer credit, remaining item selection, durable refund request recovery, stock-cache coordination and the existing batch/serial return cart are preserved. |
| `posawesome/posawesome/api/invoice_processing/creation.py`, `returns.py`, `utils.py`, `frontend/src/posapp/composables/pos/payments/usePaymentSubmission.ts` | Strip client fiscal metadata; source-row-aware remaining quantities; aggregate requested quantities; owner-approved unlimited return period; retain submitted doctype; await checkout receipt callback. Pricing/UOM/tax/accounting/outbox remain on their native shared paths. |
| `posawesome/translations/ru.csv`, `tg.csv` | Cashier labels/recovery wording in Russian and Tajik. |
| `frontend/tests/marketCheckout.spec.ts`, changed Sales Order case in `usePaymentSubmission.spec.ts`, `posawesome/posawesome/api/test_fiscal_contract.py`, `test_market_checkout_native.py`, `scripts/fiscal_transport.test.cjs`, `scripts/test_fiscal_bridge.py` | Focused amount, UI action, recovery, permissions, native accounting/stock/credit and local transport coverage. |
| `docs/FEATURE_CONTRACTS.md`, this report, bench handoff/verification queue | Shared contract, settled decisions, actual evidence, setup and independent verification handoff. |

## Focused evidence

Only this increment's new/changed cases were run. Retained historical suites and volume
matrices were not run.

- **10 new Vitest cases pass** in `marketCheckout.spec.ts`: receipt escaping/totals/returns,
  three separate actions, no re-transmission of a confirmed FD, saved-result recovery after
  ERP failure, unknown timeout behavior, no false missing-FD confirmation, refund replay
  identity and excessive quantity refusal.
- **One changed Sales Order case passes**, selected with `-t 'prints a newly submitted
  Sales Order with the server-assigned name'`; the other 25 cases were skipped intentionally.
- **Eight pure Python fiscal cases pass**: exact codes, integer money, half-up rounding,
  discount/rounding allocation, inclusive product sum, VAT, mixed tender/change, positive
  REVERT_INCOME, marking/services and invalid contract refusal.
- **Seven new native cases pass together in 13.088 seconds**, after focused fixes/rechecks. Disposable profiles,
  customers, items, opening shifts, sales, refunds, GL and stock entries were rolled back.
  A commit guard rejects any attempt by fixture code to commit. Covered cash refund replay,
  remaining quantities, cumulative paid-amount cap, customer credit actually available in
  the stored-value summary, server-priced guest returns, POS Invoice mode, real Bin stock
  restoration once on replay, NaN refusal, formatted phone/fiscal-QR lookup, no cost fields,
  Guest denial, native new/submitted invoice fiscal-field forgery denial, non-copying fiscal identifiers, and prepared/unknown/reconciled fiscal results. Runs used controlled local
  fixtures because the separate `qpr-test.localhost` database is stopped; no business sale
  was used as a test transaction. Follow the test agent's isolation rules for wider runs.
- **Three Node desktop transport cases pass** against a loopback fake printer: local URL
  validation, one HTTP transmission followed by result replay, unknown attempt refusal.
- **Three Python bridge cases pass** against a loopback fake printer: unchanged tiyin
  payload/result replay, unknown attempt refusal, untrusted Origin denial.
- Frontend `yarn build` passes, including `vue-tsc --noEmit` and the **Chrome 109 CSS audit**.
  Scoped ESLint passes on the new services, fiscal composable, return dialog, checkout
  buttons and new Vitest file. Electron package configuration and 12 build assets validate.
- Actual authenticated development route returns **HTTP 200**, native Russian boot, no
  page exceptions, and successful read-only sales/profile-fiscal APIs. The three return
  scenarios and three payment actions render inside that app. Payment rendering uses a
  synthetic local invoice with write endpoints blocked; the existing cashier PIN lock
  remains intact. This is not an end-to-end unlocked cashier sale or physical printing.

## Development activation and preservation

- Database/config backup before migration:
  `sites/radolfa.localhost/private/backups/20261113_224447-radolfa_localhost-database.sql.gz`
  and matching configuration backup. A second backup, `20261114_114434-radolfa_localhost-database.sql.gz`, precedes the idempotent non-copy metadata update.
- `bench --site radolfa.localhost migrate` applied the idempotent patch; new fields and
  unlimited-return defaults are present. Existing company/register/tax/payment settings,
  credentials, real shifts, invoices and offline queues are retained.
- `yarn build` in `frontend/` and `bench build --app posawesome` completed. Final frontend
  assets are built after the final UI change. Cache is cleared and the native supervised
  web/worker processes are refreshed gracefully (`autorestart=true`), preserving Supervisor
  ownership and queue contents. No production deployment, commit or push was made.
- A mistakenly broad `build-message-files` command regenerated unrelated locale CSVs.
  Generated churn was removed; original tracked locales and the prior 16 ERPNext RU/TG
  staff translations were restored from their recorded edits. Only this task's POS wording
  is added. Use cache refresh/affected-app translation compilation, not CSV regeneration.
- Disposable native fixture profiles/items/customers are absent after rollback. Temporary
  authenticated smoke sessions were removed after the final check. All **14 business-table
  fingerprints match** before/after the read-only smoke and fixture rechecks; normal User
  activity and disposable sessions are outside that comparison.

## Printer setup and acceptance limits

Set these on the intended **POS Profile** before hardware use:

1. **TP809 printer URL (desktop):** the real LAN IPv4 or `.local` device address, including
   its port (normally `http://<device>:8002`). Electron contacts it from the cashier PC.
2. **Local fiscal bridge URL (browser):** normally `http://localhost:5000`. On the cashier PC:

   ```bash
   python3 apps/posawesome/scripts/fiscal_bridge.py \
     --printer http://<device>:8002 \
     --origin http://radolfa.localhost:8000 \
     --journal /absolute/persistent/path/fiscal-attempts.sqlite3
   ```

   Add the actual deployed POS origin explicitly. Keep the SQLite/Electron journals
   through upgrades. Neither journal is an offline sales queue to clear during recovery.
3. Configure Cash/Bank **Mode of Payment types** and the appropriate native tax template.
   Fiscal checkout now checks and opens a closed hardware shift with the verified active
   cashier. Expired shifts still require an explicit Z/close action. Payment classification
   uses the native type, not a language-specific name. Firmware owns the official slip/QR.
4. **Receipt printer name:** the existing POS Profile `posa_qz_printer_name` identifies
   the installed OS printer in Electron and the QZ printer in a browser. Set it to the
   same physical TP809 as the fiscal URL. Electron validates the system-defined printer
   name and never silently substitutes another device. Without a name it shows the
   native print dialog; browser mode retains QZ or browser print. OS-driver configuration
   is separate from the fiscal HTTP address.

A local persistent success is acknowledged without sending again. An unknown attempt is
reconciled with the printer journal: attach the existing FD, recover its saved success, or
explicitly confirm that the journal has no document. That last action records the cashier
and attempt on the invoice before permitting a new attempt. A timeout, missing paper or
cover error alone never authorizes another transmission or a silent non-fiscal downgrade.

Fiscal mode currently accepts fully settled TJS Cash/Bank tenders. It refuses unsupported
credit/loyalty/deposit tender representations instead of inventing cash. Store-credit
returns remain available without fiscal printing. Custom/unsupported tax templates,
non-TJS receipts and mixed sale/return documents are rejected explicitly. Source returns
must use a register in the same invoice mode/currency; serial/batch selection continues in
the native return cart when needed. Ordinary guest returns use the current selling price.
Existing offline sale/outbox behavior and provisional offline receipt fallback are retained;
fiscal checkout and quick return posting require ERP connectivity.

No physical TP809, fiscal shift/OFD registration, official QR verification, actual thermal
roll alignment/cutter, Windows Electron package or live customer transaction was tested.
An official hardware receipt and true device journal reconciliation are acceptance gates in
V51, not claimed by the fake-printer tests or browser fixture rendering.

Suggested commit message: `feat(pos): add MARKET checkout modes, guarded TP809 fiscal receipts and quick returns`

Next action: test agent verifies V51 independently, with retained POS/accounting/offline and
RU/TG/browser/device matrices. The existing next implementation workstream remains the
saved Staff native posting/access proposal; no new business area starts automatically.

## Printed-sample correction increment (2026-11-14)

Owner supplied `/home/idibek/Music/1.jpeg` (fiscal sale), `2.jpeg` (device status)
and `3.jpeg` (shift opening). The photos supersede FastReport typography as the
ordinary receipt visual reference. Decisions: compact monospaced/dashed layout,
**Tajik labels on every ordinary receipt**, same physical TP809 for ordinary and
fiscal output, automatic status check/open of a closed fiscal shift with the
server-verified active cashier. An expired shift requires explicit Z/close; never
automatically close it. Printer is currently disconnected; no hardware call or
real fiscal operation is authorized as a substitute for a simulated test.

Read-only executable evidence (file offsets in `Kassa_mag.exe`):

- `Params.ini` stores `FISKAL_URL=http://192.168.1.102:8002/`; HTTP JSON endpoints
  are embedded in UnitTjFiscal (status/open/close/receipt/getFD/X/drawer).
- Receipt builder embeds `sim@mail.ru`/`Some text` at `0x4e3070` and Visa/auth0/OK
  at `0x4e3274`/`0x4e32c8`, exactly explaining those placeholders in photo 1.
- It uses positive signed-return line values in integer tiyins, deriving prices
  from final discounted row sums; the request includes `shouldPrintSlip:false`
  in this builder. Existing-FD printing is a distinct command. Our one fiscal
  registration with `shouldPrintSlip:true` remains the direct paper path.
- Tax lookup at `0x4e4f24` selects tax/VAT codes and
  `DECODE(TT.ID,0,NT.NDS_PERS,TT.TAX_PERC)`; code at VA `0x8e37be–0x8e37f8`
  multiplies the receipt sum by that selected percentage /100, but the tax
  summary embeds `STANDARD` regardless of selection. This can explain the
  photographed 6%-amount/14%-label mismatch; the actual old transaction/tax
  selection is unavailable, so it is an inference, not confirmed fiscal data.
- Ordinary FastReport uses the OS print path; no arbitrary-text HTTP printing
  endpoint was found. Never use `formReceipt` just to print an ordinary receipt.

Bounded corrections before delivery:

1. One shared Tajik monospaced 80mm store renderer, authoritative submitted
   amounts/taxes/payment split, local decimal/date formatting, escaped fields,
   sale/return/discount/customer balance, invoice barcode and no fabricated fiscal QR.
2. Electron native OS-print IPC for that renderer (the main window currently denies
   print popups), using the profile's configured printer; browser/QZ keep shared HTML.
3. Separate reachability, registration/blocking, open/expired shift and OFD queue
   status. Preflight before preparing receipt transmission, auto-open only closed
   shifts using server-verified cashier, never auto-close/reissue on ambiguity.
4. Preserve canonical tax codes, integer sums and native calculation; remove
   invented bank authorization/card/result details. Retain submitted sale and all
   existing unknown/result recovery safeguards.
5. Only changed/new focused tests; standalone previews plus actual read-only dev
   smoke, frontend build/cache/supervised refresh. Physical TP809/OFD/driver/Cyrillic
   alignment and exact firmware response shapes remain explicit V51 acceptance gates.

No company tax templates, pricing, stock/payment ledgers, permissions, business
transactions, offline queues, commits or pushes change in this correction increment.

### Correction delivery and focused evidence

Implemented locally (focused tests passed); Verification: Queued for test agent (V51).
Active on `radolfa.localhost:8000`; hardware is disconnected and no fiscal operation
was performed. [Sale/discount/return previews](receipt-previews/README.md) include
standalone HTML, PNG and 80mm PDFs generated from the actual shared renderer.

- `market_checkout.py` now exposes narrow submitted payment/tax data, taxpayer ID,
  server-derived original subtotal/discount and authoritative final total. This avoids
  deriving original subtotal from an exclusive-tax grand total. Customer credit,
  loyalty and outstanding/refund figures remain native document values.
- `marketReceipt.ts` supplies Tajik labels, photographed monospaced/dashed structure,
  decimal/date formatting, header, split tenders, tax lines and invoice barcode to all
  checkout/last/recent printing. Tax/item descriptions remain source-document text.
- `electron/receipt.js`, `main.js` and `preload.js` provide origin/main-frame-guarded
  native OS printing of the same HTML. The isolated print window blocks document
  scripts/remote resources with CSP, validates the selected printer, measures roll
  height and destroys itself after success/failure. It never uses fiscal HTTP.
- `fiscal_checkout_context` validates the submitted contract and resolves the verified
  current terminal cashier before any hardware action; it never prepares an attempt.
  `fiscalShift.ts` reads complete status, blocks unregistered/blocked/expired devices,
  opens closed shifts and rereads status. An opening timeout never proceeds to issuing
  a receipt; retry starts with status. A simultaneous terminal opening is reconciled
  through status. Neither path automatically closes a shift.
- Receipt/bridge transport now allows `openShift`; exact MARKET refusal code
  `SHIFT_MUST_BE_OPENED` is recognized as a rejected document. Existing receipt
  attempt/result journals and manual reconciliation remain unchanged. Preflight
  failures get a retry state without misleading missing-FD actions; an ambiguous
  prepared transmission retains all journal recovery actions.
- Fiscal bank metadata is `null` when no actual acquiring result is available; no
  invented Visa/card brand, authorization `0`, or bank `OK`. The existing canonical
  tax/template mapping and integer totals remain authoritative. Fiscal success wording
  confirms stored FD rather than claiming an OFD acknowledgement that was not received.

**29 focused cases passed across bounded runs:** 21 selected changed/new Vitest
(10 shift preflight, 4 store receipt and 7 fiscal flow cases; 3 unrelated cases
skipped); 2 native rollback fixtures, 1 new pure Python bank-metadata case; 3 new
Node OS-print helper cases, 1 new desktop open-shift transport case and 1 new bridge
open-shift case. No retained suites, volume tests or broad browser matrix was run.
Scoped ESLint, frontend type checking, `yarn build`, Chrome109 CSS audit,
`bench build --app posawesome`, Electron package config and 12 build assets pass.

The native fixture initially encountered pre-existing live naming-counter collisions.
Fixture opening/invoice names now use isolated UUID names without changing those
counters, and cleanup runs even after setup failure. A subtotal assertion was also
corrected to account for the site's native item discount (200 before discount).
All changes/fixtures were rolled back; no live numbering repair was performed.
An actual Electron probe caught that disabling JavaScript prevented height measurement;
the helper now uses the sandbox plus a document CSP, and that real runtime probe passes
with the physical spooler stubbed.

No schema change or migration was needed. Frontend/bench assets and translations were
built, site cache cleared, and the existing Supervisor-managed web master refreshed
from PID60670 to PID107238 (same local bench/user). Actual authenticated Chrome
startup returned HTTP200 with no page exceptions; live `receipt_data` exposed the
new totals/payment/tax contract and matched the submitted invoice total. The single
smoke session was removed; all **14 business-table hashes are unchanged**, with zero
disposable MKT profiles/items/customers/openings. Existing business data, company tax
setup, roles, real shifts and browser offline queues were preserved.

**V51 acceptance remaining:** connect the TP809, configure its actual LAN URL and
OS driver name, read actual status/firmware field shapes, verify Tajik glyphs/paper
width/cut/barcode and QZ/native output, open a controlled hardware shift, and perform
separately authorized fiscal sale/refund/FD reprint/OFD checks. Confirm that this firmware
accepts absent bank metadata rather than requiring placeholder values; implement real
acquirer metadata only from an actual acquiring integration. Device identity/company
registration and the photographed tax mismatch require real device/journal evidence;
we did not copy or alter the printer's registration or native tax rates.

Suggested correction commit: `fix(pos): match TP809 receipt samples and preflight fiscal shifts`
Next: independent V51 verification/hardware acceptance; the unrelated saved Staff
posting/access proposal remains the next implementation workstream.

## Purchase-history correction — implementation and verification (2026-11-14)

Status: **Implemented locally (focused tests passed); Verification: Queued for test agent (V51).**

- `api/market_checkout.py`: shared read-only `purchase_history` endpoint, today by
  default, inclusive older date ranges, unified phone/name/invoice/FD/barcode/QR
  search, and deterministic 20-row SI/POS pagination. Uses parameterized SQL and
  canonical company/permitted-profile authority. Searches formatted phones on both
  Customer and invoice contact without a customer preselection cutoff; wildcards
  are literal. Drafts, refunds and consolidated accounting summaries are excluded.
  No prices, stock, fiscal attempts or print status are changed by browsing.
- `flows/PurchaseHistory.vue`: one common responsive list for both flows, with
  date/time, customer/phone, register, amount, read-only submitted item inspection,
  debounced search, page navigation and stale-response/error guards. A stale/checking
  reachability probe cannot block a healthy read RPC; explicit manual offline mode
  and browser offline status still refuse browsing. Refund/fiscal guards are unchanged. Desktop item
  table becomes compact item rows on phones. Offline access explains the required
  connection; existing IndexedDB carts/outbox are untouched.
- `flows/Returns.vue`: opens that list immediately; selecting a purchase uses the
  existing native remaining-quantity projection. «Другой чек» retains the history
  filters/page. Separate guest product scanning, quantity selection, native cash/
  credit posting, durable refund identity/recovery and fiscal refund choice remain.
- `flows/ReceiptHistory.vue`, `layouts/DefaultLayout.vue`, `invoice/InvoiceActionButtons.vue`,
  `navbar/NavbarMenu.vue`: «Чеки» opens history without requiring a remembered last
  sale. The dialog lives in the shared layout so the existing navigation-menu entry
  works from other POS pages too. One row action prints/reprints the selected ordinary
  receipt using the existing Tajik MARKET renderer and browser/QZ/Electron routing; fiscal issuance
  is absent from this window. Original submitted values and source register remain
  on the paper. Duplicate in-flight clicks are guarded and failures retain history.
- RU/TG CSVs add only the 20 new labels/messages per locale; no full CSV regeneration.
  Feature contracts and this plan record the new entry points and unchanged authority.

Focused evidence:

- `yarn vitest run tests/purchaseHistory.spec.ts`: **14 new cases pass** (191 ms;
  0.997 s total). Covers immediate today list, unified search/older dates, pagination,
  stale search/details, manual offline/invalid period/stale startup probe, both
  toolbar layouts without last invoice, ordinary-only late printing/error guard, native return selection and guest
  scan entry. Two affected cases pass again after the narrow-screen detail correction.
- Four new `TestMarketCheckoutNative.test_purchase_history_*` cases pass (**6.895 s**)
  through this bench's real Frappe/ERPNext controllers and database, under rollback
  with commit guard. Includes name/formatted phone/barcode/URL/invoice/FD lookup, older
  dates, literal wildcard/SQL injection-like text, combined SI/POS paging, exclusion
  of returns/drafts/consolidations, other-cashier visibility, register/company/Guest
  refusal and invalid dates. The extended FD/QR/malformed-URL case passes again
  in 2.398 s. No live fixtures remain.
- Scoped ESLint, frontend type check, Vite build/Chrome109 CSS audit and affected-app
  bench build/translation compilation pass. Electron package configuration and the
  12-asset manifest check pass (final build `1794645035291`). No schema changes:
  no migration was necessary.
- Development activation: affected assets/translations built, site cache cleared,
  supervised local Gunicorn refreshed. Authenticated `/app/posapp` returns HTTP200;
  actual RU dialogs load today's first 20 purchases with another page available,
  find a May purchase by date/invoice, inspect items and load native return rows.
  The shared receipt dialog also opens after navigating to the Expenses page,
  preserving the existing global navigation-menu entry. Mobile item amounts fit
  inside the compact detail rows with no horizontal dialog overflow.
  Actual browser print service generates the older invoice's Tajik HTML/Code128
  and invokes the **stubbed** browser print callback once (no hardware). No fiscal
  title/API or refund/submission request occurs. Cashier PIN remains locked; dialogs
  are opened through the app event bus in this read-only admin smoke, not an unlocked
  cashier acceptance claim. Fourteen full business-table hashes remain unchanged;
  ephemeral smoke sessions are deleted. Desktop/mobile screenshots and JSON evidence
  are under `/tmp/purchase-history-*`.

Retained cross-cashier access, concurrency, full RU/TG/light/dark/scanner/keyboard,
Electron/QZ/OS driver and physical TP809 checks remain queued under V51. Date input
calendar formatting follows the browser/OS locale, consistent with existing POS
history filters. No physical-paper completion flag is invented: all submitted sales
remain available for ordinary printing/reprinting, including sales finished without
paper. Printer is still disconnected; no actual receipt/refund/OFD document was sent.

Suggested commit message: `fix(pos): share searchable purchase history for returns and receipts`
