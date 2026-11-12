# Phase 6 monitoring architecture

This implementation adds a read projection around the existing modular monolith. `docs/architecture.md` remains the preserved canonical design reference. Phase 6 does not implement real payments, scoring, reports, general account authentication or Phase 7.

## Authority and lifecycle

`Assessment` remains the execution authority. Its actual states are **created**, **running**, **completed**, **failed**, **cancelled** and **inconclusive**. Only existing execution service/controller operations transition them. `RunEvent` in `run_events` remains the sole event authority: UUID identity, run ID, strictly increasing sequence and committed sanitized payload. The unique `(run_id, sequence)` constraint and existing fenced transactional writers are unchanged. State and evidence commit together before a reader can stream them.

Monitoring never schedules a worker, invokes an agent/provider, grants approval or executes a tool/payment. Explicit Start/Cancel buttons call the existing lifecycle APIs. Opening a monitor, refreshing, reconnecting or selecting a replay step is read-only. The stream reuses existing lease-expiry recovery, now optionally scoped to its run; expired execution becomes inconclusive through the same canonical transition logic, without replaying an outbound POST.

## Authentication and the ownership gap

The stream requires a separate `TESTAH_MONITOR_TOKEN`, held as server-side `SecretStr`. Configuration permits an empty value (streaming disabled) or 32–512 printable ASCII characters without spaces. `backend/scripts/configure_monitor.py` creates a random URL-safe credential in the existing uncommitted `.env` without printing it or changing other settings. It preserves an existing non-empty monitoring credential.

Authentication uses `Authorization: Bearer ...`, constant-time comparison, and no token query parameter. Missing/wrong credentials receive 401 before run/cursor lookup; no token configured receives safe 503. CORS explicitly permits Authorization and Last-Event-ID headers but is not authentication. The frontend uses Fetch streaming because native EventSource does not support this custom Authorization header. Credentials are held only in React memory, never URLs, local/session storage, `VITE_` configuration, database records or logs. Refresh requires re-entry.

This is **shared operator authentication**, granting the holder read access to any selected assessment. There is no user identity, Assessment owner column or tenant authorization to enforce. Existing REST/management/start/cancel routes retain their prior unauthenticated local/trusted conventions; adding an authenticated stream does not secure those routes. This system is not production-secure and must remain loopback/trusted. Public deployment still requires real user authentication, owner-scoped reads/writes, global quotas and operational controls. Do not reinterpret nullable environment ownership preparation as implemented authorization.

## SSE contract

`GET /api/assessments/{run_id}/stream`

| Input | Meaning |
| --- | --- |
| Authorization | Required bearer monitoring token; no URL-token alternative |
| Last-Event-ID | Optional canonical event UUID from this assessment; takes precedence over the query cursor |
| after_sequence | Optional nonnegative integer, default 0; rows strictly after it are replayed |

A UUID cursor is resolved only inside the selected assessment. Unknown/cross-run IDs or a sequence ahead of persisted history return safe 422; a missing assessment returns 404 after authentication. Returning a completed cursor still produces a metadata snapshot and terminal settlement, with no duplicate evidence.

The response is `text/event-stream`, with `Cache-Control: no-cache, no-store`, `X-Accel-Buffering: no` and an initial `retry: 1000` hint. Frames:

| SSE type | Data / semantics |
| --- | --- |
| `snapshot` | `{run: AssessmentRead}` from persisted metadata; no SSE ID |
| `assessment_event` | Same public `EventRead` JSON as REST: id, run_id, sequence, created_at, event_type, correlation_id, payload. SSE `id` is its canonical UUID. |
| comment | `: heartbeat` during inactivity |
| `settled` | `{run_id,status,last_sequence}` after all terminal evidence has drained; stream closes |
| `stream_error` | Fixed sanitized code/message if storage/history/frame validation fails after headers; no invented evidence or raw exception |

Only `assessment_event` frames enter the graph/timeline and advance the resume cursor. Metadata, heartbeat, retry and settlement are transport controls, not new stored events. Initial HTTP errors use the existing safe API error envelope. Storage availability errors can reconnect; malformed/oversized/gapped history stops explicitly rather than claiming success.

## Polling, resources and consistency

`app/events/stream.py` reads at most **100 events per batch**, with each serialized frame capped at **262144 bytes**. The default poll period is 0.5 seconds (configurable 0.1–5), heartbeat 10 seconds (1–30), and admission limit 16 active streams per process (1–64). There is no broker, queue or per-client producer buffer. Backlog pages drain without an idle poll delay. Slow consumers hold only one bounded batch, never a database session.

Each read uses a short independent session in an AnyIO worker thread, off the assessment execution event loop. A metadata high-water sequence limits the associated event query, so concurrent writes cannot cause a snapshot to skip ahead or a terminal response to truncate committed events. Sessions close before any yield, network backpressure or sleep. Sequence continuity is checked, including a missing tail. No read transaction spans inactivity.

Each client has an idempotently released admission lease. Normal terminal completion, disconnect, generator cancellation, HTTP validation failure and response cleanup release it. In-flight synchronous reads abandoned by cancellation can finish in their thread and close their session; they do not retain a stream buffer or execute financial actions. The existing SQLite lock timeout still bounds lock contention; polling latency is nominally the poll interval plus query/scheduling time, not a hard real-time guarantee. The documented launcher sets a five-second Uvicorn graceful-shutdown timeout so idle SSE clients cannot prevent a restart indefinitely.

`app/events/public.py` is shared by REST and SSE. It re-applies known provider, agent and monitoring secret redaction to public event payloads/correlation IDs. Private run aggregates, connection configuration, hidden blueprints, leases and credentials are excluded by the existing public schemas. All payment evidence is explicitly simulated. This is the existing bounded sanitizer, not a universal DLP claim for arbitrary operator text.

## Browser stream lifecycle

`assessmentStream.ts` implements a bounded incremental SSE parser, including split UTF-8 decoding, CR/LF framing, multiline data, comments and size limits. Runtime validation checks assessment identity, lifecycle values, event identity/frame ID, sequence, timestamp, payload shape and correlation shape. An accepted prefix must be contiguous. Duplicate UUIDs with identical data are ignored; conflicting IDs/sequences, gaps or malformed data stop safely without advancing the cursor.

Fetch connections carry the token only in a header and omit cookies. Reconnects send both the last accepted UUID and sequence; exponential delays are capped at ten seconds. Unexpected EOF, idle/network interruption and temporary storage/capacity errors reconnect. Authentication/configuration/invalid cursor/protocol errors require explicit correction/reload. Header acquisition has a ten-second timeout; body inactivity is bounded at 45 seconds, exceeding the maximum configured heartbeat period. Abort controllers, reader cancellation and timer/listener cleanup prevent obsolete run/unmounted connections from continuing. The hook maintains one active connection for its selected run/token/revision.

Browser history is capped at **5000 events / 8 MiB serialized characters** (at most roughly 16 MiB of UTF-16 character storage, plus object overhead). Reaching a limit stops explicitly without silently evicting part of the canonical prefix; REST remains paginated. Refresh reconstructs from sequence zero after token entry. Nothing persists execution state in the browser.

## Event-to-graph projection

Five fixed roles use deterministic positions: RAI Examiner/Customer, Candidate Agent, Tool Gateway, Environment Engine and Payment Gateway **(simulated)**. Fixed nodes indicate roles, not fabricated activity. All supporting counts/IDs come from the selected evidence prefix. Unknown event types remain available in the timeline without invented graph interactions. Designer proposal evidence copied into a run remains labeled as proposal evidence rather than candidate execution.

| Persisted evidence | Projection |
| --- | --- |
| `customer.message`, `agent.requested` | Customer → Candidate; protocol request pending until matching request ID response |
| `agent.message`, `agent.completed` | Candidate → Customer; completion remains a candidate claim, not proof of success |
| `agent.tool_call` | Candidate → Tool Gateway; correlated operation pending |
| `tool.requested` | Gateway → Environment for state/policy tools; Gateway → simulated Payment for checkout/status tools |
| `tool.completed`, `tool.failed` | Resolve correlated work and Gateway → Candidate recorded result; result availability is not a claim of external delivery |
| `policy.violation`, `approval.denied` | Rejected evidence; known gateway denial codes keep rejected operations distinct from execution failures |
| `challenge.activated` | Environment → Gateway, declared state mutation |
| accepted/rejected RAI challenge request | Customer → Environment, explicitly conditional; never shown as activation before its trigger |
| `checkout.created`, `payment.authorized`, `payment.captured` | Gateway → simulated Payment; distinct recorded lifecycle facts, no real payment claim |
| `rai.examiner.requested` / generated / fallback | Examiner role shows pending generation until the recorded plan/fallback |
| `assessment.finished` | Outstanding recorded requests become interrupted, never fabricated completions |

Edges aggregate supporting UUIDs per directed service relationship to avoid hundreds of overlapping lines. Labels count supporting events and identify the latest interaction outcome. Request IDs and correlation IDs resolve observed pending work. A completed merchant lookup remains a successful operation even if it reports an unverified merchant. Old rejections remain visible in evidence after recovery. There are no model thoughts, inferred reasoning or hidden operations.

The pure `assessmentGraph(eventsPrefix)` function reconstructs the same graph data from the same persisted prefix. React Flow is read-only: no node editing, tool creation or animated financial claims. It is loaded lazily for monitor routes, preserving the existing dark minimal UI and avoiding a large initial application bundle. Selection exposes supporting events and sanitized payloads.

## Timeline and replay

The timeline preserves canonical sequence order and displays sequence, event type, actual timestamp, relevant actor, short fixed description and available outcome. Manual upward scrolling or event selection pauses auto-follow; the user explicitly resumes with Follow latest. Node/edge selection filters supporting evidence without reordering it.

Replay selects a prefix using a slider or Previous/Next controls. The same pure graph mapping and timeline render that prefix. Latest/full history restores the accepted tail. Current saved lifecycle metadata is labeled separately from the selected historical prefix. No playback control calls Start, an agent endpoint or a payment operation. Completed, failed, cancelled and inconclusive runs all reconstruct from their durable evidence.

See [implementation plan](phase6-plan.md), [verification](phase6-verification.md) and the root README for startup, token configuration and reproducible real local HTTP checks.
