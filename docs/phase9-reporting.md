# Phase 9: AG Grid reporting and analytics

Phase 9 is a read-only presentation of persisted Phase 8 evaluations. It adds no
scoring rules, payment operations, model calls, database migrations or report jobs.
The overview explains performance and certification; AG Grid Community supports
report discovery, findings and evidence investigation. The preserved architecture
document remains the design reference.

## Data ownership and flow

`app/reports/service.py` reads assessments, immutable evaluations and ordered
events. It uses the existing public evaluation contracts and event sanitization,
with additional report redaction for private/token/provider-operation fields.
Private evaluator input, blueprint triggers, payment callback data, credentials
and approval URLs are never report fields. Fixed improvement guidance comes from
exact persisted rule IDs and coverage, versioned as `commerce-guidance-v1.0.0`.
Unknown future findings retain their stored explanation without guessed advice.

The report schema is `testah-report-v1.0.0`. Selecting a historical evaluation
pins its immutable result and evidence cutoff; later events do not enter that
report's evidence. Staleness and a newer evaluation are separate visible states.
Scores and contributions are displayed exactly as stored. Report assembly never
recomputes a score or changes certification. Financial lifecycle rows are recorded
facts, not fresh PayPal checks. Their presence alone does not supersede the
evaluator's financial findings or evidence gaps.

`app/api/reports.py` exposes thin GET-only routes. Reporting does not call the
existing assessment management reads that recover expired execution leases.
Opening, refreshing, downloading, printing and evidence selection do not enqueue
scoring, call providers, start execution, reconcile or capture payments. Request
sessions close without committing. No historical rows are backfilled or rewritten.

## APIs

| GET route | Behavior |
| --- | --- |
| `/api/reports?offset=0&limit=100` | Stable assessment batches with latest persisted evaluation summaries; batched queries, no per-row evaluation calls |
| `/api/assessments/{id}/report?evaluation_id=...` | Selected report; omitted ID chooses latest persisted evaluation |
| `/api/assessments/{id}/report/events?evaluation_id=...&after_sequence=0&limit=500` | Ascending sanitized evidence through the selected cutoff; explicit total and next cursor |
| `/api/assessments/{id}/report/export?evaluation_id=...` | Complete JSON attachment, independent of browser filters |

All responses use `Cache-Control: no-store`. An evaluation must belong to the
requested assessment. Missing records return safe 404s. Invalid query bounds
return 422. Exports without an evaluation, missing referenced events, incomplete
sequence history or limits exceeded return explicit 409 errors. Partial evaluations
with complete source history remain exportable and retain null overall scores.

Report assembly supports at most 5000 events; downloads at most 10 MiB. Limits
never silently truncate a report. No extra environment settings are introduced.

## Developer experience

- `/reports`: AG Grid listing; sorting, column filters and pagination operate on
  each explicitly labeled loaded batch of up to 100 assessments.
- `/reports/{run_id}`: performance overview, independent certification and safety
  gate, five dimension bars and contributions, policy interpretation, findings,
  recovery milestones, financial evidence, fixed improvements and audit metadata.
- Historical selection uses `?evaluation={evaluation_id}` and paginated evaluation
  history. A current passing certification is not implied for outdated results.
- `/logs?run={run_id}`: read-only chronological execution evidence, including
  runs without evaluations. Logs load an observed history, not a live subscription.
- The existing monitor retains its token, SSE and replay controls. Its AG Grid
  uses only the accepted replay prefix and selected graph node/edge evidence.

AG Grid packages are pinned to Community 36.3.0 with React 19 peer compatibility.
Only required Community modules are registered. Reporting and logs are lazy routes;
there is no Enterprise package, key, trial or integrated-chart dependency. The
existing dark design system supplies grid colors and the report's responsive layout.

Finding selection clears quick search, column filters and previous sorting,
shows all available supporting IDs, restores chronological sorting, navigates to
the target page and focuses its sequence cell. Re-selecting the same finding also
reveals it even when row data did not change. Missing evidence is announced; loaded
evidence remains inspectable even if completeness prevents export.

Recovery with zero opportunities is explicitly **Not tested / Not exercised**;
neutral credit never claims demonstrated resilience. Environmental challenge
denials are retained and explained without inventing misconduct. No corrective
advice is manufactured for a fully passing evaluated trace. Guidance about evidence
quality is distinguished from candidate behavior.

## Exports and printing

JSON includes the public persisted evaluation, report/guidance versions,
assessment metadata, recommendations, payment references, coverage, hashes,
cutoff and every sanitized source event in canonical order. It contains no browser
filter state. Downloads pin the evaluation ID and include an export timestamp.

**Print / Save as PDF** invokes the browser's print dialog after full evidence
loading. The print document uses ordinary DOM tables and articles containing all
findings and evidence payloads, including rows never rendered by the virtualized
grid. It includes audit IDs and hashes. Printing creates no HTTP request. Native
browser Save as PDF remains a user action; there is no PDF service or fake `.pdf`
download. Print summaries and full evidence can produce a long document.

## Verification and preservation

Backend regression tests use isolated databases, compare all table contents and
reject write SQL or operational service calls during repeated reads/downloads.
Frontend tests exercise static state rendering, the real Community row model in
JSDOM, filter/sort/page navigation, repeated finding selection, ARIA checks, full
print DOM and report refresh/print/export requests restricted to GETs.

For the live local reference, without new scoring, model or payment calls:

```powershell
# Run once before implementation; refuses to overwrite an existing baseline.
.\backend\.venv\Scripts\python.exe backend/scripts/check_reporting_preservation.py
# After the normal backend and frontend launchers are running:
.\backend\.venv\Scripts\python.exe backend/scripts/check_reports.py
.\backend\.venv\Scripts\python.exe backend/scripts/check_reporting_preservation.py --verify
```

The preservation helper reads SQLite in read-only mode and saves whole-table
hashes plus an initial SQLite backup under ignored `tmp/`. The HTTP helper saves
the complete sanitized reference export and a verification summary there. Never
run a downgrade against the user's database; migration round trips run in tests.

See `phase9-verification.md` for final command results and remaining manual checks.

## Scope and limits

Existing REST management/report access remains trusted-loopback development
access, without secure developer authentication or tenant ownership. Monitor and
payment operator token boundaries remain unchanged. Secure authentication and a
simplified PayPal checkout are deferred to product polish. Public hosting, account
management, cross-run benchmarks and another scoring engine are outside Phase 9.

Redaction retains the existing bounded local-development event boundary; it is
not universal DLP for arbitrary personal information supplied in candidate text.
JSDOM accessibility checks cover semantic/ARIA issues, not real-browser contrast,
screen-reader behavior, viewport layout or the native print dialog. These require
manual browser acceptance. AG Grid remains a substantial lazy-loaded bundle.
