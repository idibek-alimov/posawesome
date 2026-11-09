# Prospective staff commission capture — POS handoff

Date: 2026-11-09. **S2e1–S2e4 implemented/verified locally within their recorded bounds; capture remains inactive.**
Canonical cross-app contract and verification:
[ERPNext Staff S2e1](../../erpnext/docs/simplification/staff-s2e1.md) and
[S2e3 implementation/evidence](../../erpnext/docs/simplification/staff-s2e3.md) and
[S2e4 POS/observation/volume evidence](../../erpnext/docs/simplification/staff-s2e4.md).
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
before rollout. The historical S2e1/S2e2 increments changed no capture hook, queue version
or cashier grant; S2e3 now supplies a default-off native bridge owned by ERPNext.

The S2e1 audit found zero-share loss and payment-hydration overwrite paths. These are repaired
locally under [S2e2 implementation/evidence](../../erpnext/docs/simplification/staff-s2e2.md).
Shared `copySalesTeam` preserves supplied percentages through invoice preparation and both
return entrypoints. The payment selection binding reads without mutating the source;
only deliberate selection/clear replaces the team. The server allocated-amount helper
preserves zero. Legacy single-person compatibility and native precision/sum validation
remain. There is no new attribution fallback, capture hook, schema or HR permission.

**S2e2 verification (historical):** 13 disposable native cases, 68 retained Python and 139 focused frontend
cases passed; four RU/TG desktop/mobile real-component fixtures passed. Both actual worker
functions execute in-process with enqueue intercepted; no real RQ/race/volume claim.
Thirty source/permission table hashes match after fixture rollback. Build/type-check/lint,
Chrome 109 CSS and 12-asset verification passed. Three unrelated failures in untouched
payment-method/totals fixtures reproduced on an isolated HEAD baseline remain; two obsolete
selection test assertions were repaired. Existing Russian-only captions remain in Tajik.
See S2e2 for file-by-file changes, linked-feature coverage, exact commands and limitations.

S2e2 did not check physical browser/QZ/fiscal printing, authenticated full checkout, real
RQ/concurrency/volume or intended-site activation/acceptance. S2e4 adds the recorded worker/
concurrency/bounded-volume evidence below; physical/full-checkout and activation limits remain. Local ignored assets were
built; no intended-site query/write/setup/migration/cache/restart/activation, real transaction,
commit or push occurred. Test DB/Redis and the temporary browser fixture server were stopped.

**S2e3 completed locally in ERPNext:** company opt-in/version/server activation, private
immutable typed outcomes, exact-source capture authority and native SI/POS lifecycle bridge.
Native submit authority grants no HR viewing; permission/validation bypass flags are not
capture authority. Unsupported evidence preserves valid native sources with unavailable
outcomes. Unexpected private failures are sanitized and roll native source/GL/stock back.
Returns inherit captured originals; cancellation keeps evidence, and consolidated parents
create no second commission sale. Inactive settings create no sidecars. Intended-site
capture remains off. S2e3 alone made no POS attestation, real RQ or volume-readiness claim;
S2e4 supplies the bounded integration/evidence below.

**[S2e4 is implemented and verified locally](../../erpnext/docs/simplification/staff-s2e4.md).**
Foreground and both actual worker functions create private exact-object attestations inside
execution. They revalidate persisted profile/company/source/shift/cashier/request-ledger
scope and retain native source dates, queue acknowledgement, response/realtime/printing/cache
privacy. No capability is queued and no HR role is granted. The draft worker now reauthorizes
its profile and exact ledger invoice. Both worker paths lock the durable request before its source and use current reads for
concurrent duplicates; late failed duplicates preserve the winner. Duplicate workers preserve POST_SUBMIT_DONE/FAILED;
failed drafts can retry, while posted payment failures use explicit repair. Repair owns one
final ledger save, avoiding a real stale-document failure after successful native work.

An explicit private `observe_captured_source` backend operation, under current native HR/
evidence/source/cost authority, appends all captured members atomically after native
fulfilment/merge/valuation. Read endpoints remain pure; missing/changed proof cannot create
Originals, reprice first-known cost or become zero. There is no automatic observer or Desk
write-on-refresh. Graph/event limits remain, with explicit 2,000-prior-Original and 8 MiB new
Original/observation-batch proof limits to contain dense amplification.

**S2e4 verification:** 274 automated cases across both apps; 22 real RQ jobs including both
queue paths, no-HR actor, actual role revocation, discovery/write connection loss and retry,
committed repair and simultaneous native/POS workers; eight real connection races plus
activation discovery. Actual native 499/500-event months are complete, 501 withholds the
whole total; 1,000/10,000 out-of-period native-schema noise fixtures leave matching monthly
query counts unchanged. Dense child, split, prior-return and actual 1,999/2,000/2,001-parent
graphs fail closed at their bounds. All monitored 32/34/35 source/permission hashes match
after rollbacks/full restores. Dedicated DB/Redis are stopped again. Native closed-shift
validation is preserved; trusted offline reassignment keeps the original posting date.

The ERPNext report records exact commands, query/timing data, fixture limitations and private
observer operation. Near-limit native invoices are slow and large POS remarks retain their
existing text-column limit; these checks do not establish general checkout/month throughput.
No new frontend/build/browser, physical Windows/QZ/fiscal or real-device offline claim.
No intended-site query/write/migration/reload/activation, opt-in, role grant, real business
transaction, commit or push occurred in S2e4.

**Next:** ERPNext/HRMS native payroll handoff audit and contract. Keep estimates separate
from net payable/payment and retain Q08 historical/paid/floor gates. Intended-site opt-in,
operator use of the private observer, wider permission-aware paging, physical devices and
owner acceptance remain separately scoped work; prior development activation is unchanged.

Suggested commit message (no commit performed):
`feat: integrate disabled POS commission capture and bounded observations`.
