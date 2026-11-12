# Phase 9 completion and verification

Phase 9 delivers read-only reporting over persisted Phase 8 evaluations, with a
professional overview and AG Grid Community for report listings, findings and
evidence. Implementation is confined to reporting, frontend integration, tests,
verification helpers and documentation. No later phase was started.

## Delivered

- `/reports` and `/reports/{run_id}` with overall performance, independent workflow
  certification/safety gate, five stored dimension scores and contributions,
  policy interpretation, recovery milestones, financial evidence and audit hashes.
- AG Grid Community 36.3.0 only, matching React 19 peer support, explicit Community
  modules, dark theme, sorting, filtering and pagination. No Enterprise dependency.
- Finding selection clears conflicting quick/column filters and previous sorting,
  shows supporting events, navigates to the correct page and focuses the event.
  Repeated selection works even when the scoped row array has not changed.
- Sanitized event inspector, searchable event IDs/tool action summaries, logs page
  and monitor graph-to-grid filtering, preserving existing SSE/token/replay controls.
- Versioned fixed improvement guidance based on persisted findings and coverage.
  No new scoring engine, LLM findings, numerical recomputation or provider checks.
- Complete JSON exports pinned to an evaluation and cutoff; ordinary DOM print
  sections include every finding and sanitized event beyond virtualized grid rows.
  Browser **Print / Save as PDF** does not issue HTTP requests.
- Safe pending/unrequested/error/partial/stale/historical/untested states. Missing
  source history prevents complete export/print but retains evidence investigation.

Architecture, API contracts, budgets and operating instructions are in
[phase9-reporting.md](phase9-reporting.md).

## Verification results

- Full backend regression suite: **561 passed, no failures/errors/skips**.
  Includes existing health success/failure, safe errors, CORS, migrations,
  protocol/execution, RAI/payment and deterministic-scoring tests.
  Result: `tmp/phase9-backend-results.xml`.
- Final reporting suite rerun against current guidance/redaction/payment projection:
  **11 passed**, no failures/errors/skips. These are the same 11 tests included
  in the full run, not 11 additional collected tests.
  Result: `tmp/phase9-reports-results.xml`.
- Complete frontend suite: **43 passed, no failures/skips**. Includes real Community
  grid models/React effects in JSDOM, clearing hidden filters and descending sort,
  pagination to event 58, repeated finding selection, full-report refresh/print/
  download restricted to GETs and complete print/download evidence beyond page 1.
  Result: `tmp/phase9-frontend-tests.log`.
- Automated accessibility scans of the evidence inspector and complete report page
  found **no serious or critical violations**. Color contrast was disabled because
  JSDOM cannot verify rendered colors; these scans do not establish full WCAG compliance.
- `npm ci` succeeded from the lockfile; npm reported **0 vulnerabilities**.
- Strict TypeScript and test-project typechecking passed as part of the production
  build; production build passed. Result: `tmp/phase9-build.log`.
- `alembic check`: no new upgrade operations; current migration remains
  **0008_evaluation (head)**. Phase 9 adds no migration or environment setting.
- Real local HTTP acceptance verifies the reference report, 7-event cursor pages,
  complete JSON equality with all evidence pages, listing, refresh and SPA routes
  for reports/logs/monitor. Result: `tmp/phase9-http-verification.json`.

The backend read-only regression compares every table before/after repeated
report requests, refuses write SQL and fails on payment/execution/scoring-service
calls. It includes an expired execution lease to detect accidental management
recovery. Other tests cover unrequested history, cross-run evaluation access,
immutable old evaluation selection, late evidence, partial/gapped history, private
input exclusion, known-secret/token/callback redaction and explicit size limits.

## Reference and database preservation

Reference assessment: `448a13ed-d692-4355-acb3-0a7de6117529`.

- Persisted evaluation `d1d8163e-fa80-43fd-9c41-d7ceebd131ab` remains **100/100**,
  certification **pass**, non-stale, retrospective `commerce-scoring-v1.0.0`.
- All **68 original execution events** remain in canonical order.
- Original challenge activation at 29 and denial at 30–32 remain visible. The
  report preserves the evaluator's environmental-disruption classification and
  does not invent a misconduct deduction or corrective action.
- One recovered episode retains 100 recovery rule points. Authorization, capture
  and payment inspection references remain available for inspection.
- The original completed **USD 80 PayPal Sandbox capture**, order/capture IDs and
  all payment records remain unchanged. Reports never contact PayPal to reverify it.
- Whole-table before/after hashes match for every SQLite table, including all
  **44 assessments, 2083 execution events, 6 payments and 5 evaluations**, plus
  jobs, bindings, agent/environment and RAI records. `docs/architecture.md` also
  matches its original hash.
- Baseline and result: `tmp/phase9-preservation-baseline.json` and
  `tmp/phase9-preservation-result.json`. Initial SQLite backup:
  `tmp/phase9-before.db`. The baseline helper refuses to overwrite its first baseline.
- The complete sanitized reference download is saved at
  `tmp/phase9-reference-report.json`.

No live model calls, new Sandbox purchases, captures or reconciliations were made
for reporting verification. Provider regression scenarios use isolated fixtures
and mocks. The real database was never downgraded or populated with test records.

## Manual browser acceptance: blocked, with steps retained

The browser-control inventory reported **“The browser access host is unavailable”**
and the native helper pipe was unavailable. An explicit attempt to open the local
report in the in-app browser returned the same error. Consequently, interactive
visual/responsive/keyboard/screen-reader/native-print-dialog checks could not be
completed. HTTP route checks and JSDOM tests passed; they are not represented as
manual browser verification.

When browser access is available, perform these checks on the existing reference;
none requires starting a new assessment, scoring, or making a payment:

1. Open `/reports`, sort/filter a column, paginate and open the reference report.
   Confirm the clean dark overview, 100/100, pass, retrospective label and five
   stored dimension weights/contributions.
2. Search evidence for a value that hides capture event 58, change sorting and
   pagination, then select the task-capture finding. Its supporting events must
   be displayed and the inspector located. Repeat selection after adding another
   filter. Check the challenge-denial and recovery evidence as well.
3. Download JSON with evidence filtered. Confirm 68 events, the original denial,
   USD 8000 minor-unit Sandbox capture, correct IDs/hashes and cutoff. Compare to
   `/report/events` and the saved reference export.
4. Choose Print / Save as PDF. Check readable summary pages, all findings, audit
   metadata and evidence through event 68, including sanitized payloads. Save via
   the native dialog if desired. Grid pagination must not limit printed evidence.
5. Check a historical evaluation, unrequested assessment and failed/partial test
   fixture where available. Confirm truthful labels and no invented final score
   or resilience claim. Do not mutate a historical run to manufacture these states.
6. Check 390 px and desktop layouts, 200% zoom, Tab/Shift+Tab, keyboard grid
   filtering/sorting/pagination, focus visibility, inspector announcement, screen
   reader labels and contrast. Confirm scrolling stays inside the grid on mobile.
7. Open the monitor with the existing separate monitoring token. Select a graph
   node/edge and a replay prefix; the grid must use only its supporting accepted
   events. Check the browser console for errors.
8. Observe the network during report open/refresh/print/export: only read requests,
   no evaluate/reconcile/capture/start calls. Rerun the preservation helper afterward.

## Limits and environment notes

- Public deployment, secure developer authentication, owner isolation and simplified
  PayPal checkout remain outside Phase 9. Existing trusted-loopback access and
  separate monitor/payment-token boundaries remain unchanged.
- Report assembly is limited to 5000 events and JSON downloads to 10 MiB, with
  explicit errors rather than silent truncation. Listing filters apply to the
  labeled loaded batch of up to 100 assessments.
- AG Grid is lazy-loaded but still produces a roughly 1 MB minified / 283 KB gzip
  shared evidence chunk; Vite emits its standard chunk-size warning.
- The existing Starlette/AnyIO BlockingPortal deprecation warning remains. The
  JSDOM full-grid test can emit a React asynchronous `act(...)` warning; assertions
  pass. Real-browser rendering/console verification remains outstanding.
- Restricted Windows execution initially hit Node `uv_os_get_passwd` errors.
  Authorized frontend verification passed. `npm ci` initially encountered Vite's
  locked esbuild executable; the verified local Vite process was stopped and the
  clean install then succeeded. The frontend was restarted afterward.
- No credential values or environment files were changed. Backend and frontend
  are left running on their existing loopback ports.
