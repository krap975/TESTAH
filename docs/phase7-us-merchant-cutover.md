# Phase 7: stage a US Sandbox merchant for USD

## Observed configuration

Read-only local audit on November 6, 2026 (America/Los_Angeles): four saved Sandbox intents/orders use USD, all four app bindings match the current on-disk configuration, and there is one distinct bound provider merchant. Two intents are recorded as `awaiting_buyer_approval`, two as `expired`. There is no explicit merchant override. The create adapter sends the persisted integer-minor-unit amount and currency without conversion. Verified order responses must match that amount/currency and the persisted merchant. No identifiers, credentials, tokens or private cart contents were printed. The audit reads the configuration file, not another process's in-memory settings; a backend restart is required to load a staged change.

The account's India registration is user-reported. Country and currency-receiving preferences are not stored in Testah and cannot be confirmed from its client-ID digest or ordinary client-credentials OAuth response. No authenticated PayPal request, approval, order, capture or reconciliation was initiated during this audit. No existing intent, assessment, currency, merchant, credential or environment file was rewritten. The running backend retains its loaded configuration until explicitly restarted.

## Diagnosis and validation limits

PayPal lists USD as supported, while [its currency documentation](https://developer.paypal.com/api/codes/currency) also describes country-specific offerings and payment-receiving preferences. A supported currency is not a guarantee that a particular seller can receive it. [PayPal India receiving preferences](https://www.paypal.com/in/cshelp/article/what-are-payment-receiving-preferences-and-how-can-i-set-them-help536) can block currencies the merchant does not hold. The checkout message is consistent with an account/currency restriction; it does not establish that every Indian business account rejects USD. Do not infer the precise PayPal cause from order creation succeeding.

Creating a new US Sandbox business and a REST app attached to that business is a supported test setup. Follow [Sandbox accounts](https://developer.paypal.com/sandbox-testing/accounts) and [merchant app account selection](https://developer.paypal.com/platforms/disputes/set-up/). A new US test account does not bypass restrictions on any real account.

OAuth preflight proves only that PayPal accepts the supplied Sandbox app credentials. It cannot attest to the merchant's country, USD receiving eligibility, or a buyer's ability to complete checkout. Verify country, app association and receiving preferences in the Sandbox UI. Successful checkout/capture would require a separately authorized later test; this task does not perform one.

## Cutover safeguards

- New Sandbox assessments freeze a private digest of the configured app client ID at creation. A changed app or missing legacy assessment binding blocks starting that assessment or reserving a new checkout. Existing snapshots are not backfilled with a new app. Create a new assessment after configuration validation.
- Existing payment intents keep their original app digest, merchant, currency, order/capture IDs, callback state, authorization, timestamps and operation keys. No script migrates or redirects them.
- For non-final intents, an app/pin mismatch returns a safe `409 / paypal_merchant_changed` before any PayPal request, lease recovery, intent status change or evidence write. This includes reconciliation and capture. Missing configuration returns safe 503. Final intents return persisted state without provider requests; persisted listing/history remains readable.
- Reconciliation of an old intent requires the original app and seller configuration. The system has one active server app; it does not automatically select another merchant or keep a database of credential values. Retain old credentials securely for original-account investigation/reconciliation. Do not treat cutover as resolution of pending or unknown payments.
- An already-sent financial operation still follows the original durable evidence and reconciliation rules. Freeze new starts and allow in-flight operations to settle before a planned stop. Do not claim a server stop can undo an already-sent request.
- Explicit seller pins retain exact matching. Blank `TESTAH_PAYPAL_MERCHANT_ID` omits payee and binds the actual merchant from the authenticated create response. An email, Classic API username, Client ID, OAuth `app_id`, synthetic merchant ID or guessed identifier is never a substitute.
- Gateway authorization, exact amounts/currency/cart, merchant policy, budget reservations, buyer approval, callback binding, separate payment operator access, fencing, idempotency and capture-details verification remain enforced. Neither staging nor OAuth preflight executes these financial operations.

## Exact local procedure

1. **Preserve the old account and evidence.** Do not delete its Sandbox account/app, database rows or order IDs. Keep its credentials in your existing secure local storage. Do not click Capture or Reconcile as part of this configuration task. Do not reuse or edit an old intent/assessment for the US merchant.
2. **Create a new Sandbox seller.** In PayPal Developer Dashboard, open **Testing Tools → Sandbox Accounts → Create account**. Select **Business** and **United States**. Create a fresh account; duplicating the India account is not a country-change procedure. Confirm the resulting account is Business/US. Log into this account at Sandbox PayPal and verify USD balance/primary currency and the supported payment-receiving preferences permit the intended USD test. Keep any required restrictions intact; if PayPal still disallows the setup, use PayPal support.
3. **Create the matching Sandbox REST app.** Open **Apps & Credentials → Sandbox → Create App**. Select **Merchant** if a type is offered, and select the new US business account as the app's Sandbox business account. Recheck that association on the app detail page. Obtain both the Client ID and Client Secret from this new app, locally only. Use a separate Sandbox Personal buyer account later; never the seller itself.
4. **Stage without activating.** From `backend/`, copy the current configuration locally:

   ```powershell
   if (Test-Path -LiteralPath .env.paypal-us) { throw 'Staged configuration already exists; inspect it locally before proceeding.' }
   Copy-Item -LiteralPath .env -Destination .env.paypal-us
   ```

   Edit `.env.paypal-us` in a local editor. Replace only `TESTAH_PAYPAL_CLIENT_ID` and `TESTAH_PAYPAL_CLIENT_SECRET` with the new app's values. Set `TESTAH_PAYPAL_MERCHANT_ID=` blank, or use only the independently verified new US merchant ID. Never carry an old explicit seller pin into the new app. Keep payment mode `paypal_sandbox`, the fixed Sandbox environment/API origin, loopback callback and existing distinct payment/monitoring operator tokens. Do not put values in commands, chat, `VITE_` variables or screenshots. `.env` and `.env.*` are ignored; never commit or share either file. Do not overwrite an existing staged file containing values you need to retain.
5. **Validate the staged file without a payment.** From `backend/`:

   ```powershell
   .\.venv\Scripts\python.exe scripts/check_paypal_configuration.py --env-file .env.paypal-us
   .\.venv\Scripts\python.exe scripts/check_paypal_configuration.py --env-file .env.paypal-us --authenticate
   ```

   The first command performs database SELECTs only. The second additionally obtains an OAuth token, using the fixed, bounded, DNS-validated Sandbox adapter. It never invokes an Orders, Payments, approval or reconciliation endpoint; token values are never printed or saved. Process `TESTAH_` overrides block validation rather than silently validating the wrong credentials. Use a clean shell without those overrides. Require `configuration_present=true`, `sandbox_mode=true`, `sandbox_origin_fixed=true` and, for the second command, `oauth_authenticated=true`. Country/USD flags intentionally remain false: the UI checks in steps 2–3 are separate requirements. For this new app, the old intents should appear as bound to another app; do not change them to make that count zero.
6. **Activate only after both UI and OAuth validation.** Stop new assessment starts, wait for in-flight work to finish, then stop the backend through its existing terminal. Preserve the original local credentials securely. Apply only the validated Client ID, Client Secret and optional new seller pin to active `backend/.env`; preserve unrelated settings. If validation failed or the US account/app association is uncertain, leave active `.env` unchanged. No currency or database rewrite is needed, and this correction adds no migration. Restart with:

   ```powershell
   .\scripts\start_backend.cmd
   ```

7. **Verify configuration presence again.** In another terminal, from `backend/`, run the default read-only audit:

   ```powershell
   .\.venv\Scripts\python.exe scripts/check_paypal_configuration.py
   ```

   Confirm the server was restarted from the same `.env` without process overrides. A healthy API alone is not PayPal validation. No frontend credentials are required, and this change needs no frontend configuration update.
8. **Use a new assessment only when later payment testing is authorized.** Create a fresh USD assessment after the validated cutover. Do not start it, create an order, approve or capture as part of this configuration task. Old assessments without the new assessment binding must be recreated rather than adopted. After a separately authorized future test, verify the actual returned merchant against the new US seller; successful order creation alone does not prove USD acceptance or capture.

## Verification

| Check | Result |
| --- | --- |
| PayPal, execution, database and health tests | 161 passed, 12 deselected in 410.92 seconds |
| New cutover cases | Passed: old-assessment fencing, new-assessment app binding, all intent fields/run evidence unchanged after wrong-app reconciliation, original-app reconciliation, and value-free OAuth-only preflight |
| Migration round trip | Passed in the selected backend tests |
| `alembic check` | No new upgrade operations detected; no schema change required |
| Frontend production build and strict type checks | Passed |
| Default read-only CLI audit | Passed twice with the same four USD orders, one merchant and four current on-disk app bindings |

Exact backend invocation, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_paypal.py tests/test_execution.py tests/test_database.py tests/test_health.py -k "not real_sample_http_assessment and not rai_designer_to_controller_real_http" -q -p no:cacheprovider --basetemp E:\Testah\tmp\paypal-us-cutover-20261106
```

The 12 deselected cases start the existing sample-agent HTTP server on fixed port 9001; they were excluded to avoid conflicting with a running sample agent. This is a relevant scoped run, not a claim that the entire backend suite was rerun. One upstream Starlette/AnyIO deprecation warning remains. Provider requests in tests use mocked HTTP. No authenticated PayPal request or payment was made by this task. No new US credentials have been supplied or activated; country, app association and real OAuth validation for the new app remain the operator's pending steps. No server restart or active configuration change was performed.
