# POS Smoke Tests

This suite is a production-safety smoke gate for global runtime errors.

## Run

```bash
yarn test:smoke
```

## Local Secrets

Copy `frontend/.env.example` to `frontend/.env.local` and fill in local values.

`frontend/.env.local` is ignored by git and is auto-loaded by `frontend/playwright.config.ts`.

## Environment Variables

- `POSA_SMOKE_BASE_URL`: Frappe site URL (default: `http://127.0.0.1:8000`)
- `POSA_SMOKE_PATH`: POS route (default: `/app/posapp`)
- `POSA_SMOKE_USER`: login username (optional)
- `POSA_SMOKE_PASSWORD`: login password (optional)
- `POSA_SMOKE_SID`: existing Frappe session cookie (optional alternative to user/password)
- `POSA_STARTUP_RECOVERY_E2E`: set to `1` to enable the live slow-start recovery scenarios
- `POSA_E2E_CASHIER`: cashier assigned to the active POS Profile (required when the terminal is locked)
- `POSA_E2E_CASHIER_PIN`: that cashier's local-only POS PIN

Run only the startup recovery coverage after deploying the current frontend build:

```bash
yarn playwright test tests/e2e/startup-recovery.spec.ts --config=playwright.config.ts
```

The test delays live read requests in the browser, verifies that terminal security remains fail-closed, retries the cashier list, and confirms that a slow catalog no longer owns the startup overlay indefinitely. It does not submit an invoice. Keep all real values in ignored `frontend/.env.local`; never add them to `.env.example`.

In CI, the POS app route smoke test is skipped unless `POSA_SMOKE_BASE_URL` is configured.
If credentials are set, the test logs in before opening POS.
If credentials are not set, test assumes an already authenticated session.

## Shift and expense release checks

`shift-review.readonly.spec.ts` is opt-in and uses real Desk controls and RPCs. It
opens lists, optional expense/review detail and native source links; it never submits
an expense, closes a shift, approves a loss or sends a printer/transfer command.

```bash
POSA_SHIFT_REVIEW_SMOKE=1 yarn playwright test tests/smoke/shift-review.readonly.spec.ts \
  --config=playwright.config.ts --workers=1
```

Configure `POSA_SMOKE_BASE_URL` and credentials/session in ignored local settings.
The `shared expense entry` case uses the base user/session. It opens ordinary Expense
Desk entry and, when `POSA_SHIFT_REVIEW_NAME` is supplied, the missing-expense form on
that review. Supply a review with an actionable shortage and a manager/owner login.
It checks native date/required-note controls and cancels the final review confirmation
without recording an expense. Run it alone with `-g 'shared expense entry'` when only
one language/user is configured.
The matrix requires real English, Russian and Tajik users: set `POSA_SMOKE_USER_EN`,
`POSA_SMOKE_USER_RU`, `POSA_SMOKE_USER_TG` and matching `POSA_SMOKE_PASSWORD_<LANG>`
as needed (the base user/password are fallbacks). It checks the boot language instead
of assuming a query parameter changed the logged-in user's language. No user language,
role or business configuration is changed by the browser test.

Optional `POSA_SHIFT_REVIEW_COMPANY` selects a permitted company through the native
Expense Desk filter. `POSA_SHIFT_REVIEW_NAME` enables native review detail/source-link
checks using a known permitted review. Existing expense rows open the shared detail
dialog. Screenshots go to the configured Playwright output directory. The suite checks
desktop/mobile, theme, keyboard focus, overflow, uncaught errors and scoped WCAG A/AA
Axe results. This is not physical printing or full manual accessibility certification.

If the matching bundled browser is unavailable, `POSA_SMOKE_BROWSER_EXECUTABLE` can
select an already installed Chromium executable for these tests. Record its version
in release evidence; do not infer that it verifies the Chrome 109 runtime baseline.
