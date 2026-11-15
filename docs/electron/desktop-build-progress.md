# Windows Desktop Build Progress

Updated: 2026-11-15. Scope: first installable development preview.

Product decisions remain in [desktop-app-decisions.md](desktop-app-decisions.md).
This progress record distinguishes implemented behavior from the complete product.

## Implemented

- Dedicated Electron runtime package and npm lockfile. Packaging includes the
  desktop files and production `electron-store` dependencies, not Vue/Vite,
  Electron Builder, or the root frontend dependency tree.
- Windows x64 NSIS `.exe` installer with desktop/Start menu shortcuts. Uninstall
  does not request app-data deletion. Application ID and artifact naming stay stable.
- Saved server address, normalized to `/app/posapp`, with HTTPS for public hosts
  and local-network HTTP support. Installation PIN protects subsequent changes.
- Separate Russian/Tajik setup, offline-recovery, and printer-settings pages.
- Cashier printer settings available from the native application menu and
  `Ctrl+Shift+P`, including while the server is unreachable. Opening/saving this
  window does not navigate/reload checkout or clear the cart.
- Local printer address takes precedence over the remembered POS Profile default.
  It is scoped to the ERPNext origin on this computer. Initial assumption is one
  dedicated printer per terminal; explicit register binding is not implemented.
- Read-only connection test sends `DEVICE_STATUS` with `shouldPrintSlip: false`.
  Device reachable/blocked is distinct from permission to issue a fiscal receipt
  or OFD connectivity. No sale or shift operation is sent by the test.
- Main-frame/window/origin checks on desktop IPC, sandboxed renderers, restricted
  local pages, HTTP(S)-only external links, and no remote access to configuration
  setters. Camera scanning requires explicit consent from the configured POS.
- Single-instance behavior and first-exit explanation. Window exit does not close
  the ERPNext/fiscal shift; existing explicit POS closing continues to own closure.
- Fiscal journal preserves unknown attempts across address changes, replays saved
  results without a second transmission, and rejects reuse with changed payloads.

## Build and check

From the POSAwesome repository root:

```powershell
npm --prefix electron ci
npm run test:desktop
npm run electron:build:win
npm run electron:smoke -- --require-artifact
npm run electron:verify-archive
```

Expected artifact: `dist-electron/POSAwesome-Setup-15.33.0.exe` for this version.
The version is the existing project version, not a claim of a new production release.

The build driver checks matching root/runtime versions, uses the installed
Electron runtime for same-platform builds, and keeps build-tool caches under
ignored `.desktop-cache/` unless `ELECTRON_BUILDER_CACHE` is explicitly set.

### Windows tool extraction

Electron Builder 25's `winCodeSign-2.6.0` download includes macOS symbolic links.
Extraction can fail on Windows accounts without symbolic-link privileges. This
machine was prepared by extracting the already downloaded official archive into
`.desktop-cache/winCodeSign/winCodeSign-2.6.0`, excluding `darwin`. Only the
irrelevant macOS tools were omitted; Windows resource editing remains enabled.
No Windows security/developer settings were changed. A new build machine may need
the same preparation or an appropriately tested packaging-tool update.

## Verification evidence

- `node --test scripts/desktop_settings.test.cjs scripts/fiscal_transport.test.cjs
  scripts/desktop_runtime.test.cjs`: 15 passing tests.
- Tests exercise server/PIN validation, shop isolation, local override precedence,
  restricted IPC, preserved POS navigation, subresource-failure handling, result
  replay, unknown-outcome protection after address changes, and payload identity.
- Windows NSIS installer generation and artifact-presence verification succeeded.
- Real Electron runtime was opened against `scripts/desktop_preview.cjs`, an
  isolated mock shop and mock printer status endpoint. The fixture uses its own
  `dist-electron/preview-profile-*` data directory and cannot issue fiscal receipts.
- Visually inspected Russian/Tajik printer settings; exercised connection test,
  save, and close; confirmed the mock checkout/cart remained intact. The preview
  was closed afterward. This is not authenticated ERPNext or physical printer QA.
- JavaScript syntax checks and `git diff --check` passed. Frontend/Python builds
  were not run because this milestone changes desktop code and documentation only.
- `node scripts/verify_desktop_archive.cjs` passed against the final rebuilt
  `app.asar`: packaged desktop files match source, the stable package identity
  and version match, `electron-store` is included, and Vue/Vite/Electron Builder/
  TypeScript/the Electron development package are excluded from the app archive.
- Dependency preparation actually used `npm --prefix electron install
  --no-audit --no-fund`, followed by an offline package-lock refresh after aligning
  the runtime package name with the original application identity.
- Full repository lint was not run: root/frontend dependencies were not installed.
  Targeted desktop tests, JavaScript syntax checks, native mock UI checks, Windows
  packaging, archive contents, and whitespace checks were used for this scope.

## Files and linked behavior

- `electron/main.js`, `electron/preload.js`: guarded native IPC, separate settings
  windows, single instance, permission handling, and exit explanation.
- `electron/settings.js`: URL/PIN validation and site-scoped printer preferences.
- `electron/fiscal.js`: retain payload identity/printer provenance and handle
  interrupted responses without weakening no-resend behavior.
- `electron/renderer/`: local setup, recovery, and printer pages, shared styles,
  Russian/Tajik text, and handlers; these do not recalculate sale totals.
- `electron/package.json`, `electron/package-lock.json`, root `package.json`,
  `.gitignore`: isolated desktop dependency/install/build workflow and NSIS settings.
- `scripts/build_desktop.cjs`, `scripts/electron_smoke_check.mjs`,
  `scripts/verify_desktop_archive.cjs`: version/runtime selection and artifact checks.
- `scripts/desktop_settings.test.cjs`, `scripts/desktop_runtime.test.cjs`,
  `scripts/fiscal_transport.test.cjs`: configuration, IPC/lifecycle, status-only
  testing, and fiscal transmission regression checks.
- `scripts/desktop_preview.cjs`: isolated native UI fixture with a mock shop and
  status endpoint; no real ERPNext login, device, or fiscal issuance.
- `README.md`, architecture/feature contracts, and Electron documentation: current
  commands, local override authority, evidence, and remaining implementation scope.

Linked behavior checked: printer defaults/overrides, ordinary receipt routing,
canonical fiscal payload/attempt preservation, unknown-result recovery, POS window
navigation, application exit versus shift closure, package identity/dependencies,
and local language/layout. Pricing, discounts, taxes, UOM, stock, payment posting,
invoice synchronization, and reports keep their existing source paths; they were
not exercised against live business data in this desktop milestone.

## Still required for the agreed product

1. Reliable offline cold start and restart with the actual Frappe/POS runtime,
   cashier/session authority, valid cached opening, and safe cart persistence.
   The recovery page still offers reconnect/settings and is not a working checkout.
2. Offline fiscal receipt choice, durable review of all offline sales after sync,
   and selective fiscalization by any permitted cashier. Existing checkout still
   requires ERP connectivity for immediate fiscalization; no automatic queue was added.
3. Integrate pending fiscal decisions into the existing End shift workflow while
   preserving independent ERPNext closing, printer closing, and cash-transfer outcomes.
4. Test actual shop/register assignment, authenticated POS loading, session expiry,
   restart/reconnect and no-duplicate behavior. Test installation/upgrades on target
   Windows versions; supported versions have not yet been agreed with the owner.
5. Verify the TP809 model/firmware and physical receipt, status, paper failure,
   timeout, reconciliation, shift and OFD behavior using controlled test data.
6. Installer icon/branding polish, installation-PIN recovery/change flow, signing,
   controlled updates, backup/recovery, and a supported Electron runtime review.
   The preview retains Electron 33.4.11 from the existing project baseline and is unsigned.

No production deployment, real invoice/payment submission, fiscal document,
printer shift operation, or live-data deletion was used for this milestone.

Suggested commit message: `feat(desktop): build Windows preview with protected setup and local printer settings`.
