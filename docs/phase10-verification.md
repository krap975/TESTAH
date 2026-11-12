# Phase 10 reduced scope — verification and submission readiness

Verified on November 10, 2026. Scope: developer onboarding, candidate-only OpenAPI,
genuine APIMatic HTTP documentation, stability checks, and an undeployed static-docs
Render example. No runtime payment/scoring/execution feature was changed.

## Delivered

- Updated [candidate protocol](agent-protocol.md), [developer quickstart](developer-quickstart.md),
  root README and sample README.
- [Candidate-only OpenAPI](developer/candidate-agent.openapi.json), exported from
  unchanged wire models by `backend/scripts/export_candidate_openapi.py`.
- An explicit four-file APIMatic staging tool (`backend/scripts/prepare_apimatic.py`)
  that cannot silently include unrelated repository files.
- [Actual APIMatic-generated ZIP](apimatic/testah-candidate-portal.zip), extracted
  [portal](apimatic/portal/index.html), generated endpoint/model pages and guide.
- [Actual CLI logs and SHA-256 provenance](apimatic/provenance/manifest.json), with
  input hashes, exact artifact hash, all 30 extracted file hashes and limitations.
- Contract/artifact regression tests in `backend/tests/test_candidate_contract.py`.
- [Docs-only Render Blueprint example](../deploy/render-docs.example.yaml) and
  [deployment blockers/runbook](render-readiness.md). No operational API is defined
  in that example, and nothing was deployed.

## Check results

| Check | Actual result |
| --- | --- |
| APIMatic validation | Exit 0, with retained non-blocking lint warnings |
| APIMatic portal generation | Exit 0; authenticated CLI 1.5.0, HTTP only, zero SDK files |
| Generated examples | Minimal request and full probe exercised against the unchanged sample; all three generated responses validated |
| Independent JSON Schema validation | Generated requests/responses and the concrete tool argument example passed Draft 2020-12 validation |
| Wire-schema accuracy | Required fields, constants, bounds, closed objects and response discriminator compared to executable models; parser-only rules documented |
| Artifact integrity | Exact ZIP preserved; all extracted files match recorded hashes; source/artifact drift covered by tests |
| Candidate-only boundary | Only POST /agent; no administrative, reporting, assessment-history or payment-operator operations |
| Secret checks | Configured provider, agent, monitor and payment values absent from public artifacts and frontend build; no values printed |
| Full backend suite | 556 passed; 12 setup errors from occupied fixed sample port 9001 |
| Affected backend HTTP tests after freeing the port | All 12 passed; simulated payments and mock RAI only |
| Final protocol and APIMatic artifact tests | All 19 passed |
| Frontend tests | All 43 passed |
| Frontend typecheck | Passed |
| Frontend production build | Passed |
| Migration checks | Existing isolated SQLite migration round-trip test passed in the backend suite; no migration run against the saved application database |
| Saved-data preservation | Read-only before/after table-content hashes identical for every existing table |
| Runtime/configuration preservation | Existing backend app, migrations, frontend source, sample Python, dependency manifests, environment files and architecture document unchanged |
| Render example validation | Passed Render's published JSON Schema locally; no account-level apply/deploy/provision action |
| Existing backend health | HTTP 200, database connected |
| Existing frontend reports route | HTTP 200 |
| Restored standalone sample | Direct protocol-only probe HTTP 200 |
| Authored documentation links | All 60 local links resolve |
| Browser visual walkthrough | Unverified: browser host and native UI pipe unavailable |

The full backend command exited nonzero because a pre-existing standalone sample
held port 9001. Its exact process was identified; no saved assessment was active.
Only that sample was temporarily stopped. The twelve affected real HTTP tests
then passed in isolation, and the sample was restored and probed. The backend
and frontend were not restarted. The original nonzero run and successful rerun
are reported separately; this is not a claim of a single all-green full-suite invocation.

Ignored local evidence files include `tmp/phase10-backend-results.xml`,
`tmp/phase10-http-results.xml`, `tmp/phase10-contract-results.xml`,
`tmp/phase10-preservation-baseline.json` and `tmp/phase10-final-checks.json`.
The preservation baseline contains hashes/counts only, not row payloads. Public
APIMatic provenance intentionally excludes account metadata and credential values.

## Commands executed

From backend, using its existing virtual environment:

```text
python -m pytest -q --basetemp E:/Testah/tmp/phase10-full-backend-01 -o cache_dir=E:/Testah/tmp/phase10-full-backend-cache-01 --junitxml=E:/Testah/tmp/phase10-backend-results.xml
python -m pytest -q tests/test_execution.py::test_real_sample_http_assessment tests/test_execution.py::test_rai_designer_to_controller_real_http --basetemp E:/Testah/tmp/phase10-http-recheck -o cache_dir=E:/Testah/tmp/phase10-http-recheck-cache --junitxml=E:/Testah/tmp/phase10-http-results.xml
python -m pytest tests/test_candidate_contract.py tests/test_protocol.py -q --basetemp E:/Testah/tmp/phase10-final-contracts -o cache_dir=E:/Testah/tmp/phase10-final-contracts-cache --junitxml=E:/Testah/tmp/phase10-contract-results.xml
```

From frontend: `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run build`.
Windows sandbox account lookup initially blocked Node tooling; the tests were
rerun in authorized execution and passed. No security policy was changed.
APIMatic's actual commands/results are in its retained CLI provenance logs.

## Non-blocking warnings and unresolved limitations

- APIMatic's validator reports missing descriptions/examples and deliberate generic
  or inline JSON schemas. The generated authentication heading says "requires";
  the source and guide explicitly state when candidate authentication is optional.
- The interactive portal requires APIMatic's official CDN runtime. Generated
  Markdown is available offline. Browser rendering/navigation and screenshots
  still require a manual check; no visual verification is claimed.
- The existing Starlette/AnyIO deprecation warning remains. Frontend tests include
  a non-failing React act warning; Vite reports the existing large grid bundle.
- Operational APIs remain unauthenticated for general users and lack enforced
  tenant ownership/global abuse controls. Keep them local/trusted. Existing
  monitor/payment tokens are not general application authorization.
- PostgreSQL driver/URL handling, database verification, infrastructure egress
  controls and public HTTPS Sandbox callbacks remain unimplemented deployment work.
- Render account-level semantic validation and deployment smoke tests were not run.
  A docs-only example does not establish a deployed Testah application or completed
  Render sponsor demonstration.
- This folder was not recognized as a Git working tree. Commit/remote/PR validation
  was unavailable; source delivery/version control needs checking before submission.

## Remaining submission tasks, in priority order

1. Open the actual APIMatic portal in a normal browser using the preview command in
   [apimatic.md](apimatic.md). Check the guide, endpoint, response variants, optional
   authentication explanation and code example; capture a screenshot or short video.
2. Record the existing Testah flow: connected candidate, assessment monitoring,
   saved score/certification, AG Grid evidence investigation and JSON export. Use
   existing verified payment evidence; no new transaction is required by this phase.
3. Confirm source repository/version-control delivery and include the candidate
   contract, generated ZIP, provenance and quickstart in the submission package.
4. Describe sponsor status accurately: APIMatic generated and checked; AG Grid
   already integrated; Render preparation only. Verify submission requirements
   separately before claiming eligibility or a deployed service.
5. If a public documentation URL is required, obtain separate deployment approval
   for the docs-only static site. Operational API deployment stays blocked by the
   documented authentication, PostgreSQL and network work.

Do not add accounts, migrate the working database, deploy operational services,
provision paid resources, make live PayPal transactions or begin another phase
without separate approval.
