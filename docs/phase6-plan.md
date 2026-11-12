# Phase 6 implementation plan (recorded before code changes)

The user explicitly approved Phase 6, superseding the earlier stop-after-Phase-5 scope restriction for this task only. Stop after verifying Phase 6; do not begin Phase 7.

## Findings

- `Assessment` is the execution/lifecycle authority. Its states are created, running, completed, failed, cancelled and inconclusive.
- `RunEvent` / `run_events` is the sole evidence authority. UUID event IDs and the unique `(run_id, sequence)` order already exist. State and events commit together through fenced transactions.
- The controller and gateway already record customer, candidate, tool, approval, challenge, simulated payment and termination events. No new execution events or shadow runtime state are needed.
- The assessment page currently reloads event history through REST polling. `/monitor` is a placeholder. There are no user accounts, assessment owners or general API authentication.
- Designer/Examiner/provider behavior, tool/payment rules, templates and canonical architecture source must remain unchanged.

## Implementation

1. Add a separate server-only monitoring bearer token, validated in constant time, required for SSE. Empty configuration disables streaming safely. Fetch streaming permits Authorization headers without URL tokens. The browser holds the token only in memory. This shared operator authentication is not per-user ownership; existing management APIs remain unauthenticated and the application remains loopback/trusted development software.
2. Add `GET /api/assessments/{run_id}/stream`: authenticate before run/cursor lookup; replay committed rows using Last-Event-ID (scoped UUID) or `after_sequence`; read bounded batches in short sessions off the event loop; no sessions during sleeps/yields. Poll at a bounded interval, heartbeat while idle, drain terminal history then settle/close. Limit concurrent streams and frame sizes; clean up on disconnect/cancellation. Reuse existing canonical lease-expiry recovery without replaying execution.
3. Share public event serialization/redaction between REST and SSE. Never stream private run aggregates or blueprint data. Metadata/settled/error frames are transport controls, not fabricated evidence events.
4. Build a reusable bounded Fetch/SSE parser and reconnect service plus React hook. Validate run/event identifiers and contiguous order, deduplicate stable IDs, resume only from accepted events, stop on terminal/auth/protocol errors, abort readers/timers on cleanup. Refresh replays durable history and never starts a run.
5. Replace the monitor placeholder with a saved-run selector, current lifecycle metadata and explicit start/cancel controls. Add links from assessment details. Keep existing assessment pages working.
6. Use React Flow with five fixed nodes: customer/Examiner, candidate, Tool Gateway, Environment Engine and simulated Payment Gateway. Aggregate deterministic interaction edges from actual event types with stable supporting event IDs. Active means a recorded request lacking its recorded response; terminal outstanding work becomes interrupted. Rejected, failed, successful and informational evidence remain distinct. Selecting nodes/edges filters/selects the timeline.
7. Add a chronological timeline and sanitized detail inspector. Auto-follow only while the user stays at the latest events; manual exploration pauses it. A prefix slider/step control reconstructs historical graph/timeline without network execution or payment replay.
8. Add backend stream/auth/order/replay/concurrency/isolation/sanitization/disconnect tests and frontend parsing/reconnect/deduplication/mapping/replay/lifecycle tests. Run full pytest, frontend tests/typecheck/build and Alembic check. Verify one real local assessment's streamed evidence equals REST history, including reconnect, and document exact manual steps and limitations.

React Flow is the UI addition. Frontend tests use Node's built-in test runner with `tsx` and Node type definitions for TypeScript support. An initially considered older Vitest version was removed after its dependency audit reported vulnerabilities; the selected dependency set audits cleanly. No database migration, broker, distributed queue, real payments, scoring or RAI behavior change is planned. Preserve `docs/architecture.md`; document implemented streaming in execution/Phase 6 architecture notes and README.
