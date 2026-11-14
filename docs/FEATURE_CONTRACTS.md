# Feature Contracts

This file defines how major POS features are connected.

Codex must check this file before changing any related feature.

---

## 1. Pricing Contract

Pricing is linked with:

- Item master
- Item price
- Customer price list
- POS Profile price list
- POS Profile currency
- POS Profile company
- Pricing Rule
- UOM conversion
- Manual rate change
- Discount percentage
- Discount amount
- Tax calculation
- Cart total
- Payment total
- Sales Invoice payload
- Print receipt
- Offline cache

Rules:

- Price must be resolved from one shared pricing flow.
- Manual rate should not be overwritten unless ERPNext behavior requires it.
- Customer price list should take priority over POS Profile price list when configured.
- Pricing changes must check POS Profile price list and customer-specific price list priority.
- UOM conversion must not inflate or deflate prices incorrectly.
- Multi-currency conversion must be handled consistently.
- Discount percentage and discount amount must not fight each other.
- Cart totals, payment totals, invoice payload, and printed totals must match.

---

## 2. Discount Contract

Discount is linked with:

- Item row
- Cart summary
- Invoice total
- Additional discount
- Payment screen
- Print receipt
- Backend invoice payload

Rules:

- Discount percentage and discount amount must remain synchronized.
- Changing one discount field must not reset item rate incorrectly.
- Zero rate should not be created unless explicitly allowed.
- Total discount must match printed and submitted invoice values.
- Discount logic should not be duplicated across screens.

---

## 3. Cart Contract

Cart is linked with:

- Item search
- Barcode scan
- UOM selection
- POS Profile warehouse
- POS Profile customer
- POS Profile company
- Batch/serial logic
- Stock validation
- Pricing
- Discounts
- Taxes
- Payments
- Offline storage
- Sales Invoice creation
- Printing

Rules:

- Cart state is the source for visible cart data.
- Derived totals must be calculated consistently.
- Avoid separate total calculation logic in multiple screens.
- Cart should survive offline/online transitions safely.
- Large carts must remain performant.
- Cart defaults must respect POS Profile configuration.

---

## 4. Offline Cache Contract

Offline cache is linked with:

- Items
- Prices
- Customers
- Stock
- POS Profile
- POS Profile configuration
- Cart
- Sales Invoice sync
- Printing
- App version updates

Rules:

- Cached data shape must match API data shape as much as possible.
- Missing or stale cache must not crash the app.
- New build/version changes must not leave old IndexedDB data in a broken state.
- Sync transformations must be backward compatible where possible.
- Offline mode must use the same business rules as online mode wherever possible.
- Offline cache must refresh safely when POS Profile configuration changes.
- Offline pricing data must not depend on a record having been used online
  previously.
- Item Prices must preserve price list, UOM, currency, customer, and validity.
- Pricing Rule sync must include customer/group rules before a customer is
  selected offline.
- Multi-currency sync must cover price-list, invoice, company, and payment
  account currencies, including dated Currency Exchange records.
- Disabled, deleted, or out-of-scope pricing records must be removed locally.

---

## 5. Printing Contract

Printing is linked with:

- Cart data
- Invoice data
- Customer
- Taxes
- Discounts
- UOM
- Payment methods
- QZ Tray
- Browser print
- ERPNext print format
- POS Profile print format
- POS Profile letter head

Rules:

- Printed totals must match submitted invoice totals.
- QZ Tray and browser print should use the same final invoice values.
- Receipt formatting changes must not change business calculations.
- Print output should not calculate totals differently from the invoice payload.
- Print settings should respect POS Profile configuration where applicable.

---

## 6. Customer Contract

Customer selection is linked with:

- Customer price list
- Credit limit/outstanding balance if implemented
- Cart pricing refresh
- Taxes
- Discounts
- Sales Invoice payload
- Payment screen
- Print receipt
- Offline customer cache

Rules:

- Customer change must refresh all dependent pricing/tax fields safely.
- Customer-specific price list must be respected.
- Offline customer data must not crash pricing logic if optional fields are missing.

---

## 7. UOM Contract

UOM is linked with:

- Item master
- Barcode
- Price list
- Conversion factor
- Stock quantity
- Rate
- Discount
- Cart total
- Sales Invoice payload
- Print receipt

Rules:

- UOM conversion must be applied consistently.
- Rate must not be inflated because of wrong conversion direction.
- Quantity, stock, and invoice payload must use compatible UOM data.

---

## 8. POS Profile Contract

POS Profile is linked with:

- Company
- Warehouse
- Cost Center
- Customer
- Customer price list fallback
- POS Profile price list
- Currency
- Taxes and Charges
- Payment Methods
- Write Off Account
- Change Amount Account
- Stock validation
- Item filtering
- Customer filtering
- Offline cache
- Sync logic
- Sales Invoice payload
- Print format
- QZ Tray receipt
- POS opening and closing

Rules:

- POS Profile must be checked before changing any POS behavior.
- Do not hardcode company, warehouse, price list, payment method, tax, or print behavior.
- Customer-specific price list should take priority when configured, then POS Profile price list should be used as fallback.
- Stock, warehouse, and invoice payload must respect POS Profile configuration.
- Payment screen must respect payment methods configured in POS Profile.
- Print and receipt logic must respect POS Profile print settings where applicable.
- Offline cache must load and store POS Profile-dependent data safely.
- Custom POS Profile fields must be considered when present.

---

## 9. Shift expense and manager review contract

Phase 1 owner-approved policies and the future implementation boundary are documented in:

- [POS shift review contract](shift-review-contract.md): closing/review scope, signed
  differences, native reuse, source provenance, resolution/cancellation and worked cases.
- [Shared ERPNext expense contract](../../erpnext/docs/expense-workflow-contract.md):
  canonical expense ownership, source/category rules, approved role matrix and posting routes.

Phase 2 expense policy/posting guards are implemented locally; see the
[completion/setup report](expense-services-phase-2.md). Phase 3 history and legacy/offline
compatibility are also implemented locally; see the
[history/retry report](expense-history-phase-3.md). Phase 4 POS expense UI and independent
result recovery are implemented locally; see the [POS UI report](pos-expense-ui-phase-4.md).
Phase 5 ERPNext Desk redesign is implemented locally; see the
[Desk report](../../erpnext/docs/expense-desk-phase-5.md). Phase 6 discrepancy records,
guarded resolution services and closing integration are implemented locally; see the
[backend/setup report](shift-review-phase-6.md). The Phase 7 manager Desk page is implemented locally; see the [manager UI report](shift-review-phase-7.md). The Phase 8 connected journey is implemented locally; see the [integration report](shift-review-phase-8.md). Schema and
explicit source/category setup are required before rollout. Preserve the existing shared
closing calculation and the real child-Document regression.

Phase 9 local native verification/release handoff is complete; see the
[evidence report](shift-review-phase-9.md) and [release runbook](shift-review-release.md).
Both apps must be updated together. Intended-site grants/permissions, backup/upgrade,
installed-app handoffs and physical bank/printer checks remain operator release gates.

## 10. Prospective staff commission capture

The [POS capture handoff](staff-commission-capture-contract.md) links to the canonical
ERPNext S2e1 adoption contract. Live capture is not enabled. Preserve profile/company,
server shift/cashier, request-ledger, background/offline/date and payment/receipt behavior;
private HR attribution/evidence must not enter cashier responses or caches. S2e2's recorded
split/zero-share preservation repair is implemented/verified locally; S2e3's disabled
private authority/outcomes/native bridge is verified locally in ERPNext. S2e4 now connects
foreground and both real workers to exact-object private authority, serializes simultaneous
same-request workers with current locking reads, preserves failed-payment/
repair/retry states and adds explicit HR-authorized complete-manifest observations. Worker,
race and bounded volume/graph checks pass locally; company opt-ins remain off. See the
handoff for proof limits, measured latency, operator/fixture/device boundaries and the next
native payroll handoff audit.

## 11. MARKET checkout, receipts and quick returns

The owner-approved scope, reference measurements, implementation and verification limits
are in [MARKET checkout and returns](market-checkout-returns.md).

- Checkout distinguishes no paper, MARKET store receipt and TP809 fiscal receipt.
  Native form/import/API saves cannot forge fiscal identifiers or copy them to new records.
  Fiscal amounts come from the submitted server invoice, in integer tiyins. Never derive
  fiscal totals from the open cart or copy reference code's float/tax-name heuristics.
- POS Profile supplies printer/bridge configuration. Electron main process owns direct
  device HTTP; browsers use the local bridge. Both retain attempt results across retries.
- A timeout/paper error retains an unknown result. Recover the existing FD, acknowledge
  the saved success, or explicitly audit a cashier's check that the journal has no FD.
  Never automatically resend or turn an unknown result into a non-fiscal sale.
- Store receipt and recent/last printing use one renderer and submitted invoice values.
  Sales Orders, quotations and draft printing retain their normal document flow.
- «Возврат» and «Чеки» open the same paginated purchase history, today/newest first,
  with phone/name/invoice/FD search and older date ranges. Search spans permitted
  registers in the current company and both submitted SI/POS sales, excludes drafts,
  returns and consolidated accounting summaries, and exposes no cost/margin fields.
  Read-only item inspection never loads the cart. «Чеки» always prints an ordinary
  receipt through the shared renderer; it cannot issue/reconcile a fiscal document
  and does not rely on a browser's remembered last sale or claim physical-print status.
- The photographed TP809 slips supersede FastReport typography for ordinary receipts:
  compact monospaced 80mm layout, dashed separators and Tajik labels. Ordinary paper
  uses the OS driver (native isolated Electron printing or browser/QZ); it never calls
  formReceipt. Official fiscal identifiers/QR remain firmware-owned.
- Fiscal checkout validates the submitted invoice and server-verified active cashier,
  checks detailed device status and opens a closed hardware shift before preparing an
  attempt. Never automatically close expired shifts. An opening timeout stops receipt
  transmission; retry reads status first. OFD connectivity/queue differs from device
  reachability and confirmed registration in fiscal memory.
- Quick returns are bounded to permitted registers/company and use native idempotent
  submission, stock, payments, customer credit and cashier/shift authority. Preserve the
  remaining source row quantities, cumulative cash-refund cap and batch/serial cart path.
- Fiscal checkout and quick refunds require ERP connectivity; existing offline carts and
  invoice queues remain intact. Credit/loyalty tenders must never be invented as cash for
  a fiscal document. Physical printer/OFD acceptance is separate from mocked/native tests.
