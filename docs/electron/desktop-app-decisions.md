# POSAwesome Windows Desktop App — Agreed Decisions

Recorded: 2026-11-15.

Status: Product decisions approved in discussion. The owner authorized starting
development, then interrupted the initial inspection to request this record.
No application code was changed during that inspection. This document records
the intended product, not a claim that all features already work.

## 1. Purpose and distribution

- Build a Windows desktop POSAwesome application using the existing Electron
  foundation in this repository.
- Cashiers launch it by double-clicking a desktop icon. It opens in its own
  application window without normal browser tabs or an address bar.
- Distribute a normal Windows `.exe` installer, for example
  `POSAwesome-Setup-<version>.exe`, with desktop and Start menu shortcuts.
- Customers do not need to install Electron, Node.js, or development tools.
- Use one configurable installer for multiple shop owners. Do not build a
  separate executable for every shop.
- ERPNext remains on a server; installing the desktop app does not install
  ERPNext on the cashier's computer.

## 2. Hosting and shop separation

- ERPNext will most likely run on a VPS.
- Each shop has a separate ERPNext site.
- Assume one dedicated fiscal printer per checkout computer/register for the
  initial design. Shared fiscal printers are not a confirmed requirement.
- The installer/operator is the owner of this project. Shop owners and cashiers
  should be able to use the application without technical setup work.

## 3. Configuration and access

- The project owner configures the ERPNext server URL and register assignment
  during installation.
- Fiscal printer connection settings must be configurable.
- Keep company, warehouse, prices, taxes, payment methods, and other existing
  POS business settings under ERPNext/POS Profile authority.
- Cashiers and shop owners must be able to change the fiscal printer address
  quickly, without reinstalling or restarting the app.
- Provide a simple printer connection screen with an address field,
  **Test connection**, **Save**, and understandable connection/error status.
- Printer settings must remain accessible when the VPS/internet is unavailable.
- Save the address locally for the configured shop/register and preserve it
  across restarts. A working local correction must not be silently overwritten
  by a server default on reconnection.
- Changing the address must preserve the current cart, shift, pending sales,
  and fiscal attempt history.
- Administrative server/register configuration is separate from the limited
  printer connection controls exposed to cashiers. The exact administrative
  protection mechanism is still to be designed.

### Changing printer addresses

The owner reports that the printer sometimes changes between:

- `http://192.168.1.102:8002/`
- `http://192.168.1.101:8002/`

This is an explicit recovery requirement. Suggested installation practice is to
reserve a stable printer address in the router where possible; the cause of
these changes has not been verified. Manual address editing must remain usable.

## 4. Fiscal printer integration

- Target country: **Tajikistan**.
- Working target model: **TP809**, subject to confirmation from a physical
  device or supplier documentation.
- Reference application inspected:
  `C:\Users\Admin\Downloads\MARKET`.
- Put fiscal API communication inside the Electron application so the desktop
  installation can communicate directly with the printer on the shop network.
- ERPNext on the VPS should not need direct network access to the shop printer.
- A separate local browser bridge should not be required for this desktop path.
- Keep ordinary receipt printing distinct from issuing a fiscal document.

Reference evidence: MARKET's `Params.ini` contains `FISKAL_URL`. Read-only
inspection of its cashier executable found HTTP API paths and JSON receipt
fields, including `api/deviceStatus`, `api/openShift`, `api/closeShift`,
`api/formReceipt`, and `api/getFDByNumber`. This was static inspection, not a
verified request to a real printer. The literal TP809 model name was not
confirmed from those executable strings.

## 5. Offline selling and restart recovery

- Cashiers must continue selling when internet/VPS connectivity is unavailable.
- After a computer/app restart during an outage, reopen checkout and recover
  the existing shift, saved cart, and pending sales.
- Offline operation may **continue an existing shift only**. Opening a new
  shift requires a server connection.
- Initial installation, sign-in/provisioning, and preparation of the required
  local data take place online.
- Keep the interface/startup resources and necessary register data available
  locally; relying only on opening the VPS website is insufficient.
- Reuse and strengthen the existing offline invoice/cache/sync infrastructure
  rather than creating competing pricing or accounting logic.
- Persist completed sales durably before reporting that they were saved.
- Synchronize sales to ERPNext after connectivity returns, preserving transaction
  identities so retries do not create duplicate invoices, payments, or stock
  movements.
- Show server connectivity separately from fiscal printer connectivity.

## 6. Checkout buttons and deferred fiscalization

Preserve the three familiar checkout choices, as in MARKET:

| Checkout action | Offline behavior |
| --- | --- |
| Finish without receipt | Save the sale locally without printing. |
| Finish with receipt | Save locally and print an ordinary receipt through the available local printing path. |
| Finish with fiscal receipt | Save locally and retain the request as pending fiscalization; do not require immediate fiscal issuance. |

The owner accepts saving sales locally and fiscalizing later. The owner reports
that the fiscal printer does not work properly without internet; exact device
behavior remains a physical-device verification item.

### Review after reconnection

- Provide a review list of **all offline sales**, retaining their original
  checkout receipt choice even after ERPNext synchronization.
- Any cashier may review the list and select which eligible sales to fiscalize.
  This is not restricted to owners or supervisors.
- Provide **Fiscalize selected** with visible progress and individual outcomes.
- Do not automatically fiscalize all offline sales on reconnection.
- Clearly distinguish sales that originally requested fiscal receipts.
- Unselected sales remain available for review. Do not silently change their
  fiscal state or claim a fiscal receipt was issued.
- Fiscalizing later operates on the existing synchronized sale; it must not
  create another sale, payment, or stock movement.
- Retain the original sale timestamp and the later fiscal issuance details.

### Separate synchronization and fiscal outcomes

Track ERPNext synchronization separately from fiscal issuance. The intended
user-facing distinctions include:

- ERPNext: pending synchronization, synchronized, or needs attention.
- Fiscal: not requested, pending, confirmed, or result unknown.

These are conceptual states, not a requirement to replace the existing schema
or translated status values without reviewing compatibility.

A receipt that has never been sent is different from one sent without a clear
response. Preserve durable attempt/result records across restart and address
changes. Never automatically resend an uncertain attempt. Reconcile the printer
journal/existing fiscal document first. Already fiscalized sales must not be
issued again; reprinting an existing document is a separate operation.

## 7. Simple shift and application lifecycle

The owner described MARKET as opening a shift when the POS opens and closing a
shift when the app closes. After discussion, the owner accepted the simpler
explicit workflow below so ordinary exit/restart also works offline.

### Opening the app

- Resume an existing shift automatically.
- If no shift exists and the server is reachable, show **Start shift** immediately.
- Preserve the existing opening-cash entry and other required opening fields.
- Do not silently create a shift or assume an opening cash balance.
- If no valid existing shift exists while offline, explain that a connection is
  required to start one.

### Closing the app

- The window's **×** closes the application and leaves the shift open.
- Persist the current cart and pending work before normal exit.
- Do not present a three-choice shift-closing dialog on every exit.
- On the first ordinary exit, explain:
  **Your shift stays open. To finish your working day, use End shift.**
  Include a **Don't show again** option.
- A crash or unexpected shutdown must not be treated as successful shift closure.
  Recover the existing shift on restart.

### Ending the working shift

- Provide a clearly labeled **End shift** action.
- Guide the cashier through totals, counted cash, and explicit closing confirmation.
- Surface unresolved offline sales in this workflow so they are not forgotten.
- Require connectivity and the required synchronization/review before completing
  ERPNext shift closure.
- If offline, explain:
  **Connect to the server to close your shift. You can exit now and close it after reconnecting.**
- Coordinate printer fiscal-shift operations through the shift workflow while
  retaining separate ERPNext and printer outcomes.
- Never report complete success when ERPNext closing succeeds but printer closing
  fails or is uncertain. Preserve the result for recovery.
- Exact fiscal opening timing and the treatment of undecided deferred receipts
  at End shift still require implementation design; do not introduce automatic
  fiscal closure or receipt issuance merely because the window is closing.

## 8. Current implementation findings

The initial read-only inspection found:

- `electron/main.js` and `electron/renderer/setup.html` already provide an
  Electron shell and saved ERPNext server URL.
- `package.json` already has Electron Builder Windows/NSIS configuration.
- `electron/fiscal.js` already provides direct local fiscal HTTP requests and
  an attempt journal.
- The fiscal printer URL currently comes from POS Profile; the requested local
  cashier-editable setting still needs implementation.
- The desktop load-failure page currently offers connection retry/settings,
  rather than a working checkout by itself. Service worker and offline boot
  code also exist; offline cold start/restart needs end-to-end verification.
- The current fiscal checkout prepares its payload through ERPNext before
  contacting the printer. Deferred selection should reuse the guarded server
  fiscal workflow after the sale has synchronized.
- Existing offline queues, cached opening-shift recovery, and shift-closing
  guards provide foundations to extend.
- Existing documentation explicitly requires online fiscal checkout. Update
  linked contracts when implementing deferred review, without removing the
  guarded submitted-invoice fiscal calculation path.

## 9. Open questions and verification boundaries

- Supported Windows versions have not been decided. Windows 10/11 versus older
  versions was asked but not answered.
- Confirm the physical printer model, firmware/API details, device identity,
  and real printing/recovery behavior.
- Decide how to protect installer-only configuration and resume an authorized
  cashier session offline.
- Define the detailed deferred-review persistence, retention, reconciliation,
  and closing rules, including failed synchronization and returned/cancelled sales.
- Define update delivery, signing, backup/recovery, and release support policy.
- Automatic printer discovery was discussed only as a possible improvement;
  manual address editing is the confirmed requirement.
- Shared printers are outside the initial assumption, not permanently ruled out.
- Mocked responses or packaging checks do not prove physical printer/OFD acceptance.
- The owner authorized local development, not production deployment or real fiscal
  test transactions.

## 10. Development direction

Build on the existing Electron and POSAwesome implementation. Follow `AGENTS.md`
and the architecture, feature-contract, workflow, and verification documents.
Preserve shared pricing, taxes, UOM, payments, stock, offline identities, ordinary
printing, and server fiscal calculation authority. Keep product decisions in this
record distinct from implementation progress and release verification evidence.
