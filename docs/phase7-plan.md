# Phase 7 integration plan

Approved scope: Sandbox Orders only; preserve the architecture reference, existing simulation, RAI and protocol 1.0. No scoring or Phase 8.

Inspection: `app/tools/gateway.py` owns the six tools, strict arguments, merchant/product checks, budget, exact cart fingerprints, deterministic challenges and run-local idempotency. `app/payments/simulation.py` emits created → authorized → completed synchronously. `app/execution/service.py` serializes all aggregate/event writes with a run lock and fenced worker lease; controller HTTP calls occur outside transactions. `RunEvent` supplies both REST and authenticated Phase 6 SSE. Assessment details and monitor exist; no buyer checkout UI exists.

1. Freeze configured payment mode on assessment creation. Add a normalized Sandbox intent with unique approval, order, capture and operation IDs. Reserve budget while pending; successful capture alone increments purchases.
2. Gateway authorization must precede durable checkout reservation. Payment service owns credentials, official SDK/REST calls, safe errors and exact provider verification. Commit operation claims and evidence before network calls. Never replay an uncertain create operation after the bounded original attempt; reconcile captures by GET.
3. Use PayPal's actual approval link. Hash and bind callback state to the run/order; browser return only prompts a server query. Explicit reconciliation/capture uses a separate payment operator token; monitoring credentials cannot capture. Keep monitoring/replay read-only.
4. Pause candidate turns while a Sandbox intent is pending, with a bounded buyer wait. Keep truthful terminal states and allow read reconciliation after worker interruption without new financial writes.
5. Extend evidence projection and add a minimal dark checkout panel. Mock transport and workflow tests cover credentials, mismatches, isolation, concurrency, fencing, retries, redaction and migrations. Run existing checks. Real Sandbox verification requires separately configured credentials and interactive buyer approval.
