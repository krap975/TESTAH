# APIMatic integration and provenance

APIMatic was genuinely used to validate the candidate-only OpenAPI contract and
generate an HTTP documentation portal through an authenticated Docs as Code
workflow. This is separate from ordinary FastAPI Swagger and manually authored
Markdown. No application SDK, live API call, deployment or paid resource was added.

## Artifacts

- [Exact APIMatic-generated ZIP](apimatic/testah-candidate-portal.zip).
- [Extracted interactive portal](apimatic/portal/index.html); serve it over local
  HTTP as described below rather than opening it as a file URL.
- [Generated endpoint reference](apimatic/portal/llms-pages/http/api-endpoints/candidate-agent/respond-to-testah.md).
- [Generated response union](apimatic/portal/llms-pages/http/models/oneof-anyof-definitions/agent-response.md).
- [Generated onboarding guide](apimatic/portal/llms-pages/http/candidate-integration/overview.md).
- [Actual validation output](apimatic/provenance/validation.txt) and
  [actual generation output](apimatic/provenance/generation.txt), both exit code 0.
- [Provenance manifest](apimatic/provenance/manifest.json): CLI/runtime, generation
  status, input hashes, exact ZIP hash, every extracted file hash, and verification limits.

The source [OpenAPI](developer/candidate-agent.openapi.json) contains exactly
`POST /agent`, the endpoint the developer implements and Testah calls. Its server
is deliberately non-resolving `https://candidate.invalid`. There are no management,
assessment-history, reporting or payment-operator endpoints, saved records, real
credentials or live backend hostnames in the submitted input.

Only four reviewed files were staged for generation: the contract, a minimal
build file, table of contents and public guide. The repository, `.env` and database
were never uploaded. [Build sources](apimatic/src/APIMATIC-BUILD.json) select only
HTTP documentation; the output has zero SDK files.

## Verification and compatibility choices

APIMatic CLI **1.5.0** runs on the installed Node.js **22.11.0**. It was installed
in an ignored temporary folder, without changing application dependencies. This
uses the documented [v1 workflow](https://docs.apimatic.io/apimatic-cli/commands/)
and [build-directory format](https://docs.apimatic.io/docs-as-code/contents-of-the-build-directory/).
No account upgrade or additional platform feature was enabled.

The initial validator rejected repeated cosmetic schema titles, an inline
polymorphic response and the example.com hostname. The documentation exporter
removes repeated titles, lifts the unchanged response union into a named component,
and uses the reserved invalid hostname. Pydantic's unconstrained JSON-value schema
is represented as an equivalent union of all six JSON types so generated scalar
examples retain their types. These changes affect exported documentation only;
the application wire models and connector are unchanged. Tests compare validation
constraints, including required fields, closed objects, constants, bounds and the
response discriminator.

The v1 generator synthesizes some values inside arbitrary JSON maps. Its endpoint
example therefore intentionally uses the valid four-field minimal request. The
public guide contains the full executable probe, including its exact tool argument
schema. Both generated requests were exercised against the unchanged sample ASGI
application; all three generated response examples pass the real response adapter.

Validation succeeded with non-blocking lint warnings: some property descriptions
and defaults/examples are absent, inline/empty JSON schemas are used deliberately,
and the server is not associated with a live environment. The exact diagnostics
are retained, not suppressed. The portal's generated authentication heading says
"requires" even though source OpenAPI expresses optional authentication; the guide
explicitly explains that it is required only when the candidate enables it.

The ZIP integrity, extracted-file hashes, candidate-only operation boundary and
known configured-secret scan passed. Actual configured values were checked locally
without being printed or included in provenance. Browser visual verification was
attempted but could not run because the browser host and native UI pipe were
unavailable. Programmatic checks and generated Markdown inspection passed; a
manual browser walkthrough/screenshot remains a submission task.

## Preview locally

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m http.server 8766 --bind 127.0.0.1 --directory docs/apimatic/portal
```

Open `http://127.0.0.1:8766`. This serves documentation only. The interactive
portal loads APIMatic's official `https://dxjs.apimatic.io/v7/static/js/portal.v7.js`
runtime and needs internet access. Generated Markdown pages are readable offline.
Do not enter working credentials in a public playground or run the placeholder URL.

## Reproduce generation

Use the existing authenticated account and its supported entitlements; do not
upgrade a plan or publish without separate approval. Keep credentials in APIMatic's
own login session, never in command examples, build sources or logs.

```powershell
Set-Location E:\Testah
npm.cmd install --prefix ./tmp/phase10-apimatic-tooling --no-audit --no-fund --save-exact @apimatic/cli@1.5.0
.\tmp\phase10-apimatic-tooling\node_modules\.bin\apimatic.cmd auth login
.\backend\.venv\Scripts\python.exe backend/scripts/export_candidate_openapi.py --check
.\backend\.venv\Scripts\python.exe backend/scripts/prepare_apimatic.py
.\tmp\phase10-apimatic-tooling\node_modules\.bin\apimatic.cmd api validate --file=docs/developer/candidate-agent.openapi.json
.\tmp\phase10-apimatic-tooling\node_modules\.bin\apimatic.cmd portal generate --input=tmp/phase10-apimatic-input --destination=tmp/apimatic-new-output --zip
```

Use a fresh destination. After regeneration, inspect the generated request, guide,
response variants and schemas, scan for private data, and refresh the exact ZIP,
extracted files, CLI logs and provenance hashes together. Current artifact tests
fail on source/artifact drift instead of silently accepting stale documentation.
