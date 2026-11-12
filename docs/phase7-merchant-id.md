# Phase 7 merchant configuration audit

> For subsequent account/currency cutover safeguards, assessment app freezing and OAuth-only staging, see [US merchant cutover](phase7-us-merchant-cutover.md). A configuration mismatch now rejects reconciliation without changing the original intent.

November 6, 2026 (America/Los_Angeles). This is a configuration correction within Phase 7. No payment was initiated and no authenticated PayPal account request was made during this task. All provider workflow tests use mocked HTTP with the real installed SDK.

## PayPal requirement

The official [Orders create schema](https://developer.paypal.com/api/orders/v2/orders-create) declares purchase-unit `payee` and its `merchant_id` optional. For this first-party, single-merchant integration the app's merchant receives an order without an explicit payee. The intended account must be the Sandbox business account associated with the configured app. This change does not implement partner delegation or a multi-seller marketplace.

No merchant lookup is needed to configure this workflow. PayPal's [Log in with PayPal flow](https://developer.paypal.com/log-in/build) obtains profile information through a user authorization-code/consent flow, rather than the existing Orders client-credentials grant. The OAuth response's `app_id` identifies an app, not the seller's merchant ID. No undocumented identity lookup, credential decoding or guessed identifier is used. Developer account details and Sandbox business settings remain optional sources for an explicit pin; this task did not inspect a signed-in developer account or claim to retrieve its ID.

## Backend usage and change

| Consumer | Before | Current behavior |
| --- | --- | --- |
| `app/core/config.py` | Blank default, effectively mandatory downstream | Blank explicitly supported; supplied values retain validation |
| `app/payments/paypal.py:configured` | Requires merchant ID alongside client credentials/operator access | Blank allowed; a nonempty known placeholder still fails closed |
| `app/execution/service.py` | Sandbox assessment readiness calls `configured` | Readiness permits blank ID without contacting PayPal |
| `app/payments/service.py:reserve_payment` | Copies configured merchant into intent | Copies optional pin and freezes a private hash of the app client ID |
| `app/payments/paypal.py:create_order` | Always supplies `payee.merchant_id` | Supplies only an actual configured pin; blank omits the entire payee |
| `app/payments/service.py:verify_order` | Exact persisted merchant match | First successful create verification binds a valid returned merchant ID if unset; subsequent responses require exact match |
| `app/payments/service.py:process` | Configuration merchant equality before creation/capture | Checks frozen app binding and any explicit pin before creation/capture; legacy intents keep explicit-pin requirement |
| `app/models/payment.py` | Non-null merchant ID | Empty only before verified creation; merchant remains non-null. Adds nullable private `client_binding` for backward compatibility |
| `app/api/payments.py`, public payment/evidence | Exposes synthetic scenario merchant | Unchanged: private provider merchant and app binding are not exported |

Synthetic `merchant_id` fields in blueprints, registry arguments, gateway, simulation and runtime remain scenario identifiers. They are never substituted for the PayPal merchant ID. Those modules and their authorization checks are unchanged. `scripts/configure_payments.py` only manages the operator token and does not consume the seller ID.

Migration `0007_paypal_binding` adds a nullable 64-character column without modifying old rows. New intents persist only a SHA-256 digest of the high-entropy app client ID, never credential values, secrets or OAuth tokens. The digest is an app-change guard, not a merchant ID. A different app cannot create or capture an existing intent. The adapter also avoids reusing an OAuth token cached for another app. Existing intents without this binding require their original explicit merchant configuration; blank configuration cannot silently adopt a legacy intent. Original SDK transport, timeouts, retries and request IDs are preserved.

Merchant binding happens in the same transaction as verified order identity, run/checkout references, amount/currency and order evidence. A missing or invalid returned merchant fails closed. An inspection cannot bind or rebind a merchant. A later different merchant fails verification before capture. Explicit pins retain their exact-match behavior.

Gateway scenario merchant verification, exact cart approval, budget/reservation, single-use authorization, PayPal buyer approval, callback binding, separate payment operator authentication, fenced claims, independent capture-details verification and no replay of uncertain POSTs remain in place. Monitoring/listing/replay remain read-only.

## Local configuration

Set the real Sandbox client ID and secret locally, keep the separate operator token, and leave `TESTAH_PAYPAL_MERCHANT_ID=` blank. Remove a nonempty placeholder instead of inventing a value. Run `alembic upgrade head` from `backend/`, restart the API and create a new Sandbox assessment. Optional explicit pinning requires the actual business merchant ID. Keep existing pinned values for pending legacy intents.

## Validation

The local `.env` contained a recognized merchant placeholder. Only that setting was cleared; all other parsed values, including credentials and operator tokens, were preserved. A boolean-only `Settings()` check confirmed both client fields configured, merchant blank, and Sandbox configuration ready. This checks configuration presence, not provider authentication. No credentials or account identifiers were printed.

| Check | Result |
| --- | --- |
| Initial focused PayPal/database run | 59 passed; additional migration/binding tests added afterward |
| Final focused PayPal/database run | 62 passed, including upgrade/downgrade preservation and final binding checks |
| Frontend production build and strict type checks | Passed |
| Local `alembic upgrade head` | Passed; head `0007_paypal_binding` |
| Local `alembic check` | No new upgrade operations detected |
| Full backend suite | 490 passed, 1 failed in 1267.09 seconds; see local HTTP timeout below |
| Exact failed local HTTP case, isolated rerun | 1 passed in 6.22 seconds with the original one-second timeout |

The full-suite failure was `test_real_sample_http_assessment[budget_constrained_purchase-safe-completed-None]`: the existing one-second local sample-agent connection probe returned HTTP 504 before an assessment was created. The same transient probe failure is recorded in the earlier Phase 7 configuration audit. All PayPal tests passed. The exact failed case passed on an isolated rerun with the original timeout and no code, production network or control changes. All 491 distinct backend cases passed across the completed invocations; the full invocation is not reported as all-green. One upstream Starlette/AnyIO deprecation warning remains.

Real PayPal acceptance, buyer approval and capture remain unverified by design. Restart the API to reload the local environment; no payment operation is required to apply the configuration.
