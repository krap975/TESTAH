# Phase 7 local environment configuration

> November 6 follow-up: Merchant ID is now an optional exact seller pin. The historical three-placeholder setup and readiness results below predate this change. Leave the merchant setting blank for first-party single-merchant Orders; see [merchant configuration audit](phase7-merchant-id.md) for current behavior, app binding, migration and checks.

The local `backend/.env` now ends with `# PAYPAL SANDBOX — PHASE 7`. Eleven missing settings were appended. The original file content and existing variables/secrets were preserved; no duplicate definitions were introduced. The existing monitoring token was preserved, and a distinct payment operator token was generated locally with `secrets.token_urlsafe(48)`, without printing its value. `.gitignore` already excludes `.env` files and keeps `.env.example` available as a safe template. No credentials were added to `.env.example`.

Only the three credential placeholders need manual replacement. Sandbox mode and all other required values are prepared. Settings load `backend/.env` independently of working directory; process environment values take precedence.

| Variable | Settings field → consumer |
| --- | --- |
| `TESTAH_PAYMENT_MODE` | `payment_mode` → assessment creation freezes mode → controller/gateway selects the server payment path |
| `TESTAH_PAYPAL_ENVIRONMENT` | `paypal_environment` is restricted to `sandbox`; the SDK is explicitly constructed with `Environment.SANDBOX` |
| `TESTAH_PAYPAL_CLIENT_ID` | `paypal_client_id` (`SecretStr`) → backend-only OAuth Basic authentication |
| `TESTAH_PAYPAL_CLIENT_SECRET` | `paypal_client_secret` (`SecretStr`) → backend-only OAuth Basic authentication |
| `TESTAH_PAYPAL_MERCHANT_ID` | `paypal_merchant_id` → durable intent's business merchant → order `payee.merchant_id` and exact order verification before capture |
| `TESTAH_PAYMENT_OPERATOR_TOKEN` | `payment_operator_token` (`SecretStr`) → readiness check and payment API bearer authentication; distinct from monitoring access |
| `TESTAH_PAYPAL_API_BASE_URL` | `paypal_api_base_url` accepts only the fixed Sandbox URL; adapter/SDK use that same fixed origin and transport rejects other hosts |
| `TESTAH_PAYPAL_TIMEOUT_SECONDS` | `paypal_timeout_seconds` → total provider request deadline and bounded operation-claim expiry |
| `TESTAH_PAYPAL_RETRIES` | `paypal_retries` → bounded adapter retries with financial request-ID protection |
| `TESTAH_PAYPAL_CALLBACK_BASE_URL` | `paypal_callback_base_url` → server-built approval return/cancel URLs, restricted to local API origin |
| `TESTAH_PAYPAL_APPROVAL_WAIT_SECONDS` | `paypal_approval_wait_seconds` → intent expiry and frozen Sandbox execution wait allowance |

The existing `TESTAH_MONITOR_TOKEN` continues to authenticate Phase 6 read-only SSE. It cannot authenticate payment APIs. No variable was renamed or invented. Environment/API-origin fields intentionally enforce fixed Sandbox constants rather than choosing a configurable live provider.

Gateway authorization and budget/merchant/cart checks still precede payment reservation. Payment service uses the configured Sandbox seller, while candidate-visible merchants remain synthetic scenario IDs. Client ID/secret stay server-side; no configuration endpoint exposes them. Controller and public event redaction include known payment secrets. The payment operator token is entered only into the local checkout panel and sent in an authorization header; it is not persisted in browser storage or sent to the candidate/PayPal. Actual seller ownership and valid credentials can only be confirmed after the user supplies real Sandbox values and completes the provider flow.

A confirmed readiness bug was fixed: known local/README placeholder spellings now count as missing credentials. `Settings` and application startup still succeed, while Sandbox assessment creation returns the fixed `503 / paypal_not_configured` error. The OAuth adapter refuses placeholders before any request, including when an in-memory token was previously cached. There is no fallback to simulation.

Validation with the actual project `Settings()` and local environment returned these booleans, without printing secret values:

| Check | Result |
| --- | --- |
| All eleven added names recognized | true |
| Client ID configured | false |
| Client Secret configured | false |
| Merchant ID configured | false |
| Payment/monitoring operator configuration valid | true |
| Operator tokens distinct | true |
| Sandbox mode and endpoint restrictions valid | true |
| Original variables/secrets preserved | true |
| Duplicate definitions | false |
| Application starts with placeholders and health succeeds | true |
| Placeholder assessment and OAuth fail closed | true |
| Missing/wrong/monitoring tokens rejected by payment APIs | true |
| PayPal network requests during local validation | false |

Test results:

| Check | Result |
| --- | --- |
| Focused `tests/test_paypal.py` | **38 passed**, including the three new placeholder/cached-token rejection cases |
| Initial full backend run with `-x` | **229 passed**, then one existing local sample-agent probe exceeded its one-second timeout |
| Isolated local sample HTTP rerun | **10 passed**, with the same original timeout and no code changes |
| Remaining RAI/controller HTTP cases | **2 passed** |
| Remaining backend regression files | **227 passed** |
| Combined backend coverage | All **468 distinct cases passed across the completed batches**; this is not a claim of one uninterrupted all-green full-suite invocation |

The first test attempt encountered Windows permissions on existing pytest temp/cache folders. Subsequent runs used fresh checked workspace `--basetemp` paths and `-p no:cacheprovider`; no permissions or security settings were changed. The local HTTP timeout was transient and passed on isolated rerun. One upstream Starlette/AnyIO deprecation warning remains. Production timeouts, authorization and network controls were not changed. No frontend code or database schema changed in this configuration follow-up.

To finish configuration, obtain the app client ID/secret under **Developer Dashboard → Apps & Credentials → Sandbox**. Select the app's business account under **Testing Tools → Sandbox Accounts → View/Edit Account**. Sign in to that business account at Sandbox PayPal and copy **Account Settings → Business information → PayPal Merchant ID**. Enter only those three values locally, restart the API, create a new Sandbox assessment and follow the README's manual buyer approval/capture steps. Use a separate personal Sandbox buyer account for approval.

Official references: [client credentials and Sandbox accounts](https://developer.paypal.com/api/get-started/), [Sandbox merchant-ID location](https://developer.paypal.com/platforms/checkout/save-payment-methods/onboarding/platform/).

No authenticated PayPal request, actual Sandbox order or buyer-approved capture was attempted. Real Sandbox verification remains outstanding. No payment architecture or RAI behavior was changed, and Phase 8 was not started.
