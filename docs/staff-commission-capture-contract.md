# Prospective staff commission capture — POS handoff

Date: 2026-11-09. **S2e1 contract and S2e2 source repair complete locally; capture remains inactive.**
Canonical cross-app contract and verification:
[ERPNext Staff S2e1](../../erpnext/docs/simplification/staff-s2e1.md).
Related: [feature contracts](FEATURE_CONTRACTS.md), [architecture](ARCHITECTURE.md).

POS Awesome owns its profile/company, opening shift, server terminal cashier, durable
submission ledger, both background paths, trusted offline shift reassignment and payment/
change/credit repair. ERPNext owns commission rules, dated terms, original evidence and the
independent HR-authorized monthly estimate. Native SI/POS source identity connects them;
commission capture must not replace the POS submission API with the private HR submit adapter.

The adoption contract preserves source posting dates, request aliases/ledger identity,
profile stock/warehouse/price-list/customer/currency/tax/payment/print defaults, offline queues,
response/realtime privacy and existing submitted-versus-payment-complete states. It requires
a separately authorized private bridge, disabled opt-in setup, atomic source/outcome proof,
complete splits, pending-cost observations and real worker/concurrency/volume verification
before rollout. No source hook, production schema, queue version or cashier grant changed here.

The S2e1 audit found zero-share loss and payment-hydration overwrite paths. These are repaired
locally under [S2e2 implementation/evidence](../../erpnext/docs/simplification/staff-s2e2.md).
Shared `copySalesTeam` preserves supplied percentages through invoice preparation and both
return entrypoints. The payment selection binding reads without mutating the source;
only deliberate selection/clear replaces the team. The server allocated-amount helper
preserves zero. Legacy single-person compatibility and native precision/sum validation
remain. There is no new attribution fallback, capture hook, schema or HR permission.

**Verification:** 13 disposable native cases, 68 retained Python and 139 focused frontend
cases passed; four RU/TG desktop/mobile real-component fixtures passed. Both actual worker
functions execute in-process with enqueue intercepted; no real RQ/race/volume claim.
Thirty source/permission table hashes match after fixture rollback. Build/type-check/lint,
Chrome 109 CSS and 12-asset verification passed. Three unrelated failures in untouched
payment-method/totals fixtures reproduced on an isolated HEAD baseline remain; two obsolete
selection test assertions were repaired. Existing Russian-only captions remain in Tajik.
See S2e2 for file-by-file changes, linked-feature coverage, exact commands and limitations.

Physical browser/QZ/fiscal printing, authenticated full checkout, real RQ/concurrency/volume
and intended-site activation/acceptance remain unchecked here. Local ignored assets were
built; no intended-site query/write/setup/migration/cache/restart/activation, real transaction,
commit or push occurred. Test DB/Redis and the temporary browser fixture server were stopped.

**Next: S2e3**, disabled company opt-in/outcomes/private authority/native SI/POS bridge under
the canonical S2e1 contract, then S2e4 POS foreground/worker/offline/replay/observation/scale
integration. Ordinary submissions remain uncaptured; source submission and payment completion
retain their existing distinct semantics.

Suggested commit message (no commit performed):
`fix(pos): preserve recorded salesperson splits and zero shares`.
