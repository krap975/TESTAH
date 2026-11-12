# Phase 1 verification

Verified on October 31, 2026 (America/Los_Angeles), using Windows PowerShell, Python 3.12.16, Node 22.11.0, and npm 10.9.0.

## Commands and results

| Command | Working directory | Result |
| --- | --- | --- |
| uv venv backend/.venv --python <isolated Python 3.12 executable> | repository | Created environment |
| uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt | repository | Installed all backend requirements |
| .\.venv\Scripts\python.exe -m pytest | backend | 7 passed |
| .\.venv\Scripts\python.exe -m alembic upgrade head | backend | Database initialized |
| .\.venv\Scripts\python.exe -m alembic current | backend | 0001_foundation (head) |
| .\.venv\Scripts\python.exe -m alembic check | backend | No new upgrade operations detected |
| npm.cmd install --no-audit --no-fund | frontend | Dependencies installed; package-lock.json created |
| npm.cmd ci --offline --no-audit --no-fund --cache E:\Testah\tmp\npm-cache | frontend | 138 packages installed from lockfile |
| npm.cmd run build | frontend | Strict TypeScript and Vite production bundle passed |
| .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 | backend | Application startup completed |
| npm.cmd run dev | frontend | Vite served http://127.0.0.1:5173 |
| Invoke-RestMethod http://127.0.0.1:8000/api/health | repository | status=ok, service=Testah API, database=connected |
| Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173 | repository | HTTP 200 |
| Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/reports | repository | HTTP 200; SPA fallback available |
| node tmp/ui-smoke.mjs | repository | Four React integration checks passed |

The migration test covers a new temporary SQLite file, repeated upgrade, version persistence, foreign-key configuration, schema-drift check, downgrade, and re-upgrade. API tests cover health, database failure, CORS, not-found errors, input validation, and sanitized unexpected errors.

The temporary DOM integration harness bundles the real React application and calls the running API using Fetch. It verified actual health rendering, all seven navigation links and the Reports empty state, a simulated connection failure, and retry recovery against the real API. jsdom and the harness are isolated under ignored tmp/ and are not application dependencies.

## Environment issues resolved

- The default Python command was an unusable Windows alias; Python 3.13 had no executable and the working system Python was 3.10. Used uv to provision Python 3.12 in ignored tmp/ and create the backend environment. Bootstrap command: the existing Python 3.10 executable with -m pip install --target tmp/bootstrap uv, followed by tmp/bootstrap/bin/uv.exe python install 3.12 --install-dir E:\Testah\tmp\python. Network downloads required approved sandbox escalation.
- Initial sandbox npm/PyPI downloads were blocked. Approved downloads succeeded; no network failure remains.
- A lockfile reinstall initially collided with the running Vite/esbuild executable on Windows and partially removed dependencies. Stopped Vite, reran npm ci successfully, and reran the production build.
- An initial temporary outage assertion used a Node Error object across DOM contexts. Corrected the harness to use the DOM Error context; all four checks passed. No application workaround was needed.

## Remaining limitations

Browser host and native UI automation are unavailable in this environment. Real-browser visual inspection, mobile layout inspection, and browser-specific CORS behavior were not tested. HTTP checks, backend CORS tests, and React DOM integration passed.

pytest reports one third-party Starlette/AnyIO deprecation warning; it does not affect the seven passing tests. No Phase 2 capabilities are implemented. The baseline intentionally has no domain tables. No production deployment or authentication was attempted.

The copied architecture.md exactly matches the supplied complete Markdown design; original Markdown and PDF references are preserved.

