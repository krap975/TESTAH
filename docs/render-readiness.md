# Render readiness

The historical reduced Phase 10 deferred operational hosting. The separately
approved November 12 preparation task adds PostgreSQL driver/URL handling,
serialized startup migrations, exact HTTPS production origins, and shared
workspace access for trusted demo users.

Use the current [deployment runbook](render-deployment.md) and
[verification/security report](deployment-verification.md). No Render resources
have been created and public verification still requires deployment approval.

The [original docs-only example](../deploy/render-docs.example.yaml),
[developer quickstart](developer-quickstart.md), [candidate OpenAPI](developer/candidate-agent.openapi.json)
and [APIMatic artifact/provenance](apimatic.md) are preserved. Static docs can be
hosted independently with approval.

The application Blueprint is for trusted invitees sharing one workspace.
Review plan expiry/cold starts, actual origins, credentials, access distribution
and verification results before applying it. Auto-deploy off does not prevent
initial provisioning.
