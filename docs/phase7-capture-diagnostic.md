# Phase 7 pending capture investigation

Assessment: `4a83fff8-f1ef-46bf-add4-8b730204eeeb`  
Checkout: `818a7ff1-56b7-4d8f-bdcd-26eeb833691e`  
PayPal Sandbox order: `3UY04316J9204552N`  
Verified capture: `7M11726261799453F`  
Amount: USD 80.00 (`8000` minor units).

## Verified outcome

The capture-disabled operator reconciliation initiated at approximately
2026-11-07 07:37 UTC returned HTTP 200, `capture_pending`, the existing capture
ID above and no payment error. This endpoint independently retrieves capture
details from PayPal and verifies the order, merchant, capture identity,
amount/currency and related order. The verified provider capture status is
`PENDING`, not `COMPLETED`. No new order or capture was submitted during this
investigation.

The running backend retains the original app configuration. The current
`backend/.env` has a different app binding, so the standalone provider diagnostic
refused it with `paypal_merchant_changed` before OAuth or provider requests.
The original credentials are unavailable to the operator. No credentials were
extracted from the process and no binding was changed or bypassed. The original
backend remains running; restarting it now would discard that working credential
context and load the different app on disk.

The existing reconciliation response does not expose PayPal's top-level order
status or capture `status_details.reason`. Original capture HTTP status/body,
latency and retry count are not retained in the available logs/evidence. There
is no persisted capture error or capture-timeout event. The exact provider hold
reason and original HTTP response cannot be established from those records.
An execution-controller timeout must not be described as a PayPal HTTP timeout.

## Persisted timeline

All times below are UTC on 2026-11-07 (the previous calendar date in PST).

| Time | Sequence | Evidence |
| --- | --- | --- |
| 07:09:46 | 44–45 | Order created; awaiting buyer approval |
| 07:11:13 | 46 | Buyer approval verified |
| 07:16:41 | 47 | Capture requested; request-time capture ID correctly null |
| 07:21:24 | 48–50 | Execution timeout; assessment finished inconclusive |

The normalized payment row already contains the actual capture ID, whereas the
runtime checkout and timeline have no pending-result event containing that ID.
There is no active operation claim. The budget remains reserved: purchases `0`,
spent minor units `0`, reserved minor units `8000`. Historical evidence was not
rewritten, and no completion, purchase or capture ID was fabricated.

## Code defects and fixes

1. Capture submission first set the payment to `capture_pending`. The provider
   `PENDING` branch emitted evidence only if that status changed. Consequently,
   a successful pending lookup skipped `payment.capture_pending`, leaving the
   runtime snapshot and timeline without the real ID. Repeated status checks
   repeated the same skip. The branch now also detects a missing runtime capture
   ID/status or a stale error. It publishes the verified result once and clears
   transient errors; unchanged subsequent reads do not duplicate evidence.
2. A separate uncertainty-path defect could restore `approved` after a capture
   request when a later order GET contained no capture. That path now records
   `unknown` / `paypal_capture_unconfirmed` and never repeats the capture POST.

Authorization, buyer approval, cart/policy checks, merchant/app binding, exact
money checks, operation claims and independent capture verification remain in
place. The fixes are on disk and are not loaded into the preserved running
backend. With matching original credentials available, a controlled restart and
capture-disabled reconciliation would append a new verified pending/completed
event; it would not alter request-time evidence.

## Safe next action

Keep this payment pending. Inspect the original seller's Sandbox transaction
details for its pending reason, or contact PayPal Sandbox support with the order
and capture IDs. Restoring authorized access to that original app permits direct
GET diagnostics with the helper below. New merchant credentials cannot reconcile
or take over this intent. Do not repeat the purchase while its outcome remains
unresolved.

The assessment is already terminal `inconclusive` after its frozen 720-second
execution limit and cannot safely resume. A later verified completion can update
financial evidence through the normal reconciliation service, including for a
terminal run, but must not resume or relabel the assessment as successful.

From `backend/`, this command checks the existing known capture through the
preserved authenticated local backend with capture explicitly disabled:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_payment.py --run-id 4a83fff8-f1ef-46bf-add4-8b730204eeeb --checkout-id 818a7ff1-56b7-4d8f-bdcd-26eeb833691e --order-id 3UY04316J9204552N --backend-status
```

For restored matching original credentials in a private local env file, use
`--provider --env-file <private-file-path>` instead of `--backend-status`. Provider
mode permits OAuth token acquisition and fixed Sandbox order/capture GETs only;
all financial POSTs are blocked. It validates merchant/app and order/capture
bindings and returns only selected safe metadata and recognized reason codes.
The local diagnostic session is query-only on SQLite. Backend reconciliation uses
the existing service transactions and may update operation claims or append
new verified evidence; it never overwrites historical events.

## Verification

- Reproduced both state-machine defects with failing tests before fixing them.
- PayPal, database and health tests: **79 passed**.
- Additional read-only diagnostic/reason-filter tests: **2 passed**.
- Coverage includes first pending capture evidence, stale-runtime repair without
  event rewrites, no repeat capture after uncertainty, completed-capture GET
  reconciliation for a terminal run without resuming it, and diagnostic financial
  POST rejection. Tests use mocked PayPal responses and initiate no payments.
- Frontend production build and strict typecheck passed.
- Alembic check passed; no schema migration was needed.
- One upstream Starlette/AnyIO deprecation warning; no test failures.

The provider's documented read operations are
[Show order details](https://developer.paypal.com/api/orders/v2/orders-get) and
[Show captured payment details](https://developer.paypal.com/api/payments/v2/captures-get).
